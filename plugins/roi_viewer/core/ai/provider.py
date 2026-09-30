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
