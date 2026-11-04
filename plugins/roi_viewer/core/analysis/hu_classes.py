# --------------------------------------------------------------------------
# HU classes inside a parent ROI.
#
# Rule: a voxel belongs to class c when it is inside the parent ROI AND
# c.min_hu <= HU < c.max_hu (half-open: the upper bound belongs to the next
# class). Classes must not overlap (validate_classes() rejects it); gaps are
# allowed and their voxels are reported as "unclassified", so
#     sum(class voxels) + unclassified voxels = parent ROI voxels
# always holds.
#
# Labels: 0 = outside the ROI or unclassified, otherwise the class_id
# (1..254, uint8 - the 2D overlay and the 3D preview read this array).
# --------------------------------------------------------------------------
from dataclasses import dataclass, replace
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .roi_statistics import HUStatistics, hu_statistics, voxel_volume_mm3

MAX_CLASS_ID = 254
EXPERIMENTAL_NOTE = "Tham khảo / thử nghiệm — không dùng để chẩn đoán"


@dataclass(frozen=True)
class HUClass:
    class_id: int
    display_name: str
    min_hu: float
    max_hu: float
    display_color: Tuple[float, float, float] = (1.0, 0.5, 0.0)  # RGB 0..1
    visible: bool = True
    opacity: float = 0.5

    def with_changes(self, **changes) -> "HUClass":
        return replace(self, **changes)


@dataclass(frozen=True)
class Preset:
    key: str
    display_name: str
    classes: Tuple[HUClass, ...]
    note: str = ""


# Experimental reference preset: lung density bands similar to the
# categories of the reviewed 3D Slicer Lung CT workflow. Not validated
# here, not a diagnosis; every range stays editable.
LUNG_DENSITY_PRESET = Preset(
    key="lung_density",
    display_name="Mật độ phổi (thử nghiệm)",
    note=EXPERIMENTAL_NOTE,
    classes=(
        HUClass(1, "Emphysema", -1050.0, -950.0, (0.55, 0.0, 0.75), True, 0.5),
        HUClass(2, "Inflated", -950.0, -750.0, (0.2, 0.6, 1.0), True, 0.5),
        HUClass(3, "Infiltrated", -750.0, -400.0, (1.0, 0.8, 0.0), True, 0.5),
        HUClass(4, "Collapsed", -400.0, 0.0, (1.0, 0.35, 0.0), True, 0.5),
        HUClass(5, "Vessels / dense", 0.0, 3071.0, (0.85, 0.1, 0.1), True, 0.5),
    ),
)
CUSTOM_PRESET = Preset(key="custom", display_name="Tùy chỉnh", classes=())
PRESETS = (CUSTOM_PRESET, LUNG_DENSITY_PRESET)


def validate_classes(classes: Sequence[HUClass]) -> List[str]:
    """Errors (Vietnamese, for the UI); an empty list means valid."""
    errors = []
    if len(classes) > MAX_CLASS_ID:
        errors.append(f"Tối đa {MAX_CLASS_ID} lớp.")
    ids = [c.class_id for c in classes]
    if len(set(ids)) != len(ids):
        errors.append("Mã lớp bị trùng.")
    for c in classes:
        if not (1 <= int(c.class_id) <= MAX_CLASS_ID):
            errors.append(f"Mã lớp {c.class_id} phải từ 1 đến {MAX_CLASS_ID}.")
        if not str(c.display_name).strip():
            errors.append(f"Lớp {c.class_id} chưa có tên.")
        if not (np.isfinite(c.min_hu) and np.isfinite(c.max_hu)) or not c.min_hu < c.max_hu:
            errors.append(f"Lớp '{c.display_name}': 'Từ HU' phải nhỏ hơn 'Đến HU'.")
        if not 0.0 <= float(c.opacity) <= 1.0:
            errors.append(f"Lớp '{c.display_name}': độ trong suốt phải từ 0 đến 1.")
    ordered = sorted((c for c in classes if c.min_hu < c.max_hu), key=lambda c: (c.min_hu, c.max_hu))
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt.min_hu < prev.max_hu:
            errors.append(f"Lớp '{prev.display_name}' và '{nxt.display_name}' chồng lấn khoảng HU.")
    return errors


def classify(volume, mask, classes: Sequence[HUClass]) -> np.ndarray:
    """uint8 label array (see the module header). Visibility and opacity
    do not affect it. Raises ValueError for invalid classes."""
    errors = validate_classes(classes)
    if errors:
        raise ValueError("; ".join(errors))
    vol = np.asarray(volume)
    m = np.asarray(mask) != 0
    if m.shape != vol.shape:
        raise ValueError(f"mask shape {m.shape} does not match volume shape {vol.shape}")
    labels = np.zeros(vol.shape, dtype=np.uint8)
    for c in classes:
        labels[m & (vol >= c.min_hu) & (vol < c.max_hu)] = np.uint8(c.class_id)
    return labels


@dataclass(frozen=True)
class ClassStatistics:
    class_id: Optional[int]  # None = unclassified
    display_name: str
    min_hu: Optional[float]
    max_hu: Optional[float]
    voxel_count: int
    volume_mm3: float
    volume_ml: float
    percent_of_roi: float
    hu: Optional[HUStatistics]


@dataclass(frozen=True)
class ClassificationResult:
    classes: Tuple[ClassStatistics, ...]
    unclassified: ClassStatistics
    roi_voxels: int

    @property
    def accounted_voxels(self) -> int:
        return sum(c.voxel_count for c in self.classes) + self.unclassified.voxel_count


def class_statistics(volume, mask, labels, classes: Sequence[HUClass], spacing_xyz) -> ClassificationResult:
    vol = np.asarray(volume)
    m = np.asarray(mask) != 0
    lab = np.asarray(labels)
    roi = int(np.count_nonzero(m))
    voxel_mm3 = voxel_volume_mm3(spacing_xyz)

    def stats(cid, name, lo, hi, sel):
        n = int(np.count_nonzero(sel))
        mm3 = float(n) * voxel_mm3
        return ClassStatistics(cid, name, lo, hi, n, mm3, mm3 / 1000.0, (100.0 * n / roi) if roi else 0.0,
                               hu_statistics(vol[sel]))

    rows = tuple(stats(c.class_id, c.display_name, float(c.min_hu), float(c.max_hu), lab == c.class_id)
                 for c in classes)
    unclassified = stats(None, "Chưa phân lớp", None, None, m & (lab == 0))
    return ClassificationResult(classes=rows, unclassified=unclassified, roi_voxels=roi)


def colour_table(classes: Sequence[HUClass]) -> dict:
    """Overlay colour table for Slice().aux_matrices_colours: every label
    0..max id gets an entry (InVesalius builds its lookup table from the
    keys' min..max), hidden classes and gaps are transparent."""
    by_id = {c.class_id: c for c in classes}
    top = max(by_id) if by_id else 1
    table = {}
    for value in range(0, top + 1):
        c = by_id.get(value)
        if c is None or not c.visible:
            table[value] = (0.0, 0.0, 0.0, 0.0)
        else:
            r, g, b = (float(v) for v in c.display_color)
            table[value] = (r, g, b, float(c.opacity))
    return table


COVERAGE_NONE = "none"  # ROI not empty, no voxel in any class
COVERAGE_LOW = "low"  # more than LOW_COVERAGE_UNCLASSIFIED of the ROI unclassified
LOW_COVERAGE_UNCLASSIFIED = 95.0
COVERAGE_MESSAGES = {
    COVERAGE_NONE: "Không có voxel nào của ROI nằm trong các khoảng HU đã khai báo. Hãy kiểm tra lại các khoảng phân lớp.",
    COVERAGE_LOW: "Phần lớn voxel chưa thuộc lớp HU nào.",
}


def coverage_warning(result: Optional[ClassificationResult]) -> Optional[str]:
    """None, COVERAGE_LOW or COVERAGE_NONE. A warning only - the result is
    still correct (e.g. a bone ROI with lung-range classes is 100 %
    unclassified) and the ranges are never changed automatically."""
    if result is None or result.roi_voxels == 0:
        return None
    if result.unclassified.voxel_count == result.roi_voxels:
        return COVERAGE_NONE
    if 100.0 * result.unclassified.voxel_count / result.roi_voxels > LOW_COVERAGE_UNCLASSIFIED:
        return COVERAGE_LOW
    return None
