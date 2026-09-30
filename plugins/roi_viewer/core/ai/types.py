# --------------------------------------------------------------------------
# E6 data types - plain, immutable where possible, no wx/VTK/InVesalius.
#
# Coordinates follow core/coordinates.py (no new convention): world points
# are (x, y, z) mm in the SLICE frame (origin 0, y >= 0), voxel indices are
# (z, y, x) into Slice().matrix, spacing is (x, y, z).
# --------------------------------------------------------------------------
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np


class DeviceKind:
    """Provider-neutral device choice. A provider reports which of these it
    can actually use (probe()); nothing here names a specific GPU."""

    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    ALL = (AUTO, CPU, CUDA)


class PromptType:
    POSITIVE_POINT = "positive_point"
    NEGATIVE_POINT = "negative_point"
    BOX = "box"
    # Reserved names only - PLANNED, no UI, no provider contract in E6.
    SCRIBBLE = "scribble"
    LASSO = "lasso"
    SUPPORTED = (POSITIVE_POINT, NEGATIVE_POINT, BOX)
    RESERVED = (SCRIBBLE, LASSO)


class Capability:
    AUTOMATIC = "automatic"  # can run with no prompt at all
    PROMPTS = "prompts"  # uses the prompt types in supported_prompt_types


@dataclass(frozen=True)
class AIProviderInfo:
    provider_id: str
    display_name: str
    version: str = ""
    available: bool = False
    unavailable_reason: str = ""
    capabilities: Tuple[str, ...] = ()
    supported_prompt_types: Tuple[str, ...] = ()
    supported_devices: Tuple[str, ...] = ()
    requires_weights: bool = False


@dataclass(frozen=True)
class PointPrompt:
    world_xyz: Tuple[float, float, float]
    voxel_zyx: Tuple[int, int, int]
    positive: bool

    @property
    def prompt_type(self) -> str:
        return PromptType.POSITIVE_POINT if self.positive else PromptType.NEGATIVE_POINT


@dataclass(frozen=True)
class BoxPrompt:
    corner1_world: Tuple[float, float, float]
    corner2_world: Tuple[float, float, float]
    voxel_min_zyx: Tuple[int, int, int]  # inclusive
    voxel_max_zyx: Tuple[int, int, int]  # inclusive

    prompt_type = PromptType.BOX


@dataclass(frozen=True)
class AIPrompts:
    """Immutable snapshot handed to a provider - later edits to the
    session's prompt set never reach a running inference."""

    points: Tuple[PointPrompt, ...] = ()
    box: Optional[BoxPrompt] = None

    @property
    def count(self) -> int:
        return len(self.points) + (1 if self.box is not None else 0)

    @property
    def prompt_types(self) -> Tuple[str, ...]:
        types = {p.prompt_type for p in self.points}
        if self.box is not None:
            types.add(PromptType.BOX)
        return tuple(sorted(types))


@dataclass(frozen=True)
class AIVolume:
    """The real image volume, as InVesalius holds it (see
    docs/CT3D_ADVANCED_E6_AI_ARCHITECTURE_REPORT.md, "AI input volume"):
    Slice().matrix, (z, y, x) int16, CT DICOM values are HU (rescale
    slope/intercept applied on import), spacing (x, y, z) mm, origin 0,
    InVesalius's own grid (not re-oriented to RAS/LPS). `array` is a
    read-only view - a provider cannot modify the project's image."""

    array: np.ndarray
    spacing_xyz: Tuple[float, float, float]
    origin_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    index_order: Tuple[str, str, str] = ("z", "y", "x")

    @property
    def shape_zyx(self) -> Tuple[int, int, int]:
        return tuple(self.array.shape)


def read_only_volume(matrix, spacing_xyz) -> AIVolume:
    view = np.asarray(matrix).view()
    view.flags.writeable = False
    return AIVolume(array=view, spacing_xyz=tuple(float(s) for s in spacing_xyz))


@dataclass(frozen=True)
class AIInferenceRequest:
    volume: AIVolume
    prompts: AIPrompts = AIPrompts()
    device: str = DeviceKind.AUTO
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIInferenceResult:
    """A provider's candidate. `mask` must be on the native (z, y, x) grid
    of the request volume and binary (bool, or 0/1, or 0/255) - the
    provider does any resampling/cropping back itself; preview_bridge
    rejects anything else instead of reshaping or thresholding it."""

    mask: Any
    model_name: str = ""
    model_version: str = ""
    device_used: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
