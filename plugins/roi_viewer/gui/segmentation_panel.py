# --------------------------------------------------------------------------
# Segmentation Panel Module
# Description: Panel for ROI segmentation tools, wired to the real
#              InVesalius mask pipeline (invesalius.data.slice_.Slice) via
#              the exact pubsub topics InVesalius's own threshold task
#              panel uses - not a disconnected local copy of the volume.
# --------------------------------------------------------------------------

from typing import Optional

import wx
import wx.lib.scrolledpanel as scrolled

from ..core import segmentation_preview

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s

# E2 (Advanced Segmentation Enhancement Track, enhancement/advanced-
# segmentation branch only): the real Slice().aux_matrices/to_show_aux key
# this plugin's preview overlay uses. A plain string constant (not a
# per-instance attribute) since it must stay identical between the code
# that writes it (see _show_preview_overlay()) and the code that clears it
# (_clear_preview_overlay()) regardless of which SegmentationPanel/
# controller instance is involved.
PREVIEW_AUX_KEY = "roi_viewer_preview"


def choose_surface_algorithm(mask) -> str:
    """
    Phase 08 (CT3D_P08_ROI3D_CLOSURE) surface-rebuild policy, extracted
    to a small pure function in Phase 11 (CT3D_P11_TEST_AUTOMATION) so it
    is unit-testable without wx/pubsub - behavior is unchanged, this is
    the exact expression _on_update_surface() used inline before.

    See _on_update_surface()'s docstring below for the full root-cause
    story: with algorithm="Default", InVesalius's marching cubes never
    reads the mask's own voxel array at all (it re-contours the original
    image at mask.threshold_range) - only "Binary" (or "ca_smoothing")
    triggers the from_binary=True path that actually reads mask.matrix.
    So any mask that has been directly edited (mask.was_edited == True -
    set by real brush edits in invesalius/data/styles.py, and by this
    plugin's own Region Growing path, see _on_region_grown() below) must
    use "Binary"; an unedited threshold-only mask keeps "Default"
    (behavior-preserving - no regression for the ordinary threshold
    workflow).
    """
    return "Binary" if getattr(mask, "was_edited", False) else "Default"


class SegmentationPanel(scrolled.ScrolledPanel):
    """
    Panel for segmentation tools (threshold-based mask creation, plus
    undo/redo of the current mask's voxel data).

    `controller` is the owning ROIViewerFrame - it holds the shared
    core/ manager instances (seg_mgr, mask_mgr) created once per plugin
    session, so state (like undo history) survives switching tabs.
    """

    def __init__(self, parent, controller):
        scrolled.ScrolledPanel.__init__(self, parent)
        self.controller = controller
        self._roi_list_ids = []
        # E2: preview state lives on this panel instance (like mask_mgr/
        # roi_mgr live on `controller`) - pure bookkeeping, see
        # core/segmentation_preview.py's module docstring. `_preview_temp_file`
        # is the real temp-file path backing the memmap array (mirrors
        # invesalius/data/styles.py's Watershed _remove_mask() pattern -
        # see _clear_preview_overlay() below). `_preview_seed_world`/
        # `_preview_seed_voxel` hold the last seed picked while Preview
        # Workflow is enabled, waiting for an explicit "Preview Region
        # Growing" click (see _on_seed_picked()'s branch below).
        self.preview_mgr = segmentation_preview.SegmentationPreviewManager()
        self._preview_temp_file = None
        self._preview_seed_world = None
        self._preview_seed_voxel = None
        self._init_ui()
        self.SetupScrolling()

    def _init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, wx.ID_ANY, _("ROI Segmentation Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)

        # --- Threshold -> real mask creation ---
        box_thresh = wx.StaticBox(self, wx.ID_ANY, _("Threshold"))
        thresh_sizer = wx.StaticBoxSizer(box_thresh, wx.VERTICAL)

        self.cb_auto_thresh = wx.CheckBox(self, wx.ID_ANY, _("Auto threshold (Otsu)"))
        thresh_sizer.Add(self.cb_auto_thresh, 0, wx.ALL, 5)

        thresh_row = wx.BoxSizer(wx.HORIZONTAL)
        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("Min:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.spin_min = wx.SpinCtrl(self, wx.ID_ANY, "226", min=-1024, max=8000)
        thresh_row.Add(self.spin_min, 1, wx.ALL, 5)

        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("Max:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.spin_max = wx.SpinCtrl(self, wx.ID_ANY, "3071", min=-1024, max=8000)
        thresh_row.Add(self.spin_max, 1, wx.ALL, 5)

        thresh_sizer.Add(thresh_row, 0, wx.EXPAND, 5)

        self.btn_apply_thresh = wx.Button(self, wx.ID_ANY, _("Create Mask from Threshold"))
        thresh_sizer.Add(self.btn_apply_thresh, 0, wx.ALL | wx.EXPAND, 5)

        # E2 (enhancement/advanced-segmentation branch only): disabled
        # unless "Enable Preview Workflow" (below) is checked - see
        # _on_enable_preview_toggle().
        self.btn_preview_otsu = wx.Button(self, wx.ID_ANY, _("Preview Otsu"))
        self.btn_preview_otsu.Enable(False)
        thresh_sizer.Add(self.btn_preview_otsu, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(thresh_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- Region growing (semi-automatic seed-based segmentation) ---
        # NOTE: core/segmentation.SegmentationManager.region_growing()
        # (a real 6-connected BFS flood-fill from a seed voxel, bounded
        # by an intensity tolerance) already existed but was never
        # called from anywhere - a real "backend exists, not wired"
        # gap. Reuses the same real 3D picker as the Interaction tab
        # (controller.picker) to let the user click the seed point, and
        # the same real voxel<->world conversion already verified for
        # 3D pick -> 2D sync (controller.sync_mgr.world_to_voxel).
        box_rg = wx.StaticBox(self, wx.ID_ANY, _("Region Growing (seed-based)"))
        rg_sizer = wx.StaticBoxSizer(box_rg, wx.VERTICAL)

        rg_row = wx.BoxSizer(wx.HORIZONTAL)
        rg_row.Add(wx.StaticText(self, wx.ID_ANY, _("Tolerance:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        # min=0 (not 1): tolerance 0 is a valid, meaningful choice -
        # "grow only voxels with exactly the seed's value" - see
        # core/segmentation.py.SegmentationManager.region_growing()'s
        # validation (Round-2 audit, section C).
        self.spin_rg_tolerance = wx.SpinCtrl(self, wx.ID_ANY, "50", min=0, max=2000)
        rg_row.Add(self.spin_rg_tolerance, 1, wx.ALL, 5)
        rg_sizer.Add(rg_row, 0, wx.EXPAND, 5)

        self.btn_pick_seed = wx.ToggleButton(self, wx.ID_ANY, _("Pick Seed Point (3D)"))
        rg_sizer.Add(self.btn_pick_seed, 0, wx.ALL | wx.EXPAND, 5)

        self.rg_status = wx.StaticText(self, wx.ID_ANY, _(""))
        rg_sizer.Add(self.rg_status, 0, wx.ALL | wx.EXPAND, 5)

        # E2: disabled unless Preview Workflow is enabled AND a seed has
        # already been picked while in that mode (see _on_seed_picked()'s
        # preview branch) - see _on_enable_preview_toggle() and
        # _on_preview_region_growing()'s own guard.
        self.btn_preview_region_growing = wx.Button(self, wx.ID_ANY, _("Preview Region Growing"))
        self.btn_preview_region_growing.Enable(False)
        rg_sizer.Add(self.btn_preview_region_growing, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(rg_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- E2 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch ONLY - never present on
        # thesis-ct-roi-tools/ct3d-rc1): Preview -> Accept/Cancel
        # workflow. Off by default (ENABLE_PREVIEW_SEGMENTATION default
        # OFF) - with the checkbox unchecked, "Preview Otsu"/"Preview
        # Region Growing" above stay disabled and the classic
        # immediate-commit behavior (Create Mask from Threshold /
        # seed-pick auto-grows-and-creates-a-mask) is 100% unchanged.
        # See docs/CT3D_ADVANCED_E2_PREVIEW_REPORT.md and
        # docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md's "E2 Preview
        # Architecture" section for the full design.
        box_preview = wx.StaticBox(self, wx.ID_ANY, _("Preview Segmentation (E2, enhancement branch)"))
        preview_sizer = wx.StaticBoxSizer(box_preview, wx.VERTICAL)

        self.cb_enable_preview = wx.CheckBox(self, wx.ID_ANY, _("Enable Preview Workflow"))
        preview_sizer.Add(self.cb_enable_preview, 0, wx.ALL, 5)

        preview_status_row = wx.BoxSizer(wx.HORIZONTAL)
        preview_status_row.Add(wx.StaticText(self, wx.ID_ANY, _("Preview status:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.lbl_preview_status = wx.StaticText(self, wx.ID_ANY, _("Idle"))
        preview_status_row.Add(self.lbl_preview_status, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        preview_sizer.Add(preview_status_row, 0, wx.EXPAND, 3)

        preview_btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_preview_accept = wx.Button(self, wx.ID_ANY, _("Accept Preview"))
        self.btn_preview_accept.Enable(False)
        preview_btn_row.Add(self.btn_preview_accept, 1, wx.ALL, 2)
        self.btn_preview_cancel = wx.Button(self, wx.ID_ANY, _("Cancel Preview"))
        self.btn_preview_cancel.Enable(False)
        preview_btn_row.Add(self.btn_preview_cancel, 1, wx.ALL, 2)
        preview_sizer.Add(preview_btn_row, 0, wx.EXPAND, 3)

        sizer.Add(preview_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- ROI management (core/roi_manager.ROIManager) ---
        # NOTE: this is the "quản lý segmentation" piece - a named,
        # organized view over the masks this panel has created, backed
        # by real InVesalius operations (Change mask selected / Show
        # mask / Change mask name / Remove masks), not a disconnected
        # bookkeeping list.
        box_roi = wx.StaticBox(self, wx.ID_ANY, _("Segmentation Set (Advanced ROI Manager)"))
        roi_sizer = wx.StaticBoxSizer(box_roi, wx.VERTICAL)

        # E1 (Advanced ROI Manager): "Advanced ROI Manager"/"Segmentation
        # Set" is the honest name for this - the real backend is still
        # InVesalius's independent per-ROI masks (Project().mask_dict),
        # NOT a single shared multi-label voxel volume. See
        # docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md for why this
        # is not called "true multilabel" and never claims to be.
        active_row = wx.BoxSizer(wx.HORIZONTAL)
        active_row.Add(wx.StaticText(self, wx.ID_ANY, _("Active ROI:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_active_roi = wx.StaticText(self, wx.ID_ANY, _("(none)"))
        active_row.Add(self.lbl_active_roi, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        # Read-only colour indicator (mirrors the real Mask.colour this
        # ROI wraps - see core/roi_manager.py's ROI class docstring).
        # Not an editable colour picker - E1's feature list only asks
        # for an indicator, and inventing a new "change colour" control
        # beyond what was actually requested is exactly the kind of
        # unrequested scope this track's own architecture rules warn
        # against.
        self.roi_color_swatch = wx.Panel(self, wx.ID_ANY, size=(18, 18))
        self.roi_color_swatch.SetBackgroundColour(wx.Colour(200, 200, 200))
        active_row.Add(self.roi_color_swatch, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        roi_sizer.Add(active_row, 0, wx.EXPAND, 3)

        self.roi_list = wx.CheckListBox(self, wx.ID_ANY, size=(-1, 90))
        self.roi_list.Bind(wx.EVT_CHECKLISTBOX, self._on_roi_visibility_toggled)
        self.roi_list.Bind(wx.EVT_LISTBOX, self._on_roi_selected)
        roi_sizer.Add(self.roi_list, 1, wx.ALL | wx.EXPAND, 5)

        roi_btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_roi_rename = wx.Button(self, wx.ID_ANY, _("Rename"))
        roi_btn_row.Add(self.btn_roi_rename, 1, wx.ALL, 2)
        self.btn_roi_delete = wx.Button(self, wx.ID_ANY, _("Delete"))
        roi_btn_row.Add(self.btn_roi_delete, 1, wx.ALL, 2)
        roi_sizer.Add(roi_btn_row, 0, wx.EXPAND, 3)

        # E1: lock/solo/bulk-visibility - all real backend logic lives in
        # core/roi_manager.ROIManager (pure, unit-tested without wx/
        # pubsub); this panel only calls it and replays the resulting
        # visibility changes onto the real "Show mask" topic (see
        # _apply_visibility_changes() below).
        roi_btn_row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_roi_lock = wx.Button(self, wx.ID_ANY, _("Lock"))
        roi_btn_row2.Add(self.btn_roi_lock, 1, wx.ALL, 2)
        self.btn_roi_unlock = wx.Button(self, wx.ID_ANY, _("Unlock"))
        roi_btn_row2.Add(self.btn_roi_unlock, 1, wx.ALL, 2)
        self.btn_roi_solo = wx.ToggleButton(self, wx.ID_ANY, _("Solo"))
        roi_btn_row2.Add(self.btn_roi_solo, 1, wx.ALL, 2)
        roi_sizer.Add(roi_btn_row2, 0, wx.EXPAND, 3)

        roi_btn_row3 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_roi_show_all = wx.Button(self, wx.ID_ANY, _("Show All"))
        roi_btn_row3.Add(self.btn_roi_show_all, 1, wx.ALL, 2)
        self.btn_roi_hide_all = wx.Button(self, wx.ID_ANY, _("Hide All"))
        roi_btn_row3.Add(self.btn_roi_hide_all, 1, wx.ALL, 2)
        roi_sizer.Add(roi_btn_row3, 0, wx.EXPAND, 3)

        # NOTE: closes a real gap found by auditing the mask -> surface
        # chain: invesalius/data/surface.py does not subscribe to any
        # mask-edit topic ("Reload actual slice", "Create new mask",
        # etc.), so an already-created 3D surface does NOT update
        # automatically after brush/undo/region-growing edits. Auto-
        # rebuilding on every single edit would be the "incremental
        # remesh" research problem the project's own planning doc flags
        # as an advanced, optional contribution (and a real perf risk -
        # rebuilding a full-volume mesh per brush stroke can freeze the
        # UI) - a manual, on-demand rebuild button is the safe, correct
        # middle ground: it genuinely closes the loop (edit -> visible
        # in 3D) without that risk.
        self.btn_update_surface = wx.Button(self, wx.ID_ANY, _("Update 3D Surface from Selected ROI"))
        roi_sizer.Add(self.btn_update_surface, 0, wx.ALL | wx.EXPAND, 3)

        sizer.Add(roi_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- Brush tools ---
        # NOTE: this does NOT capture mouse events itself (that would
        # fight InVesalius's own 2D canvas interactor). Instead it
        # drives InVesalius's real, already-working brush editor through
        # the exact pubsub topics its own toolbar/task panel use (see
        # invesalius/gui/task_slice.py and invesalius/data/styles.py):
        # "Enable style"/"Disable style" (style=SLICE_STATE_EDITOR) to
        # toggle edit mode on the real 2D canvas, and "Set edition brush
        # size"/"Set brush format"/"Set edition operation" to configure
        # it. The actual mouse-drag painting is InVesalius's own,
        # unmodified - this panel is just a remote control for it.
        box_brush = wx.StaticBox(self, wx.ID_ANY, _("Brush Tools (real 2D editor)"))
        brush_sizer = wx.StaticBoxSizer(box_brush, wx.VERTICAL)

        op_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_brush_draw = wx.RadioButton(self, wx.ID_ANY, _("Draw"), style=wx.RB_GROUP)
        self.rb_brush_draw.SetValue(True)
        op_row.Add(self.rb_brush_draw, 0, wx.ALL, 3)

        self.rb_brush_erase = wx.RadioButton(self, wx.ID_ANY, _("Erase"))
        op_row.Add(self.rb_brush_erase, 0, wx.ALL, 3)
        brush_sizer.Add(op_row, 0, wx.EXPAND, 3)

        shape_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_brush_circle = wx.RadioButton(self, wx.ID_ANY, _("Circle"), style=wx.RB_GROUP)
        self.rb_brush_circle.SetValue(True)
        shape_row.Add(self.rb_brush_circle, 0, wx.ALL, 3)

        self.rb_brush_square = wx.RadioButton(self, wx.ID_ANY, _("Square"))
        shape_row.Add(self.rb_brush_square, 0, wx.ALL, 3)
        brush_sizer.Add(shape_row, 0, wx.EXPAND, 3)

        brush_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Brush size:")), 0, wx.ALL, 3)
        self.slider_brush_size = wx.Slider(
            self, wx.ID_ANY, 30, 1, 100, style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        brush_sizer.Add(self.slider_brush_size, 0, wx.ALL | wx.EXPAND, 3)

        self.btn_toggle_brush = wx.ToggleButton(self, wx.ID_ANY, _("Enable Brush Tool"))
        brush_sizer.Add(self.btn_toggle_brush, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(brush_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- Undo/Redo of the REAL current mask ---
        box_undo = wx.StaticBox(self, wx.ID_ANY, _("Undo / Redo (current mask)"))
        undo_box_sizer = wx.StaticBoxSizer(box_undo, wx.VERTICAL)

        self.btn_checkpoint = wx.Button(self, wx.ID_ANY, _("Save Checkpoint"))
        undo_box_sizer.Add(self.btn_checkpoint, 0, wx.ALL | wx.EXPAND, 5)

        undo_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_undo = wx.Button(self, wx.ID_ANY, _("Undo"))
        undo_row.Add(self.btn_undo, 1, wx.ALL, 5)

        self.btn_redo = wx.Button(self, wx.ID_ANY, _("Redo"))
        undo_row.Add(self.btn_redo, 1, wx.ALL, 5)

        undo_box_sizer.Add(undo_row, 0, wx.EXPAND, 5)

        sizer.Add(undo_box_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Status
        self.status_text = wx.StaticText(self, wx.ID_ANY, _("Status: Ready"))
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(sizer)

        self.cb_auto_thresh.Bind(wx.EVT_CHECKBOX, self._on_auto_thresh_toggle)
        self.btn_apply_thresh.Bind(wx.EVT_BUTTON, self._on_apply_threshold)
        self.btn_preview_otsu.Bind(wx.EVT_BUTTON, self._on_preview_otsu)
        self.btn_pick_seed.Bind(wx.EVT_TOGGLEBUTTON, self._on_toggle_pick_seed)
        self.btn_preview_region_growing.Bind(wx.EVT_BUTTON, self._on_preview_region_growing)
        self.cb_enable_preview.Bind(wx.EVT_CHECKBOX, self._on_enable_preview_toggle)
        self.btn_preview_accept.Bind(wx.EVT_BUTTON, self._on_preview_accept)
        self.btn_preview_cancel.Bind(wx.EVT_BUTTON, self._on_preview_cancel)
        self.btn_roi_rename.Bind(wx.EVT_BUTTON, self._on_roi_rename)
        self.btn_roi_delete.Bind(wx.EVT_BUTTON, self._on_roi_delete)
        self.btn_roi_lock.Bind(wx.EVT_BUTTON, self._on_roi_lock)
        self.btn_roi_unlock.Bind(wx.EVT_BUTTON, self._on_roi_unlock)
        self.btn_roi_solo.Bind(wx.EVT_TOGGLEBUTTON, self._on_roi_solo_toggled)
        self.btn_roi_show_all.Bind(wx.EVT_BUTTON, self._on_roi_show_all)
        self.btn_roi_hide_all.Bind(wx.EVT_BUTTON, self._on_roi_hide_all)
        self.btn_update_surface.Bind(wx.EVT_BUTTON, self._on_update_surface)
        self.btn_checkpoint.Bind(wx.EVT_BUTTON, self._on_checkpoint)
        self.btn_undo.Bind(wx.EVT_BUTTON, self._on_undo)
        self.btn_redo.Bind(wx.EVT_BUTTON, self._on_redo)

        self.btn_toggle_brush.Bind(wx.EVT_TOGGLEBUTTON, self._on_toggle_brush)
        self.rb_brush_draw.Bind(wx.EVT_RADIOBUTTON, self._on_brush_operation_changed)
        self.rb_brush_erase.Bind(wx.EVT_RADIOBUTTON, self._on_brush_operation_changed)
        self.rb_brush_circle.Bind(wx.EVT_RADIOBUTTON, self._on_brush_format_changed)
        self.rb_brush_square.Bind(wx.EVT_RADIOBUTTON, self._on_brush_format_changed)
        self.slider_brush_size.Bind(wx.EVT_SLIDER, self._on_brush_size_changed)

        # Auto-disable the real edit style when this panel goes away, so
        # closing the ROI Viewer window (or switching away mid-edit)
        # never leaves InVesalius's 2D canvas stuck in brush-edit mode
        # with no visible way to turn it back off.
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    def _brush_enabled(self):
        return self.btn_toggle_brush.GetValue()

    # ------------------------------------------------------------------
    # Threshold -> real mask
    # ------------------------------------------------------------------
    def _on_auto_thresh_toggle(self, event):
        if not self.cb_auto_thresh.GetValue():
            return
        try:
            from ..interface.project_interface import ProjectInterface

            volume = ProjectInterface().get_volume_data()
            if volume is None:
                self.status_text.SetLabel(_("Status: No project loaded"))
                return
            lo, hi = self.controller.seg_mgr.auto_threshold_otsu(volume)
            self.spin_min.SetValue(int(lo))
            self.spin_max.SetValue(int(hi))
            self.status_text.SetLabel(_("Status: Auto threshold computed"))
        except Exception as e:
            self.status_text.SetLabel(_("Status: Auto threshold failed"))
            print(f"ROI Viewer: auto threshold failed - {e}")

    def _commit_threshold_mask(self, lo, hi) -> Optional[str]:
        """The real "Create Mask from Threshold" commit, extracted so E2's
        Accept-Otsu-preview path (see _on_preview_accept()) can reuse the
        EXACT same real mask-creation call with the EXACT threshold the
        preview showed, instead of a second, divergence-prone
        implementation (instruction: "Accept Otsu -> call existing tested
        'Create Mask from Threshold' logic"). Returns the new mask's name
        on success, None on failure - callers decide how to report that.
        """
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const
            from ..interface.project_interface import ProjectInterface

            mask_count = len(ProjectInterface().get_mask_dict())
            colour = const.MASK_COLOUR[mask_count % len(const.MASK_COLOUR)]
            name = f"ROI Viewer {mask_count + 1}"

            # NOTE: this is the exact same topic/argument shape
            # InVesalius's own threshold UI uses to create a mask - see
            # invesalius/data/slice_.py's __add_mask_thresh(self,
            # mask_name, thresh, colour). Using it here means the new
            # mask is a real, first-class InVesalius mask (shows up in
            # the mask list, 2D views, and 3D volume), not a disconnected
            # copy living only in this plugin.
            # "Create new mask" is handled synchronously (see
            # invesalius/data/slice_.py's __add_mask_thresh) and, per
            # main.py's _on_mask_created subscriber, also triggers
            # ROIManager.rebuild_from_project_masks() + a ROI List
            # refresh before this sendMessage() call returns - see
            # core/roi_manager.py's module docstring for why the ROI
            # List no longer needs its own direct create_roi() call
            # here (it would just be a second, redundant source of
            # truth for data the real mask already owns).
            Publisher.sendMessage(
                "Create new mask", mask_name=name, thresh=(lo, hi), colour=colour
            )
            return name
        except ImportError as e:
            print(f"ROI Viewer: could not create mask - {e}")
            return None

    def _on_apply_threshold(self, event):
        lo = self.spin_min.GetValue()
        hi = self.spin_max.GetValue()

        if lo > hi:
            wx.MessageBox(
                _("Min threshold must be <= Max threshold."), _("Error"), wx.OK | wx.ICON_ERROR
            )
            return

        self.controller.seg_mgr.set_threshold(lo, hi)

        name = self._commit_threshold_mask(lo, hi)
        if name is not None:
            self.status_text.SetLabel(_(f"Status: Created mask '{name}'"))
        else:
            wx.MessageBox(_("Segmentation not available."), _("Error"), wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------
    # Region growing (semi-automatic, seed-based)
    # ------------------------------------------------------------------
    def _on_toggle_pick_seed(self, event):
        if not self.btn_pick_seed.GetValue():
            # User cancelled - unregister without growing anything.
            self.controller.picker.remove_callback(self._on_seed_picked)
            self.rg_status.SetLabel(_(""))
            return

        if not self.controller.ensure_picker_initialized():
            self.btn_pick_seed.SetValue(False)
            self.rg_status.SetLabel(_("No 3D view available yet"))
            return

        self.controller.picker.add_callback(self._on_seed_picked)
        self.controller.picker.enable()
        self.rg_status.SetLabel(_("Click a seed point in the 3D view..."))

    def _on_seed_picked(self, world_point):
        # One-shot: a seed pick always disarms the toggle, whether or
        # not growing succeeds. This also guarantees the button/status
        # never gets stuck in a "picking..." state if anything below
        # fails - see the try/except wrapping the whole body.
        wx.CallAfter(self.btn_pick_seed.SetValue, False)
        self.controller.picker.remove_callback(self._on_seed_picked)

        try:
            import math

            # Round-2 audit, section C: a VTK pick can in principle
            # hand back non-finite coordinates (e.g. a picker miss on
            # degenerate geometry) - reject before doing any conversion
            # or spinning up a worker thread for a nonsensical seed.
            if world_point is None or len(world_point) != 3 or not all(math.isfinite(c) for c in world_point):
                self.rg_status.SetLabel(_("Invalid pick position - try again"))
                return

            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            volume = pi.get_volume_data()
            if volume is None:
                wx.CallAfter(self.rg_status.SetLabel, _("No project loaded"))
                return

            # Same real world<->voxel conversion already verified for
            # 3D-pick -> 2D-slice sync (interaction_panel.py) - see
            # core/sync_2d3d.SyncManager2D3D.world_to_voxel()'s
            # docstring for the axis mapping this relies on.
            self.controller.sync_mgr.set_volume_info(pi.get_spacing(), pi.get_shape())
            seed = self.controller.sync_mgr.world_to_voxel(*world_point)
            tolerance = self.spin_rg_tolerance.GetValue()

            seed_error = self.controller.seg_mgr.validate_seed(seed, volume.shape)
            if seed_error is not None:
                self.rg_status.SetLabel(_(f"Region growing: {seed_error}"))
                return

            # E2 (enhancement/advanced-segmentation branch only): with
            # Preview Workflow enabled, a seed pick only RECORDS the seed
            # - it does NOT start growing. The (possibly slow) computation
            # is deferred to an explicit "Preview Region Growing" click,
            # so the user can still adjust Tolerance after picking before
            # spending the compute. Classic mode (checkbox unchecked) is
            # completely unchanged below this point - growing starts
            # immediately, exactly as before this milestone.
            if self.cb_enable_preview.GetValue():
                self._preview_seed_world = tuple(world_point)
                self._preview_seed_voxel = seed
                wx.CallAfter(self.btn_preview_region_growing.Enable, True)
                wx.CallAfter(
                    self.rg_status.SetLabel,
                    _(f"Seed picked at voxel {seed} - click 'Preview Region Growing'"),
                )
                return

            wx.CallAfter(self.rg_status.SetLabel, _(f"Growing from voxel {seed}..."))
            # scipy/numpy BFS over a full CT volume can take real time
            # (see the performance note on SegmentationManager.
            # region_growing() itself) - run off the UI thread so the
            # app doesn't freeze, then marshal the result back with
            # wx.CallAfter.
            #
            # Thread-safety audit (Round-2, section C): worker() below
            # touches only `volume` (a real numpy array, read-only
            # here) and SegmentationManager.region_growing() (pure
            # numpy/scipy, no wx/VTK calls, no shared mutable state) -
            # it never touches a wx widget, a VTK renderer, or shows a
            # dialog directly. The only cross-thread handoff is the
            # wx.CallAfter() call itself, which is the correct/required
            # way to marshal work back onto the main thread - see
            # _on_region_grown() below, which does the actual mask
            # creation, roi_mgr/UI updates and any confirmation dialog,
            # entirely on the main thread.
            import threading

            def worker():
                try:
                    result_mask = self.controller.seg_mgr.region_growing(volume, seed, tolerance)
                    wx.CallAfter(self._on_region_grown, result_mask, seed, tolerance)
                except ValueError as e:
                    # Invalid input (e.g. a negative tolerance somehow
                    # reaching here) - a clear, specific message rather
                    # than the generic "failed" below.
                    wx.CallAfter(self.rg_status.SetLabel, _(f"Region growing: {e}"))
                except Exception:
                    import traceback

                    wx.CallAfter(self.rg_status.SetLabel, _("Region growing failed"))
                    print("ROI Viewer: region growing failed -\n" + traceback.format_exc())

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.rg_status.SetLabel(_("Region growing failed"))
            print(f"ROI Viewer: region growing setup failed - {e}")

    def _commit_region_growing_result(self, result_mask, seed, tolerance) -> Optional[str]:
        """
        Creates a real InVesalius mask sized to match the volume, then
        overwrites its voxel data with the region-growing result - the
        same direct matrix-write technique already verified for
        Undo/Redo (mask.matrix[:] = ...), so this is real, first-class
        mask data, not a disconnected copy. Extracted from
        _on_region_grown() (E2, Advanced Segmentation Enhancement Track)
        so the Accept-region-growing-preview path (_on_preview_accept())
        can reuse this EXACT real commit instead of a second,
        divergence-prone implementation. Returns the new mask's name on
        success, None on failure (reason printed to console; callers
        decide how to surface that in the UI).
        """
        try:
            import numpy as np
            import invesalius.data.slice_ as sl
            import invesalius.constants as const
            from invesalius.pubsub import pub as Publisher
            from ..interface.project_interface import ProjectInterface

            mask_count = len(ProjectInterface().get_mask_dict())
            colour = const.MASK_COLOUR[mask_count % len(const.MASK_COLOUR)]
            name = f"Region Growing {mask_count + 1}"

            # Create an empty real mask of the right shape/threshold
            # bookkeeping via the standard path (this also triggers
            # ROIManager.rebuild_from_project_masks() via main.py's
            # "Create new mask" subscriber - see core/roi_manager.py's
            # module docstring), then overwrite its voxel data with the
            # actual region-growing result.
            Publisher.sendMessage(
                "Create new mask", mask_name=name, thresh=(1, 1), colour=colour
            )
            new_mask = sl.Slice().current_mask
            if new_mask is None or new_mask.matrix is None:
                print("ROI Viewer: region growing commit failed - mask creation returned no current mask")
                return None

            # InVesalius mask matrices carry a 1-voxel padding border
            # (see interface/project_interface.py notes elsewhere on
            # mask padding); result_mask matches the unpadded volume
            # shape, so write into the interior.
            target = new_mask.matrix[1:, 1:, 1:]
            if target.shape != result_mask.shape:
                # Shapes should match ProjectInterface().get_shape(), but
                # guard defensively rather than raising into a
                # background-thread-originated callback.
                print(f"ROI Viewer: region growing commit failed - shape mismatch {target.shape} vs {result_mask.shape}")
                return None

            target[:] = np.where(result_mask > 0, 255, target)
            # Round-2 audit, section B: a mask created via the
            # thresh=(1,1) bookkeeping placeholder above starts with
            # every slice's "already thresholded" sentinel
            # (Slice.do_threshold_to_all_slices()'s
            # mask.matrix[n, 0, 0] check) at 0 - i.e. "never
            # visited". invesalius/data/slice_.py's
            # do_threshold_to_all_slices() runs automatically the
            # FIRST time ANY surface is built for this mask
            # (CreateSurfaceFromIndex calls it before "Create
            # surface"), and for every slice whose sentinel is
            # still 0 it OVERWRITES that slice's voxels by
            # re-deriving them from thresh=(1,1) against the real
            # image - discarding this hand-written region-growing
            # result completely and silently, with no exception.
            # Verified for real (test_surface_update_small_roi.py's
            # own mask-write, which hit exactly this): the
            # resulting surface reflected wherever the real CT
            # image happened to equal exactly 1, not the actual
            # grown/edited region. Marking every slice's sentinel
            # as already-visited here - the exact same real
            # mechanism InVesalius's own do_threshold_to_all_slices
            # uses to protect a slice it already computed - tells
            # it to leave this hand-written data alone.
            new_mask.matrix[1:, 0, 0] = 1
            new_mask.matrix.flush()
            # Phase 08 fix: this mask's voxel data is 100% hand-
            # written (region growing result), not derived from
            # mask.threshold_range - _on_update_surface() needs
            # was_edited=True to know it must use a mask-driven
            # algorithm ("Binary") instead of "Default" (which
            # would silently ignore this data entirely and
            # re-contour the raw image instead - see that
            # method's own NOTE for the full root-cause).
            new_mask.was_edited = True
            return name
        except Exception as e:
            print(f"ROI Viewer: committing region growing result failed - {e}")
            return None

    def _on_region_grown(self, result_mask, seed, tolerance):
        """
        Runs on the main thread (via wx.CallAfter). Classic (non-preview)
        commit path - unchanged behavior from before E2, now delegating
        the actual mask creation/voxel-write to
        _commit_region_growing_result() (shared with E2's Accept path).

        Round-2 audit, section C: before committing anything, computes
        how much of the volume the result actually covers
        (SegmentationManager.region_stats()) and, if it exceeds
        seg_mgr.max_region_fraction, asks for confirmation instead of
        silently creating a huge, not-really-"region of interest" mask
        - the exact failure mode that made the D9 surface-update test
        in round 1 use an unrealistic 16.2M-voxel (~58% of volume) mask
        in the first place.
        """
        try:
            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            stats = self.controller.seg_mgr.region_stats(result_mask, pi.get_spacing())
            voxel_count = stats["voxel_count"]

            if voxel_count == 0:
                self.rg_status.SetLabel(
                    _(f"No region found from seed {seed} (tolerance {tolerance}) - try a higher tolerance")
                )
                return

            seed_value = pi.get_volume_data()[seed] if pi.get_volume_data() is not None else "?"
            info = _(
                f"seed value {seed_value}, tolerance {tolerance}, "
                f"{voxel_count} voxels ({stats['fraction'] * 100:.1f}% of volume)"
            )
            if "volume_mm3" in stats:
                info += _(f", {stats['volume_mm3']:.1f} mm3")

            if stats["exceeds_limit"]:
                limit_pct = self.controller.seg_mgr.max_region_fraction * 100
                proceed = wx.MessageBox(
                    _(
                        f"This region covers {stats['fraction'] * 100:.1f}% of the volume "
                        f"({voxel_count} voxels) - larger than the {limit_pct:.0f}% safety "
                        f"threshold and likely not a meaningful region of interest.\n\n"
                        f"{info}\n\nCreate it anyway?"
                    ),
                    _("Region growing: large region"),
                    wx.YES_NO | wx.ICON_WARNING,
                )
                if proceed != wx.YES:
                    self.rg_status.SetLabel(_(f"Region growing cancelled ({info})"))
                    return

            name = self._commit_region_growing_result(result_mask, seed, tolerance)
            if name is None:
                self.rg_status.SetLabel(_("Region growing: failed to create/apply mask"))
                return

            self._refresh_after_edit()
            self.rg_status.SetLabel(_(f"Status: grown '{name}' - {info}"))
        except Exception as e:
            self.rg_status.SetLabel(_("Region growing: failed to apply result"))
            print(f"ROI Viewer: applying region growing result failed - {e}")

    # ------------------------------------------------------------------
    # E2 (Advanced Segmentation Enhancement Track, enhancement/advanced-
    # segmentation branch ONLY): Preview -> Accept/Cancel workflow.
    # ------------------------------------------------------------------
    def _preview_ready(self) -> bool:
        return self.preview_mgr.state == segmentation_preview.PreviewState.PREVIEW_READY

    def _update_preview_buttons(self):
        self.btn_preview_accept.Enable(self._preview_ready())
        self.btn_preview_cancel.Enable(self.preview_mgr.state != segmentation_preview.PreviewState.IDLE)

    def _show_preview_overlay(self, array):
        """
        Render `array` (real 0/255 data, real unpadded volume shape - see
        core/segmentation_preview.py's module docstring) as a translucent
        overlay on the 2D slice views, via InVesalius's own real
        Slice().aux_matrices/to_show_aux mechanism - the SAME real,
        already-proven native path its own Watershed tool uses for its
        live preview (see invesalius/data/styles.py's
        WatershedInteractorStyle.SetUp()/CleanUp(), the reference pattern
        this mirrors). This NEVER touches Project().mask_dict - see
        docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md's "E2 Preview
        Architecture" section for the full source-audit trail behind
        this choice.

        NOTE (real, PRE-EXISTING native constraint, not introduced by
        this plugin): confirmed by reading invesalius/data/slice_.py's
        slice-rendering method directly - the generic to_show_aux blend
        only runs when self.current_mask is not None (the exact same
        real constraint Watershed's own overlay has). Callers
        (_on_preview_otsu()/_on_preview_region_growing()) already
        guarantee a current mask exists before a computation is even
        started.
        """
        try:
            import invesalius.data.slice_ as sl
            from invesalius.pubsub import pub as Publisher

            s = sl.Slice()
            s.aux_matrices[PREVIEW_AUX_KEY] = array
            # Orange, 50% alpha - deliberately distinct from a real
            # mask's own (usually red-family) blend colour, so a preview
            # can never be visually mistaken for an already-committed
            # mask (instruction: "Use a clearly distinct preview
            # appearance").
            s.aux_matrices_colours[PREVIEW_AUX_KEY] = {
                0: (0.0, 0.0, 0.0, 0.0),
                255: (1.0, 0.65, 0.0, 0.5),
            }
            s.to_show_aux = PREVIEW_AUX_KEY
            Publisher.sendMessage("Reload actual slice")
        except Exception as e:
            print(f"ROI Viewer: could not show preview overlay - {e}")

    def _clear_preview_overlay(self):
        """
        Undo _show_preview_overlay() and release the temp-file-backed
        array - mirrors invesalius/data/styles.py's Watershed
        _remove_mask()/CleanUp() cleanup pattern exactly. Safe to call
        when no overlay is currently shown (Cancel with nothing computed
        yet, repeated calls from multiple lifecycle hooks, etc.) - never
        raises.
        """
        import os

        try:
            import invesalius.data.slice_ as sl
            from invesalius.pubsub import pub as Publisher

            s = sl.Slice()
            if s.to_show_aux == PREVIEW_AUX_KEY:
                s.to_show_aux = ""
            s.aux_matrices.pop(PREVIEW_AUX_KEY, None)
            s.aux_matrices_colours.pop(PREVIEW_AUX_KEY, None)
            Publisher.sendMessage("Reload actual slice")
        except Exception as e:
            print(f"ROI Viewer: preview overlay cleanup failed (likely no project loaded) - {e}")
        finally:
            if self._preview_temp_file:
                try:
                    os.remove(self._preview_temp_file)
                except OSError:
                    pass
                self._preview_temp_file = None

    def cancel_preview(self):
        """Public lifecycle hook - called from gui/roi_panel.py's
        on_project_close()/on_project_load() and from this panel's own
        _on_destroy(), so a preview never survives a project swap or the
        plugin closing (instruction: preview must be cleared on project
        close, project load/reload, plugin close, plugin destroy)."""
        self._clear_preview_overlay()
        self.preview_mgr.cancel()
        self._preview_seed_world = None
        self._preview_seed_voxel = None
        # Widget updates are best-effort and wrapped separately from the
        # real-data cleanup above: during whole-app/plugin-window
        # teardown these wx widgets can already be mid-destruction (same
        # real crash class already guarded against for the brush toggle
        # in _on_destroy() below - "wrapped C/C++ object ... has been
        # deleted"). The data-level cleanup above must still always run.
        try:
            if hasattr(self, "btn_preview_region_growing"):
                self.btn_preview_region_growing.Enable(False)
                self.lbl_preview_status.SetLabel(_("Idle"))
                self._update_preview_buttons()
        except RuntimeError as e:
            print(f"ROI Viewer: preview widget cleanup skipped (likely app shutdown) - {e}")

    def _on_enable_preview_toggle(self, event):
        enabled = self.cb_enable_preview.GetValue()
        self.btn_preview_otsu.Enable(enabled)
        # Preview Region Growing only enables once BOTH preview mode is
        # on AND a seed has already been recorded - see
        # _on_seed_picked()'s preview branch above.
        self.btn_preview_region_growing.Enable(enabled and self._preview_seed_voxel is not None)
        if not enabled:
            # Turning preview mode OFF while a preview is active/pending
            # must not leave a dangling overlay or a stuck state - same
            # "explicit override cancels in-progress convenience state"
            # reasoning as E1's show_all()/hide_all() cancelling solo.
            self.cancel_preview()

    def _on_preview_otsu(self, event):
        try:
            import os
            import invesalius.data.slice_ as sl
            from ..interface.project_interface import ProjectInterface

            # Real, pre-existing native constraint - see
            # _show_preview_overlay()'s docstring. Same guard pattern
            # (and same user-facing wording style) as _on_toggle_brush()'s
            # existing "no mask selected" check.
            if sl.Slice().current_mask is None:
                wx.MessageBox(
                    _("Create or select a mask first (see Threshold above) so the preview can be shown."),
                    _("No mask selected"), wx.OK | wx.ICON_WARNING,
                )
                return

            pi = ProjectInterface()
            volume = pi.get_volume_data()
            if volume is None:
                self.lbl_preview_status.SetLabel(_("No project loaded"))
                return

            lo, hi = self.controller.seg_mgr.auto_threshold_otsu(volume)
            self.controller.seg_mgr.set_threshold(lo, hi)
            # Same real inclusive-both-ends comparison
            # SetMaskThreshold()/do_threshold_to_all_slices() use for the
            # actual committed mask (instruction: "derive candidate mask
            # using the SAME threshold semantics that final creation
            # would use") - see _commit_threshold_mask()'s NOTE.
            candidate01 = self.controller.seg_mgr.apply_threshold(volume)

            gen = self.preview_mgr.new_generation()
            temp_file, array = sl.Slice().create_temp_mask()
            array[:] = candidate01 * 255

            ok = self.preview_mgr.set_otsu_preview(gen, array, threshold=(lo, hi), name="Otsu Preview")
            if not ok:
                # Superseded before this synchronous computation even
                # finished (shouldn't happen for a same-thread, non-async
                # path, but never assume) - release rather than leak.
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                return

            self._preview_temp_file = temp_file
            self._show_preview_overlay(array)
            voxel_count = int(candidate01.sum())
            self.lbl_preview_status.SetLabel(_(f"Ready: Otsu threshold ({lo}, {hi}), {voxel_count} voxels"))
            self._update_preview_buttons()
        except Exception as e:
            self.lbl_preview_status.SetLabel(_("Otsu preview failed"))
            print(f"ROI Viewer: Otsu preview failed - {e}")

    def _on_preview_region_growing(self, event):
        if self._preview_seed_voxel is None:
            wx.MessageBox(_("Pick a seed point first."), _("No seed"), wx.OK | wx.ICON_WARNING)
            return
        try:
            import invesalius.data.slice_ as sl
            from ..interface.project_interface import ProjectInterface

            if sl.Slice().current_mask is None:
                wx.MessageBox(
                    _("Create or select a mask first (see Threshold above) so the preview can be shown."),
                    _("No mask selected"), wx.OK | wx.ICON_WARNING,
                )
                return

            pi = ProjectInterface()
            volume = pi.get_volume_data()
            if volume is None:
                self.lbl_preview_status.SetLabel(_("No project loaded"))
                return

            seed = self._preview_seed_voxel
            seed_world = self._preview_seed_world
            tolerance = self.spin_rg_tolerance.GetValue()
            gen = self.preview_mgr.new_generation()
            self.lbl_preview_status.SetLabel(_(f"Computing (voxel {seed}, tolerance {tolerance})..."))
            self.btn_preview_region_growing.Enable(False)

            # Same real background-thread + wx.CallAfter pattern as the
            # classic path in _on_seed_picked() above - see that
            # method's own thread-safety note (applies identically here:
            # worker() only touches `volume` read-only and the pure
            # SegmentationManager.region_growing(), never a wx/VTK
            # object directly).
            import threading

            def worker():
                try:
                    result_mask = self.controller.seg_mgr.region_growing(volume, seed, tolerance)
                    wx.CallAfter(
                        self._on_region_grown_preview, result_mask, seed_world, seed, tolerance, gen
                    )
                except Exception:
                    import traceback

                    wx.CallAfter(self.lbl_preview_status.SetLabel, _("Region growing preview failed"))
                    wx.CallAfter(self.btn_preview_region_growing.Enable, True)
                    print("ROI Viewer: region growing preview failed -\n" + traceback.format_exc())

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.lbl_preview_status.SetLabel(_("Region growing preview failed"))
            print(f"ROI Viewer: region growing preview setup failed - {e}")

    def _on_region_grown_preview(self, result_mask, seed_world, seed_voxel, tolerance, generation_id):
        """Runs on the main thread (via wx.CallAfter) - the preview-mode
        counterpart of _on_region_grown(). Never creates a real mask;
        only populates preview_mgr + the 2D overlay."""
        self.btn_preview_region_growing.Enable(True)
        if self.preview_mgr.is_stale(generation_id):
            # A newer preview (or a Cancel, or disabling Preview
            # Workflow) already superseded this request - discard
            # silently. This is the real async-race guard (instruction
            # section 6/21's generation_id requirement;
            # core/segmentation_preview.py's class docstring has the
            # full "request 1 finishes late" scenario this covers).
            print("ROI Viewer: discarded stale region growing preview result")
            return
        try:
            import os
            import numpy as np
            import invesalius.data.slice_ as sl
            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            stats = self.controller.seg_mgr.region_stats(result_mask, pi.get_spacing())
            voxel_count = stats["voxel_count"]

            if voxel_count == 0:
                self.preview_mgr.cancel()
                self.lbl_preview_status.SetLabel(
                    _(f"No region found from seed {seed_voxel} (tolerance {tolerance}) - try a higher tolerance")
                )
                self._update_preview_buttons()
                return

            temp_file, array = sl.Slice().create_temp_mask()
            array[:] = np.where(result_mask > 0, 255, 0)

            ok = self.preview_mgr.set_region_growing_preview(
                generation_id, array, seed_world, seed_voxel, tolerance, stats, name="Region Growing Preview"
            )
            if not ok:
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
                return
            self._preview_temp_file = temp_file

            info = f"{voxel_count} voxels ({stats['fraction'] * 100:.1f}% of volume)"
            if "volume_mm3" in stats:
                info += f", {stats['volume_mm3']:.1f} mm3"
            if stats["exceeds_limit"]:
                limit_pct = self.controller.seg_mgr.max_region_fraction * 100
                # Informational only, non-blocking (instruction section
                # 12: "show warning/statistics BEFORE Accept... the user
                # may still inspect the candidate preview") - the actual
                # blocking confirmation happens in _on_preview_accept()
                # at commit time, same as the classic path.
                info += f" - WARNING: exceeds {limit_pct:.0f}% safety threshold, confirmation required on Accept"
            self.lbl_preview_status.SetLabel(_(f"Ready: {info}"))
            self._show_preview_overlay(array)
            self._update_preview_buttons()
        except Exception as e:
            self.lbl_preview_status.SetLabel(_("Region growing preview failed"))
            print(f"ROI Viewer: applying region growing preview result failed - {e}")

    def _on_preview_accept(self, event):
        if not self.preview_mgr.begin_accept():
            return  # not PREVIEW_READY (nothing to accept, or already accepting) - no-op
        self.btn_preview_accept.Enable(False)
        self.btn_preview_cancel.Enable(False)
        try:
            kind = self.preview_mgr.preview_kind
            name = None
            if kind == "otsu":
                lo, hi = self.preview_mgr.source_threshold
                # Reuses the EXACT same real commit as the classic
                # "Create Mask from Threshold" button - see
                # _commit_threshold_mask()'s docstring.
                name = self._commit_threshold_mask(lo, hi)
            elif kind == "region_growing":
                stats = self.preview_mgr.stats or {}
                if stats.get("exceeds_limit"):
                    limit_pct = self.controller.seg_mgr.max_region_fraction * 100
                    proceed = wx.MessageBox(
                        _(
                            f"This region covers {stats.get('fraction', 0) * 100:.1f}% of the volume "
                            f"- larger than the {limit_pct:.0f}% safety threshold and likely not a "
                            f"meaningful region of interest.\n\nCreate it anyway?"
                        ),
                        _("Region growing: large region"), wx.YES_NO | wx.ICON_WARNING,
                    )
                    if proceed != wx.YES:
                        self.preview_mgr.revert_accept()
                        self.lbl_preview_status.SetLabel(_("Accept cancelled (oversized region) - preview still active"))
                        self._update_preview_buttons()
                        return
                # preview_array holds 0/255 values (see
                # _on_region_grown_preview()) - _commit_region_growing_
                # result() does `np.where(result_mask > 0, ...)`, so a
                # 0/255 array works identically to a 0/1 one.
                name = self._commit_region_growing_result(
                    self.preview_mgr.preview_array, self.preview_mgr.seed_voxel, self.preview_mgr.tolerance
                )

            if name is None:
                self.preview_mgr.revert_accept()
                wx.MessageBox(_("Failed to create the final mask."), _("Error"), wx.OK | wx.ICON_ERROR)
                self._update_preview_buttons()
                return

            self._clear_preview_overlay()
            self.preview_mgr.finish_accept()
            self._preview_seed_world = None
            self._preview_seed_voxel = None
            self.btn_preview_region_growing.Enable(False)
            self.controller.on_roi_source_changed()
            self._refresh_after_edit()
            self.lbl_preview_status.SetLabel(_(f"Idle (accepted '{name}')"))
            self._update_preview_buttons()
        except Exception as e:
            print(f"ROI Viewer: preview accept failed - {e}")
            self.preview_mgr.revert_accept()
            self.lbl_preview_status.SetLabel(_("Accept failed - preview still active"))
            self._update_preview_buttons()

    def _on_preview_cancel(self, event):
        self.cancel_preview()

    # ------------------------------------------------------------------
    # Undo / Redo of the real current mask
    # ------------------------------------------------------------------
    def _current_mask(self):
        try:
            import invesalius.data.slice_ as sl

            return sl.Slice().current_mask
        except Exception:
            return None

    def _on_checkpoint(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("Status: No mask selected"))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None:
            editor = self.controller.mask_mgr.create_editor(mask.index, mask.matrix.shape)
        editor.mask = mask.matrix
        editor.save_state()
        self.status_text.SetLabel(_("Status: Checkpoint saved"))

    def _roi_locked_for_mask(self, mask_index) -> bool:
        """Thin wx-layer wrapper - the actual decision logic lives in
        core/roi_manager.ROIManager.is_locked_for_mask_index() so it's
        unit-testable without wx (see that method's docstring)."""
        return self.controller.roi_mgr.is_locked_for_mask_index(mask_index)

    def _on_undo(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("Status: No mask selected"))
            return
        if self._roi_locked_for_mask(mask.index):
            self.status_text.SetLabel(_("Status: ROI is locked - unlock to undo"))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None or not editor.undo_manager.can_undo():
            self.status_text.SetLabel(_("Status: Nothing to undo"))
            return
        previous = editor.undo_manager.undo(mask.matrix)
        if previous is not None:
            mask.matrix[:] = previous
            self._refresh_after_edit()
            self.status_text.SetLabel(_("Status: Undone"))

    def _on_redo(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("Status: No mask selected"))
            return
        if self._roi_locked_for_mask(mask.index):
            self.status_text.SetLabel(_("Status: ROI is locked - unlock to redo"))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None or not editor.undo_manager.can_redo():
            self.status_text.SetLabel(_("Status: Nothing to redo"))
            return
        nxt = editor.undo_manager.redo(mask.matrix)
        if nxt is not None:
            mask.matrix[:] = nxt
            self._refresh_after_edit()
            self.status_text.SetLabel(_("Status: Redone"))

    def _refresh_after_edit(self):
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Reload actual slice")
            Publisher.sendMessage("Render volume viewer")
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Real brush editor (remote-controls InVesalius's own 2D edit style)
    # ------------------------------------------------------------------
    def _on_toggle_brush(self, event):
        if self.btn_toggle_brush.GetValue():
            mask = self._current_mask()
            if mask is None:
                self.btn_toggle_brush.SetValue(False)
                wx.MessageBox(
                    _("Create or select a mask first (see Threshold above)."),
                    _("No mask selected"), wx.OK | wx.ICON_WARNING,
                )
                return
            if self._roi_locked_for_mask(mask.index):
                self.btn_toggle_brush.SetValue(False)
                wx.MessageBox(
                    _("This ROI is locked. Unlock it before editing with the brush."),
                    _("ROI locked"), wx.OK | wx.ICON_WARNING,
                )
                return
            try:
                from invesalius.pubsub import pub as Publisher
                import invesalius.constants as const

                Publisher.sendMessage("Enable style", style=const.SLICE_STATE_EDITOR)
                self._push_brush_config()
                self.btn_toggle_brush.SetLabel(_("Disable Brush Tool"))
                self.status_text.SetLabel(
                    _("Status: Brush active - paint on the 2D slice views")
                )
            except ImportError as e:
                self.btn_toggle_brush.SetValue(False)
                print(f"ROI Viewer: could not enable brush - {e}")
        else:
            self._disable_brush()

    def _disable_brush(self):
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const

            Publisher.sendMessage("Disable style", style=const.SLICE_STATE_EDITOR)
        except ImportError:
            pass
        self.btn_toggle_brush.SetLabel(_("Enable Brush Tool"))
        self.status_text.SetLabel(_("Status: Ready"))

    def _push_brush_config(self):
        """Send the panel's current operation/shape/size to the real editor style."""
        if not self._brush_enabled():
            return
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const

            operation = const.BRUSH_ERASE if self.rb_brush_erase.GetValue() else const.BRUSH_DRAW
            cursor_format = const.BRUSH_SQUARE if self.rb_brush_square.GetValue() else const.BRUSH_CIRCLE

            Publisher.sendMessage("Set edition operation", operation=operation)
            Publisher.sendMessage("Set brush format", cursor_format=cursor_format)
            Publisher.sendMessage("Set edition brush size", size=self.slider_brush_size.GetValue())
        except ImportError as e:
            print(f"ROI Viewer: could not update brush config - {e}")

    def _on_brush_operation_changed(self, event):
        self._push_brush_config()

    def _on_brush_format_changed(self, event):
        self._push_brush_config()

    def _on_brush_size_changed(self, event):
        self._push_brush_config()

    def _on_destroy(self, event):
        event.Skip()
        if event.GetEventObject() is not self:
            return
        # Same leak class fixed for the 3D-pick observer in
        # roi_panel.ROIViewerFrame._on_close(): don't leave an armed
        # seed-pick callback registered on the shared picker pointing
        # back into this (about to be destroyed) panel.
        self.controller.picker.remove_callback(self._on_seed_picked)
        # E2: always clear any active/pending preview on destroy,
        # regardless of brush state - same "never leave native/plugin
        # state stuck across a close" reasoning as the brush cleanup
        # immediately below.
        self.cancel_preview()
        if not self._brush_enabled():
            return
        # NOTE: deliberately not calling self._disable_brush() here - it
        # also touches this panel's own child widgets (SetLabel on
        # btn_toggle_brush/status_text), which can themselves already be
        # mid-destruction at this point during whole-app shutdown.
        # Just best-effort the one thing that actually matters (not
        # leaving InVesalius's 2D canvas stuck in edit mode), and never
        # let a teardown-time failure here crash the app - see the
        # matching note in measurement_panel.py's _on_destroy, which hit
        # exactly this class of bug for real (crash_report_
        # 20260907_153620.txt: "wrapped C/C++ object ... has been
        # deleted" from InVesalius's own interactor cleanup).
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const

            Publisher.sendMessage("Disable style", style=const.SLICE_STATE_EDITOR)
        except Exception as e:
            print(f"ROI Viewer: brush cleanup on destroy failed (likely app shutdown) - {e}")

    # ------------------------------------------------------------------
    # ROI list (core/roi_manager.ROIManager) <-> real InVesalius masks
    # ------------------------------------------------------------------
    def _refresh_roi_list(self):
        """Rebuild the ROI list widget from roi_mgr, preserving check state (visibility).

        E1: lock/solo markers are shown as plain-text prefixes rather
        than owner-drawn icons - wx.CheckListBox has no built-in support
        for per-item colour/icon columns, and adding a custom-drawn
        ListCtrl just for this is more UI-rendering risk than this
        milestone's scope justifies (see
        docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md)."""
        self._roi_list_ids = list(self.controller.roi_mgr.rois.keys())
        solo_id = self.controller.roi_mgr.solo_roi_id
        labels = []
        for rid in self._roi_list_ids:
            roi = self.controller.roi_mgr.rois[rid]
            prefix = ""
            if roi.locked:
                prefix += "[LOCKED] "
            if solo_id == rid:
                prefix += "[SOLO] "
            labels.append(f"{prefix}{roi.name} (mask #{roi.mask_index})")
        self.roi_list.Set(labels)
        for i, rid in enumerate(self._roi_list_ids):
            self.roi_list.Check(i, self.controller.roi_mgr.rois[rid].visible)
        self.btn_roi_solo.SetValue(solo_id is not None)
        self._refresh_active_roi_indicator()

    def _selected_roi_id(self):
        sel = self.roi_list.GetSelection()
        if sel == wx.NOT_FOUND or not hasattr(self, "_roi_list_ids") or sel >= len(self._roi_list_ids):
            return None
        return self._roi_list_ids[sel]

    def _refresh_active_roi_indicator(self):
        """E1: keep the "Active ROI:" label and colour swatch in sync
        with roi_mgr.current_roi_id - called after selection changes AND
        after any list rebuild (so it stays correct even when the active
        ROI's own name/colour changed, or it was removed, without a
        selection event firing)."""
        roi = self.controller.roi_mgr.get_current_roi()
        if roi is None:
            self.lbl_active_roi.SetLabel(_("(none)"))
            self.roi_color_swatch.SetBackgroundColour(wx.Colour(200, 200, 200))
        else:
            self.lbl_active_roi.SetLabel(roi.name)
            r, g, b = (int(c) for c in roi.color[:3])
            self.roi_color_swatch.SetBackgroundColour(wx.Colour(r, g, b))
        self.roi_color_swatch.Refresh()

    def _apply_visibility_changes(self, changes):
        """Replay a {roi_id: new_visible} dict (as returned by
        ROIManager.enter_solo()/exit_solo()/show_all()/hide_all()) onto
        the real InVesalius "Show mask" topic, by real mask index - the
        cache (roi.visible) was already updated by the roi_mgr call that
        produced `changes`; this only pushes those changes to the real
        source of truth (Mask.is_shown) that Save/Open actually
        persists."""
        if not changes:
            return
        try:
            from invesalius.pubsub import pub as Publisher

            for rid, visible in changes.items():
                roi = self.controller.roi_mgr.get_roi(rid)
                if roi is not None:
                    Publisher.sendMessage("Show mask", index=roi.mask_index, value=visible)
        except ImportError:
            pass

    def _on_roi_selected(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            return
        roi = self.controller.roi_mgr.get_roi(rid)
        self.controller.roi_mgr.set_current_roi(rid)
        self._refresh_active_roi_indicator()
        try:
            from invesalius.pubsub import pub as Publisher

            # Real InVesalius: make this mask the active one (2D/3D
            # edits, threshold display, etc. all act on the "current"
            # mask) - see invesalius/data/slice_.py's
            # __select_current_mask, subscribed to "Change mask selected".
            Publisher.sendMessage("Change mask selected", index=roi.mask_index)
            self.status_text.SetLabel(_(f"Status: Selected '{roi.name}'"))
        except ImportError:
            pass

    def _on_roi_visibility_toggled(self, event):
        index = event.GetInt()
        if index < 0 or index >= len(self._roi_list_ids):
            return
        rid = self._roi_list_ids[index]
        roi = self.controller.roi_mgr.get_roi(rid)
        roi.visible = self.roi_list.IsChecked(index)
        # E1: a manual visibility click is an explicit user override -
        # if Solo was active, silently leaving roi_mgr.solo_roi_id set
        # while the checkboxes no longer reflect a real "only one ROI
        # visible" state would desync the cache from what's on screen.
        # Same reasoning as show_all()/hide_all() also cancelling solo.
        if self.controller.roi_mgr.solo_roi_id is not None:
            self.controller.roi_mgr.cancel_solo()
            self.btn_roi_solo.SetValue(False)
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Show mask", index=roi.mask_index, value=roi.visible)
        except ImportError:
            pass

    def _on_roi_rename(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
            return
        roi = self.controller.roi_mgr.get_roi(rid)
        dlg = wx.TextEntryDialog(self, _("New name:"), _("Rename ROI"), roi.name)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetValue().strip()
            if new_name:
                roi.name = new_name
                try:
                    from invesalius.pubsub import pub as Publisher

                    # Keeps the real InVesalius mask list (Masks tab) in
                    # sync with the name shown here - see invesalius/
                    # data/slice_.py's __set_mask_name, subscribed to
                    # "Change mask name".
                    Publisher.sendMessage("Change mask name", index=roi.mask_index, name=new_name)
                except ImportError:
                    pass
                self._refresh_roi_list()
        dlg.Destroy()

    def _on_roi_delete(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
            return
        roi = self.controller.roi_mgr.get_roi(rid)
        if roi.locked:
            wx.MessageBox(
                _(f"ROI '{roi.name}' is locked. Unlock it before deleting."),
                _("ROI locked"), wx.OK | wx.ICON_WARNING,
            )
            return
        confirm = wx.MessageBox(
            _(f"Delete ROI '{roi.name}' and its mask? This cannot be undone."),
            _("Confirm delete"), wx.YES_NO | wx.ICON_WARNING,
        )
        if confirm != wx.YES:
            return
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Remove masks", mask_indexes=[roi.mask_index])
        except ImportError:
            pass
        self.controller.roi_mgr.delete_roi(rid)
        self._refresh_roi_list()
        self.status_text.SetLabel(_(f"Status: Deleted '{roi.name}'"))

    # ------------------------------------------------------------------
    # E1 (Advanced ROI Manager): lock / solo / show-all / hide-all
    # ------------------------------------------------------------------
    def _on_roi_lock(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
            return
        self.controller.roi_mgr.set_locked(rid, True)
        self._refresh_roi_list()
        roi = self.controller.roi_mgr.get_roi(rid)
        self.status_text.SetLabel(_(f"Status: Locked '{roi.name}'"))

    def _on_roi_unlock(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
            return
        self.controller.roi_mgr.set_locked(rid, False)
        self._refresh_roi_list()
        roi = self.controller.roi_mgr.get_roi(rid)
        self.status_text.SetLabel(_(f"Status: Unlocked '{roi.name}'"))

    def _on_roi_solo_toggled(self, event):
        if self.btn_roi_solo.GetValue():
            rid = self._selected_roi_id()
            if rid is None:
                self.btn_roi_solo.SetValue(False)
                wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
                return
            changes = self.controller.roi_mgr.enter_solo(rid)
            self._apply_visibility_changes(changes)
            roi = self.controller.roi_mgr.get_roi(rid)
            self.status_text.SetLabel(_(f"Status: Solo '{roi.name}'"))
        else:
            changes = self.controller.roi_mgr.exit_solo()
            self._apply_visibility_changes(changes)
            self.status_text.SetLabel(_("Status: Solo off"))
        self._refresh_roi_list()

    def _on_roi_show_all(self, event):
        changes = self.controller.roi_mgr.show_all()
        self._apply_visibility_changes(changes)
        self._refresh_roi_list()
        self.status_text.SetLabel(_("Status: All ROIs shown"))

    def _on_roi_hide_all(self, event):
        changes = self.controller.roi_mgr.hide_all()
        self._apply_visibility_changes(changes)
        self._refresh_roi_list()
        self.status_text.SetLabel(_("Status: All ROIs hidden"))

    def _on_update_surface(self, event):
        """
        Rebuild the 3D surface for the selected ROI's mask (or the real
        current mask if none is selected in this list) - see the NOTE
        by btn_update_surface's construction for why this exists and
        why it's manual rather than automatic.

        Phase 08 (CT3D_P08_ROI3D_CLOSURE) root cause, found by reading
        invesalius/data/surface_process.py.create_surface_piece()
        directly: with algorithm="Default" and from_binary=False (the
        combination this button always sent before this fix),
        marching cubes contours the ORIGINAL IMAGE at mask.
        threshold_range - it NEVER reads the mask's own voxel array at
        all. Editing a mask (brush, region growing, undo/redo - ANY
        direct write to mask.matrix) therefore has ZERO effect on a
        "Default"-algorithm rebuild: the geometry is 100% determined
        by the unedited image + threshold range, regardless of mask
        content. Confirmed for real: a tiny synthetic ROI grown 3x in
        3 cycles produced byte-identical polydata (same point/cell
        count, same bounds) every single time.

        InVesalius's own real "Configure 3D surface" dialog
        (invesalius/gui/dialogs.py's SurfaceMethodPanel) already knows
        this - it hides "Default" from the choice list and shows a
        tooltip ("It is not possible to use the Default method because
        the mask was edited") whenever mask.was_edited is True,
        forcing "Context aware smoothing" (algorithm="ca_smoothing")
        instead. Both "ca_smoothing" and "Binary" set from_binary=True
        in AddNewActor, which DOES contour the real mask array
        (create_surface_piece's from_binary branch: `image =
        converters.to_vtk(a_mask, ...)`) - "Binary" is the simpler of
        the two (no extra smoothing-parameter dict needed) and is used
        here since correctness (mesh actually matches the edited mask)
        matters more than the extra smoothing "ca_smoothing" adds.
        """
        try:
            import invesalius.data.slice_ as sl
            import invesalius.project as prj
            from invesalius.pubsub import pub as Publisher

            rid = self._selected_roi_id()
            if rid is not None:
                mask_index = self.controller.roi_mgr.get_roi(rid).mask_index
                mask = prj.Project().mask_dict.get(mask_index)
            else:
                mask = sl.Slice().current_mask
                if mask is None:
                    wx.MessageBox(_("No mask selected."), _("Error"), wx.OK | wx.ICON_ERROR)
                    return
                mask_index = mask.index

            algorithm = choose_surface_algorithm(mask)

            # Same real topic/argument shape used and verified in the
            # performance test (test_perf.py) that measured real render
            # FPS on a surface built this way.
            surface_options = {
                "method": {"algorithm": algorithm, "options": {}},
                "options": {
                    "index": mask_index, "name": "", "quality": "Optimal *",
                    "fill": False, "keep_largest": False, "overwrite": True,
                },
            }
            Publisher.sendMessage("Create surface from index", surface_parameters=surface_options)
            self.status_text.SetLabel(
                _(f"Status: Rebuilding 3D surface for mask #{mask_index} (method: {algorithm})...")
            )
        except Exception as e:
            wx.MessageBox(_("Surface update failed."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: surface update failed - {e}")
