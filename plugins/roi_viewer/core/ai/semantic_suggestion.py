# --------------------------------------------------------------------------
# Optional structure-name suggestion for an interactive (MedSAM2) candidate
# (feature/interactive-ai-direct-click). MedSAM2 segments, it does not name
# anatomy, so nothing here asks it to.
#
# Source: ONLY a TotalSegmentator full-task result that ALREADY exists in
# the TotalSegmentator provider's in-memory cache (core/ai/providers/
# totalsegmentator_provider.py keeps `_cache = (key, label_data, affine,
# run_s)` of the last full run, key[0] = blake2b(16) of the voxel values).
# It is used only when key[0] equals the same digest of the CURRENT volume.
# TotalSegmentator is never run for this and its code is not changed; the
# cache is read, not modified. No cache / another volume / weak or
# ambiguous overlap -> no suggestion ("Chưa xác định cấu trúc.").
#
# Measures per label L, for candidate C:  coverage = |C ∩ L| / |C|,
# dice = 2|C ∩ L| / (|C| + |L|). A suggestion needs the best label to pass
# ALL of MIN_COVERAGE, MIN_DICE and MIN_MARGIN (best coverage minus the
# second best). Thresholds: see docs/CT3D_DIRECT_INTERACTION_ARCHITECTURE.md
# ("Semantic suggestion") for the 0543 measurements they come from.
# A suggestion is a name proposal for the operator, not a diagnosis.
# --------------------------------------------------------------------------
import hashlib
from dataclasses import dataclass
from typing import Optional

import numpy as np

MIN_COVERAGE = 0.80
MIN_DICE = 0.70
MIN_MARGIN = 0.50

NO_CACHE = "no_cache"
OTHER_VOLUME = "other_volume"
EMPTY = "empty"
WEAK = "weak"
AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Suggestion:
    label: Optional[str]
    reason: str = ""  # "" when a label is suggested, else one of the codes above
    coverage: float = 0.0
    dice: float = 0.0
    second_label: Optional[str] = None
    second_coverage: float = 0.0


def volume_digest(volume) -> str:
    """Same digest as TotalSegmentatorProvider.volume_key()[0]."""
    values = np.ascontiguousarray(volume)
    return hashlib.blake2b(memoryview(values).cast("B"), digest_size=16).hexdigest()


def cached_labels(ts_provider, volume):
    """(labels (z, y, x), {id: name}) of an existing full run of THIS volume,
    or (None, reason)."""
    cache = getattr(ts_provider, "_cache", None) if ts_provider is not None else None
    if not cache:
        return None, NO_CACHE
    try:
        key, data = cache[0], cache[1]
        if key[0] != volume_digest(volume):
            return None, OTHER_VOLUME
        from .providers.totalsegmentator_provider import from_nifti_data

        labels = np.asarray(from_nifti_data(np.asarray(data)))
        class_map = ts_provider._class_map()
    except Exception as e:
        print(f"ROI Viewer: structure suggestion skipped - {e}")
        return None, NO_CACHE
    if labels.shape != tuple(np.asarray(volume).shape):
        return None, OTHER_VOLUME
    return (labels, dict(class_map)), ""


def suggest(candidate, labels, class_map) -> Suggestion:
    c = np.asarray(candidate, dtype=bool)
    n = int(c.sum())
    if n == 0:
        return Suggestion(None, EMPTY)
    lab = np.asarray(labels)
    inside = np.bincount(lab[c].ravel().astype(np.int64))
    if inside.size:
        inside[0] = 0  # background is never a structure
    if inside.size == 0 or inside.max() == 0:
        return Suggestion(None, WEAK)
    order = np.argsort(inside)[::-1]
    best, second = int(order[0]), int(order[1]) if order.size > 1 else 0
    total_best = int(np.count_nonzero(lab == best))
    coverage = inside[best] / n
    dice = 2 * inside[best] / (n + total_best) if (n + total_best) else 0.0
    second_cov = (inside[second] / n) if second and inside[second] else 0.0
    name = class_map.get(best, str(best))
    second_name = class_map.get(second) if second_cov else None
    if coverage < MIN_COVERAGE or dice < MIN_DICE:
        return Suggestion(None, WEAK, float(coverage), float(dice), second_name, float(second_cov))
    if coverage - second_cov < MIN_MARGIN:
        return Suggestion(None, AMBIGUOUS, float(coverage), float(dice), second_name, float(second_cov))
    return Suggestion(name, "", float(coverage), float(dice), second_name, float(second_cov))
