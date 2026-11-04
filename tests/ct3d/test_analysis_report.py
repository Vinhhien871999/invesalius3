# --------------------------------------------------------------------------
# Analysis report (core/analysis/analysis_report.py): the data object, the
# deterministic CSV, filename sanitisation (no patient words), optional AI
# metadata, and a real PDF written by matplotlib's PDF backend.
# --------------------------------------------------------------------------
import csv
import io

import numpy as np
import pytest

from plugins.roi_viewer.core.analysis import analysis_report as rep
from plugins.roi_viewer.core.analysis.analysis_session import analyse, compare
from plugins.roi_viewer.core.analysis.hu_classes import HUClass, colour_table
from plugins.roi_viewer.core.analysis.roi_statistics import roi_histogram

SPACING = (0.5, 0.5, 2.0)
CLASSES = (HUClass(1, "air", -1100, -500, (0.2, 0.6, 1.0)), HUClass(2, "soft", -100, 200, (1.0, 0.5, 0.0)))
DATASET = {"label": "NGUYEN VAN A - CT chest", "modality": "CT", "shape_zyx": (8, 10, 12), "spacing_xyz": SPACING}


def _session():
    vol = np.full((8, 10, 12), -1000, dtype=np.int16)
    vol[:, :, 6:] = 50
    vol[2, 3, 3] = 900  # unclassified (above both classes)
    a = np.zeros(vol.shape, bool)
    a[1:4, 2:8, 2:10] = True
    return vol, a, analyse(vol, a, SPACING, 1, "AI - lung_left", CLASSES)


def test_report_data_matches_the_session():
    vol, a, s = _session()
    r = rep.build_report_data(s, DATASET, "2026-11-04 10:00")
    assert r.roi["voxel_count"] == 144 and r.roi["volume_ml"] == pytest.approx(144 * 0.5 / 1000)
    assert r.hu["max"] == 900 and r.hu["min"] == -1000
    assert [c["voxel_count"] for c in r.classes] == [71, 72] and r.unclassified["voxel_count"] == 1
    assert sum(c["voxel_count"] for c in r.classes) + r.unclassified["voxel_count"] == r.roi["voxel_count"]
    assert r.disclaimer == "Phần mềm nghiên cứu/thử nghiệm, chưa được kiểm định lâm sàng."
    assert r.ai is None and r.comparison is None  # nothing invented


def test_ai_metadata_only_when_recorded():
    _, _, s = _session()
    meta = {"provider_name": "TotalSegmentator", "structure": "lung_left", "mode": "standard",
            "device": "cuda", "runtime_seconds": 1.3, "prompt_count": 0, "provider_details": {"x": 1}}
    r = rep.build_report_data(s, DATASET, "t", ai_metadata=meta, source="AI")
    assert r.ai == {"provider_name": "TotalSegmentator", "structure": "lung_left", "mode": "standard",
                    "device": "cuda", "runtime_seconds": 1.3}
    assert rep.build_report_data(s, DATASET, "t", ai_metadata={}).ai is None


def test_comparison_table_in_report():
    vol, a, s = _session()
    b = np.zeros(a.shape, bool)
    b[4:7, 2:8, 2:10] = True
    c = compare(vol, a, b, SPACING, "A", "B", CLASSES)
    r = rep.build_report_data(s, DATASET, "t", comparison=c)
    metrics = {row[0]: row for row in r.comparison["rows"]}
    assert metrics["voxel_count"][1:] == (144.0, 144.0, 288.0, 288.0)  # A, B, A+B, A∪B (disjoint)
    assert len(r.comparison["class_rows"]) == 3 and r.comparison["dice"] == 0.0


def test_csv_is_deterministic_and_complete():
    _, _, s = _session()
    r = rep.build_report_data(s, DATASET, "t")
    text = rep.csv_text(r)
    assert text == rep.csv_text(rep.build_report_data(s, DATASET, "other time"))  # no timestamp in the CSV
    rows = list(csv.reader(io.StringIO(text)))
    assert tuple(rows[0]) == rep.CSV_COLUMNS
    assert [row[1] for row in rows[1:]] == ["air", "soft", "Chưa phân lớp"]
    assert sum(int(row[4]) for row in rows[1:]) == 144
    assert rows[1][5] == repr(71 * 0.5) and rows[3][2] == "" and rows[3][3] == ""  # exact repr numbers


def test_csv_without_classes_has_one_roi_row():
    vol, a, _ = _session()
    s = analyse(vol, a, SPACING, 1, "ROI", ())
    rows = list(csv.reader(io.StringIO(rep.csv_text(rep.build_report_data(s, DATASET, "t")))))
    assert len(rows) == 2 and rows[1][4] == "144" and rows[1][7] == "100.0"


@pytest.mark.parametrize("name, expected", [
    ("AI - lung_left", "AI_-_lung_left"), ("Phổi trái / đáy", "Phoi_trai_day"), ("../../etc", "etc"),
    ("C:\\Users\\Nguyen\\x", "C_Users_Nguyen_x"), ("", "roi"), ("ĐĐ", "DD"),
])
def test_filename_sanitisation(name, expected):
    assert rep.sanitize_filename(name) == expected


def test_default_filename_has_no_dataset_label():
    name = rep.default_basename("AI - lung_left", "2026-11-04")
    assert name == "AI_-_lung_left_analysis_20261104"
    assert "NGUYEN" not in name and "/" not in name and "\\" not in name


def test_pdf_written_locally(tmp_path):
    vol, a, s = _session()
    r = rep.build_report_data(s, DATASET, "2026-11-04 10:00")
    path = tmp_path / "report.pdf"
    rep.write_pdf(r, path, slices=rep.centroid_slices(vol, a, s.labels, s.statistics),
                  class_colours=colour_table(CLASSES), histogram=roi_histogram(vol, a))
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page") >= 2  # tables page + slice page
    assert len(data) > 2000


def test_centroid_slices_shapes():
    vol, a, s = _session()
    slices = rep.centroid_slices(vol, a, s.labels, s.statistics)
    assert set(slices) == {"Axial", "Coronal", "Sagittal"}
    assert slices["Axial"][0].shape == (10, 12) and slices["Coronal"][0].shape == (8, 12)
    assert slices["Sagittal"][1].shape == (8, 10)
    assert slices["Axial"][2] == 1.0 and slices["Coronal"][2] == 4.0 and slices["Sagittal"][2] == 4.0  # mm aspect
