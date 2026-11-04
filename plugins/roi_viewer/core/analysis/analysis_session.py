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
    """One quantity for A, B, the arithmetic sum A + B (a voxel in both ROIs
    counts twice) and the physical union A ∪ B (every voxel once). For
    voxel counts and volumes `a_plus_b` is the plain sum; for HU statistics
    it is the statistic of A's values followed by B's (shared voxels twice)."""
    metric: str
    a: Optional[float]
    b: Optional[float]
    a_plus_b: Optional[float]
    union: Optional[float]

    @property
    def total(self) -> Optional[float]:  # former name of a_plus_b (arithmetic, not a union)
        return self.a_plus_b


@dataclass(frozen=True)
class SpatialRelation:
    """Set relation of the two ROIs on the voxel grid. Dice = 2|A∩B| / (|A|+|B|),
    IoU (Jaccard) = |A∩B| / |A∪B|; both empty -> 1.0 (identical empty sets),
    exactly one empty -> 0.0."""
    a_voxels: int
    b_voxels: int
    intersection_voxels: int
    union_voxels: int
    only_a_voxels: int
    only_b_voxels: int
    voxel_ml: float
    dice: float
    iou: float

    def ml(self, voxels: int) -> float:
        return voxels * self.voxel_ml


@dataclass(frozen=True)
class ClassComparisonRow:
    """One HU class for A, B, A + B (arithmetic; % of |A| + |B|) and A ∪ B
    (each voxel once; % of |A ∪ B|)."""
    display_name: str
    a_voxels: int
    a_ml: float
    a_percent: float
    b_voxels: int
    b_ml: float
    b_percent: float
    sum_ml: float
    sum_percent: float
    union_voxels: int
    union_ml: float
    union_percent: float

    @property
    def combined_ml(self) -> float:  # former name of sum_ml
        return self.sum_ml

    @property
    def combined_percent(self) -> float:  # former name of sum_percent
        return self.sum_percent


@dataclass(frozen=True)
class Comparison:
    name_a: str
    name_b: str
    rows: Tuple[ComparisonRow, ...]
    class_rows: Tuple[ClassComparisonRow, ...]
    relation: SpatialRelation
    set_hu: Dict[str, Optional[object]] = field(default_factory=dict)  # HU stats of INTERSECTION / ONLY_A / ONLY_B

    @property
    def overlap_voxels(self) -> int:
        return self.relation.intersection_voxels


def dice_iou(a_voxels: int, b_voxels: int, intersection: int) -> Tuple[float, float]:
    union = a_voxels + b_voxels - intersection
    if a_voxels + b_voxels == 0:
        return 1.0, 1.0
    return 2.0 * intersection / (a_voxels + b_voxels), (intersection / union) if union else 0.0


def compare(volume, mask_a, mask_b, spacing_xyz, name_a, name_b, classes: Sequence[HUClass] = (),
            hu_available: bool = True) -> Comparison:
    """Two ROIs side by side (e.g. two lungs - nothing here knows anatomy),
    overlap-aware: A, B, A + B (arithmetic) and A ∪ B (physical), plus the
    spatial relation (intersection, only A, only B, Dice, IoU). Inputs are
    never modified."""
    from .roi_statistics import voxel_volume_mm3

    vol = np.asarray(volume) if (volume is not None and hu_available) else None
    a = np.asarray(mask_a) != 0
    b = np.asarray(mask_b) != 0
    if a.shape != b.shape:
        raise ValueError(f"ROI shapes differ: {a.shape} vs {b.shape}")
    inter, union = a & b, a | b
    na, nb, ni, nu = (int(np.count_nonzero(x)) for x in (a, b, inter, union))
    dice, iou = dice_iou(na, nb, ni)
    voxel_ml = voxel_volume_mm3(spacing_xyz) / 1000.0
    relation = SpatialRelation(na, nb, ni, nu, na - ni, nb - ni, voxel_ml, dice, iou)
    rows: List[ComparisonRow] = [
        ComparisonRow("voxel_count", float(na), float(nb), float(na + nb), float(nu)),
        ComparisonRow("volume_ml", na * voxel_ml, nb * voxel_ml, (na + nb) * voxel_ml, nu * voxel_ml),
    ]
    set_hu: Dict[str, Optional[object]] = {}
    if vol is not None:
        va, vb = vol[a].ravel(), vol[b].ravel()
        ha, hb = hu_statistics(va), hu_statistics(vb)
        hs, hu = hu_statistics(np.concatenate([va, vb])), hu_statistics(vol[union])
        for key in ("mean", "median", "std", "minimum", "maximum"):
            rows.append(ComparisonRow(f"hu_{key}", *(getattr(h, key) if h else None for h in (ha, hb, hs, hu))))
        set_hu = {"INTERSECTION": hu_statistics(vol[inter]), "ONLY_A": hu_statistics(vol[a & ~b]),
                  "ONLY_B": hu_statistics(vol[b & ~a])}
    class_rows: List[ClassComparisonRow] = []
    if classes and vol is not None:
        results = [class_statistics(vol, m, classify(vol, m, classes), classes, spacing_xyz) for m in (a, b, union)]
        ca, cb, cu = results
        for ra, rb, ru in zip(ca.classes + (ca.unclassified,), cb.classes + (cb.unclassified,),
                              cu.classes + (cu.unclassified,)):
            n = ra.voxel_count + rb.voxel_count
            class_rows.append(ClassComparisonRow(
                ra.display_name, ra.voxel_count, ra.volume_ml, ra.percent_of_roi,
                rb.voxel_count, rb.volume_ml, rb.percent_of_roi,
                n * voxel_ml, (100.0 * n / (na + nb)) if (na + nb) else 0.0,
                ru.voxel_count, ru.volume_ml, ru.percent_of_roi))
    return Comparison(name_a, name_b, tuple(rows), tuple(class_rows), relation, set_hu)
