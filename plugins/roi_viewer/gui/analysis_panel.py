# --------------------------------------------------------------------------
# "Phân tích ROI" - the post-segmentation analysis section of the "Công cụ"
# tab: statistics and HU histogram of the current ROI, HU classes inside
# it (2D overlay + transient 3D preview), "convert class to ROI", ROI A/B
# comparison, CSV and PDF report. Computation lives in core/analysis/; this
# panel reads the current ROI through core/native_mask, runs the heavy
# part on a worker thread and shows the results.
#
# Isolation: the 2D overlay uses its own Slice().aux_matrices key and never
# replaces another overlay (the E2 preview has priority); the 3D preview is
# its own non-pickable actors (core/analysis/analysis_preview_3d.py). No
# mask, preview, E4/E5 actor or surface changes - except through the
# explicit "Chuyển lớp đang chọn thành ROI" button, which commits through
# native_mask.commit_preview_array_to_new_mask() like every candidate.
# --------------------------------------------------------------------------
import datetime
import threading

import wx

from ..core import native_mask
from ..core.analysis import analysis_report as report_mod
from ..core.analysis.analysis_preview_3d import AnalysisPreview3DManager, build_class_meshes
from ..core.analysis.analysis_session import analyse, compare
from ..core.analysis.hu_classes import (COVERAGE_LOW, COVERAGE_NONE, CUSTOM_PRESET, LUNG_DENSITY_PRESET, HUClass,
                                        colour_table, coverage_warning, validate_classes)
from ..core.analysis.roi_statistics import roi_histogram
from ..i18n import _, fmt_float, fmt_int
from . import ui_helpers

ANALYSIS_AUX_KEY = "roi_viewer_analysis"
PRESET_ORDER = (CUSTOM_PRESET, LUNG_DENSITY_PRESET)
NEW_CLASS_COLOURS = ((0.2, 0.6, 1.0), (1.0, 0.8, 0.0), (1.0, 0.35, 0.0), (0.55, 0.0, 0.75), (0.1, 0.7, 0.3),
                     (0.85, 0.1, 0.1))


class HistogramView(wx.Panel):
    """Bars of a core Histogram (x = HU, y = voxel count), drawn with a
    PaintDC - no plotting dependency in the GUI."""

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, size=(-1, 96))
        self.histogram = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def set_histogram(self, histogram):
        self.histogram = histogram
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        h = self.histogram
        w, height = self.GetClientSize()
        if h is None or not h.counts or max(h.counts) == 0 or w < 20:
            return
        bottom, plot_h = height - 16, height - 22
        peak = max(h.counts)
        bar_w = max(1.0, (w - 8) / len(h.counts))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(90, 90, 90)))
        for i, count in enumerate(h.counts):
            bh = int(round(plot_h * count / peak))
            if bh:
                dc.DrawRectangle(int(4 + i * bar_w), bottom - bh, max(1, int(bar_w)), bh)
        dc.SetTextForeground(wx.Colour(90, 90, 90))
        dc.SetFont(wx.Font(wx.FontInfo(7)))
        dc.DrawText(f"{h.edges[0]:.0f} HU", 4, bottom + 2)
        text = f"{h.edges[-1]:.0f} HU"
        dc.DrawText(text, w - 4 - dc.GetTextExtent(text).width, bottom + 2)


class AnalysisPanel(wx.Panel):
    def __init__(self, parent, controller):
        wx.Panel.__init__(self, parent)
        self.controller = controller
        self.session = None
        self.classes = []  # list of HUClass being edited
        self.histogram = None
        self.comparison = None
        self.preview_3d = AnalysisPreview3DManager()
        self._generation = 0
        self._compare_generation = 0
        self._converting = False
        self._dirty = False  # class editor differs from the selected class
        self._loading_editor = False
        self._busy = False
        self._callback_mask = None
        # Worker threads + wx.CallAfter in the application; tests set False
        # to run the same code synchronously (no event loop there).
        self.background = True
        self._init_ui()

    # ------------------------------------------------------------------ UI
    def _init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.pane, p = ui_helpers.collapsible(self, _("ROI analysis"), self._on_section_toggled)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(ui_helpers.hint(p, _("Statistics and HU classes of the current ROI. Research use only.")),
                 0, wx.ALL | wx.EXPAND, 3)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(p, wx.ID_ANY, _("ROI to analyse:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_source = wx.StaticText(p, wx.ID_ANY, "-")
        row.Add(self.lbl_source, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        body.Add(row, 0, wx.EXPAND)
        self.btn_compute = wx.Button(p, wx.ID_ANY, _("Compute"))
        body.Add(self.btn_compute, 0, wx.ALL | wx.EXPAND, 2)
        self.lbl_status = ui_helpers.StatusText(p, "")
        body.Add(self.lbl_status, 0, wx.ALL | wx.EXPAND, 3)
        self.lbl_stats = ui_helpers.StatusText(p, "")
        body.Add(self.lbl_stats, 0, wx.ALL | wx.EXPAND, 3)

        # histogram + range override
        self.histogram_view = HistogramView(p)
        body.Add(self.histogram_view, 0, wx.ALL | wx.EXPAND, 3)
        self.cb_hist_auto = wx.CheckBox(p, wx.ID_ANY, _("Automatic HU range"))
        self.cb_hist_auto.SetValue(True)
        body.Add(self.cb_hist_auto, 0, wx.ALL, 3)
        self.spin_hist_min = wx.SpinCtrlDouble(p, wx.ID_ANY, min=-3000, max=4000, initial=-1000, inc=10)
        self.spin_hist_max = wx.SpinCtrlDouble(p, wx.ID_ANY, min=-3000, max=4000, initial=400, inc=10)
        body.Add(ui_helpers.labelled_row(p, _("From HU:"), self.spin_hist_min), 0, wx.EXPAND)
        body.Add(ui_helpers.labelled_row(p, _("To HU:"), self.spin_hist_max), 0, wx.EXPAND)
        self.btn_hist_redraw = wx.Button(p, wx.ID_ANY, _("Redraw histogram"))
        body.Add(self.btn_hist_redraw, 0, wx.ALL | wx.EXPAND, 2)

        # HU classes
        self.cls_pane, c = ui_helpers.collapsible(p, _("HU classes"), self._on_section_toggled)
        cs = wx.BoxSizer(wx.VERTICAL)
        self.choice_preset = wx.Choice(c, wx.ID_ANY, choices=[_("Custom"), _("Lung density (experimental)")])
        self.choice_preset.SetSelection(0)
        cs.Add(ui_helpers.labelled_row(c, _("Preset:"), self.choice_preset), 0, wx.EXPAND)
        self.lbl_preset_note = ui_helpers.hint(c, _("Reference / experimental - not for diagnosis."))
        cs.Add(self.lbl_preset_note, 0, wx.ALL | wx.EXPAND, 3)
        self.list_classes = wx.ListCtrl(c, wx.ID_ANY, size=(-1, 120), style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for i, (title, width) in enumerate(((_("Name"), 92), (_("From HU"), 58), (_("To HU"), 58),
                                            (_("Shown"), 44))):
            self.list_classes.InsertColumn(i, title, width=width)
        self._images = wx.ImageList(12, 12)
        self.list_classes.SetImageList(self._images, wx.IMAGE_LIST_SMALL)
        cs.Add(self.list_classes, 0, wx.ALL | wx.EXPAND, 3)
        self.txt_class_name = wx.TextCtrl(c, wx.ID_ANY, "")
        cs.Add(ui_helpers.labelled_row(c, _("Name:"), self.txt_class_name), 0, wx.EXPAND)
        self.spin_class_min = wx.SpinCtrlDouble(c, wx.ID_ANY, min=-3000, max=4000, initial=-1000, inc=10)
        self.spin_class_max = wx.SpinCtrlDouble(c, wx.ID_ANY, min=-3000, max=4000, initial=0, inc=10)
        cs.Add(ui_helpers.labelled_row(c, _("From HU:"), self.spin_class_min), 0, wx.EXPAND)
        cs.Add(ui_helpers.labelled_row(c, _("To HU:"), self.spin_class_max), 0, wx.EXPAND)
        self.colour_class = wx.ColourPickerCtrl(c, wx.ID_ANY, wx.Colour(51, 153, 255))
        self.cb_class_visible = wx.CheckBox(c, wx.ID_ANY, _("Shown"))
        self.cb_class_visible.SetValue(True)
        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(self.colour_class, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        crow.Add(self.cb_class_visible, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        cs.Add(crow, 0)
        self.slider_opacity = wx.Slider(c, wx.ID_ANY, 50, 0, 100)
        cs.Add(ui_helpers.labelled_row(c, _("Opacity:"), self.slider_opacity), 0, wx.EXPAND)
        self.btn_class_add = wx.Button(c, wx.ID_ANY, _("+ Add class"))
        self.btn_class_remove = wx.Button(c, wx.ID_ANY, _("Remove class"))
        cs.Add(ui_helpers.button_row(self.btn_class_add, self.btn_class_remove), 0, wx.EXPAND)
        self.btn_class_apply = wx.Button(c, wx.ID_ANY, _("Apply changes"))
        cs.Add(self.btn_class_apply, 0, wx.ALL | wx.EXPAND, 2)
        self.lbl_dirty = ui_helpers.StatusText(c, "")
        self.lbl_dirty.SetForegroundColour(wx.Colour(170, 60, 0))
        cs.Add(self.lbl_dirty, 0, wx.ALL | wx.EXPAND, 3)
        self.cb_show_2d = wx.CheckBox(c, wx.ID_ANY, _("Show classes on 2D"))
        self.cb_show_3d = wx.CheckBox(c, wx.ID_ANY, _("Show classes in 3D"))
        cs.Add(self.cb_show_2d, 0, wx.ALL, 3)
        cs.Add(self.cb_show_3d, 0, wx.ALL, 3)
        self.lbl_classes = ui_helpers.StatusText(c, "")
        cs.Add(self.lbl_classes, 0, wx.ALL | wx.EXPAND, 3)
        self.lbl_coverage = ui_helpers.StatusText(c, "")
        self.lbl_coverage.SetForegroundColour(wx.Colour(170, 60, 0))
        cs.Add(self.lbl_coverage, 0, wx.ALL | wx.EXPAND, 3)
        self.btn_convert = wx.Button(c, wx.ID_ANY, _("Convert selected class to ROI"))
        cs.Add(self.btn_convert, 0, wx.ALL | wx.EXPAND, 2)
        c.SetSizer(cs)
        body.Add(self.cls_pane, 0, wx.ALL | wx.EXPAND, 2)

        # comparison
        self.cmp_pane, q = ui_helpers.collapsible(p, _("Compare ROIs"), self._on_section_toggled)
        qs = wx.BoxSizer(wx.VERTICAL)
        # ComboBox (read-only), not Choice: the items are the user's own mask names.
        self.combo_roi_a = wx.ComboBox(q, wx.ID_ANY, choices=[], style=wx.CB_READONLY)
        self.combo_roi_b = wx.ComboBox(q, wx.ID_ANY, choices=[], style=wx.CB_READONLY)
        qs.Add(ui_helpers.labelled_row(q, _("ROI A:"), self.combo_roi_a), 0, wx.EXPAND)
        qs.Add(ui_helpers.labelled_row(q, _("ROI B:"), self.combo_roi_b), 0, wx.EXPAND)
        self.btn_compare = wx.Button(q, wx.ID_ANY, _("Compare"))
        qs.Add(self.btn_compare, 0, wx.ALL | wx.EXPAND, 2)
        self.lbl_compare = ui_helpers.StatusText(q, "")
        qs.Add(self.lbl_compare, 0, wx.ALL | wx.EXPAND, 3)
        q.SetSizer(qs)
        body.Add(self.cmp_pane, 0, wx.ALL | wx.EXPAND, 2)

        self.btn_csv = wx.Button(p, wx.ID_ANY, _("Export statistics (CSV)"))
        self.btn_report = wx.Button(p, wx.ID_ANY, _("Create analysis report"))
        body.Add(self.btn_csv, 0, wx.ALL | wx.EXPAND, 2)
        body.Add(self.btn_report, 0, wx.ALL | wx.EXPAND, 2)
        p.SetSizer(body)
        sizer.Add(self.pane, 0, wx.ALL | wx.EXPAND, 2)
        self.SetSizer(sizer)

        self.btn_compute.Bind(wx.EVT_BUTTON, self._on_compute)
        self.btn_hist_redraw.Bind(wx.EVT_BUTTON, self._on_redraw_histogram)
        self.cb_hist_auto.Bind(wx.EVT_CHECKBOX, lambda e: self._update_controls())
        self.choice_preset.Bind(wx.EVT_CHOICE, self._on_preset)
        self.list_classes.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_class_selected)
        self.btn_class_add.Bind(wx.EVT_BUTTON, self._on_class_add)
        self.btn_class_remove.Bind(wx.EVT_BUTTON, self._on_class_remove)
        self.btn_class_apply.Bind(wx.EVT_BUTTON, self._on_class_apply)
        self.cb_show_2d.Bind(wx.EVT_CHECKBOX, self._on_toggle_2d)
        self.cb_show_3d.Bind(wx.EVT_CHECKBOX, self._on_toggle_3d)
        self.btn_convert.Bind(wx.EVT_BUTTON, self._on_convert)
        self.btn_compare.Bind(wx.EVT_BUTTON, self._on_compare)
        self.btn_csv.Bind(wx.EVT_BUTTON, self._on_export_csv)
        self.btn_report.Bind(wx.EVT_BUTTON, self._on_report)
        self.txt_class_name.Bind(wx.EVT_TEXT, self._on_editor_changed)
        for w in (self.spin_class_min, self.spin_class_max):
            w.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_editor_changed)
            w.Bind(wx.EVT_TEXT, self._on_editor_changed)
        self.colour_class.Bind(wx.EVT_COLOURPICKER_CHANGED, self._on_editor_changed)
        self.cb_class_visible.Bind(wx.EVT_CHECKBOX, self._on_editor_changed)
        self.slider_opacity.Bind(wx.EVT_SLIDER, self._on_editor_changed)
        self._refresh_class_list()
        self._update_controls()

    def _on_section_toggled(self, event):
        top = self.GetParent()
        self.Layout()
        if hasattr(top, "SetupScrolling"):
            ui_helpers.relayout_scrolled(top)
        if event is not None:
            event.Skip()

    def _spawn(self, fn, name):
        if self.background:
            threading.Thread(target=fn, daemon=True, name=name).start()
        else:
            fn()

    def _deliver(self, fn, *args):
        if self.background:
            wx.CallAfter(fn, *args)
        else:
            fn(*args)

    # ------------------------------------------------------------------ data access
    @staticmethod
    def _slice():
        import invesalius.data.slice_ as sl

        return sl.Slice()

    @staticmethod
    def _spacing():
        from ..interface.project_interface import ProjectInterface

        return tuple(float(v) for v in ProjectInterface().get_spacing())

    @staticmethod
    def _hu_available() -> bool:
        try:
            import invesalius.project as prj

            return str(getattr(prj.Project(), "modality", "")).upper() == "CT"
        except Exception:
            return False

    @staticmethod
    def _mask_dict():
        try:
            import invesalius.project as prj

            return prj.Project().mask_dict or {}
        except Exception:
            return {}

    def _source_mask(self):
        try:
            return self._slice().current_mask
        except Exception:
            return None

    def _logical(self, mask):
        return native_mask.logical_foreground(self._slice(), mask)

    def _session_mask(self):
        """The analysed Mask object if it still exists in the project."""
        if self.session is None:
            return None
        mask = self._mask_dict().get(self.session.mask_index)
        return mask if mask is not None and mask is self.session.extra.get("mask") else None

    # ------------------------------------------------------------------ staleness
    def _watch(self, mask):
        if mask is self._callback_mask:
            return
        self._unwatch()
        self._callback_mask = mask
        if mask is not None and hasattr(mask, "add_modified_callback"):
            mask.add_modified_callback(self._on_source_modified)

    def _unwatch(self):
        if self._callback_mask is not None:
            try:
                self._callback_mask.remove_modified_callback(self._on_source_modified)
            except Exception:
                pass
        self._callback_mask = None

    def _on_source_modified(self):
        if self.session is not None and not self.session.stale:
            self._mark_stale()

    def _mark_stale(self):
        self.session.invalidate()
        self._hide_previews()
        try:
            self.lbl_status.SetLabel(_("ROI changed. Compute the analysis again."))
        except RuntimeError:
            return
        self._update_controls()

    def ensure_current(self) -> bool:
        """True when the session is valid for the analysed ROI as it is now;
        otherwise it is marked stale (source edited or deleted)."""
        if self.session is None or self.session.stale:
            return False
        mask = self._session_mask()
        if mask is None:
            self._mark_stale()
            return False
        if not self.session.check(self._logical(mask), self._spacing()):
            self._mark_stale()
            return False
        return True

    # ------------------------------------------------------------------ compute
    def _on_compute(self, event):
        if self._dirty:
            self.lbl_status.SetLabel(_("There are unapplied changes."))
            return
        errors = validate_classes(self.classes)
        if errors:
            self.lbl_status.SetLabel(errors[0])
            return
        mask = self._source_mask()
        s = self._slice()
        if mask is None or mask.matrix is None or s.matrix is None:
            self.lbl_status.SetLabel(_("No mask selected."))
            return
        self._hide_previews()
        try:
            foreground = self._logical(mask)
        except Exception as e:
            print(f"ROI Viewer: analysis could not read the ROI - {e}")
            self.lbl_status.SetLabel(_("Analysis failed."))
            return
        spacing, hu, classes = self._spacing(), self._hu_available(), tuple(self.classes)
        hist_range = None if self.cb_hist_auto.GetValue() else (self.spin_hist_min.GetValue(),
                                                                self.spin_hist_max.GetValue())
        name, index, volume = str(getattr(mask, "name", "")), mask.index, s.matrix
        self._generation += 1
        gen = self._generation
        self._busy = True
        self.lbl_status.SetLabel(_("Computing…"))
        self._update_controls()

        def worker():
            try:
                session = analyse(volume, foreground, spacing, index, name, classes, hu)
                histogram = roi_histogram(volume, foreground, hist_range) if (hu and foreground.any()) else None
                self._deliver(self._on_computed, gen, session, histogram, mask, None)
            except Exception as e:
                self._deliver(self._on_computed, gen, None, None, mask, e)

        self._spawn(worker, "roi-viewer-analysis")

    def _on_computed(self, gen, session, histogram, mask, error):
        if gen != self._generation:
            return  # a newer computation or a reset happened
        self._busy = False
        try:
            if error is not None:
                print(f"ROI Viewer: analysis failed - {error}")
                self.lbl_status.SetLabel(_("Analysis failed."))
                self._update_controls()
                return
            session.extra["mask"] = mask
            self.session, self.histogram, self.comparison = session, histogram, None
            self._watch(mask)
            self.lbl_status.SetLabel(_("Analysis of '{name}' is up to date.").format(name=session.roi_name))
            self._show_results()
            self._update_controls()
        except RuntimeError:
            pass  # panel destroyed meanwhile

    def _on_redraw_histogram(self, event):
        if not self.ensure_current() or not self._hu_available():
            return
        mask = self._session_mask()
        hist_range = None if self.cb_hist_auto.GetValue() else (self.spin_hist_min.GetValue(),
                                                                self.spin_hist_max.GetValue())
        try:
            self.histogram = roi_histogram(self._slice().matrix, self._logical(mask), hist_range)
        except ValueError as e:
            self.lbl_status.SetLabel(_("Invalid HU range."))
            print(f"ROI Viewer: histogram - {e}")
            return
        self.histogram_view.set_histogram(self.histogram)

    def _show_results(self):
        s = self.session.statistics
        lines = [
            _("Voxels: {voxels}").format(voxels=fmt_int(s.voxel_count)),
            _("Volume: {ml} ml ({mm3} mm³)").format(ml=fmt_float(s.volume_ml, 2), mm3=fmt_float(s.volume_mm3, 1)),
        ]
        if s.hu is not None:
            lines.append(_("HU mean {mean} · median {median} · std {std}").format(
                mean=fmt_float(s.hu.mean, 1), median=fmt_float(s.hu.median, 1), std=fmt_float(s.hu.std, 1)))
            lines.append(_("HU min {min} · max {max}").format(min=fmt_float(s.hu.minimum, 0),
                                                             max=fmt_float(s.hu.maximum, 0)))
        elif s.voxel_count:
            lines.append(_("No HU statistics (not a CT image)."))
        if s.voxel_count:
            lines.append(_("Components: {n} (largest {largest} voxels)").format(
                n=s.component_count, largest=fmt_int(s.largest_component_voxels)))
            lines.append(_("Axial slices {first}-{last} ({n} with ROI)").format(
                first=s.first_axial_slice, last=s.last_axial_slice, n=s.occupied_axial_slices))
        self.lbl_stats.SetLabel("\n".join(lines))
        self.histogram_view.set_histogram(self.histogram)
        self._show_class_results()

    def _show_class_results(self):
        cls = self.session.classification if self.session else None
        if cls is None:
            self.lbl_classes.SetLabel("")
            self.lbl_coverage.SetLabel("")
            return
        lines = [_("{name}: {ml} ml ({percent}%)").format(name=r.display_name, ml=fmt_float(r.volume_ml, 2),
                                                        percent=fmt_float(r.percent_of_roi, 1))
                 for r in cls.classes]
        u = cls.unclassified
        lines.append(_("Unclassified: {ml} ml ({percent}%)").format(ml=fmt_float(u.volume_ml, 2),
                                                                    percent=fmt_float(u.percent_of_roi, 1)))
        self.lbl_classes.SetLabel("\n".join(lines))
        code = coverage_warning(cls)
        self.lbl_coverage.SetLabel(
            _("No voxel of the ROI is inside the declared HU ranges. Check the class ranges.") if code == COVERAGE_NONE
            else _("Most voxels are in no HU class.") if code == COVERAGE_LOW else "")

    # ------------------------------------------------------------------ classes
    def _refresh_class_list(self, select=None):
        self.list_classes.DeleteAllItems()
        self._images.RemoveAll()
        for i, c in enumerate(self.classes):
            bmp = wx.Bitmap(12, 12)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(wx.Colour(*(int(round(v * 255)) for v in c.display_color))))
            dc.Clear()
            dc.SelectObject(wx.NullBitmap)
            image = self._images.Add(bmp)
            self.list_classes.InsertItem(i, c.display_name, image)
            self.list_classes.SetItem(i, 1, f"{c.min_hu:g}")
            self.list_classes.SetItem(i, 2, f"{c.max_hu:g}")
            self.list_classes.SetItem(i, 3, _("yes") if c.visible else _("no"))
        if select is not None and 0 <= select < len(self.classes):
            self.list_classes.Select(select)

    def _selected_class_index(self):
        i = self.list_classes.GetFirstSelected()
        return i if 0 <= i < len(self.classes) else None

    def _on_preset(self, event):
        preset = PRESET_ORDER[self.choice_preset.GetSelection()]
        self.classes = list(preset.classes)
        self._classes_changed()

    def _on_class_selected(self, event):
        i = self._selected_class_index()
        if i is None:
            return
        self._load_editor(self.classes[i])

    def _load_editor(self, c):
        """Show class `c` in the editor; switching class discards unapplied edits."""
        self._loading_editor = True
        try:
            self.txt_class_name.SetValue(c.display_name)
            self.spin_class_min.SetValue(c.min_hu)
            self.spin_class_max.SetValue(c.max_hu)
            self.colour_class.SetColour(wx.Colour(*(int(round(v * 255)) for v in c.display_color)))
            self.cb_class_visible.SetValue(c.visible)
            self.slider_opacity.SetValue(int(round(c.opacity * 100)))
        finally:
            self._loading_editor = False
        self._set_dirty(False)

    def _on_editor_changed(self, event=None):
        if event is not None:
            event.Skip()
        if self._loading_editor:
            return
        i = self._selected_class_index()
        if i is None:
            self._set_dirty(False)
            return
        self._set_dirty(self._editor_class(self.classes[i].class_id) != self.classes[i])

    def _set_dirty(self, dirty):
        """Unapplied class edits block every action that uses the classes, so
        nothing runs on definitions other than the ones in the list."""
        self._dirty = bool(dirty)
        try:
            self.lbl_dirty.SetLabel(_("There are unapplied changes.") if self._dirty else "")
            self._update_controls()
        except RuntimeError:
            pass

    def _editor_class(self, class_id):
        colour = self.colour_class.GetColour()
        return HUClass(class_id, self.txt_class_name.GetValue().strip(), float(self.spin_class_min.GetValue()),
                       float(self.spin_class_max.GetValue()),
                       (colour.Red() / 255.0, colour.Green() / 255.0, colour.Blue() / 255.0),
                       self.cb_class_visible.GetValue(), self.slider_opacity.GetValue() / 100.0)

    def _on_class_add(self, event):
        used = {c.class_id for c in self.classes}
        class_id = next(i for i in range(1, 255) if i not in used)
        lo = max((c.max_hu for c in self.classes), default=-1000.0)
        colour = NEW_CLASS_COLOURS[(class_id - 1) % len(NEW_CLASS_COLOURS)]
        self.classes.append(HUClass(class_id, _("Class {n}").format(n=class_id), lo, lo + 100.0, colour))
        self._classes_changed(select=len(self.classes) - 1)

    def _on_class_remove(self, event):
        i = self._selected_class_index()
        if i is not None:
            del self.classes[i]
            self._classes_changed()

    def _on_class_apply(self, event):
        i = self._selected_class_index()
        if i is None:
            return
        candidate = list(self.classes)
        candidate[i] = self._editor_class(self.classes[i].class_id)
        errors = validate_classes(candidate)
        if errors:
            self.lbl_status.SetLabel(errors[0])  # the class list is left as it was
            return
        only_display = (candidate[i].min_hu, candidate[i].max_hu) == (self.classes[i].min_hu, self.classes[i].max_hu)
        self.classes = candidate
        self._set_dirty(False)
        self._classes_changed(select=i, keep_results=only_display)

    def _classes_changed(self, select=None, keep_results=False):
        """Ranges changed: results no longer match the classes - recompute.
        Only colour/visibility/opacity changed: redraw the previews."""
        self._refresh_class_list(select)
        if select is not None and 0 <= select < len(self.classes):
            self._load_editor(self.classes[select])
        else:
            self._set_dirty(False)
        if self.session is not None and not keep_results:
            self._hide_previews()
            self.session.classification = None
            self.session.labels = None
            self.lbl_classes.SetLabel("")
            self.lbl_coverage.SetLabel("")
            self.lbl_status.SetLabel(_("Classes changed. Press Compute."))
        elif self.session is not None and keep_results:
            self.session.classes = tuple(self.classes)
            if self.cb_show_2d.GetValue():
                self._show_2d()
            if self.cb_show_3d.GetValue():
                self._start_3d()
        self._update_controls()

    # ------------------------------------------------------------------ 2D overlay
    def _on_toggle_2d(self, event):
        if self.cb_show_2d.GetValue():
            if not self.ensure_current() or self.session.labels is None:
                self.cb_show_2d.SetValue(False)
                return
            if not self._show_2d():
                self.cb_show_2d.SetValue(False)
        else:
            self._hide_2d()

    def _show_2d(self) -> bool:
        from invesalius.pubsub import pub as Publisher

        s = self._slice()
        if s.to_show_aux not in ("", ANALYSIS_AUX_KEY):
            # the segmentation preview (E2) owns the overlay slot
            self.lbl_status.SetLabel(_("A segmentation preview is shown. Accept or cancel it first."))
            return False
        s.aux_matrices[ANALYSIS_AUX_KEY] = self.session.labels
        s.aux_matrices_colours[ANALYSIS_AUX_KEY] = colour_table(self.classes)
        s.to_show_aux = ANALYSIS_AUX_KEY
        Publisher.sendMessage("Reload actual slice")
        return True

    def _hide_2d(self):
        try:
            from invesalius.pubsub import pub as Publisher

            s = self._slice()
            if s.to_show_aux == ANALYSIS_AUX_KEY:
                s.to_show_aux = ""
            s.aux_matrices.pop(ANALYSIS_AUX_KEY, None)
            s.aux_matrices_colours.pop(ANALYSIS_AUX_KEY, None)
            Publisher.sendMessage("Reload actual slice")
        except Exception as e:
            print(f"ROI Viewer: analysis overlay cleanup skipped - {e}")

    # ------------------------------------------------------------------ 3D preview
    def _on_toggle_3d(self, event):
        if self.cb_show_3d.GetValue():
            if not self.ensure_current() or self.session.labels is None:
                self.cb_show_3d.SetValue(False)
                return
            self._start_3d()
        else:
            self.preview_3d.detach()
            self.controller.request_render()

    def _viewer_renderer(self):
        from ..interface.view_interface import ViewInterface

        viewer = ViewInterface().get_volume_viewer()
        return getattr(viewer, "ren", None)

    def _start_3d(self):
        labels, classes, spacing = self.session.labels, tuple(self.classes), self.session.spacing_xyz
        gen = self.preview_3d.new_generation()
        self.lbl_status.SetLabel(_("Building the 3D class preview…"))

        def worker():
            try:
                meshes = build_class_meshes(labels, classes, spacing)
                self._deliver(self._on_3d_built, gen, meshes, classes)
            except Exception as e:
                print(f"ROI Viewer: analysis 3D preview failed - {e}")

        self._spawn(worker, "roi-viewer-analysis-3d")

    def _on_3d_built(self, gen, meshes, classes):
        renderer = self._viewer_renderer()
        try:
            if renderer is None or not self.cb_show_3d.GetValue():
                return
            if self.preview_3d.show(renderer, meshes, classes, gen):
                self.controller.place_3d_camera_if_unset()
                self.controller.request_render()
                self.lbl_status.SetLabel(_("3D class preview shown."))
        except RuntimeError:
            pass

    def _hide_previews(self):
        self._hide_2d()
        self.preview_3d.detach()
        try:
            self.cb_show_2d.SetValue(False)
            self.cb_show_3d.SetValue(False)
            self.controller.request_render()
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ convert
    def _on_convert(self, event):
        if self._converting or self._dirty:
            return
        i = self._selected_class_index()
        if i is None or not self.ensure_current() or self.session.labels is None:
            if self.session is not None and not self.session.stale and i is None:
                self.lbl_status.SetLabel(_("Select a class in the list first."))
            return
        self._converting = True
        self.btn_convert.Enable(False)
        try:
            name = self.convert_class_to_roi(self.classes[i])
        finally:
            self._converting = False
            self._update_controls()
        if name:
            self.lbl_status.SetLabel(_("Created ROI '{name}'.").format(name=name))
        else:
            self.lbl_status.SetLabel(_("The class is empty - no ROI created."))

    def convert_class_to_roi(self, hu_class):
        """The class's voxels become ONE new ROI through the shared commit
        path. The parent ROI is not touched; no surface is built. Returns
        the new name, or None when the class has no voxel."""
        import numpy as np

        candidate = np.asarray(self.session.labels) == int(hu_class.class_id)
        if not candidate.any():
            return None
        name = f"{self.session.roi_name} - {hu_class.display_name}"
        self._hide_previews()  # the overlay belongs to the parent; the new mask becomes current
        mask = native_mask.commit_preview_array_to_new_mask(candidate, name, tuple(hu_class.display_color))
        if mask is None:
            return None
        provenance = getattr(self.controller, "roi_provenance", None)
        if provenance is not None:
            provenance[mask] = {"source": _("HU class '{name}' of '{parent}'").format(
                name=hu_class.display_name, parent=self.session.roi_name)}
        try:
            self.controller.on_roi_source_changed()
        except Exception as e:
            print(f"ROI Viewer: ROI list refresh after conversion failed - {e}")
        return name

    # ------------------------------------------------------------------ comparison
    def refresh_roi_choices(self):
        names = [str(getattr(m, "name", i)) for i, m in sorted(self._mask_dict().items())]
        for combo in (self.combo_roi_a, self.combo_roi_b):
            current = combo.GetValue()
            combo.Set(names)
            if current in names:
                combo.SetValue(current)

    def _mask_by_name(self, name):
        for _i, m in sorted(self._mask_dict().items()):
            if str(getattr(m, "name", "")) == name:
                return m
        return None

    def _on_compare(self, event):
        if self._dirty:
            self.lbl_compare.SetLabel(_("There are unapplied changes."))
            return
        a, b = self._mask_by_name(self.combo_roi_a.GetValue()), self._mask_by_name(self.combo_roi_b.GetValue())
        if a is None or b is None:
            self.lbl_compare.SetLabel(_("Choose ROI A and ROI B."))
            return
        # Masks are read here (native objects, main thread); the statistics run
        # on a worker (two lungs of 0543: 6.7 s - too long for the UI thread).
        try:
            mask_a, mask_b = self._logical(a), self._logical(b)
        except Exception as e:
            print(f"ROI Viewer: ROI comparison could not read the ROIs - {e}")
            self.lbl_compare.SetLabel(_("Analysis failed."))
            return
        volume, spacing, hu = self._slice().matrix, self._spacing(), self._hu_available()
        classes = tuple(self.classes) if not validate_classes(self.classes) else ()
        names = (str(a.name), str(b.name))
        self._compare_generation += 1
        gen = self._compare_generation
        self.btn_compare.Enable(False)
        self.lbl_compare.SetLabel(_("Computing…"))

        def worker():
            try:
                result = compare(volume, mask_a, mask_b, spacing, names[0], names[1], classes, hu)
                self._deliver(self._on_compared, gen, result, None)
            except Exception as e:
                self._deliver(self._on_compared, gen, None, e)

        self._spawn(worker, "roi-viewer-analysis-compare")

    def _on_compared(self, gen, result, error):
        if gen != self._compare_generation:
            return
        try:
            self.btn_compare.Enable(True)
        except RuntimeError:
            return
        if error is not None:
            print(f"ROI Viewer: ROI comparison failed - {error}")
            self.lbl_compare.SetLabel(_("Analysis failed."))
            return
        self.comparison = result
        rows = {r.metric: r for r in result.rows}
        rel = result.relation
        vol = rows["volume_ml"]
        lines = [
            _("Volume (ml): A {a} · B {b} · A∪B {u}").format(a=fmt_float(vol.a, 2), b=fmt_float(vol.b, 2),
                                                           u=fmt_float(vol.union, 2)),
            _("A + B (may double-count): {s} ml").format(s=fmt_float(vol.a_plus_b, 2)),
            _("Intersection {i} ml · only A {oa} ml · only B {ob} ml").format(
                i=fmt_float(rel.ml(rel.intersection_voxels), 2), oa=fmt_float(rel.ml(rel.only_a_voxels), 2),
                ob=fmt_float(rel.ml(rel.only_b_voxels), 2)),
            _("Dice {dice} · IoU {iou}").format(dice=fmt_float(rel.dice, 4), iou=fmt_float(rel.iou, 4)),
        ]
        if "hu_mean" in rows and rows["hu_mean"].union is not None:
            r = rows["hu_mean"]
            lines.append(_("HU mean: A {a} · B {b} · A∪B {u}").format(
                a=fmt_float(r.a, 1) if r.a is not None else "-", b=fmt_float(r.b, 1) if r.b is not None else "-",
                u=fmt_float(r.union, 1)))
        for r in result.class_rows:
            lines.append(_("{name}: A {a}% · B {b}% · A∪B {u}%").format(
                name=r.display_name, a=fmt_float(r.a_percent, 1), b=fmt_float(r.b_percent, 1),
                u=fmt_float(r.union_percent, 1)))
        if rel.intersection_voxels:
            lines.append(_("A and B share {n} voxels: A + B counts them twice, A∪B once.").format(
                n=fmt_int(rel.intersection_voxels)))
        self.lbl_compare.SetLabel("\n".join(lines))

    # ------------------------------------------------------------------ export
    def report_data(self, generated=None):
        import numpy as np

        s = self._slice()
        mask = self._session_mask()
        provenance = (getattr(self.controller, "roi_provenance", None) or {}).get(mask, {}) if mask is not None else {}
        try:
            import invesalius.project as prj

            label = str(getattr(prj.Project(), "name", "") or "")
            modality = str(getattr(prj.Project(), "modality", "") or "")
        except Exception:
            label, modality = "", ""
        dataset = {"label": label, "modality": modality, "shape_zyx": tuple(int(n) for n in np.shape(s.matrix)),
                   "spacing_xyz": tuple(round(v, 6) for v in self._spacing())}
        comparison = self.comparison
        return report_mod.build_report_data(
            self.session, dataset, generated or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            comparison=comparison, ai_metadata=provenance.get("ai"), source=provenance.get("source", ""),
            class_note=self._class_note())

    def _class_note(self):
        """The experimental-preset label, when the classes are the lung preset's."""
        ranges = [(c.display_name, c.min_hu, c.max_hu) for c in self.classes]
        if ranges and ranges == [(c.display_name, c.min_hu, c.max_hu) for c in LUNG_DENSITY_PRESET.classes]:
            return LUNG_DENSITY_PRESET.display_name + ": " + LUNG_DENSITY_PRESET.note
        return ""

    def _ask_path(self, wildcard, extension):
        name = report_mod.default_basename(self.session.roi_name, datetime.date.today().isoformat()) + extension
        with wx.FileDialog(self, _("Save"), defaultFile=name, wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None

    def check_source(self):
        """Called after plugin-side edits (cleanup, undo/redo, accept): an
        edited source makes the analysis stale right away."""
        try:
            if self.session is not None and not self.session.stale:
                self.ensure_current()
        except Exception as e:
            print(f"ROI Viewer: analysis source check failed - {e}")

    def _on_export_csv(self, event):
        if self._dirty or not self.ensure_current():
            return
        path = self._ask_path("CSV (*.csv)|*.csv", ".csv")
        if path:
            written = report_mod.write_csv(self.report_data(), path)
            self.lbl_status.SetLabel(_("Statistics saved.") if len(written) == 1 else
                                     _("Statistics and comparison saved."))

    def _on_report(self, event):
        if self._dirty or not self.ensure_current():
            return
        path = self._ask_path("PDF (*.pdf)|*.pdf", ".pdf")
        if not path:
            return
        data = self.report_data()
        slices = report_mod.centroid_slices(self._slice().matrix, self._logical(self._session_mask()),
                                            self.session.labels, self.session.statistics)
        colours, histogram = colour_table(self.classes), self.histogram
        self.btn_report.Enable(False)
        self.lbl_status.SetLabel(_("Creating the report…"))

        def worker():
            try:
                report_mod.write_pdf(data, path, slices=slices, class_colours=colours, histogram=histogram)
                self._deliver(self._on_report_written, None)
            except Exception as e:
                self._deliver(self._on_report_written, e)

        self._spawn(worker, "roi-viewer-analysis-report")

    def _on_report_written(self, error):
        try:
            self.btn_report.Enable(self.session is not None and not self.session.stale)
            if error is None:
                self.lbl_status.SetLabel(_("Report saved."))
            else:
                print(f"ROI Viewer: report failed - {error}")
                self.lbl_status.SetLabel(_("Report failed."))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ state
    def _update_controls(self):
        ok = self.session is not None and not self.session.stale
        classified = ok and self.session.labels is not None
        clean = not self._dirty
        self.btn_compute.Enable(not self._busy and clean)
        self.btn_compare.Enable(clean)
        self.btn_hist_redraw.Enable(ok and self.histogram is not None)
        for w in (self.spin_hist_min, self.spin_hist_max):
            w.Enable(not self.cb_hist_auto.GetValue())
        for w in (self.cb_show_2d, self.cb_show_3d):
            w.Enable(classified and clean)
        self.btn_convert.Enable(classified and clean and not self._converting)
        for w in (self.btn_csv, self.btn_report):
            w.Enable(ok and clean)
        has = self._selected_class_index() is not None
        for w in (self.btn_class_remove, self.btn_class_apply):
            w.Enable(has)
        mask = self._source_mask()
        self.lbl_source.SetLabel(str(getattr(mask, "name", "-")) if mask is not None else "-")
        self.lbl_preset_note.Show(self.choice_preset.GetSelection() == 1)

    def on_roi_source_changed(self):
        """ROI list changed (created, renamed, deleted): refresh the pickers;
        a deleted source makes the analysis stale."""
        try:
            self.refresh_roi_choices()
            if self.session is not None and not self.session.stale and self._session_mask() is None:
                self._mark_stale()
            self._update_controls()
        except RuntimeError:
            pass

    def reset(self):
        """Project close/load and plugin close: nothing survives."""
        self._generation += 1
        self._compare_generation += 1
        self._busy = False
        self._hide_previews()
        self._unwatch()
        self.session = None
        self.histogram = None
        self.comparison = None
        self._converting = False
        try:
            self.lbl_status.SetLabel("")
            self.lbl_stats.SetLabel("")
            self.lbl_classes.SetLabel("")
            self.lbl_compare.SetLabel("")
            self.lbl_coverage.SetLabel("")
            self.histogram_view.set_histogram(None)
            self.refresh_roi_choices()
            self._update_controls()
        except RuntimeError:
            pass

    def shutdown(self):
        self.reset()
