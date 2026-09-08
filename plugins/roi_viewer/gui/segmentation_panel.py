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
        self._roi_list_ids = []
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
        self.spin_rg_tolerance = wx.SpinCtrl(self, wx.ID_ANY, "50", min=1, max=2000)
        rg_row.Add(self.spin_rg_tolerance, 1, wx.ALL, 5)
        rg_sizer.Add(rg_row, 0, wx.EXPAND, 5)

        self.btn_pick_seed = wx.ToggleButton(self, wx.ID_ANY, _("Pick Seed Point (3D)"))
        rg_sizer.Add(self.btn_pick_seed, 0, wx.ALL | wx.EXPAND, 5)

        self.rg_status = wx.StaticText(self, wx.ID_ANY, _(""))
        rg_sizer.Add(self.rg_status, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(rg_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- ROI management (core/roi_manager.ROIManager) ---
        # NOTE: this is the "quản lý segmentation" piece - a named,
        # organized view over the masks this panel has created, backed
        # by real InVesalius operations (Change mask selected / Show
        # mask / Change mask name / Remove masks), not a disconnected
        # bookkeeping list.
        box_roi = wx.StaticBox(self, wx.ID_ANY, _("ROI List"))
        roi_sizer = wx.StaticBoxSizer(box_roi, wx.VERTICAL)

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
        self.btn_pick_seed.Bind(wx.EVT_TOGGLEBUTTON, self._on_toggle_pick_seed)
        self.btn_roi_rename.Bind(wx.EVT_BUTTON, self._on_roi_rename)
        self.btn_roi_delete.Bind(wx.EVT_BUTTON, self._on_roi_delete)
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

            # Register with ROIManager so it shows up in the ROI List
            # below. "Create new mask" is handled synchronously (see
            # invesalius/data/slice_.py's __add_mask_thresh), so the
            # real new mask is already Slice().current_mask by now.
            import invesalius.data.slice_ as sl

            new_mask = sl.Slice().current_mask
            if new_mask is not None:
                self.controller.roi_mgr.create_roi(name, new_mask.index)
                self._refresh_roi_list()
        except ImportError as e:
            wx.MessageBox(_("Segmentation not available."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: could not create mask - {e}")

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
        # not growing succeeds.
        wx.CallAfter(self.btn_pick_seed.SetValue, False)
        self.controller.picker.remove_callback(self._on_seed_picked)

        try:
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

            wx.CallAfter(self.rg_status.SetLabel, _(f"Growing from voxel {seed}..."))
            # scipy/numpy BFS over a full CT volume can take real time
            # (see the performance note on SegmentationManager.
            # region_growing() itself) - run off the UI thread so the
            # app doesn't freeze, then marshal the result back with
            # wx.CallAfter (all real wx/pubsub calls must happen on the
            # main thread).
            import threading

            def worker():
                try:
                    result_mask = self.controller.seg_mgr.region_growing(volume, seed, tolerance)
                    wx.CallAfter(self._on_region_grown, result_mask, seed, tolerance)
                except Exception:
                    import traceback

                    wx.CallAfter(self.rg_status.SetLabel, _("Region growing failed"))
                    print("ROI Viewer: region growing failed -\n" + traceback.format_exc())

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.rg_status.SetLabel(_("Region growing failed"))
            print(f"ROI Viewer: region growing setup failed - {e}")

    def _on_region_grown(self, result_mask, seed, tolerance):
        """
        Runs on the main thread (via wx.CallAfter). Creates a real
        InVesalius mask sized to match the volume, then overwrites its
        voxel data with the region-growing result - the same direct
        matrix-write technique already verified for Undo/Redo (mask.
        matrix[:] = ...), so this is real, first-class mask data, not a
        disconnected copy.
        """
        try:
            import numpy as np
            import invesalius.data.slice_ as sl
            import invesalius.constants as const
            from invesalius.pubsub import pub as Publisher
            from ..interface.project_interface import ProjectInterface

            voxel_count = int(result_mask.sum())
            if voxel_count == 0:
                self.rg_status.SetLabel(
                    _(f"No region found from seed {seed} (tolerance {tolerance}) - try a higher tolerance")
                )
                return

            mask_count = len(ProjectInterface().get_mask_dict())
            colour = const.MASK_COLOUR[mask_count % len(const.MASK_COLOUR)]
            name = f"Region Growing {mask_count + 1}"

            # Create an empty real mask of the right shape/threshold
            # bookkeeping via the standard path, then overwrite its
            # voxel data with the actual region-growing result.
            Publisher.sendMessage(
                "Create new mask", mask_name=name, thresh=(1, 1), colour=colour
            )
            new_mask = sl.Slice().current_mask
            if new_mask is None or new_mask.matrix is None:
                self.rg_status.SetLabel(_("Region growing: failed to create mask"))
                return

            # InVesalius mask matrices carry a 1-voxel padding border
            # (see interface/project_interface.py notes elsewhere on
            # mask padding); result_mask matches the unpadded volume
            # shape, so write into the interior.
            target = new_mask.matrix[1:, 1:, 1:]
            if target.shape == result_mask.shape:
                target[:] = np.where(result_mask > 0, 255, target)
            else:
                # Shapes should match ProjectInterface().get_shape(),
                # but guard defensively rather than raising into a
                # background-thread-originated callback.
                self.rg_status.SetLabel(
                    _(f"Region growing: shape mismatch {target.shape} vs {result_mask.shape}")
                )
                return

            self.controller.roi_mgr.create_roi(name, new_mask.index)
            self._refresh_roi_list()
            self._refresh_after_edit()
            self.rg_status.SetLabel(
                _(f"Status: grown {voxel_count} voxels from seed {seed} -> '{name}'")
            )
        except Exception as e:
            self.rg_status.SetLabel(_("Region growing: failed to apply result"))
            print(f"ROI Viewer: applying region growing result failed - {e}")

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
        """Rebuild the ROI list widget from roi_mgr, preserving check state (visibility)."""
        self._roi_list_ids = list(self.controller.roi_mgr.rois.keys())
        self.roi_list.Set([
            f"{self.controller.roi_mgr.rois[rid].name} (mask #{self.controller.roi_mgr.rois[rid].mask_index})"
            for rid in self._roi_list_ids
        ])
        for i, rid in enumerate(self._roi_list_ids):
            self.roi_list.Check(i, self.controller.roi_mgr.rois[rid].visible)

    def _selected_roi_id(self):
        sel = self.roi_list.GetSelection()
        if sel == wx.NOT_FOUND or not hasattr(self, "_roi_list_ids") or sel >= len(self._roi_list_ids):
            return None
        return self._roi_list_ids[sel]

    def _on_roi_selected(self, event):
        rid = self._selected_roi_id()
        if rid is None:
            return
        roi = self.controller.roi_mgr.get_roi(rid)
        self.controller.roi_mgr.set_current_roi(rid)
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

    def _on_update_surface(self, event):
        """
        Rebuild the 3D surface for the selected ROI's mask (or the real
        current mask if none is selected in this list) - see the NOTE
        by btn_update_surface's construction for why this exists and
        why it's manual rather than automatic.
        """
        try:
            import invesalius.data.slice_ as sl
            from invesalius.pubsub import pub as Publisher

            rid = self._selected_roi_id()
            if rid is not None:
                mask_index = self.controller.roi_mgr.get_roi(rid).mask_index
            else:
                mask = sl.Slice().current_mask
                if mask is None:
                    wx.MessageBox(_("No mask selected."), _("Error"), wx.OK | wx.ICON_ERROR)
                    return
                mask_index = mask.index

            # Same real topic/argument shape used and verified in the
            # performance test (test_perf.py) that measured real render
            # FPS on a surface built this way.
            surface_options = {
                "method": {"algorithm": "Default", "options": {}},
                "options": {
                    "index": mask_index, "name": "", "quality": "Optimal *",
                    "fill": False, "keep_largest": False, "overwrite": True,
                },
            }
            Publisher.sendMessage("Create surface from index", surface_parameters=surface_options)
            self.status_text.SetLabel(_(f"Status: Rebuilding 3D surface for mask #{mask_index}..."))
        except Exception as e:
            wx.MessageBox(_("Surface update failed."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: surface update failed - {e}")
