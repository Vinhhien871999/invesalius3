# --------------------------------------------------------------------------
# Transient analysis session + ROI comparison.
#
# A session belongs to one source ROI at one state: its fingerprint is
# (shape, spacing, foreground count, blake2b of the packed foreground bits).
# Any edit of the ROI changes the fingerprint, and the session then reports
# itself stale instead of showing old numbers. Nothing here is saved with
# the project.
# --------------------------------------------------------------------------
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .hu_classes import ClassificationResult, HUClass, class_statistics, classify
from .roi_statistics import ROIStatistics, compute_roi_statistics, hu_statistics

STALE_MESSAGE = "ROI đã thay đổi. Hãy tính lại phân tích."


def source_fingerprint(mask, spacing_xyz) -> Tuple:
    m = np.asarray(mask) != 0
    digest = hashlib.blake2b(np.packbits(m, axis=None).tobytes(), digest_size=16).hexdigest()
    return (tuple(int(n) for n in m.shape), tuple(round(float(s), 9) for s in spacing_xyz),
            int(np.count_nonzero(m)), digest)


@dataclass
class ROIAnalysisSession:
    mask_index: int
    roi_name: str
    fingerprint: Tuple
    spacing_xyz: Tuple[float, float, float]
    classes: Tuple[HUClass, ...] = ()
    statistics: Optional[ROIStatistics] = None
    classification: Optional[ClassificationResult] = None
    labels: Optional[np.ndarray] = None  # transient class label array
    show_2d: bool = False
    show_3d: bool = False
    stale: bool = False
    extra: Dict = field(default_factory=dict)

    def check(self, mask, spacing_xyz) -> bool:
        """True while the source ROI is unchanged; marks the session stale
        (and drops the label array) as soon as it is not."""
        if not self.stale and source_fingerprint(mask, spacing_xyz) != self.fingerprint:
            self.invalidate()
        return not self.stale

    def invalidate(self):
        self.stale = True
        self.labels = None


def analyse(volume, mask, spacing_xyz, mask_index, roi_name, classes: Sequence[HUClass] = (),
            hu_available: bool = True) -> ROIAnalysisSession:
    """Statistics, and the classification when classes are given. Inputs
    are never modified."""
    stats = compute_roi_statistics(volume if hu_available else None, mask, spacing_xyz, roi_name, hu_available)
    session = ROIAnalysisSession(mask_index=mask_index, roi_name=roi_name,
                                 fingerprint=source_fingerprint(mask, spacing_xyz),
                                 spacing_xyz=tuple(float(s) for s in spacing_xyz),
                                 classes=tuple(classes), statistics=stats)
    if classes and hu_available:
        labels = classify(volume, mask, classes)
        session.labels = labels
        session.classification = class_statistics(volume, mask, labels, classes, spacing_xyz)
    return session


@dataclass(frozen=True)
class ComparisonRow:
    metric: str
    a: Optional[float]
    b: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class ClassComparisonRow:
    display_name: str
    a_ml: float
    a_percent: float
    b_ml: float
    b_percent: float
    combined_ml: float
    combined_percent: float


@dataclass(frozen=True)
class Comparison:
    name_a: str
    name_b: str
    rows: Tuple[ComparisonRow, ...]
    class_rows: Tuple[ClassComparisonRow, ...]
    overlap_voxels: int  # counted in both A and B; "Total" adds A and B


def compare(volume, mask_a, mask_b, spacing_xyz, name_a, name_b, classes: Sequence[HUClass] = (),
            hu_available: bool = True) -> Comparison:
    """Two ROIs side by side (e.g. two lungs - nothing here knows anatomy).
    Total = A + B: voxels and volumes add, HU statistics are those of all
    values of A and B together. Voxels in both ROIs are counted twice and
    reported as overlap_voxels."""
    vol = np.asarray(volume) if volume is not None else None
    a = np.asarray(mask_a) != 0
    b = np.asarray(mask_b) != 0
    sa = compute_roi_statistics(vol if hu_available else None, a, spacing_xyz, name_a, hu_available)
    sb = compute_roi_statistics(vol if hu_available else None, b, spacing_xyz, name_b, hu_available)
    rows: List[ComparisonRow] = [
        ComparisonRow("voxel_count", float(sa.voxel_count), float(sb.voxel_count),
                      float(sa.voxel_count + sb.voxel_count)),
        ComparisonRow("volume_ml", sa.volume_ml, sb.volume_ml, sa.volume_ml + sb.volume_ml),
    ]
    if hu_available and vol is not None:
        both = hu_statistics(np.concatenate([vol[a].ravel(), vol[b].ravel()]))
        for key in ("mean", "median", "std", "minimum", "maximum"):
            rows.append(ComparisonRow(f"hu_{key}", getattr(sa.hu, key) if sa.hu else None,
                                      getattr(sb.hu, key) if sb.hu else None,
                                      getattr(both, key) if both else None))
    class_rows: List[ClassComparisonRow] = []
    if classes and hu_available and vol is not None:
        ca = class_statistics(vol, a, classify(vol, a, classes), classes, spacing_xyz)
        cb = class_statistics(vol, b, classify(vol, b, classes), classes, spacing_xyz)
        total_voxels = sa.voxel_count + sb.voxel_count
        for ra, rb in zip(ca.classes + (ca.unclassified,), cb.classes + (cb.unclassified,)):
            n = ra.voxel_count + rb.voxel_count
            class_rows.append(ClassComparisonRow(
                ra.display_name, ra.volume_ml, ra.percent_of_roi, rb.volume_ml, rb.percent_of_roi,
                ra.volume_ml + rb.volume_ml, (100.0 * n / total_voxels) if total_voxels else 0.0))
    return Comparison(name_a, name_b, tuple(rows), tuple(class_rows), int(np.count_nonzero(a & b)))
