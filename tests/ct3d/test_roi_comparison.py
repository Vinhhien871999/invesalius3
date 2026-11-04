# --------------------------------------------------------------------------
# Overlap-aware ROI comparison (core/analysis/analysis_session.compare):
# A, B, A + B (arithmetic, shared voxels twice), A ∪ B (each voxel once),
# intersection / only A / only B, Dice and IoU with the documented
# empty-mask policy, union HU statistics, per-class comparison, the
# comparison CSV round trip and the PDF section structure.
# --------------------------------------------------------------------------
import csv
import io

import numpy as np
import pytest

from plugins.roi_viewer.core.analysis import analysis_report as rep
from plugins.roi_viewer.core.analysis.analysis_session import analyse, compare, dice_iou
from plugins.roi_viewer.core.analysis.hu_classes import (
    COVERAGE_LOW, COVERAGE_MESSAGES, COVERAGE_NONE, HUClass, class_statistics, classify, coverage_warning)

SPACING = (0.5, 0.5, 2.0)
VOXEL_ML = 0.5 * 0.5 * 2.0 / 1000.0
CLASSES = (HUClass(1, "air", -1100, -500), HUClass(2, "soft", -100, 200))


def _volume():
    vol = np.full((8, 10, 12), -1000, dtype=np.int16)
    vol[:, :, 6:] = 50
    return vol


def _box(z0, z1):
    m = np.zeros((8, 10, 12), bool)
    m[z0:z1, 2:8, 2:10] = True
    return m


@pytest.mark.parametrize("a, b, expected", [
    (0, 0, (1.0, 1.0)),  # both empty: identical empty sets
    (10, 0, (0.0, 0.0)),  # one empty
    (0, 7, (0.0, 0.0)),
])
def test_dice_iou_empty_policy(a, b, expected):
    assert dice_iou(a, b, 0) == expected


def test_both_empty_and_one_empty_through_compare():
    vol = _volume()
    empty = np.zeros(vol.shape, bool)
    c = compare(vol, empty, empty, SPACING, "A", "B")
    assert (c.relation.dice, c.relation.iou, c.relation.union_voxels) == (1.0, 1.0, 0)
    c = compare(vol, _box(1, 4), empty, SPACING, "A", "B")
    assert (c.relation.dice, c.relation.iou) == (0.0, 0.0) and c.relation.only_a_voxels == 144


def test_disjoint_sets():
    vol = _volume()
    a, b = _box(1, 4), _box(4, 7)
    c = compare(vol, a, b, SPACING, "A", "B", CLASSES)
    r = c.relation
    assert (r.intersection_voxels, r.union_voxels, r.only_a_voxels, r.only_b_voxels) == (0, 288, 144, 144)
    assert (r.dice, r.iou) == (0.0, 0.0)
    rows = {x.metric: x for x in c.rows}
    assert rows["voxel_count"].a_plus_b == rows["voxel_count"].union == 288  # disjoint: A+B == A∪B
    assert rows["volume_ml"].a_plus_b == pytest.approx(rows["volume_ml"].union)


def test_subset_catches_sum_as_union():
    """A ⊂ B: intersection = A, union = B, only A = 0, A + B > A ∪ B."""
    vol = _volume()
    a, b = _box(2, 4), _box(1, 6)
    c = compare(vol, a, b, SPACING, "Mask 1", "ROI Viewer 2", CLASSES)
    r = c.relation
    na, nb = int(a.sum()), int(b.sum())
    assert r.intersection_voxels == na and r.union_voxels == nb and r.only_a_voxels == 0
    assert r.only_b_voxels == nb - na
    assert r.dice == pytest.approx(2 * na / (na + nb)) and r.iou == pytest.approx(na / nb)
    rows = {x.metric: x for x in c.rows}
    assert rows["voxel_count"].a_plus_b == na + nb > rows["voxel_count"].union == nb
    assert rows["volume_ml"].union == pytest.approx(nb * VOXEL_ML)
    assert c.overlap_voxels == na and rows["voxel_count"].total == na + nb  # `total` = arithmetic sum


def test_partial_overlap_set_identities():
    vol = _volume()
    a, b = _box(1, 5), _box(3, 7)
    c = compare(vol, a, b, SPACING, "A", "B")
    r = c.relation
    assert r.intersection_voxels == int((a & b).sum()) and r.union_voxels == int((a | b).sum())
    assert r.only_a_voxels + r.intersection_voxels == r.a_voxels
    assert r.only_b_voxels + r.intersection_voxels == r.b_voxels
    assert r.only_a_voxels + r.only_b_voxels + r.intersection_voxels == r.union_voxels
    assert r.a_voxels + r.b_voxels == r.union_voxels + r.intersection_voxels


def test_union_hu_counts_each_voxel_once():
    vol = _volume()
    a, b = _box(1, 5), _box(3, 7)
    c = compare(vol, a, b, SPACING, "A", "B")
    rows = {x.metric: x for x in c.rows}
    both = np.concatenate([vol[a], vol[b]]).astype(float)
    union = vol[a | b].astype(float)
    assert rows["hu_mean"].a_plus_b == pytest.approx(both.mean())
    assert rows["hu_mean"].union == pytest.approx(union.mean())
    assert rows["hu_std"].union == pytest.approx(union.std())
    assert c.set_hu["INTERSECTION"].mean == pytest.approx(vol[a & b].astype(float).mean())


def test_class_comparison_union_not_double_counted():
    vol = _volume()
    a, b = _box(1, 5), _box(3, 7)
    c = compare(vol, a, b, SPACING, "A", "B", CLASSES)
    for row, cid in zip(c.class_rows[:2], (1, 2)):
        assert row.union_voxels == int(((a | b) & (classify(vol, a | b, CLASSES) == cid)).sum())
        assert row.a_voxels + row.b_voxels > row.union_voxels  # the overlap is counted once in the union
    assert sum(r.union_voxels for r in c.class_rows) == int((a | b).sum())
    assert sum(r.a_voxels for r in c.class_rows) == int(a.sum())
    assert sum(r.sum_percent for r in c.class_rows) == pytest.approx(100.0)


# ------------------------------------------------------------------ coverage warning
def test_coverage_warning_levels():
    vol = np.full((1, 1, 100), 300, dtype=np.int16)  # a "bone" ROI
    roi = np.ones(vol.shape, bool)
    negative = tuple(HUClass(i + 1, f"c{i}", -1000 + 100 * i, -900 + 100 * i) for i in range(5))
    res = class_statistics(vol, roi, classify(vol, roi, negative), negative, (1, 1, 1))
    assert [r.voxel_count for r in res.classes] == [0] * 5 and res.unclassified.percent_of_roi == 100.0
    assert coverage_warning(res) == COVERAGE_NONE
    assert COVERAGE_MESSAGES[COVERAGE_NONE].startswith("Không có voxel nào của ROI")
    vol[0, 0, :3] = -950  # 3 % classified
    res = class_statistics(vol, roi, classify(vol, roi, negative), negative, (1, 1, 1))
    assert coverage_warning(res) == COVERAGE_LOW
    vol[0, 0, :10] = -950
    res = class_statistics(vol, roi, classify(vol, roi, negative), negative, (1, 1, 1))
    assert coverage_warning(res) is None
    assert coverage_warning(None) is None


# ------------------------------------------------------------------ report / CSV
def _report():
    vol = _volume()
    a, b = _box(1, 5), _box(3, 7)
    s = analyse(vol, a, SPACING, 1, "A", CLASSES)
    c = compare(vol, a, b, SPACING, "Phổi A", "B", CLASSES)
    return rep.build_report_data(s, {"modality": "CT", "shape_zyx": vol.shape, "spacing_xyz": SPACING}, "t",
                                 comparison=c), c


def test_comparison_csv_round_trip_is_exact(tmp_path):
    report, c = _report()
    paths = rep.write_csv(report, tmp_path / "x.csv")
    assert paths[1].endswith("x_comparison.csv")
    raw = (tmp_path / "x_comparison.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    by = {(r["row_type"], r["class_name"]): r for r in rows}
    r = c.relation
    assert int(by[("INTERSECTION", "")]["voxel_count"]) == r.intersection_voxels
    assert int(by[("UNION", "")]["voxel_count"]) == r.union_voxels
    assert int(by[("A_PLUS_B", "")]["voxel_count"]) == r.a_voxels + r.b_voxels
    assert float(by[("UNION", "")]["volume_ml"]) == report.comparison["sets"]["UNION"]["volume_ml"]  # exact
    assert float(by[("DICE", "")]["value"]) == r.dice and float(by[("IOU", "")]["value"]) == r.iou
    assert by[("A", "")]["roi_name"] == "Phổi A"
    assert float(by[("UNION", "")]["hu_mean"]) == {x.metric: x for x in c.rows}["hu_mean"].union
    assert int(by[("CLASS_UNION", "air")]["voxel_count"]) == c.class_rows[0].union_voxels
    assert {row["row_type"] for row in rows} == set(rep.SET_ROW_TYPES) | {
        "DICE", "IOU", "CLASS_A", "CLASS_B", "CLASS_A_PLUS_B", "CLASS_UNION"}


def test_statistics_csv_round_trip_is_exact(tmp_path):
    report, _ = _report()
    rep.write_csv(report, tmp_path / "y.csv")
    rows = list(csv.DictReader(io.StringIO((tmp_path / "y.csv").read_text(encoding="utf-8-sig"))))
    for row, c in zip(rows, list(report.classes) + [report.unclassified]):
        assert int(row["voxel_count"]) == c["voxel_count"]
        assert float(row["volume_mm3"]) == c["volume_mm3"] and float(row["percent_roi"]) == c["percent_roi"]
        if c["hu"]:
            assert float(row["hu_mean"]) == c["hu"]["mean"] and float(row["hu_std"]) == c["hu"]["std"]


def test_pdf_sections_are_sequential_with_or_without_data():
    report, _ = _report()
    titles = [t for t, _ in rep.report_sections(report)]
    assert titles == [f"{i + 1}. {name}" for i, name in enumerate(rep.SECTION_TITLES)]
    vol = _volume()
    bare = rep.build_report_data(analyse(vol, _box(1, 4), SPACING, 1, "A", ()), {"modality": "CT"}, "t")
    sections = dict(rep.report_sections(bare))
    assert [t for t in sections] == titles and sections["4. Phân lớp theo HU"] == []  # drawn as NO_DATA
    assert sections["5. So sánh ROI"] == []


def test_pdf_comparison_tables_and_overlap_note():
    report, c = _report()
    blocks = dict(rep.report_sections(report))["5. So sánh ROI"]
    tables = [b for b in blocks if b[0] == "table"]
    assert tables[0][1] == ("Chỉ số", "ROI A", "ROI B", "A+B (đếm trùng)", "A∪B")
    assert [row[0] for row in tables[0][2]][:2] == ["Voxel", "Thể tích ml"]
    rel = {row[0]: row for row in tables[1][2]}
    assert set(rel) == {"Giao A∩B", "Hợp A∪B", "Chỉ A (A\\B)", "Chỉ B (B\\A)", "Dice", "IoU (Jaccard)"}
    assert any(b[0] == "warn" and "giao nhau" in b[1] and "A∪B chỉ tính một lần" in b[1] for b in blocks)


def test_pdf_class_table_sum_and_coverage_warning():
    vol = np.full((2, 3, 4), 300, dtype=np.int16)
    roi = np.ones(vol.shape, bool)
    negative = (HUClass(1, "lung", -1000, -500),)
    s = analyse(vol, roi, (1, 1, 1), 1, "Mask 1", negative)
    report = rep.build_report_data(s, {}, "t")
    blocks = dict(rep.report_sections(report))["4. Phân lớp theo HU"]
    table = next(b for b in blocks if b[0] == "table")
    assert table[2][-1][0] == "Tổng" and table[2][-1][2] == "24" and table[2][-2][0] == "Chưa phân lớp"
    assert ("warn", COVERAGE_MESSAGES[COVERAGE_NONE]) in blocks
    assert report.coverage == COVERAGE_NONE


def test_pdf_written_with_comparison(tmp_path):
    report, _ = _report()
    pages = rep.write_pdf(report, tmp_path / "c.pdf")
    assert pages >= 1 and (tmp_path / "c.pdf").read_bytes().startswith(b"%PDF")


def test_axial_picture_has_anterior_at_the_top():
    """Slice().matrix row 0 is the most posterior DICOM row; the picture
    must show the anterior side at the top, like the InVesalius view."""
    from plugins.roi_viewer.core.analysis.roi_statistics import compute_roi_statistics

    vol = np.zeros((3, 10, 8), dtype=np.int16)
    vol[1, 0, :] = 999  # matrix row 0: posterior
    roi = np.zeros(vol.shape, bool)
    roi[1, 4:6, 3:5] = True
    st = compute_roi_statistics(vol, roi, (1, 1, 1))
    image = rep.centroid_slices(vol, roi, None, st)["Axial"][0]
    assert (image[-1] == 999).all() and not (image[0] == 999).any()  # posterior at the bottom
    contour = rep.roi_contour(rep.centroid_slices(vol, roi, None, st)["Axial"][3])
    assert contour.sum() == 4  # a 2x2 square is all boundary
