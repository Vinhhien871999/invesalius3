# --------------------------------------------------------------------------
# Analysis report: a data object built only from verified results
# (ROIAnalysisSession, Comparison, recorded AI metadata), a deterministic
# CSV, and a PDF drawn with matplotlib's own PDF backend (an InVesalius
# dependency; no pyplot, no GUI, no network). The PDF's slice pictures are
# drawn from the CT array and the class labels at the ROI centroid - never
# screen captures, so the user's views, camera and window are untouched.
#
# Filenames never contain the project or series name (they may hold
# patient identifiers): ROI name + date, sanitised.
# --------------------------------------------------------------------------
import csv
import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

DISCLAIMER = "Phần mềm nghiên cứu/thử nghiệm, chưa được kiểm định lâm sàng."
CSV_COLUMNS = ("roi_name", "class_name", "min_hu", "max_hu", "voxel_count", "volume_mm3", "volume_ml",
               "percent_roi", "hu_mean", "hu_median", "hu_std", "hu_min", "hu_max")
AI_KEYS = ("provider_name", "model_name", "model_version", "structure", "mode", "device", "runtime_seconds")


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


def _hu_dict(hu) -> Optional[Dict[str, float]]:
    if hu is None:
        return None
    return {"min": hu.minimum, "max": hu.maximum, "mean": hu.mean, "median": hu.median, "std": hu.std}


def _class_dict(row) -> Dict[str, object]:
    return {"class_id": row.class_id, "name": row.display_name, "min_hu": row.min_hu, "max_hu": row.max_hu,
            "voxel_count": row.voxel_count, "volume_mm3": row.volume_mm3, "volume_ml": row.volume_ml,
            "percent_roi": row.percent_of_roi, "hu": _hu_dict(row.hu)}


def build_report_data(session, dataset: Dict[str, object], generated: str, comparison=None,
                      ai_metadata: Optional[Dict[str, object]] = None, source: str = "") -> ReportData:
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
    comp = None
    if comparison is not None:
        comp = {"name_a": comparison.name_a, "name_b": comparison.name_b, "overlap_voxels": comparison.overlap_voxels,
                "rows": tuple((r.metric, r.a, r.b, r.total) for r in comparison.rows),
                "class_rows": tuple((r.display_name, r.a_ml, r.a_percent, r.b_ml, r.b_percent, r.combined_ml,
                                     r.combined_percent) for r in comparison.class_rows)}
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
                      comparison=comp, ai=ai, generated=generated, notes=tuple(notes))


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


def _fmt(value, digits=4) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{float(value):.{digits}f}"


def csv_rows(report: ReportData) -> List[Tuple[str, ...]]:
    """One row per class + an unclassified row, or one ROI row when there
    is no classification. Fixed column order and number format."""
    rows = []
    name = str(report.roi["name"])
    entries = list(report.classes) + ([report.unclassified] if report.unclassified else [])
    if not entries:
        hu = report.hu or {}
        entries = [{"name": "", "min_hu": None, "max_hu": None, "voxel_count": report.roi["voxel_count"],
                    "volume_mm3": report.roi["volume_mm3"], "volume_ml": report.roi["volume_ml"],
                    "percent_roi": 100.0 if report.roi["voxel_count"] else 0.0,
                    "hu": hu or None}]
    for e in entries:
        hu = e["hu"] or {}
        rows.append((name, str(e["name"]), _fmt(e["min_hu"], 1), _fmt(e["max_hu"], 1), _fmt(e["voxel_count"]),
                     _fmt(e["volume_mm3"], 3), _fmt(e["volume_ml"], 6), _fmt(e["percent_roi"], 4),
                     _fmt(hu.get("mean")), _fmt(hu.get("median")), _fmt(hu.get("std")),
                     _fmt(hu.get("min"), 1), _fmt(hu.get("max"), 1)))
    return rows


def csv_text(report: ReportData) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerows(csv_rows(report))
    return out.getvalue()


def write_csv(report: ReportData, path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text(report))


# ------------------------------------------------------------------ PDF
def centroid_slices(volume, mask, labels, statistics) -> Dict[str, Tuple[np.ndarray, Optional[np.ndarray]]]:
    """Axial / coronal / sagittal CT slices through the ROI centroid with
    the class labels of the same slice (None without classification) and
    the pixel aspect (height / width in mm) so the picture keeps the real
    proportions. Coronal/sagittal rows are flipped so the head is at the
    top, as in the 2D views."""
    if statistics.centroid_voxel_zyx is None:
        return {}
    z, y, x = (int(round(c)) for c in statistics.centroid_voxel_zyx)
    vol = np.asarray(volume)
    lab = None if labels is None else np.asarray(labels)
    sx, sy, sz = (float(v) for v in statistics.spacing_xyz)
    pick = {"Axial": (lambda a: a[z], sy / sx), "Coronal": (lambda a: a[::-1, y, :], sz / sx),
            "Sagittal": (lambda a: a[::-1, :, x], sz / sy)}
    return {k: (np.asarray(f(vol)), None if lab is None else np.asarray(f(lab)), aspect)
            for k, (f, aspect) in pick.items()}


def write_pdf(report: ReportData, path, slices: Optional[Dict] = None, class_colours: Optional[Dict] = None,
              window=(-1000.0, 400.0), histogram=None) -> None:
    """A4 report: tables of the report data, optional histogram and slice
    pictures. Local file only."""
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure

    font = {"family": "DejaVu Sans"}

    def page():
        fig = Figure(figsize=(8.27, 11.69))
        return fig

    bottom = 0.05

    def text_pages(pdf, lines, y0=0.95, size=9.5, step=0.021):
        """Writes `lines` over as many pages as needed; returns the last
        (unsaved) page and the height used on it."""
        fig, y = page(), y0
        for line, weight in lines:
            gap = step * (1.6 if weight == "h1" else 1.3 if weight == "h2" else 1.0)
            if y - gap < bottom:
                pdf.savefig(fig)
                fig, y = page(), y0
            fig.text(0.07, y, line, fontsize=size + (3 if weight == "h1" else 1.5 if weight == "h2" else 0),
                     fontweight="bold" if weight in ("h1", "h2") else "normal", fontdict=font, va="top")
            y -= gap
        return fig, y

    def num(v, d=2):
        return "-" if v is None else f"{float(v):,.{d}f}".replace(",", " ")

    r = report
    lines = [("Báo cáo phân tích ROI", "h1"), (f"Tạo lúc: {r.generated}", ""), (r.disclaimer, ""), ("", ""),
             ("A. Dữ liệu ảnh", "h2")]
    ds = r.dataset
    for key, label in (("label", "Dữ liệu"), ("modality", "Loại ảnh"), ("shape_zyx", "Kích thước (z, y, x)"),
                       ("spacing_xyz", "Spacing (x, y, z) mm")):
        if ds.get(key) not in (None, ""):
            lines.append((f"{label}: {ds[key]}", ""))
    lines += [("", ""), ("B. ROI", "h2"), (f"Tên: {r.roi['name']}", "")]
    if r.roi.get("source"):
        lines.append((f"Nguồn: {r.roi['source']}", ""))
    first, last, n = r.roi["axial_slices"]
    lines += [(f"Số voxel: {r.roi['voxel_count']:,}".replace(",", " "), ""),
              (f"Thể tích: {num(r.roi['volume_ml'], 3)} ml ({num(r.roi['volume_mm3'], 1)} mm³)", ""),
              (f"Thành phần liên thông: {r.roi['component_count']} (lớn nhất {r.roi['largest_component_voxels']:,} voxel)"
               .replace(",", " "), ""),
              (f"Lát axial: {first}–{last} ({n} lát có ROI)" if n else "Lát axial: -", "")]
    if r.hu:
        lines += [("", ""), ("C. Thống kê HU", "h2"),
                  (f"Nhỏ nhất {num(r.hu['min'], 1)} · lớn nhất {num(r.hu['max'], 1)} · trung bình "
                   f"{num(r.hu['mean'])} · trung vị {num(r.hu['median'], 1)} · độ lệch chuẩn {num(r.hu['std'])}", "")]
    if r.classes:
        lines += [("", ""), ("D. Phân lớp theo HU", "h2"),
                  ("Lớp | Khoảng HU [từ, đến) | Voxel | ml | % ROI", "")]
        for c in list(r.classes) + [r.unclassified]:
            rng = "-" if c["min_hu"] is None else f"[{num(c['min_hu'], 0)}, {num(c['max_hu'], 0)})"
            lines.append((f"{c['name']} | {rng} | {c['voxel_count']:,} | {num(c['volume_ml'], 2)} | "
                          f"{num(c['percent_roi'], 2)}".replace(",", " "), ""))
    if r.comparison:
        cp = r.comparison
        lines += [("", ""), (f"E. So sánh ROI: A = {cp['name_a']}, B = {cp['name_b']}", "h2"),
                  ("Chỉ số | A | B | Tổng", "")]
        for metric, a, b, t in cp["rows"]:
            lines.append((f"{metric} | {num(a)} | {num(b)} | {num(t)}", ""))
        for name, aml, ap, bml, bp, cml, cpct in cp["class_rows"]:
            lines.append((f"{name}: A {num(aml)} ml ({num(ap)}%) · B {num(bml)} ml ({num(bp)}%) · "
                          f"tổng {num(cml)} ml ({num(cpct)}%)", ""))
        if cp["overlap_voxels"]:
            lines.append((f"Chú ý: {cp['overlap_voxels']} voxel thuộc cả A và B (được tính hai lần trong Tổng).", ""))
    if r.ai:
        lines += [("", ""), ("F. Thông tin AI (đã ghi lại khi chạy)", "h2")]
        lines += [(f"{k}: {v}", "") for k, v in r.ai.items()]
    for note in r.notes:
        lines.append((note, ""))

    with PdfPages(str(path)) as pdf:
        fig, y = text_pages(pdf, lines)
        if histogram is not None:
            if y < 0.32:  # not enough room left: the histogram gets its own page
                pdf.savefig(fig)
                fig, y = page(), 0.95
            ax = fig.add_axes([0.1, max(0.06, y - 0.3), 0.82, 0.22])
            widths = np.diff(histogram.edges)
            ax.bar(histogram.edges[:-1], histogram.counts, width=widths, align="edge", color="0.35")
            ax.set_xlabel("HU", fontdict=font)
            ax.set_ylabel("Số voxel", fontdict=font)
            ax.set_title("Histogram HU bên trong ROI", fontdict=font, fontsize=10)
        pdf.savefig(fig)
        if slices:
            fig = page()
            fig.text(0.07, 0.96, "G. Ảnh minh họa (lát qua trọng tâm ROI, vẽ từ dữ liệu)", fontsize=12,
                     fontweight="bold", fontdict=font, va="top")
            lo, hi = window
            for i, (name, (image, lab, aspect)) in enumerate(slices.items()):
                ax = fig.add_axes([0.08, 0.62 - i * 0.30, 0.84, 0.26])
                ax.imshow(np.clip((np.asarray(image, dtype=float) - lo) / (hi - lo), 0, 1), cmap="gray",
                          interpolation="nearest", aspect=aspect)
                if lab is not None and class_colours:
                    rgba = np.zeros(lab.shape + (4,))
                    for cid, (rr, gg, bb, aa) in class_colours.items():
                        if cid:
                            rgba[lab == cid] = (rr, gg, bb, aa)
                    ax.imshow(rgba, interpolation="nearest", aspect=aspect)
                ax.set_title(name, fontdict=font, fontsize=10)
                ax.set_axis_off()
            pdf.savefig(fig)
        info = pdf.infodict()
        info["Title"] = "ROI analysis report"
        info["Creator"] = "InVesalius ROI Viewer"
