# --------------------------------------------------------------------------
# HU classes (core/analysis/hu_classes.py): half-open boundaries, overlap
# rejection, gaps reported as unclassified, exact accounting, the parent
# ROI restricts the classification, inputs unchanged, visibility does not
# change the computation, presets.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.analysis.hu_classes import (
    EXPERIMENTAL_NOTE, LUNG_DENSITY_PRESET, PRESETS, HUClass, class_statistics, classify, colour_table,
    validate_classes)

CLASSES = (HUClass(1, "low", -1000, -500), HUClass(2, "mid", -500, 0), HUClass(3, "high", 100, 500))


def _data():
    vol = np.array([-1000, -501, -500, -1, 0, 50, 99, 100, 499, 500, 2000], dtype=np.int16).reshape(1, 1, 11)
    mask = np.ones(vol.shape, bool)
    return vol, mask


def test_exact_boundary_values():
    vol, mask = _data()
    lab = classify(vol, mask, CLASSES).ravel().tolist()
    #        -1000 -501 -500 -1  0  50  99 100 499 500 2000
    assert lab == [1, 1, 2, 2, 0, 0, 0, 3, 3, 0, 0]


def test_overlap_rejected():
    bad = (HUClass(1, "a", -100, 10), HUClass(2, "b", 0, 50))
    assert any("chồng lấn" in e for e in validate_classes(bad))
    with pytest.raises(ValueError):
        classify(np.zeros((1, 1, 1)), np.ones((1, 1, 1), bool), bad)
    assert validate_classes((HUClass(1, "a", 0, 10), HUClass(2, "b", 10, 20))) == []  # touching is fine


def test_invalid_definitions():
    assert validate_classes((HUClass(1, "x", 5, 5),))
    assert validate_classes((HUClass(1, "x", 0, 1), HUClass(1, "y", 2, 3)))
    assert validate_classes((HUClass(0, "x", 0, 1),))
    assert validate_classes((HUClass(1, " ", 0, 1),))
    assert validate_classes((HUClass(1, "x", 0, 1, opacity=1.5),))


def test_gaps_are_unclassified_and_everything_is_accounted_for():
    vol, mask = _data()
    lab = classify(vol, mask, CLASSES)
    res = class_statistics(vol, mask, lab, CLASSES, (1, 1, 1))
    assert [c.voxel_count for c in res.classes] == [2, 2, 2]
    assert res.unclassified.voxel_count == 5
    assert res.accounted_voxels == res.roi_voxels == 11
    assert sum(c.percent_of_roi for c in res.classes) + res.unclassified.percent_of_roi == pytest.approx(100.0)


def test_mask_restricts_classification():
    vol, mask = _data()
    mask[0, 0, :5] = False
    lab = classify(vol, mask, CLASSES)
    assert not lab[~mask].any()
    res = class_statistics(vol, mask, lab, CLASSES, (1, 1, 1))
    assert res.roi_voxels == 6 and res.accounted_voxels == 6


def test_class_statistics_values():
    vol, mask = _data()
    lab = classify(vol, mask, CLASSES)
    res = class_statistics(vol, mask, lab, CLASSES, (0.5, 0.5, 2.0))
    high = res.classes[2]
    assert high.voxel_count == 2 and high.volume_mm3 == pytest.approx(2 * 0.5)
    assert (high.hu.minimum, high.hu.maximum, high.hu.mean, high.hu.median) == (100, 499, 299.5, 299.5)


def test_inputs_unchanged_and_visibility_irrelevant():
    vol, mask = _data()
    v0, m0 = vol.copy(), mask.copy()
    a = classify(vol, mask, CLASSES)
    hidden = tuple(c.with_changes(visible=False, opacity=0.1) for c in CLASSES)
    b = classify(vol, mask, hidden)
    assert np.array_equal(a, b) and np.array_equal(vol, v0) and np.array_equal(mask, m0)


def test_colour_table_covers_every_label():
    table = colour_table(CLASSES[:1] + (CLASSES[2].with_changes(visible=False),))
    assert sorted(table) == [0, 1, 2, 3]
    assert table[0][3] == 0 and table[2][3] == 0 and table[3][3] == 0 and table[1][3] == 0.5


def test_presets_are_generic_editable_and_labelled():
    assert [p.key for p in PRESETS] == ["custom", "lung_density"]
    assert PRESETS[0].classes == ()
    assert LUNG_DENSITY_PRESET.note == EXPERIMENTAL_NOTE == "Tham khảo / thử nghiệm — không dùng để chẩn đoán"
    assert validate_classes(LUNG_DENSITY_PRESET.classes) == []
    edited = LUNG_DENSITY_PRESET.classes[0].with_changes(max_hu=-900.0)
    assert edited.max_hu == -900.0 and LUNG_DENSITY_PRESET.classes[0].max_hu == -950.0
    words = " ".join(c.display_name.lower() for c in LUNG_DENSITY_PRESET.classes)
    assert "covid" not in words and "severity" not in words
