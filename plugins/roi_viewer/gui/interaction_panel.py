# --------------------------------------------------------------------------
# Interaction Panel Module
# Description: Panel for 2D-3D interaction tools
# --------------------------------------------------------------------------

import wx
import wx.lib.scrolledpanel as scrolled

from ..i18n import _, fmt_float
from . import ui_helpers


class InteractionPanel(scrolled.ScrolledPanel):
    """
    Panel for 2D-3D interaction tools.

    `controller` is the owning ROIViewerFrame, giving access to the
    shared picker_3d.PointPicker3D and sync_2d3d.SyncManager2D3D
    instances.
    """

    def __init__(self, parent, controller):
        scrolled.ScrolledPanel.__init__(self, parent)
        self.controller = controller
        self._callback_registered = False

        # State
        self.sync_3d_2d_enabled = True
        self.sync_2d_3d_enabled = True

        self._init_ui()
        self.SetupScrolling(scroll_x=False)
        
    def _init_ui(self):
        """
        Three groups: 2D-3D sync, 3D point picking, and a collapsed
        "advanced 3D display" section (E5 textured planes + clipping, both
        off by default). The former "Real-time Update" and "Brush Mode"
        boxes were removed: neither had any effect (the update delay only
        throttled SyncManager2D3D.request_3d_update(), whose callback list
        nothing ever registers into, and get_brush_config() had no caller -
        the real brush lives on the "Phân đoạn" tab).
        """
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- 2D <-> 3D sync (C8) ---
        box_sync = wx.StaticBox(self, wx.ID_ANY, _("2D-3D sync"))
        sync_sizer = wx.StaticBoxSizer(box_sync, wx.VERTICAL)

        self.cb_sync_2d_3d = wx.CheckBox(self, wx.ID_ANY, _("Sync 2D → 3D"))
        self.cb_sync_2d_3d.SetValue(True)
        self.cb_sync_2d_3d.SetToolTip(_("Moving the 2D crosshair moves the 3D marker and slice planes."))
        self.Bind(wx.EVT_CHECKBOX, self._on_sync_2d_3d_changed, self.cb_sync_2d_3d)
        sync_sizer.Add(self.cb_sync_2d_3d, 0, wx.ALL, 3)

        self.cb_sync_3d_2d = wx.CheckBox(self, wx.ID_ANY, _("Sync 3D → 2D"))
        self.cb_sync_3d_2d.SetValue(True)
        self.cb_sync_3d_2d.SetToolTip(_("A point picked in 3D moves the 2D views to that slice."))
        self.Bind(wx.EVT_CHECKBOX, self._on_sync_3d_2d_changed, self.cb_sync_3d_2d)
        sync_sizer.Add(self.cb_sync_3d_2d, 0, wx.ALL, 3)

        # Controls only whether the planes are drawn, not whether they
        # track the crosshair - see apply_slice_plane_visibility().
        self.cb_show_slice_planes = wx.CheckBox(self, wx.ID_ANY, _("Show slice planes in 3D"))
        self.cb_show_slice_planes.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self._on_show_slice_planes_changed, self.cb_show_slice_planes)
        sync_sizer.Add(self.cb_show_slice_planes, 0, wx.ALL, 3)

        # The plugin never switches InVesalius's toolbar tool itself.
        sync_sizer.Add(ui_helpers.hint(
            self, _("Turn on InVesalius's \"Slices' cross intersection\" tool first."), wrap=260
        ), 0, wx.ALL, 3)
        main_sizer.Add(sync_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- 3D point picking ---
        box_pick = wx.StaticBox(self, wx.ID_ANY, _("3D point picking"))
        pick_sizer = wx.StaticBoxSizer(box_pick, wx.VERTICAL)
        self.btn_pick_point = wx.Button(self, wx.ID_ANY, _("Pick a point in 3D"))
        self.Bind(wx.EVT_BUTTON, self._on_pick_point, self.btn_pick_point)
        pick_sizer.Add(self.btn_pick_point, 0, wx.ALL | wx.EXPAND, 3)
        self.txt_coords = wx.TextCtrl(self, wx.ID_ANY, "X: -, Y: -, Z: -", style=wx.TE_READONLY | wx.TE_CENTER)
        pick_sizer.Add(self.txt_coords, 0, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(pick_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # --- Advanced 3D display (E5), collapsed. Both features default
        # OFF; with both off, C8 behaves exactly as before E5. ---
        pane, p = ui_helpers.collapsible(self, _("Advanced 3D display (experimental)"), self._on_section_toggled)
        viz_sizer = wx.BoxSizer(wx.VERTICAL)

        self.cb_texture_planes = wx.CheckBox(p, wx.ID_ANY, _("Show slice image on 3D planes"))
        self.cb_texture_planes.SetValue(False)
        self.cb_texture_planes.SetToolTip(_(
            "Shows the 2D slice image on the 3D planes exactly as the 2D views show it "
            "(current Window/Level, plus the mask colour and preview overlay if shown). "
            "Display only - no mask or surface is changed."
        ))
        self.Bind(wx.EVT_CHECKBOX, self._on_texture_planes_toggle, self.cb_texture_planes)
        viz_sizer.Add(self.cb_texture_planes, 0, wx.ALL, 3)

        viz_sizer.Add(wx.StaticLine(p), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)

        self.cb_clip_enabled = wx.CheckBox(p, wx.ID_ANY, _("Enable 3D clipping"))
        self.cb_clip_enabled.SetValue(False)
        self.cb_clip_enabled.SetToolTip(_(
            "Cuts the 3D surface away along the current slice plane. Display only - "
            "the surface data, masks and saved project are not changed."
        ))
        self.Bind(wx.EVT_CHECKBOX, self._on_clip_enabled_toggle, self.cb_clip_enabled)
        viz_sizer.Add(self.cb_clip_enabled, 0, wx.ALL, 3)

        self.choice_clip_plane = wx.Choice(p, wx.ID_ANY, choices=[_("Axial"), _("Coronal"), _("Sagittal")])
        self.choice_clip_plane.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_clip_plane_changed, self.choice_clip_plane)
        viz_sizer.Add(ui_helpers.labelled_row(p, _("Plane:"), self.choice_clip_plane), 0, wx.EXPAND)

        self.cb_clip_invert = wx.CheckBox(p, wx.ID_ANY, _("Invert cut side"))
        self.cb_clip_invert.SetValue(False)
        self.Bind(wx.EVT_CHECKBOX, self._on_clip_invert_toggle, self.cb_clip_invert)
        viz_sizer.Add(self.cb_clip_invert, 0, wx.ALL, 3)

        self.choice_clip_target = wx.Choice(
            p, wx.ID_ANY, choices=[_("Final surface of current ROI"), _("Preview surface")],
        )
        self.choice_clip_target.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_clip_target_changed, self.choice_clip_target)
        viz_sizer.Add(ui_helpers.labelled_row(p, _("Target:"), self.choice_clip_target), 0, wx.EXPAND)

        self.lbl_e5_status = wx.StaticText(p, wx.ID_ANY, "")
        self.lbl_e5_status.Wrap(260)
        viz_sizer.Add(self.lbl_e5_status, 0, wx.ALL | wx.EXPAND, 3)
        p.SetSizer(viz_sizer)
        main_sizer.Add(pane, 0, wx.ALL | wx.EXPAND, 5)

        self.status_text = wx.StaticText(self, wx.ID_ANY, _("Ready."), style=wx.ST_NO_AUTORESIZE)
        main_sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(main_sizer)

    def _on_section_toggled(self, event):
        ui_helpers.relayout_scrolled(self)
        event.Skip()

    # =================
    # Event Handlers
    # =================
    
    def _on_sync_3d_2d_changed(self, event):
        """Handle sync 3D to 2D checkbox change."""
        self.sync_3d_2d_enabled = event.IsChecked()
        if self.sync_3d_2d_enabled:
            self.controller.sync_mgr.enable_sync_3d_2d()
        else:
            self.controller.sync_mgr.disable_sync_3d_2d()
        self._update_status()

    def _on_sync_2d_3d_changed(self, event):
        """Handle sync 2D to 3D checkbox change."""
        self.sync_2d_3d_enabled = event.IsChecked()
        if self.sync_2d_3d_enabled:
            self.controller.sync_mgr.enable_sync_2d_3d()
        else:
            self.controller.sync_mgr.disable_sync_2d_3d()
        self._update_status()

    def _on_show_slice_planes_changed(self, event):
        """
        Handle "Show slice planes in 3D" checkbox change. A separate
        concern from Sync 2D->3D itself (self.controller.sync_mgr.
        sync_2d_3d) - this only toggles whether the 3 plane actors are
        DRAWN; the crosshair marker's own visibility is untouched, and
        geometry keeps tracking the real crosshair position underneath
        even while hidden (see core/slice_planes_3d.py's set_visible()
        docstring for why), so toggling this back on shows the planes
        at the CURRENT position immediately, not a stale one. This is the
        master switch for both plane sets - see ROIViewerFrame.
        apply_slice_plane_visibility().
        """
        self.controller.show_slice_planes = event.IsChecked()
        self.controller.apply_slice_plane_visibility()
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Render volume viewer")
        except ImportError:
            pass

    # =================
    # E5 (Advanced Segmentation Enhancement Track, enhancement/advanced-
    # segmentation branch ONLY): Advanced 3D Visualization
    # =================

    # Index in choice_clip_plane -> real orientation string, matching
    # core/surface_clipping_3d.py's PLANE_* constants (and
    # core/slice_planes_3d.py's real one-T "SAGITAL" spelling - the
    # actual InVesalius pubsub convention, not the common two-T one).
    _CLIP_PLANE_BY_INDEX = ("AXIAL", "CORONAL", "SAGITAL")

    def _on_texture_planes_toggle(self, event):
        """
        Section 8/13: strictly opt-in, default OFF. Chooses which plane
        set "Show slice planes in 3D" draws (never both at once - avoids
        z-fighting); never changes that master checkbox's own state. The
        actual show/hide is ROIViewerFrame.apply_slice_plane_visibility().
        """
        enabled = self.cb_texture_planes.GetValue()
        self.controller.show_texture_planes = enabled
        if enabled:
            try:
                from ..interface.view_interface import ViewInterface

                viewer = ViewInterface().get_volume_viewer()
                if viewer is not None and hasattr(viewer, "ren"):
                    self.controller.textured_slice_planes_3d.attach(viewer.ren)
                    # Build immediately where C8's geometric planes
                    # currently sit, so the textures replace them in
                    # place. Not _last_cross_focal_point: it keeps moving
                    # while Sync 2D->3D is off, when C8's planes stay
                    # frozen - the textures would appear somewhere else.
                    # C8's planes hold a VIEW-frame position; texture
                    # building selects voxels, so convert back to the
                    # slice frame (core/coordinates.py).
                    position = self.controller.slice_planes_3d.get_position()
                    if position is not None:
                        from ..core.coordinates import view_to_slice

                        self.controller.update_textured_slice_planes(view_to_slice(position))
            except Exception as e:
                print(f"ROI Viewer: E5A texture planes enable failed - {e}")
        self.controller.apply_slice_plane_visibility()
        self.controller.request_render()

    def _on_clip_enabled_toggle(self, event):
        enabled = self.cb_clip_enabled.GetValue()
        clip = self.controller.surface_clipping_3d
        if enabled:
            clip.enable()
            self.refresh_clipping_target()
        else:
            clip.disable()
            self.lbl_e5_status.SetLabel("")
        self.controller.request_render()

    def _on_clip_plane_changed(self, event):
        idx = self.choice_clip_plane.GetSelection()
        if 0 <= idx < len(self._CLIP_PLANE_BY_INDEX):
            self.controller.surface_clipping_3d.set_orientation(self._CLIP_PLANE_BY_INDEX[idx])
            self.controller.request_render()

    def _on_clip_invert_toggle(self, event):
        self.controller.surface_clipping_3d.set_inverted(self.cb_clip_invert.GetValue())
        self.controller.request_render()

    def _on_clip_target_changed(self, event):
        self.refresh_clipping_target()
        self.controller.request_render()

    def refresh_clipping_target(self):
        """
        Section 18/23/24 real target resolution - called on: this
        panel's own Enable-Clipping/Target-choice changes, AND
        externally by SegmentationPanel after a ROI selection change or
        after ITS OWN "Update 3D Surface from Selected ROI" build
        completes (see segmentation_panel.py's _on_roi_selected()/
        _on_surface_info_updated()). No-op if clipping is not enabled -
        nothing to (re)resolve yet.
        """
        clip = self.controller.surface_clipping_3d
        if not self.cb_clip_enabled.GetValue():
            return
        target_idx = self.choice_clip_target.GetSelection()
        if target_idx == 1:
            # Live Preview (E4) - E4's manager already exposes its own
            # real mapper directly (Section 25 - safe to attach/detach a
            # clipping plane to it: clipping-plane state lives on the
            # mapper independently of set_polydata_if_current()'s own
            # SetInputData() calls, so the two never conflict).
            mapper = self.controller.preview_surface_3d.mapper
            clip.set_target_mapper(mapper)
            self.lbl_e5_status.SetLabel(
                _("Clipping the preview surface.") if mapper is not None
                else _("The preview surface has no mesh yet.")
            )
            return

        # Current ROI Final Surface (Section 16/18 - default target).
        mapper = None
        try:
            seg_panel = self.controller.segmentation_panel
            rid = seg_panel._selected_roi_id()
            if rid is not None:
                mask_index = self.controller.roi_mgr.get_roi(rid).mask_index
            else:
                import invesalius.data.slice_ as sl

                current = sl.Slice().current_mask
                mask_index = current.index if current is not None else None
            if mask_index is not None:
                surface_index = seg_panel.get_surface_index_for_mask(mask_index)
                if surface_index is not None:
                    from ..core.surface_clipping_3d import resolve_surface_actor

                    actor = resolve_surface_actor(surface_index)
                    if actor is not None:
                        mapper = actor.GetMapper()
        except Exception as e:
            print(f"ROI Viewer: E5B clipping target resolution failed - {e}")

        clip.set_target_mapper(mapper)
        if mapper is not None:
            self.lbl_e5_status.SetLabel(_("Clipping the final surface of the current ROI."))
        else:
            self.lbl_e5_status.SetLabel(_("The current ROI has no final 3D surface yet."))

    def _on_point_picked(self, world_point):
        """
        Called by PointPicker3D with a real-world (x, y, z) mm
        coordinate every time the user clicks in the 3D view.
        """
        x, y, z = world_point
        from ..core.coordinates import view_to_slice

        # Shown in the slice frame, the same coordinates native InVesalius
        # uses (the raw pick is in the y-flipped 3D view frame).
        wx.CallAfter(self.update_coordinates, *view_to_slice((x, y, z)))

        if not self.sync_3d_2d_enabled:
            return

        try:
            from ..interface.project_interface import ProjectInterface
            from ..interface.view_interface import ViewInterface

            from ..core.coordinates import view_to_slice

            self.controller.sync_mgr.set_volume_info(
                ProjectInterface().get_spacing(), ProjectInterface().get_shape()
            )
            # The 3D pick is in the y-flipped view frame; slice selection
            # needs the slice frame - same -y native uses for 3D pick ->
            # 2D (styles_3d.py:994). See core/coordinates.py.
            self.controller.sync_mgr.set_world_coords(*view_to_slice((x, y, z)))
            plane, index = (
                self.controller.sync_mgr.current_plane,
                self.controller.sync_mgr.current_slice_index,
            )
            wx.CallAfter(ViewInterface().set_slice_position, plane, index)
        except Exception as e:
            print(f"ROI Viewer: 3D->2D sync failed - {e}")

    def _on_pick_point(self, event):
        """Handle pick point button click."""
        if not self.controller.ensure_picker_initialized():
            self.status_text.SetLabel(_("No 3D view available yet"))
            return
        if not self._callback_registered:
            self.controller.picker.add_callback(self._on_point_picked)
            self._callback_registered = True
        self.controller.picker.enable()
        self.status_text.SetLabel(_("Click a point in the 3D view..."))
        
    def _update_status(self):
        directions = []
        if self.sync_2d_3d_enabled:
            directions.append("2D → 3D")
        if self.sync_3d_2d_enabled:
            directions.append("3D → 2D")
        if directions:
            self.status_text.SetLabel(_("Sync on: {directions}.").format(directions=", ".join(directions)))
        else:
            self.status_text.SetLabel(_("Sync off."))

    # =================
    # Public Methods
    # =================
    
    def update_coordinates(self, x, y, z):
        """
        Update coordinate display.

        NOTE: called via wx.CallAfter from _on_point_picked(), so it can
        run one event-loop tick after the pick happened - if this panel
        was destroyed in that window (e.g. the user closed the ROI
        Viewer, or reopened it, in between), self.txt_coords is a
        deleted wx C++ object and touching it raises RuntimeError. This
        is now also prevented at the source (the picker's VTK observer
        is removed on close - see picker_3d.PointPicker3D.cleanup()),
        but that fix only covers *this* window's own lifecycle; guard
        here too as defense in depth, since InVesalius's own crash
        handler caught this crashing for real.
        """
        try:
            self.txt_coords.SetValue(
                "X: {}, Y: {}, Z: {} mm".format(fmt_float(x), fmt_float(y), fmt_float(z)))
        except RuntimeError:
            pass
        
    def set_status(self, message):
        """Set status message."""
        self.status_text.SetLabel(message)
