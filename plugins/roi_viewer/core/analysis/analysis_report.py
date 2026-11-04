# --------------------------------------------------------------------------
# Analysis report: a data object built only from verified results
# (ROIAnalysisSession, Comparison, recorded AI metadata), deterministic CSV
# files, and a PDF drawn with matplotlib's own PDF backend (an InVesalius
# dependency; no pyplot, no GUI, no network). The PDF's slice pictures are
# drawn from the CT array, the ROI and the class labels at the ROI
# centroid - never screen captures, so the user's views, camera and window
# are untouched. The report has no 3D picture (an off-screen OpenGL context
# inside the running application was not judged safe - DEFERRED).
#
# CSV convention: comma delimiter, '.' decimal point, numbers written with
# Python repr (shortest exact round trip), UTF-8 with a BOM in files (so
# Excel shows Vietnamese names correctly); csv_text() itself has no BOM.
#
# Filenames never contain the project or series name (they may hold
# patient identifiers): ROI name + date, sanitised.
# --------------------------------------------------------------------------
import csv
import io
import re
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .hu_classes import COVERAGE_MESSAGES, coverage_warning

DISCLAIMER = "Phần mềm nghiên cứu/thử nghiệm, chưa được kiểm định lâm sàng."
NO_DATA = "Chưa có dữ liệu."
CSV_COLUMNS = ("roi_name", "class_name", "min_hu", "max_hu", "voxel_count", "volume_mm3", "volume_ml",
               "percent_roi", "hu_mean", "hu_median", "hu_std", "hu_min", "hu_max")
COMPARISON_COLUMNS = ("row_type", "class_name", "roi_name", "voxel_count", "volume_mm3", "volume_ml", "percent",
                      "hu_mean", "hu_median", "hu_std", "hu_min", "hu_max", "value")
SET_ROW_TYPES = ("A", "B", "A_PLUS_B", "UNION", "INTERSECTION", "ONLY_A", "ONLY_B")
AI_KEYS = ("provider_name", "model_name", "model_version", "structure", "mode", "device", "runtime_seconds")
SECTION_TITLES = ("Thông tin dữ liệu", "Thông tin ROI", "Thống kê HU", "Phân lớp theo HU", "So sánh ROI",
                  "Histogram", "Ảnh minh họa", "Ghi chú / giới hạn")
REPORT_3D_IMAGE = "DEFERRED"


@dataclass(frozen=True)
class ReportData:
    dataset: Dict[str, object]
    roi: Dict[str, object]
    hu: Optional[Dict[str, float]]
    classes: Tuple[Dict[str, object], ...]
    unclassified: Optional[Dict[str, object]]
    comparison: Optional[Dict[str, object]]
    ai: Optional[Dict[str, object]]
    generated: str
    disclaimer: str = DISCLAIMER
    notes: Tuple[str, ...] = field(default_factory=tuple)
    coverage: Optional[str] = None  # hu_classes.coverage_warning() code
    class_note: str = ""  # e.g. the experimental-preset label


def _hu_dict(hu) -> Optional[Dict[str, float]]:
    if hu is None:
        return None
    return {"min": hu.minimum, "max": hu.maximum, "mean": hu.mean, "median": hu.median, "std": hu.std}


def _class_dict(row) -> Dict[str, object]:
    return {"class_id": row.class_id, "name": row.display_name, "min_hu": row.min_hu, "max_hu": row.max_hu,
            "voxel_count": row.voxel_count, "volume_mm3": row.volume_mm3, "volume_ml": row.volume_ml,
            "percent_roi": row.percent_of_roi, "hu": _hu_dict(row.hu)}


def comparison_dict(comparison) -> Dict[str, object]:
    r = comparison.relation
    sets = {"A": r.a_voxels, "B": r.b_voxels, "A_PLUS_B": r.a_voxels + r.b_voxels, "UNION": r.union_voxels,
            "INTERSECTION": r.intersection_voxels, "ONLY_A": r.only_a_voxels, "ONLY_B": r.only_b_voxels}
    return {
        "name_a": comparison.name_a, "name_b": comparison.name_b,
        "rows": tuple((x.metric, x.a, x.b, x.a_plus_b, x.union) for x in comparison.rows),
        "sets": {k: {"voxel_count": n, "volume_ml": n * r.voxel_ml, "volume_mm3": n * r.voxel_ml * 1000.0}
                 for k, n in sets.items()},
        "set_hu": {k: _hu_dict(v) for k, v in (comparison.set_hu or {}).items()},
        "dice": r.dice, "iou": r.iou, "overlap_voxels": r.intersection_voxels,
        "class_rows": tuple(
            {"name": c.display_name, "a_voxels": c.a_voxels, "a_ml": c.a_ml, "a_percent": c.a_percent,
             "b_voxels": c.b_voxels, "b_ml": c.b_ml, "b_percent": c.b_percent, "sum_ml": c.sum_ml,
             "sum_percent": c.sum_percent, "union_voxels": c.union_voxels, "union_ml": c.union_ml,
             "union_percent": c.union_percent} for c in comparison.class_rows),
    }


def build_report_data(session, dataset: Dict[str, object], generated: str, comparison=None,
                      ai_metadata: Optional[Dict[str, object]] = None, source: str = "",
                      class_note: str = "") -> ReportData:
    """`dataset`: shape, spacing, modality, label (a label is optional and
    is never used in filenames). `ai_metadata`: what the AI run recorded
    (None/empty when the ROI did not come from AI - nothing is invented)."""
    s = session.statistics
    roi = {"name": session.roi_name, "source": source or "", "voxel_count": s.voxel_count,
           "volume_mm3": s.volume_mm3, "volume_ml": s.volume_ml, "component_count": s.component_count,
           "largest_component_voxels": s.largest_component_voxels,
           "axial_slices": (s.first_axial_slice, s.last_axial_slice, s.occupied_axial_slices),
           "centroid_world_xyz": s.centroid_world_xyz, "bbox_size_mm_xyz": s.bbox_size_mm_xyz}
    cls = session.classification
    ai = None
    if ai_metadata:
        ai = {k: ai_metadata[k] for k in AI_KEYS if ai_metadata.get(k) not in (None, "")}
        ai = ai or None
    notes = []
    if s.hu is None:
        notes.append("Không có thống kê HU (ảnh không phải CT hoặc ROI rỗng).")
    return ReportData(dataset=dict(dataset), roi=roi, hu=_hu_dict(s.hu),
                      classes=tuple(_class_dict(r) for r in cls.classes) if cls else (),
                      unclassified=_class_dict(cls.unclassified) if cls else None,
                      comparison=comparison_dict(comparison) if comparison is not None else None,
                      ai=ai, generated=generated, notes=tuple(notes), coverage=coverage_warning(cls),
                      class_note=class_note)


# ------------------------------------------------------------------ files
def sanitize_filename(text: str, fallback: str = "roi") -> str:
    """ASCII letters, digits, '-' and '_' only (Vietnamese letters are
    reduced to their base letter), at most 60 characters."""
    import unicodedata

    s = unicodedata.normalize("NFKD", str(text)).replace("đ", "d").replace("Đ", "D")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_-")
    return (s[:60].strip("_-") or fallback)


def default_basename(roi_name: str, date_text: str) -> str:
    """'<roi>_analysis_<YYYYMMDD>' - no project/series/patient words."""
    return f"{sanitize_filename(roi_name)}_analysis_{re.sub(r'[^0-9]', '', date_text)[:8]}"


def comparison_csv_path(path) -> str:
    """The comparison file written next to the statistics CSV."""
    text = str(path)
    stem = text[:-4] if text.lower().endswith(".csv") else text
    return stem + "_comparison.csv"


def _num(value) -> str:
    """Machine-readable: '' for None, integers as integers, floats with
    repr (exact round trip, '.' decimal point)."""
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return str(int(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return repr(float(value))


def _hu_cells(hu) -> Tuple[str, ...]:
    hu = hu or {}
    return tuple(_num(hu.get(k)) for k in ("mean", "median", "std", "min", "max"))


def csv_rows(report: ReportData) -> List[Tuple[str, ...]]:
    """One row per class + an unclassified row, or one ROI row when there
    is no classification. Fixed column order."""
    rows = []
    name = str(report.roi["name"])
    entries = list(report.classes) + ([report.unclassified] if report.unclassified else [])
    if not entries:
        entries = [{"name": "", "min_hu": None, "max_hu": None, "voxel_count": report.roi["voxel_count"],
                    "volume_mm3": report.roi["volume_mm3"], "volume_ml": report.roi["volume_ml"],
                    "percent_roi": 100.0 if report.roi["voxel_count"] else 0.0, "hu": report.hu}]
    for e in entries:
        rows.append((name, str(e["name"]), _num(e["min_hu"]), _num(e["max_hu"]), _num(e["voxel_count"]),
                     _num(e["volume_mm3"]), _num(e["volume_ml"]), _num(e["percent_roi"])) + _hu_cells(e["hu"]))
    return rows


def comparison_csv_rows(report: ReportData) -> List[Tuple[str, ...]]:
    """Rows keyed by (row_type, class_name): the seven set rows A, B,
    A_PLUS_B (arithmetic - shared voxels twice), UNION, INTERSECTION,
    ONLY_A, ONLY_B; then DICE and IOU (column `value`); then per class
    CLASS_A, CLASS_B, CLASS_A_PLUS_B, CLASS_UNION (`percent` of that set)."""
    cp = report.comparison
    if not cp:
        return []
    rows_by_metric = {m: (a, b, s, u) for m, a, b, s, u in cp["rows"]}
    hu_for = {}
    for i, key in enumerate(("A", "B", "A_PLUS_B", "UNION")):
        hu_for[key] = {k: rows_by_metric[f"hu_{m}"][i] for k, m in (("mean", "mean"), ("median", "median"),
                                                                     ("std", "std"), ("min", "minimum"),
                                                                     ("max", "maximum"))} \
            if "hu_mean" in rows_by_metric else None
    hu_for.update(cp.get("set_hu") or {})
    names = {"A": cp["name_a"], "B": cp["name_b"]}
    out = []
    for key in SET_ROW_TYPES:
        st = cp["sets"][key]
        out.append((key, "", names.get(key, ""), _num(st["voxel_count"]), _num(st["volume_mm3"]),
                    _num(st["volume_ml"]), "") + _hu_cells(hu_for.get(key)) + ("",))
    out.append(("DICE", "", "", "", "", "", "", "", "", "", "", "", _num(cp["dice"])))
    out.append(("IOU", "", "", "", "", "", "", "", "", "", "", "", _num(cp["iou"])))
    blank_hu = ("",) * 5
    for c in cp["class_rows"]:
        out.append(("CLASS_A", c["name"], cp["name_a"], _num(c["a_voxels"]), "", _num(c["a_ml"]),
                    _num(c["a_percent"])) + blank_hu + ("",))
        out.append(("CLASS_B", c["name"], cp["name_b"], _num(c["b_voxels"]), "", _num(c["b_ml"]),
                    _num(c["b_percent"])) + blank_hu + ("",))
        out.append(("CLASS_A_PLUS_B", c["name"], "", _num(c["a_voxels"] + c["b_voxels"]), "", _num(c["sum_ml"]),
                    _num(c["sum_percent"])) + blank_hu + ("",))
        out.append(("CLASS_UNION", c["name"], "", _num(c["union_voxels"]), "", _num(c["union_ml"]),
                    _num(c["union_percent"])) + blank_hu + ("",))
    return out


def _csv(columns, rows) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return out.getvalue()


def csv_text(report: ReportData) -> str:
    return _csv(CSV_COLUMNS, csv_rows(report))


def comparison_csv_text(report: ReportData) -> str:
    return _csv(COMPARISON_COLUMNS, comparison_csv_rows(report))


def write_csv(report: ReportData, path) -> List[str]:
    """Writes the statistics CSV, and the comparison CSV next to it when the
    report has a comparison. Returns the paths written."""
    paths = [str(path)]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(csv_text(report))
    if report.comparison:
        other = comparison_csv_path(path)
        with open(other, "w", encoding="utf-8-sig", newline="") as f:
            f.write(comparison_csv_text(report))
        paths.append(other)
    return paths


# ------------------------------------------------------------------ pictures
def centroid_slices(volume, mask, labels, statistics) -> Dict[str, Tuple]:
    """Axial / coronal / sagittal slices through the ROI centroid as
    (CT image, class labels or None, pixel aspect height/width in mm, ROI
    slice), oriented as InVesalius's 2D views show them: axial anterior at
    the top and patient left on the image right; coronal and sagittal head
    at the top; sagittal posterior on the left. (Slice().matrix row 0 is the
    most posterior DICOM row and VTK draws row 0 at the bottom, so the axial
    rows are flipped for an image drawn top-down.)"""
    if statistics.centroid_voxel_zyx is None:
        return {}
    z, y, x = (int(round(c)) for c in statistics.centroid_voxel_zyx)
    vol = np.asarray(volume)
    lab = None if labels is None else np.asarray(labels)
    roi = np.asarray(mask) != 0
    sx, sy, sz = (float(v) for v in statistics.spacing_xyz)
    pick = {"Axial": (lambda a: a[z][::-1, :], sy / sx), "Coronal": (lambda a: a[::-1, y, :], sz / sx),
            "Sagittal": (lambda a: a[::-1, :, x], sz / sy)}
    return {k: (np.asarray(f(vol)), None if lab is None else np.asarray(f(lab)), aspect, np.asarray(f(roi)))
            for k, (f, aspect) in pick.items()}


def roi_contour(roi_slice) -> np.ndarray:
    """Boundary pixels of a 2D ROI slice (inside pixels with an outside
    4-neighbour)."""
    from scipy import ndimage

    m = np.asarray(roi_slice, dtype=bool)
    return m & ~ndimage.binary_erosion(m, structure=ndimage.generate_binary_structure(2, 1))


# ------------------------------------------------------------------ PDF
def num_text(v, d=2) -> str:
    """Report numbers: '-' for None, thin-space thousands, '.' decimals."""
    if v is None:
        return "-"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}".replace(",", " ")
    return f"{float(v):,.{d}f}".replace(",", " ")


def report_sections(report: ReportData) -> List[Tuple[str, List[Tuple]]]:
    """[(numbered title, blocks)] - always the same 8 sections in order, an
    empty one says NO_DATA. Blocks: ('p', text), ('warn', text),
    ('table', headers, rows, widths), ('histogram',), ('images',)."""
    r = report
    secs: List[List[Tuple]] = [[] for _ in SECTION_TITLES]
    ds = r.dataset
    for key, label in (("label", "Dữ liệu"), ("modality", "Loại ảnh"), ("shape_zyx", "Kích thước (z, y, x)"),
                       ("spacing_xyz", "Spacing (x, y, z) mm")):
        if ds.get(key) not in (None, ""):
            secs[0].append(("p", f"{label}: {ds[key]}"))

    ro = r.roi
    first, last, n = ro["axial_slices"]
    secs[1] += [("p", f"Tên: {ro['name']}")]
    if ro.get("source"):
        secs[1].append(("p", f"Nguồn: {ro['source']}"))
    secs[1] += [("p", f"Số voxel: {num_text(ro['voxel_count'])}"),
                ("p", f"Thể tích: {num_text(ro['volume_ml'], 3)} ml ({num_text(ro['volume_mm3'], 1)} mm³) - "
                      "số voxel × kích thước voxel"),
                ("p", f"Thành phần liên thông: {ro['component_count']} (lớn nhất "
                      f"{num_text(ro['largest_component_voxels'])} voxel)"),
                ("p", f"Lát axial: {first}–{last} ({n} lát có ROI)" if n else "Lát axial: -")]
    if r.ai:
        secs[1].append(("p", "Thông tin AI (đã ghi lại khi chạy): " +
                        "; ".join(f"{k} = {v}" for k, v in r.ai.items())))

    if r.hu:
        h = r.hu
        secs[2].append(("table", ("Nhỏ nhất", "Lớn nhất", "Trung bình", "Trung vị", "Độ lệch chuẩn"),
                        [(num_text(h["min"], 1), num_text(h["max"], 1), num_text(h["mean"]),
                          num_text(h["median"], 1), num_text(h["std"]))], (0.17,) * 5))

    if r.classes:
        rows = []
        for c in list(r.classes) + [r.unclassified]:
            rng = "-" if c["min_hu"] is None else f"[{num_text(c['min_hu'], 0)}, {num_text(c['max_hu'], 0)})"
            rows.append((str(c["name"]), rng, num_text(c["voxel_count"]), num_text(c["volume_ml"]),
                         num_text(c["percent_roi"])))
        total = sum(c["voxel_count"] for c in r.classes) + r.unclassified["voxel_count"]
        rows.append(("Tổng", "", num_text(total), num_text(sum(c["volume_ml"] for c in r.classes) +
                                                           r.unclassified["volume_ml"]), "100.00" if total else "0.00"))
        if r.class_note:
            secs[3].append(("p", r.class_note))
        secs[3].append(("p", "Quy tắc: voxel thuộc lớp khi Từ HU ≤ HU < Đến HU. Tổng các lớp + chưa phân lớp = ROI."))
        secs[3].append(("table", ("Tên lớp", "Khoảng HU", "Voxel", "ml", "% ROI"), rows, (0.26, 0.2, 0.16, 0.14, 0.1)))
        if total != ro["voxel_count"]:
            secs[3].append(("warn", f"Lỗi kiểm tra: tổng {total} ≠ ROI {ro['voxel_count']}."))
        if r.coverage:
            secs[3].append(("warn", COVERAGE_MESSAGES[r.coverage]))

    cp = r.comparison
    if cp:
        labels = {"voxel_count": ("Voxel", 0), "volume_ml": ("Thể tích ml", 2), "hu_mean": ("HU trung bình", 2),
                  "hu_median": ("HU trung vị", 1), "hu_std": ("HU độ lệch chuẩn", 2), "hu_minimum": ("HU nhỏ nhất", 1),
                  "hu_maximum": ("HU lớn nhất", 1)}
        rows = []
        for metric, a, b, s, u in cp["rows"]:
            name, d = labels[metric]
            fmt = (lambda v: num_text(int(v)) if v is not None else "-") if d == 0 else (lambda v, d=d: num_text(v, d))
            rows.append((name, fmt(a), fmt(b), fmt(s), fmt(u)))
        secs[4].append(("p", f"ROI A = {cp['name_a']}; ROI B = {cp['name_b']}."))
        secs[4].append(("table", ("Chỉ số", "ROI A", "ROI B", "A+B (đếm trùng)", "A∪B"), rows,
                        (0.22, 0.15, 0.15, 0.18, 0.16)))
        st = cp["sets"]
        rel = [("Giao A∩B", num_text(st["INTERSECTION"]["voxel_count"]), num_text(st["INTERSECTION"]["volume_ml"])),
               ("Hợp A∪B", num_text(st["UNION"]["voxel_count"]), num_text(st["UNION"]["volume_ml"])),
               ("Chỉ A (A\\B)", num_text(st["ONLY_A"]["voxel_count"]), num_text(st["ONLY_A"]["volume_ml"])),
               ("Chỉ B (B\\A)", num_text(st["ONLY_B"]["voxel_count"]), num_text(st["ONLY_B"]["volume_ml"])),
               ("Dice", num_text(cp["dice"], 4), ""), ("IoU (Jaccard)", num_text(cp["iou"], 4), "")]
        secs[4].append(("p", "Quan hệ không gian"))
        secs[4].append(("table", ("Chỉ số", "Voxel / giá trị", "ml"), rel, (0.3, 0.22, 0.2)))
        if cp["overlap_voxels"]:
            secs[4].append(("warn", f"ROI A và ROI B giao nhau {num_text(cp['overlap_voxels'])} voxel. Cột A+B tính "
                                    "voxel giao hai lần; A∪B chỉ tính một lần."))
        else:
            secs[4].append(("p", "ROI A và ROI B không giao nhau: A+B = A∪B."))
        if cp["class_rows"]:
            crow = [(c["name"], num_text(c["a_ml"]), num_text(c["a_percent"]), num_text(c["b_ml"]),
                     num_text(c["b_percent"]), num_text(c["sum_ml"]), num_text(c["union_ml"]),
                     num_text(c["union_percent"])) for c in cp["class_rows"]]
            secs[4].append(("p", "Phân lớp HU của từng ROI (% trên ROI đó; A∪B: % trên hợp)"))
            secs[4].append(("table", ("Lớp", "A ml", "A %", "B ml", "B %", "A+B ml", "A∪B ml", "A∪B %"), crow,
                            (0.19, 0.1, 0.08, 0.1, 0.08, 0.11, 0.11, 0.09)))
    secs[5].append(("histogram",))
    secs[6].append(("images",))
    secs[7] += [("p", r.disclaimer), ("p", "Phân lớp HU chỉ là phân tích định lượng tham khảo, không phải chẩn đoán."),
                ("p", "Ảnh minh họa vẽ từ dữ liệu ảnh (không chụp màn hình); báo cáo chưa có ảnh 3D.")]
    secs[7] += [("p", note) for note in r.notes]
    return [(f"{i + 1}. {title}", blocks) for i, (title, blocks) in enumerate(zip(SECTION_TITLES, secs))]


def write_pdf(report: ReportData, path, slices: Optional[Dict] = None, class_colours: Optional[Dict] = None,
              window=(-1000.0, 400.0), histogram=None) -> int:
    """A4 report with the sections of report_sections(). Returns the page
    count. Local file only."""
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure

    font = {"family": "DejaVu Sans"}
    top, bottom, left = 0.95, 0.05, 0.07
    line, size = 0.0165, 9.0
    ink, warn_ink, rule = "0.1", "#a33000", "0.75"
    state = {"fig": None, "y": top, "pages": 0}

    def new_page(pdf):
        if state["fig"] is not None:
            pdf.savefig(state["fig"])
            state["pages"] += 1
        state["fig"], state["y"] = Figure(figsize=(8.27, 11.69)), top

    def need(pdf, h):
        if state["y"] - h < bottom:
            new_page(pdf)

    def text(pdf, s, weight="normal", fs=size, colour=ink, wrap=100, gap=0.0):
        for part in textwrap.wrap(s, wrap) or [""]:
            need(pdf, line)
            state["fig"].text(left, state["y"], part, fontsize=fs, fontweight=weight, color=colour, fontdict=font,
                              va="top")
            state["y"] -= line * fs / size
        state["y"] -= gap

    def table(pdf, headers, rows, widths):
        assert sum(widths) <= 0.86 + 1e-9, widths  # inside the margins
        xs = [left]
        for w in widths[:-1]:
            xs.append(xs[-1] + w)
        fs = 8.0 if len(headers) <= 5 else 7.2

        def row(cells, bold=False):
            need(pdf, line)
            fig = state["fig"]
            for i, (x, cell) in enumerate(zip(xs, cells)):
                ha = "left" if i == 0 else "right"
                xx = x if i == 0 else x + widths[i] - 0.01
                fig.text(xx, state["y"], str(cell), fontsize=fs, fontweight="bold" if bold else "normal",
                         ha=ha, va="top", color=ink, fontdict=font)
            state["y"] -= line
            fig.add_artist(_hline(fig, left, xs[-1] + widths[-1], state["y"] + line * 0.15, rule))

        need(pdf, line * 3)
        row(headers, bold=True)
        for cells in rows:
            if state["y"] - line < bottom:
                new_page(pdf)
                row(headers, bold=True)
            row(cells)
        state["y"] -= line * 0.6

    with PdfPages(str(path)) as pdf:
        new_page(pdf)
        text(pdf, "Báo cáo phân tích ROI", "bold", 14, gap=0.004)
        text(pdf, f"Tạo lúc: {report.generated}")
        text(pdf, report.disclaimer, gap=0.01)
        for title, blocks in report_sections(report):
            need(pdf, line * 3)
            text(pdf, title, "bold", 11, gap=0.004)
            if not blocks:
                text(pdf, NO_DATA, gap=0.008)
                continue
            for block in blocks:
                kind = block[0]
                if kind == "p":
                    text(pdf, block[1])
                elif kind == "warn":
                    text(pdf, block[1], "bold", colour=warn_ink)
                elif kind == "table":
                    table(pdf, *block[1:])
                elif kind == "histogram":
                    if histogram is None or not histogram.counts:
                        text(pdf, NO_DATA)
                        continue
                    need(pdf, 0.27)
                    y = state["y"]
                    ax = state["fig"].add_axes([0.12, y - 0.25, 0.8, 0.2])
                    ax.bar(histogram.edges[:-1], histogram.counts, width=np.diff(histogram.edges), align="edge",
                           color="0.35")
                    ax.set_xlabel("HU", fontdict=font)
                    ax.set_ylabel("Số voxel", fontdict=font)
                    ax.set_title(f"Histogram HU bên trong ROI ({len(histogram.counts)} khoảng, "
                                 f"{histogram.below} voxel dưới / {histogram.above} voxel trên khoảng vẽ)",
                                 fontdict=font, fontsize=8.5)
                    state["y"] = y - 0.28
                elif kind == "images":
                    if not slices:
                        text(pdf, NO_DATA)
                        continue
                    text(pdf, "Lát qua trọng tâm ROI, vẽ từ dữ liệu: viền ROI màu đỏ, màu các lớp HU nếu đã tính. "
                              "Axial: trước ở trên, trái bệnh nhân ở bên phải ảnh.")
                    lo, hi = window
                    for name, (image, lab, aspect, roi) in slices.items():
                        need(pdf, 0.26)
                        y = state["y"]
                        ax = state["fig"].add_axes([0.1, y - 0.245, 0.8, 0.225])
                        ax.imshow(np.clip((np.asarray(image, dtype=float) - lo) / (hi - lo), 0, 1), cmap="gray",
                                  interpolation="nearest", aspect=aspect)
                        rgba = np.zeros(np.shape(image) + (4,))
                        if lab is not None and class_colours:
                            for cid, (rr, gg, bb, aa) in class_colours.items():
                                if cid:
                                    rgba[lab == cid] = (rr, gg, bb, aa)
                        if roi is not None:
                            rgba[roi_contour(roi)] = (1.0, 0.1, 0.1, 1.0)
                        ax.imshow(rgba, interpolation="nearest", aspect=aspect)
                        ax.set_title(name, fontdict=font, fontsize=9)
                        ax.set_axis_off()
                        state["y"] = y - 0.26
            state["y"] -= 0.008
        pdf.savefig(state["fig"])
        state["pages"] += 1
        info = pdf.infodict()
        info["Title"] = "ROI analysis report"
        info["Creator"] = "InVesalius ROI Viewer"
    return state["pages"]


def _hline(fig, x0, x1, y, colour):
    from matplotlib.lines import Line2D

    return Line2D([x0, x1], [y, y], transform=fig.transFigure, color=colour, linewidth=0.4)
