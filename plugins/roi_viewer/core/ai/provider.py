# --------------------------------------------------------------------------
# E6 provider abstraction.
#
# A provider turns an AIInferenceRequest into a candidate mask. It MUST
# NOT create a Mask, modify Project, touch wx or VTK, or build a surface:
# its only output is the AIInferenceResult returned from infer(). It owns
# model-specific preprocessing (normalization, resampling, cropping) and
# must map its output back onto the request volume's native (z, y, x)
# grid. Heavy frameworks and model weights are loaded lazily inside
# probe()/infer(), never at import, and never downloaded or pip-installed
# by the provider: a missing dependency or model makes probe() report
# available=False with a reason.
# --------------------------------------------------------------------------
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .types import AIInferenceRequest, AIInferenceResult, AIProviderInfo, Capability, DeviceKind

# Request-validation codes (the UI maps each to a Vietnamese message).
REQUEST_OK = None
REQUEST_UNAVAILABLE = "unavailable"
REQUEST_NEEDS_PROMPT = "needs_prompt"
REQUEST_PROMPT_UNSUPPORTED = "prompt_unsupported"
REQUEST_DEVICE_UNSUPPORTED = "device_unsupported"
REQUEST_NO_VOLUME = "no_volume"
# E6b: codes for providers with parameters / patient-orientation needs
REQUEST_STRUCTURE_UNKNOWN = "structure_unknown"
REQUEST_MODE_UNSUPPORTED = "mode_unsupported"
REQUEST_ORIENTATION_UNKNOWN = "orientation_unknown"

# AIProviderInfo.unavailable_reason = "<code>: <detail>" (E6b). The UI shows a
# Vietnamese message per code and prints the detail to the console.
REASON_PACKAGE_MISSING = "package_missing"
REASON_DEPENDENCY = "dependency_missing"
REASON_API = "api_incompatible"
REASON_WEIGHTS = "weights_missing"
# Interactive AI external runtime (feature/interactive-ai-medsam2)
REASON_NOT_CONFIGURED = "not_configured"
REASON_NOT_CHECKED = "not_checked"
REASON_RUNTIME = "runtime_failed"

# progress(None, <stage>) - for models with no numeric progress. A provider
# must never report a percentage it does not really know (E6b).
STAGE_PREPARING = "preparing"
STAGE_RUNNING = "running"
STAGE_MAPPING = "mapping"

# Generic request.options keys filled by the panel (E6b)
OPTION_STRUCTURE = "target_structure"
OPTION_MODE = "mode"
OPTION_PATIENT_ORIENTATION = "patient_orientation"  # Project().patient_orientation: 6 IOP values, LPS
OPTION_ACQUISITION = "acquisition_orientation"  # "AXIAL" / "CORONAL" / "SAGITTAL" / ""
OPTION_HU_WINDOW = "hu_window"  # interactive AI: CT window preset the model sees
OPTION_GENERATION = "generation_id"  # interactive AI: E2 preview generation of the request
# Direct interaction (feature/interactive-ai-direct-click)
OPTION_SCOPE = "scope"  # "volume" (3D candidate) | "slice" (provisional, one slice)
OPTION_TARGET_Z = "target_z"  # slice of a "slice"-scope request
OPTION_SMART_INIT = "smart_init"  # derive a box from the click (fast 2D mask / click-centred box)
OPTION_SMART_PADDING = "smart_padding_fraction"
OPTION_SMART_MIN_PADDING = "smart_min_padding_px"
OPTION_SMART_FALLBACK = "smart_fallback_half_px"
OPTION_SMART_POLICY = "smart_policy"  # "point_first" (default) | "fast_2d_box"
OPTION_SMART_MIN_PIXELS = "smart_min_fast_2d_pixels"
SCOPE_VOLUME = "volume"
SCOPE_SLICE = "slice"
MODE_STANDARD = "standard"
MODE_FAST = "fast"

ProgressCallback = Callable[[float, str], None]


def check_request(info: AIProviderInfo, request: AIInferenceRequest) -> Optional[str]:
    """Generic checks every provider gets for free (validate_request()'s
    default): availability, a real 3D volume, prompt types the provider
    declared, and a device it declared."""
    if not info.available:
        return REQUEST_UNAVAILABLE
    if request.volume is None or getattr(request.volume.array, "ndim", 0) != 3:
        return REQUEST_NO_VOLUME
    if request.prompts.count == 0 and Capability.AUTOMATIC not in info.capabilities:
        return REQUEST_NEEDS_PROMPT
    if any(t not in info.supported_prompt_types for t in request.prompts.prompt_types):
        return REQUEST_PROMPT_UNSUPPORTED
    if request.device != DeviceKind.AUTO and request.device not in info.supported_devices:
        return REQUEST_DEVICE_UNSUPPORTED
    return REQUEST_OK


class AISegmentationProvider(ABC):
    """Subclass per model. `provider_id` must be unique in a registry."""

    provider_id: str = ""

    @abstractmethod
    def probe(self) -> AIProviderInfo:
        """Cheap, side-effect-free availability check (dependencies present,
        weights present at a configured path, devices really usable). Must
        not download or install anything."""

    def validate_request(self, request: AIInferenceRequest) -> Optional[str]:
        return check_request(self.probe(), request)

    @abstractmethod
    def infer(self, request: AIInferenceRequest, progress: ProgressCallback, cancel_event) -> AIInferenceResult:
        """Runs on a worker thread. Report progress with progress(fraction,
        text); check cancel_event.is_set() where the model allows and stop
        early. The result of a cancelled job is discarded by the caller
        whatever it contains."""

    def close(self) -> None:
        """Release model/device resources. Called on project close/load and
        plugin close; must be safe to call more than once."""
