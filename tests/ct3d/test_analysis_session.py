# --------------------------------------------------------------------------
# ROIAnalysisSession (core/analysis/analysis_session.py): fingerprint-based
# staleness, analysis never mutates its inputs, ROI A/B comparison.
# Lifecycle through the real panel (project close/load, plugin close,
# source deletion) is in test_analysis_panel_integration.py.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.analysis.analysis_session import analyse, compare, source_fingerprint
from plugins.roi_viewer.core.analysis.hu_classes import HUClass

SPACING = (0.5, 0.5, 2.0)
CLASSES = (HUClass(1, "air", -1100, -500), HUClass(2, "soft", -100, 200))


def _data():
    vol = np.full((8, 10, 12), -1000, dtype=np.int16)
    vol[:, :, 6:] = 50
    a = np.zeros(vol.shape, bool)
    a[1:4, 2:8, 2:10] = True
    b = np.zeros(vol.shape, bool)
    b[4:7, 2:8, 2:10] = True
    return vol, a, b


def test_fingerprint_detects_any_change():
    vol, a, _ = _data()
    f = source_fingerprint(a, SPACING)
    edited = a.copy()
    edited[0, 0, 0] = True
    moved = np.roll(a, 1, axis=2)  # same count, other voxels
    assert source_fingerprint(a.copy(), SPACING) == f
    assert source_fingerprint(edited, SPACING) != f
    assert source_fingerprint(moved, SPACING) != f and moved.sum() == a.sum()
    assert source_fingerprint(a, (0.5, 0.5, 2.5)) != f


def test_source_change_invalidates_and_drops_labels():
    vol, a, _ = _data()
    session = analyse(vol, a, SPACING, 3, "A", CLASSES)
    assert session.check(a, SPACING) and session.labels is not None
    edited = a.copy()
    edited[1, 2, 2] = False
    assert session.check(edited, SPACING) is False
    assert session.stale and session.labels is None
    assert session.check(a, SPACING) is False  # stays stale: recompute needed


def test_analysis_never_mutates_inputs():
    vol, a, b = _data()
    v0, a0, b0 = vol.copy(), a.copy(), b.copy()
    analyse(vol, a, SPACING, 1, "A", CLASSES)
    compare(vol, a, b, SPACING, "A", "B", CLASSES)
    assert np.array_equal(vol, v0) and np.array_equal(a, a0) and np.array_equal(b, b0)


def test_session_statistics_and_accounting():
    vol, a, _ = _data()
    s = analyse(vol, a, SPACING, 1, "A", CLASSES)
    assert s.statistics.voxel_count == 3 * 6 * 8
    c = s.classification
    assert c.accounted_voxels == c.roi_voxels == 144
    assert [r.voxel_count for r in c.classes] == [3 * 6 * 4, 3 * 6 * 4] and c.unclassified.voxel_count == 0


def test_no_classes_means_statistics_only():
    vol, a, _ = _data()
    s = analyse(vol, a, SPACING, 1, "A", ())
    assert s.classification is None and s.labels is None and s.statistics.voxel_count == 144


def test_comparison_rows():
    vol, a, b = _data()
    c = compare(vol, a, b, SPACING, "lung_left", "lung_right", CLASSES)
    rows = {r.metric: r for r in c.rows}
    voxel_ml = 0.5 * 0.5 * 2.0 / 1000.0
    assert rows["voxel_count"].a == 144 and rows["voxel_count"].b == 144 and rows["voxel_count"].total == 288
    assert rows["volume_ml"].total == pytest.approx(288 * voxel_ml)
    both = np.concatenate([vol[a], vol[b]]).astype(float)
    assert rows["hu_mean"].total == pytest.approx(both.mean()) and rows["hu_median"].total == np.median(both)
    air = c.class_rows[0]
    assert air.a_percent == pytest.approx(50.0) and air.combined_ml == pytest.approx(144 * voxel_ml)
    assert c.overlap_voxels == 0 and c.class_rows[-1].display_name == "Chưa phân lớp"


def test_comparison_reports_overlap():
    vol, a, _ = _data()
    c = compare(vol, a, a, SPACING, "x", "y")
    assert c.overlap_voxels == 144 and {r.metric: r for r in c.rows}["voxel_count"].total == 288
