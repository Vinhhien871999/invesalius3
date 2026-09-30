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

from ..core import native_mask, segmentation_cleanup, segmentation_preview
from ..core.ai import ENABLE_AI_SEGMENTATION
from ..core.ai import job_controller as ai_jobs
from ..core.ai import preview_bridge as ai_bridge
from ..core.ai import provider as ai_provider
from ..core.ai.prompts import AIPromptSet, PromptOutOfVolume
from ..core.ai.types import Capability, DeviceKind
from ..i18n import _, fmt_float, fmt_int
from . import ui_helpers

# E2 (Advanced Segmentation Enhancement Track, enhancement/advanced-
# segmentation branch only): the real Slice().aux_matrices/to_show_aux key
# this plugin's preview overlay uses. A plain string constant (not a
# per-instance attribute) since it must stay identical between the code
# that writes it (see _show_preview_overlay()) and the code that clears it
# (_clear_preview_overlay()) regardless of which SegmentationPanel/
# controller instance is involved.
PREVIEW_AUX_KEY = "roi_viewer_preview"


def mask_colour_to_wx(colour) -> "wx.Colour":
    """InVesalius mask colours are floats in 0..1 (constants.MASK_COLOUR);
    0..255 tuples are accepted too. Before 30/09/2026 the swatch did
    int(c) on the 0..1 floats and showed every real mask as black."""
    rgb = [float(c) for c in tuple(colour)[:3]]
    if all(0.0 <= c <= 1.0 for c in rgb):
        rgb = [c * 255.0 for c in rgb]
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return wx.Colour(r, g, b)


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

    `controller` is the owning ROIViewerPanel - it holds the shared
    core/ manager instances (seg_mgr, mask_mgr) created once per plugin
    session, so state (like undo history) survives switching tabs.
    """

    def __init__(self, parent, controller, roi_page=None):
        scrolled.ScrolledPanel.__init__(self, parent)
        self.controller = controller
        # ROI management + 3D surface widgets go on this second page ("ROI
        # & 3D") when the frame supplies one, otherwise onto this panel.
        self.roi_page = roi_page if roi_page is not None else self
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
        # E4 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch ONLY): the actual renderer-
        # attached manager (core/preview_surface_3d.PreviewSurfaceManager3D)
        # lives on self.controller (ROIViewerPanel), mirroring marker_3d/
        # slice_planes_3d - this panel only owns the debounce timer and
        # the real Mask.add_modified_callback() registration bookkeeping.
        self.E4_DEBOUNCE_MS = 400  # within the 300-500ms range Section 19 suggested
        self._e4_debounce_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_e4_debounce_timer, self._e4_debounce_timer)
        self._e4_callback_mask = None  # which real Mask currently has our modified-callback registered
        # E5 hardening (Section 5 audit): before this, every debounced
        # fire AND every "Refresh 3D Preview" click called
        # _trigger_preview_3d_rebuild() unconditionally - a real,
        # confirmed gap (not inferred from generation_id alone, per the
        # audit's explicit instruction): rapid repeated manual Refresh
        # clicks (or a Refresh landing while a debounced worker is still
        # running) could spawn an unbounded number of simultaneous
        # threading.Thread workers, each holding its own ~28MB numpy
        # snapshot strongly referenced at once - generation_id alone
        # only discards STALE *results*, it never limited how many
        # workers/snapshots could be concurrently in flight. Hardened to
        # "max 1 running worker + max 1 latest pending request":
        # _e4_build_busy gates a NEW worker from starting while one is
        # already in flight (synchronous early-return paths count as
        # "in flight" too, for the same one-at-a-time guarantee);
        # _e4_pending_reason remembers only the LATEST coalesced reason
        # requested meanwhile (Section 5: "do NOT launch another worker
        # immediately... only remember 'latest rebuild requested'").
        # _finish_preview_3d_build() is the single place that clears
        # _e4_build_busy and launches exactly one pending rebuild, if
        # any, once the current one is fully done.
        self._e4_build_busy = False
        self._e4_pending_reason = None
        # E5B (clipping - Section 16 audit): mask_index -> surface_index,
        # populated ONLY from surface builds THIS plugin's own "Update 3D
        # Surface from Selected ROI" button triggered (never guessed -
        # see core/surface_clipping_3d.py's module docstring for the
        # real, source-proven reason mask_index == surface_index is NOT
        # a safe assumption: AddNewActor()'s real overwrite path assigns
        # the rebuilt Surface's .index from the GLOBAL
        # self.last_surface_index counter, not the mask index). Guarded
        # by _pending_surface_build_mask_index, set right before this
        # panel's own "Create surface from index" send and consumed by
        # the very next real "Update surface info in GUI" event - the
        # real pubsub message AddNewActor()/its async completion path
        # sends with the actual, just-created Surface object (see
        # _on_surface_info_updated() below).
        self._roi_surface_index = {}
        self._pending_surface_build_mask_index = None
        # E6: created only when the user switches AI on - with it off no
        # provider module is imported and no AI thread can exist.
        self._ai_registry = None
        self._ai_jobs = None
        self._ai_prompts = AIPromptSet()  # session only, never saved
        self._ai_provider_ids = []  # dropdown index -> provider_id
        self._ai_devices = [DeviceKind.AUTO]  # dropdown index -> DeviceKind
        self._ai_structures = []  # E6b: provider parameter "target_structure"
        self._ai_modes = []  # E6b: provider parameter "mode"
        self._ai_preview_generation = None
        self._ai_run = None  # provider/prompt/timing info of the running job
        self._subscribe_surface_info_once()
        self._init_ui()
        self.SetupScrolling(scroll_x=False)
        ui_helpers.follow_width(self)

    def _init_ui(self):
        """
        Two pages, one class. This panel ("Phân đoạn") holds the
        segmentation workflow in the order it is used: create/preview ->
        accept -> post-process -> manual edit. ROI management and the 3D
        surface controls are built onto self.roi_page ("ROI & 3D") when
        the frame provides one. Every widget is bound directly with
        widget.Bind(), so handlers behave the same whichever page a
        widget sits on. Advanced sections are native wx.CollapsiblePanes,
        collapsed by default.
        """
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(ui_helpers.hint(
            self, _("1. Create or preview  →  2. Accept  →  3. Post-process  →  4. Update 3D surface")
        ), 0, wx.ALL | wx.EXPAND, 3)

        # Current ROI, repeated here because post-processing, brush and
        # undo all act on it while the ROI list itself is on "ROI & 3D".
        current_row = wx.BoxSizer(wx.HORIZONTAL)
        current_row.Add(wx.StaticText(self, wx.ID_ANY, _("Current ROI:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_seg_current_roi = wx.StaticText(self, wx.ID_ANY, _("(none)"))
        current_row.Add(self.lbl_seg_current_roi, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        sizer.Add(current_row, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 5)

        # --- A. Create: threshold ---
        box_thresh = wx.StaticBox(self, wx.ID_ANY, _("Threshold"))
        thresh_sizer = wx.StaticBoxSizer(box_thresh, wx.VERTICAL)

        self.cb_auto_thresh = wx.CheckBox(self, wx.ID_ANY, _("Auto threshold (Otsu)"))
        thresh_sizer.Add(self.cb_auto_thresh, 0, wx.ALL, 3)

        thresh_row = wx.BoxSizer(wx.HORIZONTAL)
        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("From")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.spin_min = wx.SpinCtrl(self, wx.ID_ANY, "226", min=-1024, max=8000)
        thresh_row.Add(self.spin_min, 1, wx.ALL, 3)
        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("to")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.spin_max = wx.SpinCtrl(self, wx.ID_ANY, "3071", min=-1024, max=8000)
        thresh_row.Add(self.spin_max, 1, wx.ALL, 3)
        thresh_sizer.Add(thresh_row, 0, wx.EXPAND)

        self.btn_apply_thresh = wx.Button(self, wx.ID_ANY, _("Create mask"))
        self.btn_apply_thresh.SetToolTip(_("Creates a real mask from the threshold range immediately."))
        # E2: enabled only while the preview workflow is on - see
        # _on_enable_preview_toggle().
        self.btn_preview_otsu = wx.Button(self, wx.ID_ANY, _("Preview Otsu"))
        self.btn_preview_otsu.Enable(False)
        thresh_sizer.Add(ui_helpers.button_row(self.btn_apply_thresh, self.btn_preview_otsu), 0, wx.EXPAND)
        sizer.Add(thresh_sizer, 0, wx.ALL | wx.EXPAND, 3)

        # --- A. Create: region growing (seed picked in the 3D view with
        # the shared controller.picker; see _on_seed_picked()) ---
        box_rg = wx.StaticBox(self, wx.ID_ANY, _("Region Growing"))
        rg_sizer = wx.StaticBoxSizer(box_rg, wx.VERTICAL)

        # min=0: tolerance 0 is valid ("exactly the seed's value").
        self.spin_rg_tolerance = wx.SpinCtrl(self, wx.ID_ANY, "50", min=0, max=2000)
        rg_sizer.Add(ui_helpers.labelled_row(self, _("Tolerance:"), self.spin_rg_tolerance), 0, wx.EXPAND)

        self.btn_pick_seed = wx.ToggleButton(self, wx.ID_ANY, _("Pick seed point (3D)"))
        self.btn_pick_seed.SetToolTip(_(
            "Click a point on the 3D surface. Without preview mode the region "
            "grows and a real mask is created immediately."
        ))
        # E2: enabled only in preview mode after a seed was picked.
        self.btn_preview_region_growing = wx.Button(self, wx.ID_ANY, _("Preview"))
        self.btn_preview_region_growing.Enable(False)
        # Stacked, not side by side: an equal-width row is twice as wide as
        # its longest label, which overflowed narrow windows.
        rg_sizer.Add(self.btn_pick_seed, 0, wx.ALL | wx.EXPAND, 2)
        rg_sizer.Add(self.btn_preview_region_growing, 0, wx.ALL | wx.EXPAND, 2)

        self.rg_status = wx.StaticText(self, wx.ID_ANY, "")
        rg_sizer.Add(self.rg_status, 0, wx.ALL | wx.EXPAND, 3)
        sizer.Add(rg_sizer, 0, wx.ALL | wx.EXPAND, 3)

        # --- A. Create: AI (E6), collapsed and off by default. An AI
        # result is only ever an E2 preview (kind "ai") - Accept/Cancel in
        # the Preview box below commit or drop it. See core/ai/__init__.py.
        pane_ai, p = ui_helpers.collapsible(self, _("AI segmentation (experimental)"), self._on_section_toggled)
        ai_sizer = wx.BoxSizer(wx.VERTICAL)
        self.cb_enable_ai = wx.CheckBox(p, wx.ID_ANY, _("Enable AI segmentation (experimental)"))
        self.cb_enable_ai.SetValue(ENABLE_AI_SEGMENTATION)
        self.cb_enable_ai.SetToolTip(_(
            "Runs an installed AI model on the real image volume. The result is only a preview - no mask "
            "is created until you click Accept. Nothing is downloaded or installed."
        ))
        ai_sizer.Add(self.cb_enable_ai, 0, wx.ALL, 3)
        self.choice_ai_model = wx.Choice(p, wx.ID_ANY, choices=[_("(none)")])
        self.choice_ai_model.SetSelection(0)
        ai_sizer.Add(ui_helpers.labelled_row(p, _("Model:"), self.choice_ai_model), 0, wx.EXPAND)
        self.choice_ai_device = wx.Choice(p, wx.ID_ANY, choices=[_("Auto")])
        self.choice_ai_device.SetSelection(0)
        ai_sizer.Add(ui_helpers.labelled_row(p, _("Device:"), self.choice_ai_device), 0, wx.EXPAND)
        # E6b: shown enabled only for a provider that declares these
        # parameters (AIProviderInfo.parameter_choices). Structure names are
        # the model's own canonical class names - not translated.
        self.combo_ai_structure = wx.ComboBox(p, wx.ID_ANY, choices=[], style=wx.CB_DROPDOWN)
        self.combo_ai_structure.SetToolTip(_(
            "Type to search. One structure per preview - the model's other classes are not used."))
        self._ai_structure_row = ui_helpers.labelled_row(p, _("Structure:"), self.combo_ai_structure)
        ai_sizer.Add(self._ai_structure_row, 0, wx.EXPAND)
        self.choice_ai_mode = wx.Choice(p, wx.ID_ANY, choices=[_("Standard accuracy")])
        self.choice_ai_mode.SetSelection(0)
        self.choice_ai_mode.SetToolTip(_(
            "Fast uses the model's lower-resolution version: less time and memory, less accurate."))
        self._ai_mode_row = ui_helpers.labelled_row(p, _("Mode:"), self.choice_ai_mode)
        ai_sizer.Add(self._ai_mode_row, 0, wx.EXPAND)

        # Point/box prompts: shown only for a model that uses them.
        self._ai_prompt_sizer = wx.BoxSizer(wx.VERTICAL)
        kind_row = wx.BoxSizer(wx.HORIZONTAL)
        kind_row.Add(wx.StaticText(p, wx.ID_ANY, _("Point type:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.rb_ai_positive = wx.RadioButton(p, wx.ID_ANY, _("Inside region"), style=wx.RB_GROUP)
        self.rb_ai_positive.SetValue(True)
        self.rb_ai_negative = wx.RadioButton(p, wx.ID_ANY, _("Exclude"))
        kind_row.Add(self.rb_ai_positive, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        kind_row.Add(self.rb_ai_negative, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self._ai_prompt_sizer.Add(kind_row, 0, wx.EXPAND)

        self.btn_ai_pick_point = wx.ToggleButton(p, wx.ID_ANY, _("Pick point (3D)"))
        self.btn_ai_cursor_point = wx.Button(p, wx.ID_ANY, _("Point at 2D cursor"))
        self._ai_prompt_sizer.Add(ui_helpers.button_row(self.btn_ai_pick_point, self.btn_ai_cursor_point),
                                  0, wx.EXPAND)
        self._ai_prompt_sizer.Add(ui_helpers.hint(p, _("Bounding box: move the 2D cursor to each corner.")),
                                  0, wx.ALL, 3)
        self.btn_ai_corner1 = wx.Button(p, wx.ID_ANY, _("Set corner 1"))
        self.btn_ai_corner2 = wx.Button(p, wx.ID_ANY, _("Set corner 2"))
        self._ai_prompt_sizer.Add(ui_helpers.button_row(self.btn_ai_corner1, self.btn_ai_corner2), 0, wx.EXPAND)
        self.lbl_ai_prompts = wx.StaticText(p, wx.ID_ANY, "")
        self._ai_prompt_sizer.Add(self.lbl_ai_prompts, 0, wx.ALL | wx.EXPAND, 3)
        self.btn_ai_clear = wx.Button(p, wx.ID_ANY, _("Clear AI points"))
        self._ai_prompt_sizer.Add(self.btn_ai_clear, 0, wx.ALL | wx.EXPAND, 2)
        ai_sizer.Add(self._ai_prompt_sizer, 0, wx.EXPAND)
        self.btn_ai_run = wx.Button(p, wx.ID_ANY, _("Preview with AI"))
        self.btn_ai_run.SetToolTip(_(
            "Shows the AI result as a preview overlay (and in the live 3D preview if on). "
            "Accept creates a new mask from exactly this preview; the model is not run again."
        ))
        self.btn_ai_cancel = wx.Button(p, wx.ID_ANY, _("Cancel AI processing"))
        ai_sizer.Add(ui_helpers.button_row(self.btn_ai_run, self.btn_ai_cancel), 0, wx.EXPAND)
        ai_state_row = wx.BoxSizer(wx.HORIZONTAL)
        ai_state_row.Add(wx.StaticText(p, wx.ID_ANY, _("State:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_ai_status = wx.StaticText(p, wx.ID_ANY, _("Off"))
        ai_state_row.Add(self.lbl_ai_status, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        ai_sizer.Add(ai_state_row, 0, wx.EXPAND)
        self.lbl_ai_help = ui_helpers.hint(p, _(
            "AI models are not bundled with the plugin. See the user guide to install TotalSegmentator."))
        ai_sizer.Add(self.lbl_ai_help, 0, wx.ALL, 3)
        p.SetSizer(ai_sizer)
        self._ai_pane, self._ai_sizer = pane_ai, ai_sizer
        sizer.Add(pane_ai, 0, wx.ALL | wx.EXPAND, 3)

        # --- B. Preview -> Accept / Cancel (E2). Off by default: with the
        # checkbox off the classic immediate-commit behaviour is unchanged.
        box_preview = wx.StaticBox(self, wx.ID_ANY, _("Preview"))
        preview_sizer = wx.StaticBoxSizer(box_preview, wx.VERTICAL)

        self.cb_enable_preview = wx.CheckBox(self, wx.ID_ANY, _("Enable preview mode"))
        self.cb_enable_preview.SetToolTip(_(
            "Otsu and Region Growing show a temporary overlay first. No real "
            "mask is created until you click Accept."
        ))
        preview_sizer.Add(self.cb_enable_preview, 0, wx.ALL, 3)

        preview_status_row = wx.BoxSizer(wx.HORIZONTAL)
        preview_status_row.Add(wx.StaticText(self, wx.ID_ANY, _("State:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_preview_status = wx.StaticText(self, wx.ID_ANY, _("Idle"))
        preview_status_row.Add(self.lbl_preview_status, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        preview_sizer.Add(preview_status_row, 0, wx.EXPAND)

        self.btn_preview_accept = wx.Button(self, wx.ID_ANY, _("Accept"))
        self.btn_preview_accept.Enable(False)
        self.btn_preview_cancel = wx.Button(self, wx.ID_ANY, _("Cancel preview"))
        self.btn_preview_cancel.Enable(False)
        preview_sizer.Add(ui_helpers.button_row(self.btn_preview_accept, self.btn_preview_cancel), 0, wx.EXPAND)
        sizer.Add(preview_sizer, 0, wx.ALL | wx.EXPAND, 3)

        # --- C. Post-processing on the current ROI (E3), collapsed ---
        pane_cleanup, p = ui_helpers.collapsible(self, _("Post-processing (current ROI)"), self._on_section_toggled)
        cleanup_sizer = wx.BoxSizer(wx.VERTICAL)

        self.btn_cleanup_keep_largest = wx.Button(p, wx.ID_ANY, _("Keep largest connected component"))
        cleanup_sizer.Add(self.btn_cleanup_keep_largest, 0, wx.ALL | wx.EXPAND, 2)

        self.spin_min_component_size = wx.SpinCtrl(p, wx.ID_ANY, "100", min=1, max=10_000_000)
        cleanup_sizer.Add(ui_helpers.labelled_row(p, _("Minimum size:"), self.spin_min_component_size, "voxel"),
                          0, wx.EXPAND)
        self.btn_cleanup_remove_small = wx.Button(p, wx.ID_ANY, _("Remove small islands"))
        self.btn_cleanup_fill_holes = wx.Button(p, wx.ID_ANY, _("Fill holes"))
        cleanup_sizer.Add(ui_helpers.button_row(self.btn_cleanup_remove_small, self.btn_cleanup_fill_holes),
                          0, wx.EXPAND)

        # max bounded to MAX_SMOOTH_ITERATIONS - see segmentation_cleanup.
        self.spin_smooth_iterations = wx.SpinCtrl(
            p, wx.ID_ANY, "1", min=1, max=segmentation_cleanup.MAX_SMOOTH_ITERATIONS
        )
        cleanup_sizer.Add(ui_helpers.labelled_row(p, _("Smoothing passes:"), self.spin_smooth_iterations),
                          0, wx.EXPAND)
        self.btn_cleanup_smooth = wx.Button(p, wx.ID_ANY, _("Smooth mask"))
        # Measured E3 finding: a 1-voxel-thick structure disappeared
        # entirely at iterations=1 with both candidate algorithms.
        self.btn_cleanup_smooth.SetToolTip(_(
            "Edits the real mask (undoable). Can remove very thin structures - "
            "use few passes and check the result. The 3D surface is not rebuilt."
        ))
        cleanup_sizer.Add(self.btn_cleanup_smooth, 0, wx.ALL | wx.EXPAND, 2)

        self.lbl_cleanup_status = wx.StaticText(p, wx.ID_ANY, "")
        cleanup_sizer.Add(self.lbl_cleanup_status, 0, wx.ALL | wx.EXPAND, 3)
        p.SetSizer(cleanup_sizer)
        sizer.Add(pane_cleanup, 0, wx.ALL | wx.EXPAND, 3)

        # --- Manual editing: InVesalius's own 2D brush, driven through its
        # real pubsub topics (this panel never captures mouse events). ---
        pane_brush, p = ui_helpers.collapsible(self, _("Manual editing (brush)"), self._on_section_toggled)
        brush_sizer = wx.BoxSizer(wx.VERTICAL)

        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_brush_draw = wx.RadioButton(p, wx.ID_ANY, _("Draw"), style=wx.RB_GROUP)
        self.rb_brush_draw.SetValue(True)
        mode_row.Add(self.rb_brush_draw, 1, wx.ALL, 3)
        self.rb_brush_erase = wx.RadioButton(p, wx.ID_ANY, _("Erase"))
        mode_row.Add(self.rb_brush_erase, 1, wx.ALL, 3)
        brush_sizer.Add(mode_row, 0, wx.EXPAND)

        shape_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_brush_circle = wx.RadioButton(p, wx.ID_ANY, _("Circle"), style=wx.RB_GROUP)
        self.rb_brush_circle.SetValue(True)
        shape_row.Add(self.rb_brush_circle, 1, wx.ALL, 3)
        self.rb_brush_square = wx.RadioButton(p, wx.ID_ANY, _("Square"))
        shape_row.Add(self.rb_brush_square, 1, wx.ALL, 3)
        brush_sizer.Add(shape_row, 0, wx.EXPAND)

        self.slider_brush_size = wx.Slider(p, wx.ID_ANY, 30, 1, 100, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        brush_sizer.Add(ui_helpers.labelled_row(p, _("Brush size:"), self.slider_brush_size), 0, wx.EXPAND)

        self.btn_toggle_brush = wx.ToggleButton(p, wx.ID_ANY, _("Enable brush"))
        self.btn_toggle_brush.SetToolTip(_("Paint directly on the 2D slice views. Edits the real mask."))
        brush_sizer.Add(self.btn_toggle_brush, 0, wx.ALL | wx.EXPAND, 3)
        p.SetSizer(brush_sizer)
        sizer.Add(pane_brush, 0, wx.ALL | wx.EXPAND, 3)

        # --- Undo / redo of the real current mask ---
        box_undo = wx.StaticBox(self, wx.ID_ANY, _("Edit history (current ROI)"))
        undo_sizer = wx.StaticBoxSizer(box_undo, wx.VERTICAL)
        self.btn_checkpoint = wx.Button(self, wx.ID_ANY, _("Save restore point"))
        self.btn_undo = wx.Button(self, wx.ID_ANY, _("Undo"))
        self.btn_redo = wx.Button(self, wx.ID_ANY, _("Redo"))
        undo_sizer.Add(self.btn_checkpoint, 0, wx.ALL | wx.EXPAND, 2)
        undo_sizer.Add(ui_helpers.button_row(self.btn_undo, self.btn_redo), 0, wx.EXPAND)
        sizer.Add(undo_sizer, 0, wx.ALL | wx.EXPAND, 3)

        self.status_text = wx.StaticText(self, wx.ID_ANY, _("Ready."), style=wx.ST_NO_AUTORESIZE)
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 3)
        self.SetSizer(sizer)

        self._build_roi_3d_page()
        self._update_ai_controls()

        self.cb_auto_thresh.Bind(wx.EVT_CHECKBOX, self._on_auto_thresh_toggle)
        self.btn_apply_thresh.Bind(wx.EVT_BUTTON, self._on_apply_threshold)
        self.btn_preview_otsu.Bind(wx.EVT_BUTTON, self._on_preview_otsu)
        self.btn_pick_seed.Bind(wx.EVT_TOGGLEBUTTON, self._on_toggle_pick_seed)
        self.btn_preview_region_growing.Bind(wx.EVT_BUTTON, self._on_preview_region_growing)
        self.cb_enable_preview.Bind(wx.EVT_CHECKBOX, self._on_enable_preview_toggle)
        self.btn_preview_accept.Bind(wx.EVT_BUTTON, self._on_preview_accept)
        self.cb_enable_ai.Bind(wx.EVT_CHECKBOX, self._on_enable_ai_toggle)
        self.choice_ai_model.Bind(wx.EVT_CHOICE, self._on_ai_model_changed)
        self.btn_ai_pick_point.Bind(wx.EVT_TOGGLEBUTTON, self._on_ai_toggle_pick_point)
        self.btn_ai_cursor_point.Bind(wx.EVT_BUTTON, self._on_ai_cursor_point)
        self.btn_ai_corner1.Bind(wx.EVT_BUTTON, lambda event: self._on_ai_corner(1))
        self.btn_ai_corner2.Bind(wx.EVT_BUTTON, lambda event: self._on_ai_corner(2))
        self.btn_ai_clear.Bind(wx.EVT_BUTTON, self._on_ai_clear)
        self.btn_ai_run.Bind(wx.EVT_BUTTON, self._on_ai_run)
        self.btn_ai_cancel.Bind(wx.EVT_BUTTON, self._on_ai_cancel)
        self.btn_preview_cancel.Bind(wx.EVT_BUTTON, self._on_preview_cancel)
        self.btn_cleanup_keep_largest.Bind(wx.EVT_BUTTON, self._on_cleanup_keep_largest)
        self.btn_cleanup_remove_small.Bind(wx.EVT_BUTTON, self._on_cleanup_remove_small)
        self.btn_cleanup_fill_holes.Bind(wx.EVT_BUTTON, self._on_cleanup_fill_holes)
        self.btn_cleanup_smooth.Bind(wx.EVT_BUTTON, self._on_cleanup_smooth)
        self.cb_enable_live_3d_preview.Bind(wx.EVT_CHECKBOX, self._on_enable_live_3d_preview_toggle)
        self.btn_refresh_3d_preview.Bind(wx.EVT_BUTTON, self._on_refresh_3d_preview)
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

    def _build_roi_3d_page(self):
        """ROI management (E1) and the 3D surface controls (final surface
        + E4 live preview) - on self.roi_page when the frame gave one."""
        page = self.roi_page
        sizer = wx.BoxSizer(wx.VERTICAL) if page is not self else self.GetSizer()

        # --- D. ROI management. Backed by the real InVesalius masks
        # (Project().mask_dict) - not a multi-label volume. ---
        box_roi = wx.StaticBox(page, wx.ID_ANY, _("ROI management"))
        roi_sizer = wx.StaticBoxSizer(box_roi, wx.VERTICAL)

        active_row = wx.BoxSizer(wx.HORIZONTAL)
        active_row.Add(wx.StaticText(page, wx.ID_ANY, _("Current ROI:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_active_roi = wx.StaticText(page, wx.ID_ANY, _("(none)"))
        active_row.Add(self.lbl_active_roi, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        # Read-only colour indicator of the real Mask.colour.
        self.roi_color_swatch = wx.Panel(page, wx.ID_ANY, size=(18, 18))
        self.roi_color_swatch.SetBackgroundColour(wx.Colour(200, 200, 200))
        active_row.Add(self.roi_color_swatch, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        roi_sizer.Add(active_row, 0, wx.EXPAND)

        self.roi_list = wx.CheckListBox(page, wx.ID_ANY, size=(-1, 110))
        self.roi_list.SetToolTip(_("Click a row to make it the current ROI; the checkbox shows or hides it."))
        self.roi_list.Bind(wx.EVT_CHECKLISTBOX, self._on_roi_visibility_toggled)
        self.roi_list.Bind(wx.EVT_LISTBOX, self._on_roi_selected)
        roi_sizer.Add(self.roi_list, 1, wx.ALL | wx.EXPAND, 3)

        self.btn_roi_rename = wx.Button(page, wx.ID_ANY, _("Rename"))
        self.btn_roi_delete = wx.Button(page, wx.ID_ANY, _("Delete"))
        roi_sizer.Add(ui_helpers.button_row(self.btn_roi_rename, self.btn_roi_delete), 0, wx.EXPAND)

        self.btn_roi_lock = wx.Button(page, wx.ID_ANY, _("Lock"))
        self.btn_roi_lock.SetToolTip(_("Blocks brush, undo/redo, post-processing and delete on this ROI. "
                                       "Session only - not saved in the project."))
        self.btn_roi_unlock = wx.Button(page, wx.ID_ANY, _("Unlock"))
        roi_sizer.Add(ui_helpers.button_row(self.btn_roi_lock, self.btn_roi_unlock), 0, wx.EXPAND)

        self.btn_roi_solo = wx.ToggleButton(page, wx.ID_ANY, _("Show only this ROI"))
        self.btn_roi_solo.SetToolTip(_("Hides every other ROI; click again to restore the previous visibility. "
                                       "Does not edit any mask."))
        roi_sizer.Add(self.btn_roi_solo, 0, wx.ALL | wx.EXPAND, 2)

        self.btn_roi_show_all = wx.Button(page, wx.ID_ANY, _("Show all"))
        self.btn_roi_hide_all = wx.Button(page, wx.ID_ANY, _("Hide all"))
        roi_sizer.Add(ui_helpers.button_row(self.btn_roi_show_all, self.btn_roi_hide_all), 0, wx.EXPAND)
        sizer.Add(roi_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- E. 3D surface. The final surface is only rebuilt on demand
        # (an automatic rebuild per edit would freeze the UI on large
        # volumes - see _on_update_surface()). ---
        box_surface = wx.StaticBox(page, wx.ID_ANY, _("3D surface"))
        surface_sizer = wx.StaticBoxSizer(box_surface, wx.VERTICAL)
        self.btn_update_surface = wx.Button(page, wx.ID_ANY, _("Update 3D surface from current ROI"))
        self.btn_update_surface.SetToolTip(_("Rebuilds the final 3D surface from the current ROI's mask. "
                                             "Edits do not update the final surface automatically."))
        surface_sizer.Add(self.btn_update_surface, 0, wx.ALL | wx.EXPAND, 3)

        # E4 live preview mesh - never the final surface; off by default.
        pane_live, p = ui_helpers.collapsible(page, _("Live 3D preview (experimental)"), self._on_section_toggled)
        live_sizer = wx.BoxSizer(wx.VERTICAL)
        self.cb_enable_live_3d_preview = wx.CheckBox(p, wx.ID_ANY, _("Enable live 3D preview"))
        self.cb_enable_live_3d_preview.SetToolTip(_(
            "Shows a temporary 3D mesh of the preview or current ROI that follows your edits. "
            "It is not the final surface and is never saved."
        ))
        live_sizer.Add(self.cb_enable_live_3d_preview, 0, wx.ALL, 3)
        self.btn_refresh_3d_preview = wx.Button(p, wx.ID_ANY, _("Refresh 3D preview"))
        self.btn_refresh_3d_preview.Enable(False)
        live_sizer.Add(self.btn_refresh_3d_preview, 0, wx.ALL | wx.EXPAND, 3)

        e4_row = wx.BoxSizer(wx.HORIZONTAL)
        e4_row.Add(wx.StaticText(p, wx.ID_ANY, _("Source:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_e4_source = wx.StaticText(p, wx.ID_ANY, "-")
        e4_row.Add(self.lbl_e4_source, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        live_sizer.Add(e4_row, 0, wx.EXPAND)
        e4_state_row = wx.BoxSizer(wx.HORIZONTAL)
        e4_state_row.Add(wx.StaticText(p, wx.ID_ANY, _("State:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.lbl_e4_state = wx.StaticText(p, wx.ID_ANY, _("Idle"))
        e4_state_row.Add(self.lbl_e4_state, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        live_sizer.Add(e4_state_row, 0, wx.EXPAND)
        self.lbl_e4_mesh_info = wx.StaticText(p, wx.ID_ANY, "")
        live_sizer.Add(self.lbl_e4_mesh_info, 0, wx.ALL | wx.EXPAND, 3)
        p.SetSizer(live_sizer)
        surface_sizer.Add(pane_live, 0, wx.ALL | wx.EXPAND, 2)
        sizer.Add(surface_sizer, 0, wx.ALL | wx.EXPAND, 5)

        self.roi_status = wx.StaticText(page, wx.ID_ANY, _("Ready."), style=wx.ST_NO_AUTORESIZE)
        sizer.Add(self.roi_status, 0, wx.ALL | wx.EXPAND, 5)

        if page is not self:
            page.SetSizer(sizer)
            page.SetupScrolling(scroll_x=False)

    def _on_section_toggled(self, event):
        for panel in {self, self.roi_page}:
            ui_helpers.relayout_scrolled(panel)
        if event is not None:
            event.Skip()

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
                self.status_text.SetLabel(_("No project loaded."))
                return
            lo, hi = self.controller.seg_mgr.auto_threshold_otsu(volume)
            self.spin_min.SetValue(int(lo))
            self.spin_max.SetValue(int(hi))
            self.status_text.SetLabel(_("Otsu threshold: {lo} to {hi}.").format(lo=int(lo), hi=int(hi)))
        except Exception as e:
            self.status_text.SetLabel(_("Could not compute the Otsu threshold."))
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
                _("The lower threshold must not exceed the upper threshold."), _("Error"), wx.OK | wx.ICON_ERROR
            )
            return

        self.controller.seg_mgr.set_threshold(lo, hi)

        name = self._commit_threshold_mask(lo, hi)
        if name is not None:
            self.status_text.SetLabel(_("Created mask '{name}'.").format(name=name))
            self._mark_preview_3d_dirty("new mask created")
        else:
            wx.MessageBox(_("Segmentation not available."), _("Error"), wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------
    # Region growing (semi-automatic, seed-based)
    # ------------------------------------------------------------------
    def _on_toggle_pick_seed(self, event):
        if not self.btn_pick_seed.GetValue():
            # User cancelled - unregister without growing anything.
            self.controller.picker.remove_callback(self._on_seed_picked)
            self.rg_status.SetLabel("")
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
                wx.CallAfter(self.rg_status.SetLabel, _("No project loaded."))
                return

            # The 3D pick is in the y-flipped view frame; convert to the
            # slice frame before voxel conversion (core/coordinates.py).
            # Before 30/09/2026 this skipped the flip, so every seed's
            # coronal index clamped to row 0.
            from ..core.coordinates import view_to_slice

            world_point = view_to_slice(world_point)
            self.controller.sync_mgr.set_volume_info(pi.get_spacing(), pi.get_shape())
            seed = self.controller.sync_mgr.world_to_voxel(*world_point)
            tolerance = self.spin_rg_tolerance.GetValue()

            seed_error = self.controller.seg_mgr.validate_seed(seed, volume.shape)
            if seed_error is not None:
                self.rg_status.SetLabel(_("Invalid seed point."))
                print(f"ROI Viewer: invalid seed - {seed_error}")
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
                    _("Seed at voxel {seed}. Click Preview.").format(seed=seed),
                )
                return

            wx.CallAfter(self.rg_status.SetLabel, _("Growing from voxel {seed}…").format(seed=seed))
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
                    wx.CallAfter(self.rg_status.SetLabel, _("Invalid region growing parameters."))
                    print(f"ROI Viewer: region growing rejected - {e}")
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
        Commits a region-growing result (classic path and E2 Accept) as a
        new real mask named "Region Growing N", through the shared
        core/native_mask.commit_preview_array_to_new_mask() - the same
        commit E6 AI Accept uses. Returns the new mask's name, or None on
        failure (reason printed to console; callers report it in the UI).

        30/09/2026: this used to write np.where(result > 0, 255, target)
        and mark only the axial "computed" sentinels. Showing a coronal or
        sagittal slice that had not been displayed yet then re-thresholded
        that plane with the placeholder threshold (1, 1) and erased the
        committed voxels, and slices the 2D views had already thresholded
        during mask creation could keep stray (1, 1) voxels. The shared
        helper writes exactly 0/255 and marks all three sentinel planes,
        like InVesalius's own Watershed commit - see core/native_mask.py.
        was_edited is still set (Phase 08 surface policy -
        choose_surface_algorithm()).
        """
        try:
            import invesalius.constants as const
            from ..interface.project_interface import ProjectInterface

            mask_count = len(ProjectInterface().get_mask_dict())
            colour = const.MASK_COLOUR[mask_count % len(const.MASK_COLOUR)]
            name = f"Region Growing {mask_count + 1}"
            mask = native_mask.commit_preview_array_to_new_mask(result_mask > 0, name, colour)
            if mask is None:
                print("ROI Viewer: region growing commit failed - mask creation returned no current mask")
                return None
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
                    _("No region found (tolerance {tolerance}). Try a higher tolerance.").format(tolerance=tolerance)
                )
                return

            info = self._region_info(stats)

            if stats["exceeds_limit"]:
                limit_pct = self.controller.seg_mgr.max_region_fraction * 100
                proceed = wx.MessageBox(
                    _(
                        "This region covers {percent}% of the volume - more than the {limit}% safety "
                        "limit, so it is probably not a meaningful ROI.\n\n{info}\n\nCreate it anyway?"
                    ).format(percent=fmt_float(stats["fraction"] * 100, 1), limit=fmt_float(limit_pct, 0), info=info),
                    _("Large region"),
                    wx.YES_NO | wx.ICON_WARNING,
                )
                if proceed != wx.YES:
                    self.rg_status.SetLabel(_("Region growing cancelled."))
                    return

            name = self._commit_region_growing_result(result_mask, seed, tolerance)
            if name is None:
                self.rg_status.SetLabel(_("Could not create the mask."))
                return

            self._refresh_after_edit()
            self.rg_status.SetLabel(_("Created '{name}': {info}.").format(name=name, info=info))
        except Exception as e:
            self.rg_status.SetLabel(_("Could not apply the region growing result."))
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
        # E6: an AI job still computing a preview is part of that preview.
        if self._ai_jobs is not None:
            self._ai_jobs.cancel()
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
            # E4: if live 3D preview was showing this (now-cancelled) E2
            # preview, fall back to Current ROI (or hide, if none) -
            # _select_preview_3d_source() re-evaluates priority fresh.
            self._mark_preview_3d_dirty("E2 preview workflow disabled")

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
                    _("Create or select a mask first - the preview overlay needs a current mask."),
                    _("No mask selected"), wx.OK | wx.ICON_WARNING,
                )
                return

            pi = ProjectInterface()
            volume = pi.get_volume_data()
            if volume is None:
                self.lbl_preview_status.SetLabel(_("No project loaded."))
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
            self.lbl_preview_status.SetLabel(
                _("Otsu preview: {voxels} voxels ({lo} to {hi}).").format(
                    voxels=fmt_int(voxel_count), lo=int(lo), hi=int(hi))
            )
            self._update_preview_buttons()
            self._mark_preview_3d_dirty("Otsu preview ready")
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
                    _("Create or select a mask first - the preview overlay needs a current mask."),
                    _("No mask selected"), wx.OK | wx.ICON_WARNING,
                )
                return

            pi = ProjectInterface()
            volume = pi.get_volume_data()
            if volume is None:
                self.lbl_preview_status.SetLabel(_("No project loaded."))
                return

            seed = self._preview_seed_voxel
            seed_world = self._preview_seed_world
            tolerance = self.spin_rg_tolerance.GetValue()
            gen = self.preview_mgr.new_generation()
            self.lbl_preview_status.SetLabel(_("Computing…"))
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
                    _("No region found (tolerance {tolerance}). Try a higher tolerance.").format(tolerance=tolerance)
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

            info = self._region_info(stats)
            if stats["exceeds_limit"]:
                limit_pct = self.controller.seg_mgr.max_region_fraction * 100
                # Informational only, non-blocking (instruction section
                # 12: "show warning/statistics BEFORE Accept... the user
                # may still inspect the candidate preview") - the actual
                # blocking confirmation happens in _on_preview_accept()
                # at commit time, same as the classic path.
                info += " " + _("(over the {limit}% limit - Accept will ask to confirm)").format(
                    limit=fmt_float(limit_pct, 0))
            self.lbl_preview_status.SetLabel(_("Region growing preview: {info}.").format(info=info))
            self._show_preview_overlay(array)
            self._update_preview_buttons()
            self._mark_preview_3d_dirty("Region Growing preview ready")
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
                            "This region covers {percent}% of the volume - more than the {limit}% safety "
                            "limit, so it is probably not a meaningful ROI.\n\nCreate it anyway?"
                        ).format(percent=fmt_float(stats.get("fraction", 0) * 100, 1), limit=fmt_float(limit_pct, 0)),
                        _("Large region"), wx.YES_NO | wx.ICON_WARNING,
                    )
                    if proceed != wx.YES:
                        self.preview_mgr.revert_accept()
                        self.lbl_preview_status.SetLabel(_("Accept cancelled - the preview is still shown."))
                        self._update_preview_buttons()
                        return
                # preview_array holds 0/255 values (see
                # _on_region_grown_preview()) - _commit_region_growing_
                # result() does `np.where(result_mask > 0, ...)`, so a
                # 0/255 array works identically to a 0/1 one.
                name = self._commit_region_growing_result(
                    self.preview_mgr.preview_array, self.preview_mgr.seed_voxel, self.preview_mgr.tolerance
                )

            elif kind == "ai":
                # E6: commit EXACTLY the previewed candidate - the model is
                # not run again and nothing is recomputed.
                name = self._commit_ai_preview(self.preview_mgr.preview_array)

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
            self.lbl_preview_status.SetLabel(_("Accepted as '{name}'.").format(name=name))
            self._update_preview_buttons()
        except Exception as e:
            print(f"ROI Viewer: preview accept failed - {e}")
            self.preview_mgr.revert_accept()
            self.lbl_preview_status.SetLabel(_("Accept failed - the preview is still shown."))
            self._update_preview_buttons()

    def _on_preview_cancel(self, event):
        self.cancel_preview()
        # E4: fall back to Current ROI (or hide, if none) - Section 18.
        self._mark_preview_3d_dirty("E2 preview cancelled")

    # ------------------------------------------------------------------
    # E6 - AI segmentation (core/ai). Orchestration only: the provider runs
    # on the job controller's worker thread, every callback below runs on
    # the GUI thread (wx.CallAfter), and the result becomes an E2 preview.
    # ------------------------------------------------------------------
    @staticmethod
    def _ai_request_message(code) -> str:
        return {
            ai_provider.REQUEST_UNAVAILABLE: _("The model is not installed."),
            ai_provider.REQUEST_NEEDS_PROMPT: _("Add at least one point or a bounding box."),
            ai_provider.REQUEST_PROMPT_UNSUPPORTED: _("This model does not support this kind of prompt."),
            ai_provider.REQUEST_DEVICE_UNSUPPORTED: _("This model cannot use the selected device."),
            ai_provider.REQUEST_NO_VOLUME: _("No project loaded."),
            ai_provider.REQUEST_STRUCTURE_UNKNOWN: _("Choose a structure from the list."),
            ai_provider.REQUEST_MODE_UNSUPPORTED: _("This model does not support the selected mode."),
            ai_provider.REQUEST_ORIENTATION_UNKNOWN: _(
                "The patient orientation of this volume is unknown - only axial DICOM series are supported."),
        }.get(code, _("AI processing failed."))

    @staticmethod
    def _ai_unavailable_message(info) -> str:
        code = (info.unavailable_reason or "").split(":", 1)[0].strip()
        name = info.display_name or info.provider_id
        return {
            ai_provider.REASON_PACKAGE_MISSING: _("{name} is not installed."),
            ai_provider.REASON_WEIGHTS: _("The {name} model is not ready."),
            ai_provider.REASON_DEPENDENCY: _("{name}: a required library is missing or broken."),
            ai_provider.REASON_API: _("The installed {name} version is not compatible."),
        }.get(code, _("{name} is not available.")).format(name=name)

    @staticmethod
    def _ai_candidate_message(code) -> str:
        return {
            ai_bridge.CANDIDATE_SHAPE: _("AI result rejected: its size does not match the image volume."),
            ai_bridge.CANDIDATE_DTYPE: _("AI result rejected: unsupported data type."),
            ai_bridge.CANDIDATE_NON_FINITE: _("AI result rejected: it contains invalid values."),
            ai_bridge.CANDIDATE_NOT_BINARY: _("AI result rejected: it is not a binary mask."),
        }.get(code, _("AI processing failed."))

    def _ai_enabled(self) -> bool:
        return self.cb_enable_ai.GetValue()

    def _selected_ai_provider_id(self):
        index = self.choice_ai_model.GetSelection()
        if 0 <= index < len(self._ai_provider_ids):
            return self._ai_provider_ids[index]
        return None

    def _selected_ai_device(self) -> str:
        index = self.choice_ai_device.GetSelection()
        return self._ai_devices[index] if 0 <= index < len(self._ai_devices) else DeviceKind.AUTO

    def _on_enable_ai_toggle(self, event):
        if self._ai_enabled():
            if self._ai_registry is None:
                from ..core.ai import registry as ai_registry

                self._ai_registry = ai_registry.load_known_providers(ai_registry.AIProviderRegistry())
            if self._ai_jobs is None:
                self._ai_jobs = ai_jobs.AIInferenceJobController(dispatch=wx.CallAfter)
                self._ai_jobs.listener = self._on_ai_event
            self._ai_registry.probe_all()
            self._refresh_ai_models()
        else:
            self.controller.picker.remove_callback(self._on_ai_point_picked)
            self.btn_ai_pick_point.SetValue(False)
            if self._ai_jobs is not None and self._ai_jobs.is_busy():
                self._on_ai_cancel(None)
            self.lbl_ai_status.SetLabel(_("Off"))
        self._update_ai_controls()

    def _refresh_ai_models(self):
        """Dropdown = available providers only. With none, say why."""
        infos = self._ai_registry.list_providers() if self._ai_registry is not None else []
        available = [i for i in infos if i.available]
        self._ai_provider_ids = [i.provider_id for i in available]
        self.choice_ai_model.Set([i.display_name for i in available] or [_("(none)")])
        self.choice_ai_model.SetSelection(0)
        for info in infos:
            if not info.available:
                print(f"ROI Viewer: AI provider '{info.provider_id}' unavailable - {info.unavailable_reason}")
        if available:
            self.lbl_ai_status.SetLabel(_("Ready."))
        elif infos:
            self.lbl_ai_status.SetLabel(self._ai_unavailable_message(infos[0]))
        else:
            self.lbl_ai_status.SetLabel(_("No compatible AI model."))
        self._refresh_ai_devices()

    def _refresh_ai_devices(self):
        pid = self._selected_ai_provider_id()
        info = self._ai_registry.info(pid) if (pid and self._ai_registry is not None) else None
        devices = [DeviceKind.AUTO] + [d for d in (info.supported_devices if info else ())
                                       if d in (DeviceKind.CPU, DeviceKind.CUDA)]
        self._ai_devices = devices
        self.choice_ai_device.Set([_("Auto") if d == DeviceKind.AUTO else d.upper() for d in devices])
        self.choice_ai_device.SetSelection(0)
        # E6b provider parameters
        choices = info.parameter_choices if info else {}
        self._ai_structures = list(choices.get(ai_provider.OPTION_STRUCTURE, ()))
        self.combo_ai_structure.Set(self._ai_structures)
        self.combo_ai_structure.AutoComplete(self._ai_structures)
        self.combo_ai_structure.SetValue("")
        self._ai_modes = list(choices.get(ai_provider.OPTION_MODE, ()))
        labels = {ai_provider.MODE_STANDARD: _("Standard accuracy"), ai_provider.MODE_FAST: _("Fast / less memory")}
        self.choice_ai_mode.Set([labels.get(m, m) for m in self._ai_modes] or [_("Standard accuracy")])
        self.choice_ai_mode.SetSelection(0)

    def _selected_ai_info(self):
        pid = self._selected_ai_provider_id()
        return self._ai_registry.info(pid) if (pid and self._ai_registry is not None) else None

    def _selected_ai_mode(self):
        index = self.choice_ai_mode.GetSelection()
        return self._ai_modes[index] if 0 <= index < len(self._ai_modes) else ai_provider.MODE_STANDARD

    @staticmethod
    def _ai_volume_orientation():
        """(patient_orientation, acquisition) as InVesalius recorded them at
        import (Project; see the TotalSegmentator provider's grid contract)."""
        try:
            import invesalius.constants as const
            import invesalius.project as prj

            proj = prj.Project()
            names = {const.AXIAL: "AXIAL", const.CORONAL: "CORONAL", const.SAGITAL: "SAGITTAL"}
            acquisition = getattr(proj, "original_orientation", "")
            acquisition = names.get(acquisition, acquisition if isinstance(acquisition, str) else "")
            return getattr(proj, "patient_orientation", None), str(acquisition).upper()
        except Exception as e:
            print(f"ROI Viewer: AI could not read the volume orientation - {e}")
            return None, ""

    def _on_ai_model_changed(self, event):
        self._refresh_ai_devices()
        self._update_ai_controls()

    def _update_ai_controls(self):
        enabled = self._ai_enabled()
        has_model = enabled and self._selected_ai_provider_id() is not None
        busy = self._ai_jobs is not None and self._ai_jobs.is_busy()
        running = busy and self._ai_jobs.state in (ai_jobs.AIJobState.PREPARING, ai_jobs.AIJobState.RUNNING)
        info = self._selected_ai_info() if has_model else None
        # E6b: a provider that consumes no prompts (e.g. TotalSegmentator) gets
        # none - the point/box controls are disabled, never faked into it.
        uses_prompts = enabled and (info is None or bool(info.supported_prompt_types))
        for widget in (self.rb_ai_positive, self.rb_ai_negative, self.btn_ai_pick_point, self.btn_ai_cursor_point,
                       self.btn_ai_corner1, self.btn_ai_corner2, self.btn_ai_clear):
            widget.Enable(uses_prompts)
        self.choice_ai_model.Enable(has_model)
        self.choice_ai_device.Enable(has_model)
        self.combo_ai_structure.Enable(has_model and bool(self._ai_structures))
        self.choice_ai_mode.Enable(has_model and len(self._ai_modes) > 1)
        # Only what the selected model really uses is shown (E6b review):
        # prompts for prompt-driven models, structure/mode where declared,
        # the install hint while no model is available.
        self._ai_show(self._ai_prompt_sizer, has_model and uses_prompts)
        self._ai_show(self._ai_structure_row, has_model and bool(self._ai_structures))
        self._ai_show(self._ai_mode_row, has_model and len(self._ai_modes) > 1)
        self._ai_show(self.lbl_ai_help, enabled and not has_model)
        self.btn_ai_run.Enable(has_model and not busy)
        self.btn_ai_cancel.Enable(running)
        self._update_ai_prompt_label()

    def _ai_show(self, item, show: bool):
        if bool(self._ai_sizer.IsShown(item)) == bool(show):
            return
        self._ai_sizer.Show(item, bool(show), recursive=True)
        self._ai_sizer.Layout()
        self._ai_pane.InvalidateBestSize()
        if not self._ai_pane.IsCollapsed():
            self._on_section_toggled(None)

    def _update_ai_prompt_label(self):
        prompts = self._ai_prompts
        if not self._ai_enabled():
            self.lbl_ai_prompts.SetLabel("")
            return
        if prompts.box is not None:
            box = _("set")
        elif prompts.corner1 is not None or prompts.corner2 is not None:
            box = _("one corner")
        else:
            box = _("none")
        self.lbl_ai_prompts.SetLabel(_("Points: {inside} inside, {excluded} excluded · Box: {box}").format(
            inside=prompts.positive_count, excluded=prompts.negative_count, box=box))

    def _ai_volume_geometry(self):
        """(spacing_xyz, shape_zyx) of the loaded volume, or None."""
        from ..interface.project_interface import ProjectInterface

        pi = ProjectInterface()
        volume = pi.get_volume_data()
        if volume is None:
            return None
        return pi.get_spacing(), tuple(volume.shape)

    def _ai_add_prompt(self, world_slice, corner=None):
        """world_slice: slice-frame (x, y, z) mm - core/coordinates.py."""
        geometry = self._ai_volume_geometry()
        if geometry is None:
            self.lbl_ai_status.SetLabel(_("No project loaded."))
            return
        spacing, shape = geometry
        try:
            if corner is None:
                self._ai_prompts.add_point(world_slice, spacing, shape, self.rb_ai_positive.GetValue())
            else:
                self._ai_prompts.set_corner(corner, world_slice, spacing, shape)
        except PromptOutOfVolume as e:
            print(f"ROI Viewer: AI prompt ignored - {e}")
            self.lbl_ai_status.SetLabel(_("Outside the image volume - ignored."))
            return
        self._update_ai_prompt_label()

    def _ai_cursor_position(self):
        position = self.controller.get_crosshair_position()
        if position is None:
            self.lbl_ai_status.SetLabel(_("No 2D cursor position yet - click a 2D view first."))
        return position

    def _on_ai_toggle_pick_point(self, event):
        if not self.btn_ai_pick_point.GetValue():
            self.controller.picker.remove_callback(self._on_ai_point_picked)
            return
        if not self.controller.ensure_picker_initialized():
            self.btn_ai_pick_point.SetValue(False)
            self.lbl_ai_status.SetLabel(_("No 3D view available yet"))
            return
        self.controller.picker.add_callback(self._on_ai_point_picked)
        self.controller.picker.enable()
        self.lbl_ai_status.SetLabel(_("Click a point in the 3D view..."))

    def _on_ai_point_picked(self, world_point):
        """Picker callback (one-shot). The pick is in the y-flipped 3D view
        frame; prompts are stored in the slice frame."""
        import math

        from ..core.coordinates import view_to_slice

        self.controller.picker.remove_callback(self._on_ai_point_picked)
        wx.CallAfter(self.btn_ai_pick_point.SetValue, False)
        if world_point is None or len(world_point) != 3 or not all(math.isfinite(c) for c in world_point):
            self.lbl_ai_status.SetLabel(_("Invalid pick position - try again"))
            return
        self._ai_add_prompt(view_to_slice(world_point))

    def _on_ai_cursor_point(self, event):
        position = self._ai_cursor_position()
        if position is not None:
            self._ai_add_prompt(position)

    def _on_ai_corner(self, which):
        position = self._ai_cursor_position()
        if position is not None:
            self._ai_add_prompt(position, corner=which)

    def _on_ai_clear(self, event):
        self._ai_prompts.clear()
        self._update_ai_prompt_label()

    def _on_ai_run(self, event):
        import time

        import invesalius.data.slice_ as sl
        from ..core.ai.types import AIInferenceRequest, read_only_volume
        from ..interface.project_interface import ProjectInterface

        pid = self._selected_ai_provider_id()
        provider = self._ai_registry.get(pid) if (pid and self._ai_registry is not None) else None
        if provider is None or self._ai_jobs is None:
            self.lbl_ai_status.SetLabel(_("No compatible AI model."))
            return
        if self._ai_jobs.is_busy():
            self.lbl_ai_status.SetLabel(_("The previous AI job is still stopping - try again shortly."))
            return
        if sl.Slice().current_mask is None:
            wx.MessageBox(
                _("Create or select a mask first - the preview overlay needs a current mask."),
                _("No mask selected"), wx.OK | wx.ICON_WARNING,
            )
            return
        pi = ProjectInterface()
        volume = pi.get_volume_data()
        if volume is None:
            self.lbl_ai_status.SetLabel(_("No project loaded."))
            return
        spacing = pi.get_spacing()
        info = self._ai_registry.info(pid)
        options = {}
        if self._ai_structures:
            structure = self.combo_ai_structure.GetValue().strip()
            if structure not in self._ai_structures:
                self.lbl_ai_status.SetLabel(_("Choose a structure from the list."))
                return
            options[ai_provider.OPTION_STRUCTURE] = structure
        if self._ai_modes:
            options[ai_provider.OPTION_MODE] = self._selected_ai_mode()
        orientation, acquisition = self._ai_volume_orientation()
        options[ai_provider.OPTION_PATIENT_ORIENTATION] = orientation
        options[ai_provider.OPTION_ACQUISITION] = acquisition
        from ..core.ai.types import AIPrompts

        prompts = self._ai_prompts.snapshot() if (info and info.supported_prompt_types) else AIPrompts()
        request = AIInferenceRequest(volume=read_only_volume(volume, spacing), prompts=prompts,
                                     device=self._selected_ai_device(), options=options)

        # A new preview replaces the current one (as for Otsu/Region Growing).
        self._clear_preview_overlay()
        self.preview_mgr.cancel()
        self._ai_preview_generation = self.preview_mgr.new_generation()
        self._ai_run = {
            "provider_id": pid, "provider_name": info.display_name if info else pid,
            "prompt_count": request.prompts.count, "device": request.device,
            "shape": tuple(volume.shape), "spacing": spacing, "started": time.perf_counter(),
            "structure": options.get(ai_provider.OPTION_STRUCTURE), "mode": options.get(ai_provider.OPTION_MODE),
            "interruptible": bool(info and Capability.INTERRUPTIBLE in info.capabilities),
        }
        self.lbl_preview_status.SetLabel(_("Computing…"))
        job = self._ai_jobs.start(provider, request)
        if job is None:
            self.preview_mgr.cancel()
            self.lbl_preview_status.SetLabel(_("Idle"))
        self._update_preview_buttons()
        self._update_ai_controls()

    def _on_ai_cancel(self, event):
        if self._ai_jobs is None:
            return
        self._ai_jobs.cancel()
        if (self._ai_preview_generation is not None
                and not self.preview_mgr.is_stale(self._ai_preview_generation)
                and self.preview_mgr.state == segmentation_preview.PreviewState.COMPUTING):
            self.preview_mgr.cancel()
            self.lbl_preview_status.SetLabel(_("Idle"))
            self._update_preview_buttons()
        if (self._ai_run or {}).get("interruptible", False) or not self._ai_jobs.is_busy():
            self.lbl_ai_status.SetLabel(_("AI processing cancelled."))
        else:
            # E6b: the model cannot be stopped mid-run - say what really happens.
            self.lbl_ai_status.SetLabel(_(
                "Cancel requested - the running model finishes in the background and its result is discarded."))
        self._update_ai_controls()

    def _on_ai_event(self, event, job, payload):
        """Job controller listener - GUI thread only (see core/ai/job_controller.py)."""
        try:
            if event == ai_jobs.EVENT_STATE:
                if payload == ai_jobs.AIJobState.PREPARING:
                    self.lbl_ai_status.SetLabel(_("Preparing…"))
                elif payload == ai_jobs.AIJobState.RUNNING:
                    self.lbl_ai_status.SetLabel(_("Running AI…"))
                elif payload == ai_jobs.AIJobState.CANCELLING:
                    if (self._ai_run or {}).get("interruptible", False):
                        self.lbl_ai_status.SetLabel(_("Stopping AI…"))
                    else:
                        self.lbl_ai_status.SetLabel(_("Waiting for the running model to finish…"))
                self._update_ai_controls()
            elif event == ai_jobs.EVENT_PROGRESS:
                fraction, stage = payload
                if fraction is None:  # the provider reports stages only - no percentage is shown
                    name = (self._ai_run or {}).get("provider_name") or "AI"
                    self.lbl_ai_status.SetLabel({
                        ai_provider.STAGE_PREPARING: _("Preparing data…"),
                        ai_provider.STAGE_RUNNING: _("Running {name}…").format(name=name),
                        ai_provider.STAGE_MAPPING: _("Mapping the result…"),
                    }.get(stage, _("Running AI…")))
                else:
                    fraction = max(0.0, min(1.0, fraction))
                    self.lbl_ai_status.SetLabel(
                        _("Running AI… {percent}%").format(percent=int(round(fraction * 100))))
            elif event == ai_jobs.EVENT_RESULT:
                self._on_ai_result(job, payload)
            elif event == ai_jobs.EVENT_FAILED:
                self._on_ai_failed(payload)
        except RuntimeError as e:  # widget already destroyed during shutdown
            print(f"ROI Viewer: AI UI update skipped - {e}")

    def _on_ai_failed(self, error):
        # A string is a request-check code; an exception is a provider failure.
        self.lbl_ai_status.SetLabel(
            self._ai_request_message(error) if isinstance(error, str) else _("AI processing failed."))
        if self._ai_jobs is not None:
            self._ai_jobs.consume_result()
        if self._ai_preview_generation is not None and not self.preview_mgr.is_stale(self._ai_preview_generation):
            self.preview_mgr.cancel()
            self.lbl_preview_status.SetLabel(_("Idle"))
        self._update_preview_buttons()
        self._update_ai_controls()

    def _on_ai_result(self, job, result):
        """A current (not stale) AI result: validate it on the native grid
        and show it as an E2 preview. No mask is created here."""
        import os
        import time

        import invesalius.data.slice_ as sl

        self._ai_jobs.consume_result()
        run = self._ai_run or {}
        if self._ai_preview_generation is None or self.preview_mgr.is_stale(self._ai_preview_generation):
            print("ROI Viewer: discarded AI result - its preview was cancelled or replaced")
            self._update_ai_controls()
            return
        try:
            foreground = ai_bridge.validate_candidate(result.mask, run.get("shape"))
        except ai_bridge.CandidateError as e:
            print(f"ROI Viewer: AI result rejected - {e}")
            self.lbl_ai_status.SetLabel(self._ai_candidate_message(e.code))
            self.preview_mgr.cancel()
            self.lbl_preview_status.SetLabel(_("Idle"))
            self._update_preview_buttons()
            self._update_ai_controls()
            return
        runtime = time.perf_counter() - run.get("started", time.perf_counter())
        if not foreground.any():
            self.lbl_ai_status.SetLabel(_("AI found no region."))
            self.preview_mgr.cancel()
            self.lbl_preview_status.SetLabel(_("Idle"))
            self._update_preview_buttons()
            self._update_ai_controls()
            return

        temp_file, array = sl.Slice().create_temp_mask()
        array[:] = ai_bridge.preview_values(foreground)
        stats = self.controller.seg_mgr.region_stats(foreground, run.get("spacing"))
        metadata = {
            "provider_id": run.get("provider_id"), "provider_name": run.get("provider_name"),
            "model_name": result.model_name, "model_version": result.model_version,
            "device": result.device_used or run.get("device"), "runtime_seconds": runtime,
            "prompt_count": run.get("prompt_count", 0),
            "structure": run.get("structure"), "mode": run.get("mode"),
            "provider_details": dict(getattr(result, "extra", {}) or {}),
        }
        if not self.preview_mgr.set_ai_preview(self._ai_preview_generation, array, metadata, stats, name="AI Preview"):
            try:
                os.remove(temp_file)
            except OSError:
                pass
            return
        self._preview_temp_file = temp_file
        self._show_preview_overlay(array)
        self.lbl_preview_status.SetLabel(_("AI preview: {info}.").format(info=self._region_info(stats)))
        self.lbl_ai_status.SetLabel(_("Done in {seconds} s.").format(seconds=fmt_float(runtime, 1)))
        print(f"ROI Viewer: AI preview ready - {metadata}")
        self._update_preview_buttons()
        self._update_ai_controls()
        self._mark_preview_3d_dirty("AI preview ready")

    def _commit_ai_preview(self, preview_array) -> Optional[str]:
        """Accept: the previewed candidate itself becomes a new real mask
        (core/native_mask.commit_preview_array_to_new_mask - the same commit
        Region Growing uses). Returns the name, or None on failure."""
        try:
            import numpy as np
            import invesalius.constants as const
            from ..interface.project_interface import ProjectInterface

            mask_count = len(ProjectInterface().get_mask_dict())
            colour = const.MASK_COLOUR[mask_count % len(const.MASK_COLOUR)]
            structure = (self.preview_mgr.ai_metadata or {}).get("structure")
            # E6b: "AI - <canonical class name>" (not translated); generic otherwise.
            name = f"AI - {structure}" if structure else f"AI Segmentation {mask_count + 1}"
            mask = native_mask.commit_preview_array_to_new_mask(np.asarray(preview_array) > 0, name, colour)
            return name if mask is not None else None
        except Exception as e:
            print(f"ROI Viewer: committing AI preview failed - {e}")
            return None

    def shutdown_ai(self):
        """Plugin close / destroy: no AI callback may reach this panel
        afterwards (a late result is dropped), models are released.
        Idempotent."""
        self.controller.picker.remove_callback(self._on_ai_point_picked)
        if self._ai_jobs is not None:
            self._ai_jobs.shutdown()
        if self._ai_registry is not None:
            self._ai_registry.close_all()
        self._ai_prompts.clear()

    def reset_ai_session(self):
        """Project close/load: stop any AI job, forget prompts, release
        provider resources. The AI checkbox keeps its state."""
        self.controller.picker.remove_callback(self._on_ai_point_picked)
        if self._ai_jobs is not None:
            self._ai_jobs.cancel()
        if self._ai_registry is not None:
            self._ai_registry.close_all()
        self._ai_prompts.clear()
        self._ai_run = None
        try:
            self.btn_ai_pick_point.SetValue(False)
            self._update_ai_controls()
        except RuntimeError as e:
            print(f"ROI Viewer: AI widget reset skipped (likely app shutdown) - {e}")

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
            self.status_text.SetLabel(_("No mask selected."))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None:
            editor = self.controller.mask_mgr.create_editor(mask.index, mask.matrix.shape)
        editor.mask = mask.matrix
        editor.save_state()
        self.status_text.SetLabel(_("Restore point saved."))

    def _roi_locked_for_mask(self, mask_index) -> bool:
        """Thin wx-layer wrapper - the actual decision logic lives in
        core/roi_manager.ROIManager.is_locked_for_mask_index() so it's
        unit-testable without wx (see that method's docstring)."""
        return self.controller.roi_mgr.is_locked_for_mask_index(mask_index)

    def _on_undo(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("No mask selected."))
            return
        if self._roi_locked_for_mask(mask.index):
            self.status_text.SetLabel(_("ROI is locked."))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None or not editor.undo_manager.can_undo():
            self.status_text.SetLabel(_("Nothing to undo."))
            return
        previous = editor.undo_manager.undo(mask.matrix)
        if previous is not None:
            mask.matrix[:] = previous
            self._refresh_after_edit()
            self.status_text.SetLabel(_("Undone."))

    def _on_redo(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("No mask selected."))
            return
        if self._roi_locked_for_mask(mask.index):
            self.status_text.SetLabel(_("ROI is locked."))
            return
        editor = self.controller.mask_mgr.get_editor(mask.index)
        if editor is None or not editor.undo_manager.can_redo():
            self.status_text.SetLabel(_("Nothing to redo."))
            return
        nxt = editor.undo_manager.redo(mask.matrix)
        if nxt is not None:
            mask.matrix[:] = nxt
            self._refresh_after_edit()
            self.status_text.SetLabel(_("Redone."))

    def _refresh_after_edit(self):
        # E4: single shared real-mutation refresh point (classic region
        # growing commit, E2 Accept, Undo, Redo, E3 cleanup all call
        # this) - one place to mark the live 3D preview dirty (Section
        # 16) rather than duplicating the call at every one of those
        # sites individually.
        self._mark_preview_3d_dirty("mask edited")
        try:
            import invesalius.data.slice_ as sl
            from invesalius.pubsub import pub as Publisher

            # The 2D views cache the shown mask slice; without discarding
            # it, "Reload actual slice" redraws the pre-edit slice.
            native_mask.discard_slice_buffers(sl.Slice())
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
                    _("Create or select a mask first."),
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
                self.btn_toggle_brush.SetLabel(_("Disable brush"))
                self.status_text.SetLabel(_("Brush on - paint on the 2D views."))
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
        self.btn_toggle_brush.SetLabel(_("Enable brush"))
        self.status_text.SetLabel(_("Ready."))

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
        # roi_panel.ROIViewerPanel.shutdown(): don't leave an armed
        # seed-pick callback registered on the shared picker pointing
        # back into this (about to be destroyed) panel.
        self.controller.picker.remove_callback(self._on_seed_picked)
        self.shutdown_ai()  # E6 - already done by the frame's close handler; idempotent
        # E2: always clear any active/pending preview on destroy,
        # regardless of brush state - same "never leave native/plugin
        # state stuck across a close" reasoning as the brush cleanup
        # immediately below.
        self.cancel_preview()
        # E4: stop the debounce timer and unregister the real
        # Mask.add_modified_callback() - the renderer-attached actor
        # itself is detached separately by
        # roi_panel.ROIViewerPanel.shutdown() (mirrors marker_3d/
        # slice_planes_3d exactly).
        self.cancel_live_preview_3d()
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
                prefix += _("[Locked]") + " "
            if solo_id == rid:
                prefix += _("[Only this]") + " "
            labels.append(_("{prefix}{name} (mask #{index})").format(prefix=prefix, name=roi.name, index=roi.mask_index))
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
        name = roi.name if roi is not None else _("(none)")
        # Mirrored on the "Phân đoạn" page, where post-processing, brush
        # and undo act on this same ROI.
        self.lbl_active_roi.SetLabel(name)
        self.lbl_seg_current_roi.SetLabel(name)
        if roi is None:
            self.roi_color_swatch.SetBackgroundColour(wx.Colour(200, 200, 200))
        else:
            self.roi_color_swatch.SetBackgroundColour(mask_colour_to_wx(roi.color))
        self.roi_color_swatch.Refresh()

    def _region_info(self, stats) -> str:
        """Short, localized region summary: '12.345 voxels (3,2% of volume), 1.234,5 mm³'."""
        info = _("{voxels} voxels ({percent}% of volume)").format(
            voxels=fmt_int(stats["voxel_count"]), percent=fmt_float(stats["fraction"] * 100, 1))
        if "volume_mm3" in stats:
            info += ", " + fmt_float(stats["volume_mm3"], 1) + " mm³"
        return info

    def _e4_source_label(self, kind) -> str:
        if kind == "otsu_preview":
            return _("Otsu preview")
        if kind == "region_growing_preview":
            return _("Region growing preview")
        if kind == "ai_preview":
            return _("AI preview")
        return _("Current ROI")

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
            self.roi_status.SetLabel(_("Current ROI: {name}.").format(name=roi.name))
            # E4 (Section 27): switching ROI while live preview is
            # enabled must rebuild for the NEW source, not leave the OLD
            # ROI's mesh attached.
            self._mark_preview_3d_dirty("ROI selection changed")
            # E5B (Section 23): switching ROI while clipping is enabled
            # with target=Current ROI Final Surface must detach from the
            # OLD surface's mapper and re-resolve for the NEW one (or
            # report "no final surface" honestly) - never leave a stale
            # ROI unexpectedly clipped.
            if hasattr(self.controller, "interaction_panel"):
                try:
                    self.controller.interaction_panel.refresh_clipping_target()
                except Exception as e:
                    print(f"ROI Viewer: E5 clipping target refresh on ROI switch failed - {e}")
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
                _("ROI '{name}' is locked. Unlock it before deleting.").format(name=roi.name),
                _("ROI locked"), wx.OK | wx.ICON_WARNING,
            )
            return
        confirm = wx.MessageBox(
            _("Delete ROI '{name}' and its mask? This cannot be undone.").format(name=roi.name),
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
        self.roi_status.SetLabel(_("Deleted '{name}'.").format(name=roi.name))

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
        self.roi_status.SetLabel(_("Locked '{name}'.").format(name=roi.name))

    def _on_roi_unlock(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            wx.MessageBox(_("Select a ROI first."), _("No selection"), wx.OK | wx.ICON_WARNING)
            return
        self.controller.roi_mgr.set_locked(rid, False)
        self._refresh_roi_list()
        roi = self.controller.roi_mgr.get_roi(rid)
        self.roi_status.SetLabel(_("Unlocked '{name}'.").format(name=roi.name))

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
            self.roi_status.SetLabel(_("Showing only '{name}'.").format(name=roi.name))
        else:
            changes = self.controller.roi_mgr.exit_solo()
            self._apply_visibility_changes(changes)
            self.roi_status.SetLabel(_("Previous visibility restored."))
        self._refresh_roi_list()

    def _on_roi_show_all(self, event):
        changes = self.controller.roi_mgr.show_all()
        self._apply_visibility_changes(changes)
        self._refresh_roi_list()
        self.roi_status.SetLabel(_("All ROIs shown."))

    def _on_roi_hide_all(self, event):
        changes = self.controller.roi_mgr.hide_all()
        self._apply_visibility_changes(changes)
        self._refresh_roi_list()
        self.roi_status.SetLabel(_("All ROIs hidden."))

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
            # E5B (Section 16/24): remember which mask THIS build is for
            # so the next real "Update surface info in GUI" event (fired
            # with the actual just-created Surface object) can be safely
            # attributed to it - see _on_surface_info_updated() and this
            # panel's __init__ NOTE for why mask_index cannot simply be
            # assumed to equal the resulting surface's own index.
            self._pending_surface_build_mask_index = mask_index
            Publisher.sendMessage("Create surface from index", surface_parameters=surface_options)
            self.roi_status.SetLabel(
                _("Rebuilding the 3D surface of '{name}'…").format(name=getattr(mask, "name", mask_index))
            )
        except Exception as e:
            wx.MessageBox(_("Surface update failed."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: surface update failed - {e}")

    # ------------------------------------------------------------------
    # E5B (Advanced Segmentation Enhancement Track, enhancement/advanced-
    # segmentation branch ONLY): mask_index -> surface_index resolution
    # for the "Current ROI Final Surface" clipping target.
    # ------------------------------------------------------------------
    def _subscribe_surface_info_once(self):
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.subscribe(self._on_surface_info_updated, "Update surface info in GUI")
        except ImportError:
            pass

    def _on_surface_info_updated(self, surface):
        """
        Real pubsub handler for "Update surface info in GUI" - fired by
        invesalius/data/surface.py's AddNewActor()/CreateSurfaceFromPolydata()
        with the actual just-created/just-updated real Surface object
        (has a real `.index`). Only attributed to a mask if THIS panel's
        own _on_update_surface() is the one that requested it (Section
        16 - never guess a mapping for a surface build this plugin did
        not itself trigger, e.g. one made via InVesalius's native
        Surface tab).
        """
        if self._pending_surface_build_mask_index is None:
            return
        mask_index = self._pending_surface_build_mask_index
        self._pending_surface_build_mask_index = None
        try:
            self._roi_surface_index[mask_index] = surface.index
        except AttributeError:
            return
        if hasattr(self.controller, "interaction_panel"):
            try:
                self.controller.interaction_panel.refresh_clipping_target()
            except Exception as e:
                print(f"ROI Viewer: E5 clipping target refresh after surface build failed - {e}")

    def get_surface_index_for_mask(self, mask_index) -> Optional[int]:
        """Public accessor for InteractionPanel's E5B clipping target
        resolution (Section 18/23) - returns None if this plugin has
        never itself (re)built a surface for this mask_index this
        session (a real, honest "no final surface for selected ROI"
        case, not an error)."""
        return self._roi_surface_index.get(mask_index)

    # ------------------------------------------------------------------
    # E3 (Advanced Segmentation Enhancement Track, enhancement/advanced-
    # segmentation branch ONLY): post-processing / cleanup (Current ROI)
    # ------------------------------------------------------------------
    def _run_cleanup(self, op_callable, op_label):
        """
        Shared real commit path for all 4 E3 cleanup operations - runs
        `op_callable(logical_region) -> (result, op_info)` (one of
        core/segmentation_cleanup.py's pure functions, already bound
        with its own parameters by the caller) against the real current
        mask's logical voxel region, and if the result actually differs:

        1. Refuses if the current ROI is locked (E1 - same pure
           decision `ROIManager.is_locked_for_mask_index()` the brush/
           undo/redo/delete guards already delegate to).
        2. Saves exactly ONE real Undo checkpoint via the EXISTING
           `controller.mask_mgr`/`UndoRedoManager` (Section 16 - no
           E3-specific undo stack).
        3. Reads the mask through core/native_mask.logical_foreground():
           unvisited slices of a lazily computed threshold mask are
           computed first (native do_threshold_to_all_slices()), and
           foreground is "value > 127", so brush-erased voxels (value 1)
           stay background.
        4. Writes the result with native_mask.write_logical_region():
           exactly 0/255 in mask.matrix[1:, 1:, 1:], all three sentinel
           planes marked computed, 2D slice buffers discarded.
           *Corrected 30/09/2026*: this used to read "!= 0" without
           computing unvisited slices (a fresh threshold mask read as
           mostly empty, and the result was then written back as final)
           and marked only the axial sentinels, on the belief that only
           do_threshold_to_all_slices() re-derives slices - but
           get_mask_slice() also re-thresholds any coronal/sagittal
           plane whose own sentinel is 0 when a 2D view shows it, which
           undid the cleanup on that plane.
        5. Sets `mask.was_edited = True` (Phase 08 D9/C7 policy - see
           choose_surface_algorithm()) but deliberately does NOT call
           "Create surface from index" - the surface intentionally goes
           stale, exactly like brush/undo/region-growing already do;
           the status message tells the user how to refresh it.

        If the result is logically identical to the input (Section 17 -
        "No-op policy"): no checkpoint, no mutation, no was_edited flip,
        no dirty flag - status simply reports nothing changed.
        """
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.lbl_cleanup_status.SetLabel(_("No mask selected."))
            return
        if self._roi_locked_for_mask(mask.index):
            wx.MessageBox(
                _("This ROI is locked. Unlock it before running cleanup."),
                _("ROI locked"), wx.OK | wx.ICON_WARNING,
            )
            return
        try:
            import numpy as np
            from ..interface.project_interface import ProjectInterface

            import invesalius.data.slice_ as sl

            s = sl.Slice()
            before_fg = native_mask.logical_foreground(s, mask)
            before = before_fg.astype(np.uint8) * 255
            result, op_info = op_callable(before)

            if np.array_equal(result > 0, before_fg):
                self.lbl_cleanup_status.SetLabel(_("No changes were needed."))
                return

            editor = self.controller.mask_mgr.get_editor(mask.index)
            if editor is None:
                editor = self.controller.mask_mgr.create_editor(mask.index, mask.matrix.shape)
            editor.mask = mask.matrix
            editor.save_state()  # exactly one checkpoint, same real UndoRedoManager as Save Checkpoint/Undo/Redo above

            native_mask.write_logical_region(s, mask, result > 0)  # also sets was_edited - see docstring

            pi = ProjectInterface()
            stats = segmentation_cleanup.cleanup_stats(before, result, pi.get_spacing())
            delta = stats["delta_percent"]
            self.lbl_cleanup_status.SetLabel(
                _("{operation}: {before} → {after} voxels ({sign}{delta}%). 3D surface not rebuilt.").format(
                    operation=op_label, before=fmt_int(stats["before_voxels"]), after=fmt_int(stats["after_voxels"]),
                    sign="+" if delta >= 0 else "−", delta=fmt_float(abs(delta), 2))
            )
            print(f"ROI Viewer: {op_label} - {op_info}")
            self._refresh_after_edit()
        except ValueError as e:
            # Real input-validation rejection (e.g. remove_small_components's
            # min_voxels<1, smooth_binary_mask's out-of-range iterations) -
            # a clear, specific message rather than the generic one below.
            self.lbl_cleanup_status.SetLabel(_("Invalid post-processing parameters."))
            print(f"ROI Viewer: post-processing rejected - {e}")
        except Exception as e:
            self.lbl_cleanup_status.SetLabel(_("Post-processing failed."))
            print(f"ROI Viewer: {op_label} failed - {e}")

    def _on_cleanup_keep_largest(self, event):
        self._run_cleanup(
            lambda region: segmentation_cleanup.keep_largest_component(region),
            _("Keep largest connected component"),
        )

    def _on_cleanup_remove_small(self, event):
        min_voxels = self.spin_min_component_size.GetValue()
        self._run_cleanup(
            lambda region: segmentation_cleanup.remove_small_components(region, min_voxels=min_voxels),
            _("Remove small islands"),
        )

    def _on_cleanup_fill_holes(self, event):
        self._run_cleanup(
            lambda region: segmentation_cleanup.fill_holes(region),
            _("Fill holes"),
        )

    def _on_cleanup_smooth(self, event):
        iterations = self.spin_smooth_iterations.GetValue()
        self._run_cleanup(
            lambda region: segmentation_cleanup.smooth_binary_mask(region, iterations=iterations),
            _("Smooth mask"),
        )

    # ------------------------------------------------------------------
    # E4 (Advanced Segmentation Enhancement Track, enhancement/advanced-
    # segmentation branch ONLY): fast, non-authoritative live 3D preview.
    # ------------------------------------------------------------------
    def _e4_enabled(self) -> bool:
        return self.cb_enable_live_3d_preview.GetValue()

    def _ensure_modified_callback_registered_for_current_mask(self):
        """Real, source-proven mutation signal (Section 15/30 audit):
        invesalius.data.mask.Mask.add_modified_callback() - a real,
        already-existing, weakref-safe (weakref.WeakMethod) public API,
        fired by invesalius/data/styles.py's OnBrushRelease() on native
        Brush/Eraser mouse-release (confirmed by direct source read: the
        ONLY 2 real call sites of Mask.modified() in the whole codebase
        are both real edit-completion events in styles.py) - not an
        unsafe mouse-hook interception. Re-registers on whichever real
        Mask is current whenever this is called (idempotent - a no-op
        if already registered on the same mask instance)."""
        mask = self._current_mask()
        if mask is self._e4_callback_mask:
            return
        if self._e4_callback_mask is not None:
            try:
                self._e4_callback_mask.remove_modified_callback(self._on_current_mask_modified)
            except Exception:
                pass
        self._e4_callback_mask = mask
        if mask is not None:
            try:
                mask.add_modified_callback(self._on_current_mask_modified)
            except Exception as e:
                print(f"ROI Viewer: could not register E4 mask-modified callback - {e}")

    def _on_current_mask_modified(self):
        """The real callback registered above. wx.CallAfter defers onto
        the main thread (this can fire from whatever thread InVesalius's
        own VTK interactor callback runs on) and is itself wrapped
        defensively - the weakref registration protects against a fully
        garbage-collected panel, but not against firing once more during
        active teardown."""
        try:
            wx.CallAfter(self._mark_preview_3d_dirty, "brush/eraser edit")
        except Exception:
            pass

    def _mark_preview_3d_dirty(self, reason):
        """Single real entry point every plugin-owned mutation that
        should refresh the live 3D preview calls (Section 16) - E3
        cleanup, Undo, Redo, E2 preview ready/cancel/accept, new ROI
        selection, and the real Brush/Eraser callback above. No-op if
        the feature is disabled (Section 18). Restarts the debounce
        timer (Section 19) - rapid successive calls coalesce into
        exactly ONE rebuild, using whatever state is current at the
        moment the timer actually fires (Section 20's "latest generation
        wins" - handled by _trigger_preview_3d_rebuild() always reading
        live state, not anything snapshotted at dirty-mark time)."""
        if not self._e4_enabled():
            return
        self._ensure_modified_callback_registered_for_current_mask()
        self._e4_debounce_timer.Stop()
        self._e4_debounce_timer.StartOnce(self.E4_DEBOUNCE_MS)
        self.lbl_e4_state.SetLabel(_("Waiting for update…"))

    def _on_enable_live_3d_preview_toggle(self, event):
        enabled = self._e4_enabled()
        self.btn_refresh_3d_preview.Enable(enabled)
        if enabled:
            self._ensure_modified_callback_registered_for_current_mask()
            self._trigger_preview_3d_rebuild("enabled")
        else:
            self._e4_debounce_timer.Stop()
            # E5 hardening (test_pending_cancelled_on_disable): a
            # coalesced pending rebuild must never fire once the user
            # explicitly turned live preview off - _finish_preview_3d_
            # build() already re-checks _e4_enabled() before acting on
            # a pending reason, but clearing it here too is immediate
            # and explicit rather than relying solely on that guard.
            self._e4_pending_reason = None
            self.controller.preview_surface_3d.clear()
            self.lbl_e4_state.SetLabel(_("Idle"))
            self.lbl_e4_source.SetLabel("-")
            self.lbl_e4_mesh_info.SetLabel("")
            self.controller.request_render()

    def _on_refresh_3d_preview(self, event):
        self._trigger_preview_3d_rebuild("manual refresh")

    def _on_e4_debounce_timer(self, event):
        self._trigger_preview_3d_rebuild("debounced edit")

    def _select_preview_3d_source(self):
        """Section 12/13 real source priority: an E2 preview that is
        currently PREVIEW_READY wins over Current ROI - read-only
        (preview_mgr.preview_array is never copied into Project().
        mask_dict, never Accepted/Cancelled automatically, never
        modified - E4 only LOOKS at it). Falls back to the real current
        mask's logical voxel region (never the padding - Section 14).
        Returns (array, spacing, source_kind) or (None, None, None) if
        nothing is available to preview."""
        try:
            from ..interface.project_interface import ProjectInterface

            spacing = ProjectInterface().get_spacing()
        except Exception:
            spacing = (1.0, 1.0, 1.0)

        if (
            self.preview_mgr.state == segmentation_preview.PreviewState.PREVIEW_READY
            and self.preview_mgr.preview_array is not None
        ):
            kind = {"otsu": "otsu_preview", "ai": "ai_preview"}.get(
                self.preview_mgr.preview_kind, "region_growing_preview")
            return self.preview_mgr.preview_array, spacing, kind

        mask = self._current_mask()
        if mask is not None and mask.matrix is not None:
            # Native read contract (core/native_mask.py): unvisited slices
            # computed first, brush-erased voxels (value 1) are background.
            try:
                import invesalius.data.slice_ as sl

                return native_mask.logical_foreground(sl.Slice(), mask), spacing, "current_roi"
            except Exception as e:
                print(f"ROI Viewer: E4 could not read the current ROI - {e}")
                return None, None, None

        return None, None, None

    def _trigger_preview_3d_rebuild(self, reason):
        """
        E5 hardening (Section 5 audit - see this file's __init__ NOTE
        for the real gap found: repeated manual "Refresh 3D Preview"
        clicks, or a Refresh landing while a debounced worker was still
        in flight, could previously spawn an unbounded number of
        simultaneous worker threads/~28MB snapshots - generation_id
        alone only discarded stale RESULTS, it never bounded how many
        builds could be concurrently in flight).

        Bounded to "max 1 running build + max 1 latest pending request":
        if a build is already in flight (_e4_build_busy), this call only
        remembers `reason` as the latest pending one and returns
        immediately - it does NOT start a second worker/snapshot. The
        actual build logic lives in _run_preview_3d_rebuild(); every one
        of its exit paths (synchronous early-return OR the async
        worker's callback) goes through _finish_preview_3d_build(),
        which clears the busy flag and - if a newer request arrived
        meanwhile - launches exactly ONE more rebuild for that latest
        reason. generation_id (core/preview_surface_3d.py) is unchanged
        and still separately guards against a stale worker's RESULT
        being applied - this hardening is a second, independent
        guarantee (bounded concurrency), not a replacement for it.
        """
        if not self._e4_enabled():
            return
        if self._e4_build_busy:
            self._e4_pending_reason = reason
            return
        self._e4_build_busy = True
        self._run_preview_3d_rebuild(reason)

    def _run_preview_3d_rebuild(self, reason):
        if not self.controller.ensure_preview_surface_attached():
            self.lbl_e4_state.SetLabel(_("No 3D view available yet"))
            self._finish_preview_3d_build()
            return

        array, spacing, kind = self._select_preview_3d_source()
        if array is None:
            self.controller.preview_surface_3d.clear()
            self.lbl_e4_state.SetLabel(_("No foreground voxels for 3D preview."))
            self.lbl_e4_source.SetLabel("-")
            self.lbl_e4_mesh_info.SetLabel("")
            self.controller.request_render()
            self._finish_preview_3d_build()
            return

        try:
            import numpy as np

            # Real snapshot BEFORE handing off to the worker (Section
            # 14/23): a plain numpy copy, never the live memmap a brush
            # stroke could be actively mutating. Combined with the
            # busy-gate above, at most ONE snapshot (~28MB for a
            # dataset-0051-sized volume) is ever strongly referenced at
            # a time - no unbounded queue, only the latest requested
            # generation matters.
            snapshot = np.array(array)
        except Exception as e:
            self.lbl_e4_state.SetLabel(_("3D preview build failed"))
            print(f"ROI Viewer: E4 snapshot failed - {e}")
            self._finish_preview_3d_build()
            return

        gen = self.controller.preview_surface_3d.new_generation()
        self.lbl_e4_source.SetLabel(self._e4_source_label(kind))
        self.lbl_e4_state.SetLabel(_("Building mesh…"))

        # Same real background-thread + wx.CallAfter pattern already
        # proven by Region Growing/E2 (Section 21). STRICT rule
        # (Section 21/22): this worker only computes plain numpy/VTK
        # data objects it constructs itself (converters.to_vtk/
        # vtkImageFlip/vtkFlyingEdges3D - see build_preview_mesh()'s own
        # docstring) - it NEVER touches a wx widget, the renderer, the
        # actor, or the camera. The only cross-thread handoff is the
        # wx.CallAfter() call itself; _on_preview_3d_built() below is
        # the ONLY place that touches the actor/mapper/renderer. Exactly
        # one worker thread is alive per build thanks to the busy-gate
        # in _trigger_preview_3d_rebuild() above.
        import threading

        def worker():
            try:
                import time
                from ..core.preview_surface_3d import build_preview_mesh

                t0 = time.time()
                polydata = build_preview_mesh(snapshot, spacing)
                elapsed = time.time() - t0
                wx.CallAfter(self._on_preview_3d_built, gen, polydata, kind, elapsed)
            except Exception:
                import traceback

                wx.CallAfter(self.lbl_e4_state.SetLabel, _("3D preview build failed"))
                wx.CallAfter(self._finish_preview_3d_build)
                print("ROI Viewer: E4 preview build failed -\n" + traceback.format_exc())

        threading.Thread(target=worker, daemon=True).start()

    def _finish_preview_3d_build(self):
        """
        The ONE place that clears _e4_build_busy and, if a newer request
        was coalesced while this build ran (_e4_pending_reason), starts
        exactly one more rebuild for it - never more than one, and never
        if live preview was disabled or the panel/project was torn down
        meanwhile (both checked via _e4_enabled(), which already guards
        against a destroyed checkbox widget - see its own docstring).
        Called from every exit path of _run_preview_3d_rebuild() (the
        synchronous early-returns) and from _on_preview_3d_built() /
        the worker's own failure branch (the async completion paths).
        """
        self._e4_build_busy = False
        pending = self._e4_pending_reason
        self._e4_pending_reason = None
        if pending is not None and self._e4_enabled():
            self._trigger_preview_3d_rebuild(pending)

    def _on_preview_3d_built(self, generation_id, polydata, kind, elapsed_seconds):
        """Runs on the main thread (wx.CallAfter). Discards a stale
        result (Section 20) via the manager's own generation guard -
        the SAME real async-race protection concept E2 already
        established (core/segmentation_preview.py), reused here rather
        than reimplemented. Always finishes via _finish_preview_3d_build()
        (Section 5 hardening) regardless of whether the result was
        stale, so the busy-gate is reliably released and any coalesced
        pending request gets its turn."""
        try:
            mgr = self.controller.preview_surface_3d
        except Exception:
            self._finish_preview_3d_build()
            return  # controller/frame already torn down
        ok = mgr.set_polydata_if_current(generation_id, polydata, source_kind=kind)
        if not ok:
            print("ROI Viewer: discarded stale E4 preview mesh result")
            self._finish_preview_3d_build()
            return
        try:
            if polydata is None:
                self.lbl_e4_state.SetLabel(_("No foreground voxels for 3D preview."))
                self.lbl_e4_mesh_info.SetLabel("")
            else:
                self.lbl_e4_state.SetLabel(
                    _("Updated in {seconds} s.").format(seconds=fmt_float(elapsed_seconds, 2)))
                self.lbl_e4_mesh_info.SetLabel(
                    _("{points} points, {cells} cells").format(
                        points=fmt_int(polydata.GetNumberOfPoints()), cells=fmt_int(polydata.GetNumberOfCells()))
                )
            self.controller.request_render()
        except RuntimeError as e:
            # Widgets destroyed mid-flight (plugin closing while a build
            # was in progress) - the real mgr-level update above already
            # succeeded/was rejected correctly; only this status-label
            # cosmetic update is skipped.
            print(f"ROI Viewer: E4 status widget update skipped (likely app shutdown) - {e}")
        finally:
            self._finish_preview_3d_build()

    def cancel_live_preview_3d(self):
        """Public lifecycle hook, mirrors cancel_preview() (E2) - called
        from this panel's own _on_destroy() so no pending debounce timer
        or stale worker result touches a destroyed widget. Does NOT
        detach the renderer-attached actor itself (gui/roi_panel.py's
        own lifecycle hooks already call self.preview_surface_3d.detach()
        directly on project close/load/plugin close, mirroring marker_3d/
        slice_planes_3d exactly) - this only stops OUR OWN timer/
        callback bookkeeping.

        E5 hardening: also drops any coalesced pending rebuild request
        (test_pending_cancelled_on_project_close) - a request queued for
        a project/panel that is going away must never fire once it's
        gone. Does NOT clear _e4_build_busy itself: an in-flight worker
        thread is daemon and reads only its own already-captured
        snapshot/closure state, so it cannot touch a destroyed widget;
        its eventual wx.CallAfter callback runs _finish_preview_3d_build()
        as normal and finds no pending request left to act on."""
        try:
            self._e4_debounce_timer.Stop()
        except Exception:
            pass
        self._e4_pending_reason = None
        if self._e4_callback_mask is not None:
            try:
                self._e4_callback_mask.remove_modified_callback(self._on_current_mask_modified)
            except Exception:
                pass
            self._e4_callback_mask = None
