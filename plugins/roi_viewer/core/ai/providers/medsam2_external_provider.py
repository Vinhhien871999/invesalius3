# --------------------------------------------------------------------------
# Interactive AI - MedSAM2 through the EXTERNAL runtime
# (feature/interactive-ai-medsam2, docs/CT3D_INTERACTIVE_AI_ARCHITECTURE.md).
#
# This module imports numpy and the plugin only. MedSAM2, sam2 and torch
# live in a separate Python environment; this provider talks to it through
# core/ai/external (a persistent child process, JSON Lines, .npy files).
#
# Three levels, so nothing heavy happens by surprise:
#   probe()              cheap, no process: is the runtime configured?
#                        (registry.probe_all() on "Bật phân đoạn AI")
#   check_environment()  explicit ("Kiểm tra môi trường", worker thread):
#                        starts the worker, HELLO + PROBE; capabilities and
#                        devices come from the worker - never assumed here
#   infer()              job-controller thread: LOAD_VOLUME once per
#                        volume fingerprint, PREDICT, validated candidate
# The worker starts only after the operator ticked AI on, selected this
# model, and the check passed. close() (project close/load, plugin close)
# shuts it down and deletes its temporary data.
# --------------------------------------------------------------------------
import hashlib
import threading
from typing import Callable, Optional

import numpy as np

from ..external import config as runtime_config
from ..external import protocol
from ..external.errors import RequestCancelled, RuntimeFailure
from ..external.runtime_client import InteractiveAIRuntimeClient
from ..provider import (
    OPTION_GENERATION,
    OPTION_HU_WINDOW,
    REASON_NOT_CHECKED,
    REASON_NOT_CONFIGURED,
    REASON_RUNTIME,
    STAGE_MAPPING,
    STAGE_PREPARING,
    STAGE_RUNNING,
    AISegmentationProvider,
)
from ..types import AIInferenceResult, AIProviderInfo, Capability, DeviceKind, PromptType

PROVIDER_ID = "medsam2"
DISPLAY_NAME = "MedSAM2"  # the panel shows "Phân đoạn AI tương tác (MedSAM2)"
MASK_NAME_PREFIX = "AI - MedSAM2"

# Worker error codes that mean "the environment is not usable" (UI: needs setup)
SETUP_CODES = (protocol.E_DEPENDENCY, protocol.E_CHECKPOINT_MISSING, protocol.E_WORKER_START,
               protocol.E_PROTOCOL_VERSION, protocol.E_NOT_CONFIGURED)


class InferenceFailed(RuntimeError):
    """infer() failure with a protocol error code (the panel maps it)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def candidate_sha256(mask) -> str:
    """SHA-256 of a candidate as 0/1 uint8 bytes in C order - the identity
    checked between preview and Accept."""
    arr = np.ascontiguousarray(np.asarray(mask) > 0, dtype=np.uint8)
    return hashlib.sha256(arr.tobytes()).hexdigest()


def prompts_payload(prompts) -> dict:
    """AIPrompts (voxel (z, y, x) authoritative) -> protocol prompts."""
    points = [{"zyx": [int(v) for v in p.voxel_zyx],
               "label": protocol.LABEL_POSITIVE if p.positive else protocol.LABEL_NEGATIVE} for p in prompts.points]
    box = None
    if prompts.box is not None:
        box = {"min_zyx": [int(v) for v in prompts.box.voxel_min_zyx],
               "max_zyx": [int(v) for v in prompts.box.voxel_max_zyx]}
    return {"points": points, "box": box}


class MedSAM2ExternalProvider(AISegmentationProvider):
    provider_id = PROVIDER_ID

    def __init__(self, config_loader: Callable = runtime_config.load_config,
                 client_factory: Callable = InteractiveAIRuntimeClient):
        self._config_loader = config_loader
        self._client_factory = client_factory
        self._client: Optional[InteractiveAIRuntimeClient] = None
        self._config = None
        self._checked: Optional[AIProviderInfo] = None
        self._lock = threading.Lock()
        self.last_timings = {}

    # ------------------------------------------------------------- info
    def _base(self, **kw) -> AIProviderInfo:
        values = dict(provider_id=PROVIDER_ID, display_name=DISPLAY_NAME, show_when_unavailable=True,
                      checkable=True, requires_weights=True)
        values.update(kw)
        return AIProviderInfo(**values)

    def probe(self) -> AIProviderInfo:
        """Cheap: configuration only. Never starts the worker."""
        config = self._config_loader()
        if not config.usable:
            self._drop_client()
            self._checked = None
            self._config = config
            return self._base(unavailable_reason=f"{REASON_NOT_CONFIGURED}: {config.problem}: {config.problem_detail}")
        if self._config is not None and config != self._config:
            self._drop_client()  # configuration changed: check again
            self._checked = None
        self._config = config
        if self._checked is not None:
            return self._checked
        return self._base(unavailable_reason=f"{REASON_NOT_CHECKED}: press the environment check")

    def check_environment(self) -> AIProviderInfo:
        """Blocking (call from a worker thread): start the external runtime
        and ask it what it really supports."""
        config = self._config_loader()
        self._config = config
        if not config.usable:
            self._checked = None
            return self._base(unavailable_reason=f"{REASON_NOT_CONFIGURED}: {config.problem}: {config.problem_detail}")
        with self._lock:
            try:
                client = self._get_client()
                reply = client.probe()
            except RuntimeFailure as e:
                self._checked = None
                return self._base(unavailable_reason=f"{REASON_RUNTIME}: {e.code}: {e.detail}")
        info = reply.get("provider_info") or {}
        self._checked = self._info_from_worker(info, client)
        return self._checked

    def _info_from_worker(self, info: dict, client) -> AIProviderInfo:
        caps = info.get("capabilities") or {}
        details = {
            "model": info.get("name", ""), "version": info.get("version", ""),
            "checkpoint": info.get("checkpoint", ""), "model_config": info.get("model_config", ""),
            "torch": info.get("torch", ""), "cuda_device": info.get("cuda_device", ""),
            "box_kind": caps.get("box_kind", ""), "propagation_3d": bool(caps.get("propagation_3d")),
            "worker_python": (client.hello or {}).get("python", ""),
            "worker_start_s": client.timings.get("worker_start_s"), "probe_s": client.timings.get("probe_s"),
            "audited_commit": info.get("audited_commit", ""),
        }
        if not info.get("available"):
            reason = info.get("reason") or protocol.E_INTERNAL
            return self._base(version=str(info.get("version", "")), details=details,
                              unavailable_reason=f"{REASON_RUNTIME}: {reason}: {info.get('detail', '')}")
        prompt_types = []
        if caps.get("positive_point"):
            prompt_types.append(PromptType.POSITIVE_POINT)
        if caps.get("negative_point"):
            prompt_types.append(PromptType.NEGATIVE_POINT)
        if caps.get("box"):
            prompt_types.append(PromptType.BOX)
        devices = tuple(d for d in (info.get("devices") or []) if d in (DeviceKind.CPU, DeviceKind.CUDA))
        windows = tuple(str(w) for w in (info.get("window_presets") or []))
        return self._base(
            version=str(info.get("version", "")), available=True,
            capabilities=(Capability.PROMPTS, Capability.INTERRUPTIBLE),
            supported_prompt_types=tuple(prompt_types), supported_devices=devices,
            parameter_choices={OPTION_HU_WINDOW: windows} if windows else {}, details=details,
        )

    # ------------------------------------------------------------- client
    def _get_client(self) -> InteractiveAIRuntimeClient:
        if self._client is None:
            self._client = self._client_factory(self._config)
        self._client.reopen()
        return self._client

    def _drop_client(self):
        client, self._client = self._client, None
        if client is not None:
            client.close()

    # ------------------------------------------------------------- infer
    def infer(self, request, progress, cancel_event) -> AIInferenceResult:
        if self._checked is None or not self._checked.available:
            raise InferenceFailed(protocol.E_NOT_CONFIGURED, "environment not checked")
        progress(None, STAGE_PREPARING)
        generation = int(request.options.get(OPTION_GENERATION, 0) or 0)
        options = {}
        if request.options.get(OPTION_HU_WINDOW):
            options[OPTION_HU_WINDOW] = request.options[OPTION_HU_WINDOW]

        def on_progress(message):
            stage = message.get("message", "")
            if stage == "running":
                progress(None, STAGE_RUNNING)
            elif stage == "mapping":
                progress(None, STAGE_MAPPING)

        with self._lock:
            client = self._get_client()
            try:
                candidate, response = client.predict(
                    request.volume.array, request.volume.spacing_xyz, prompts_payload(request.prompts), generation,
                    device=request.device, orientation=request.options.get("patient_orientation"),
                    options=options, cancel_event=cancel_event, on_progress=on_progress)
            except RequestCancelled as e:
                raise InferenceFailed(protocol.E_CANCELLED, e.detail) from None
            except RuntimeFailure as e:
                raise InferenceFailed(e.code, e.detail) from None
            self.last_timings = dict(client.timings)
        details = dict(response.get("details") or {})
        prompts = request.prompts
        extra = {
            "interactive": True, "mask_name_prefix": MASK_NAME_PREFIX,
            "provider": "MedSAM2 (external runtime)", "checkpoint": details.get("checkpoint", ""),
            "model_config": details.get("model_config", ""), "hu_window": details.get("window"),
            "positive_points": sum(1 for p in prompts.points if p.positive),
            "negative_points": sum(1 for p in prompts.points if not p.positive),
            "box": prompts.box is not None, "key_frames": details.get("key_frames"),
            "box_slice_range": details.get("box_slice_range"), "largest_component": details.get("largest_component"),
            "flip_rows_to_dicom": details.get("flip_rows_to_dicom"), "peak_vram_mb": details.get("peak_vram_mb"),
            "worker_predict_s": response.get("predict_seconds"), "candidate_voxels": response.get("voxels"),
            "candidate_bounds_zyx": response.get("bounds_zyx"), "volume_id": response.get("volume_id"),
            "generation_id": response.get("generation_id"), "timings": dict(self.last_timings),
            "candidate_sha256": candidate_sha256(candidate),
        }
        return AIInferenceResult(mask=candidate, model_name="MedSAM2",
                                 model_version=details.get("model_version") or self._checked.version,
                                 device_used=details.get("device", request.device), extra=extra)

    def close(self) -> None:
        """Project close/load, plugin close: worker shut down (killed if it
        does not stop), temp data deleted. The environment-check result is
        kept - the next prediction starts the worker again."""
        client = self._client
        if client is not None:
            if self._lock.locked():  # a request is running: do not wait for it
                client.kill()
            client.close()


def create_provider() -> MedSAM2ExternalProvider:
    return MedSAM2ExternalProvider()
