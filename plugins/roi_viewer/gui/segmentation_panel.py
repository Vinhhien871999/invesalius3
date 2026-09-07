# --------------------------------------------------------------------------
# Segmentation Panel Module
# Description: Panel for ROI segmentation tools, wired to the real
#              InVesalius mask pipeline (invesalius.data.slice_.Slice) via
#              the exact pubsub topics InVesalius's own threshold task
#              panel uses - not a disconnected local copy of the volume.
# --------------------------------------------------------------------------

import wx
import wx.lib.scrolledpanel as scrolled

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s


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

        sizer.Add(thresh_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- Brush tools (configuration only in this version - see
        # note on _on_undo/_on_redo below for what is actually wired) ---
        box_brush = wx.StaticBox(self, wx.ID_ANY, _("Brush Tools"))
        brush_sizer = wx.StaticBoxSizer(box_brush, wx.VERTICAL)

        brush_note = wx.StaticText(
            self, wx.ID_ANY,
            _("Use InVesalius's own 2D brush/eraser tool to paint the "
              "current mask. Undo/Redo below snapshots and restores the "
              "real current mask, so it also undoes edits made with the "
              "native brush."),
        )
        brush_note.Wrap(280)
        brush_sizer.Add(brush_note, 0, wx.ALL | wx.EXPAND, 5)

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
        self.btn_checkpoint.Bind(wx.EVT_BUTTON, self._on_checkpoint)
        self.btn_undo.Bind(wx.EVT_BUTTON, self._on_undo)
        self.btn_redo.Bind(wx.EVT_BUTTON, self._on_redo)

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

    def _on_apply_threshold(self, event):
        lo = self.spin_min.GetValue()
        hi = self.spin_max.GetValue()

        if lo > hi:
            wx.MessageBox(
                _("Min threshold must be <= Max threshold."), _("Error"), wx.OK | wx.ICON_ERROR
            )
            return

        self.controller.seg_mgr.set_threshold(lo, hi)

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
            Publisher.sendMessage(
                "Create new mask", mask_name=name, thresh=(lo, hi), colour=colour
            )
            self.status_text.SetLabel(_(f"Status: Created mask '{name}'"))
        except ImportError as e:
            wx.MessageBox(_("Segmentation not available."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: could not create mask - {e}")

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

    def _on_undo(self, event):
        mask = self._current_mask()
        if mask is None or mask.matrix is None:
            self.status_text.SetLabel(_("Status: No mask selected"))
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
