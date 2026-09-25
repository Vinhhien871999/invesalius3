# --------------------------------------------------------------------------
# Interaction Panel Module
# Description: Panel for 2D-3D interaction tools
# --------------------------------------------------------------------------

import wx
import wx.lib.scrolledpanel as scrolled

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s


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
        self.realtime_update_enabled = True
        self.update_delay = 100

        self._init_ui()
        self.SetupScrolling()
        
    def _init_ui(self):
        """Initialize the interaction panel UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # =================
        # Title
        # =================
        title = wx.StaticText(self, wx.ID_ANY, _("2D-3D Interaction"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # 3D Point Picking
        # =================
        box_pick = wx.StaticBox(self, wx.ID_ANY, _("3D Point Picking"))
        pick_sizer = wx.StaticBoxSizer(box_pick, wx.VERTICAL)
        
        # Enable sync checkboxes
        self.cb_sync_3d_2d = wx.CheckBox(self, wx.ID_ANY, _("Sync 3D -> 2D"))
        self.cb_sync_3d_2d.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self._on_sync_3d_2d_changed, self.cb_sync_3d_2d)
        pick_sizer.Add(self.cb_sync_3d_2d, 0, wx.ALL, 3)
        
        self.cb_sync_2d_3d = wx.CheckBox(self, wx.ID_ANY, _("Sync 2D -> 3D"))
        self.cb_sync_2d_3d.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self._on_sync_2d_3d_changed, self.cb_sync_2d_3d)
        pick_sizer.Add(self.cb_sync_2d_3d, 0, wx.ALL, 3)

        # Phase 13.5 (pre-Phase-14, visual enhancement of Sync 2D -> 3D -
        # still C8, not a new feature ID): a separate concern from the
        # Sync checkbox itself - controls only whether the 3 slice-plane
        # actors are drawn (core/slice_planes_3d.SlicePlanes3D), not
        # whether the crosshair marker/planes track position at all.
        self.cb_show_slice_planes = wx.CheckBox(self, wx.ID_ANY, _("Show slice planes in 3D"))
        self.cb_show_slice_planes.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self._on_show_slice_planes_changed, self.cb_show_slice_planes)
        pick_sizer.Add(self.cb_show_slice_planes, 0, wx.ALL, 3)

        # Plugin never auto-toggles InVesalius's own native toolbar tool
        # - the user must turn it on themselves for 2D click/drag to
        # actually send the real "Set cross focal point" topic this
        # whole feature depends on (see core/sync_2d3d.py /
        # roi_panel.py.on_cross_focal_point_changed()'s own NOTEs for
        # why that topic, not a new one, is used).
        lbl_prereq = wx.StaticText(
            self, wx.ID_ANY,
            _('Requires InVesalius "Slices\' cross intersection" tool to be active.'),
        )
        lbl_prereq.Wrap(260)
        lbl_prereq.SetForegroundColour(wx.Colour(90, 90, 90))
        pick_sizer.Add(lbl_prereq, 0, wx.ALL, 3)

        # Pick point button
        self.btn_pick_point = wx.Button(self, wx.ID_ANY, _("Pick Point in 3D"))
        self.Bind(wx.EVT_BUTTON, self._on_pick_point, self.btn_pick_point)
        pick_sizer.Add(self.btn_pick_point, 0, wx.ALL | wx.EXPAND, 3)
        
        # Coordinate display
        self.txt_coords = wx.TextCtrl(
            self, wx.ID_ANY, "X: -, Y: -, Z: -",
            style=wx.TE_READONLY | wx.TE_CENTER
        )
        pick_sizer.Add(self.txt_coords, 0, wx.ALL | wx.EXPAND, 3)
        
        main_sizer.Add(pick_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # =================
        # E5 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch ONLY): Advanced 3D Visualization
        # - textured slice planes (E5A) + surface clipping/cutaway (E5B).
        # Both default OFF - with both left off, C8's existing behavior
        # (geometric SlicePlanes3D, no clipping) is byte-identical to
        # before E5 existed. See _on_texture_planes_toggle()/
        # _on_clip_enabled_toggle() below and docs/CT3D_ADVANCED_E5_
        # VISUALIZATION_REPORT.md for the full design/audit.
        # =================
        box_viz = wx.StaticBox(self, wx.ID_ANY, _("3D Visualization (E5, enhancement branch)"))
        viz_sizer = wx.StaticBoxSizer(box_viz, wx.VERTICAL)

        self.cb_texture_planes = wx.CheckBox(self, wx.ID_ANY, _("Show CT texture on slice planes"))
        self.cb_texture_planes.SetValue(False)
        self.Bind(wx.EVT_CHECKBOX, self._on_texture_planes_toggle, self.cb_texture_planes)
        viz_sizer.Add(self.cb_texture_planes, 0, wx.ALL, 3)

        viz_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)

        clip_title = wx.StaticText(self, wx.ID_ANY, _("Clipping / Cutaway"))
        viz_sizer.Add(clip_title, 0, wx.ALL, 3)

        self.cb_clip_enabled = wx.CheckBox(self, wx.ID_ANY, _("Enable Clipping"))
        self.cb_clip_enabled.SetValue(False)
        self.Bind(wx.EVT_CHECKBOX, self._on_clip_enabled_toggle, self.cb_clip_enabled)
        viz_sizer.Add(self.cb_clip_enabled, 0, wx.ALL, 3)

        clip_plane_row = wx.BoxSizer(wx.HORIZONTAL)
        clip_plane_row.Add(wx.StaticText(self, wx.ID_ANY, _("Plane:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.choice_clip_plane = wx.Choice(self, wx.ID_ANY, choices=[_("Axial"), _("Coronal"), _("Sagittal")])
        self.choice_clip_plane.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_clip_plane_changed, self.choice_clip_plane)
        clip_plane_row.Add(self.choice_clip_plane, 1, wx.ALL, 3)
        viz_sizer.Add(clip_plane_row, 0, wx.EXPAND, 3)

        self.cb_clip_invert = wx.CheckBox(self, wx.ID_ANY, _("Invert"))
        self.cb_clip_invert.SetValue(False)
        self.Bind(wx.EVT_CHECKBOX, self._on_clip_invert_toggle, self.cb_clip_invert)
        viz_sizer.Add(self.cb_clip_invert, 0, wx.ALL, 3)

        clip_target_row = wx.BoxSizer(wx.HORIZONTAL)
        clip_target_row.Add(wx.StaticText(self, wx.ID_ANY, _("Target:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.choice_clip_target = wx.Choice(
            self, wx.ID_ANY,
            choices=[_("Current ROI Final Surface"), _("Live Preview (E4)")],
        )
        self.choice_clip_target.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self._on_clip_target_changed, self.choice_clip_target)
        clip_target_row.Add(self.choice_clip_target, 1, wx.ALL, 3)
        viz_sizer.Add(clip_target_row, 0, wx.EXPAND, 3)

        self.lbl_e5_status = wx.StaticText(self, wx.ID_ANY, "")
        self.lbl_e5_status.Wrap(260)
        viz_sizer.Add(self.lbl_e5_status, 0, wx.ALL | wx.EXPAND, 3)

        main_sizer.Add(viz_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # =================
        # Real-time Update
        # =================
        box_update = wx.StaticBox(self, wx.ID_ANY, _("Real-time Update"))
        update_sizer = wx.StaticBoxSizer(box_update, wx.VERTICAL)
        
        self.cb_realtime = wx.CheckBox(self, wx.ID_ANY, _("Enable real-time update"))
        self.cb_realtime.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self._on_realtime_changed, self.cb_realtime)
        update_sizer.Add(self.cb_realtime, 0, wx.ALL, 3)
        
        # Update delay slider
        delay_label = wx.StaticText(self, wx.ID_ANY, _("Update delay (ms):"))
        update_sizer.Add(delay_label, 0, wx.ALL, 3)
        
        self.slider_delay = wx.Slider(
            self, wx.ID_ANY, 100, 0, 500,
            style=wx.SL_HORIZONTAL
        )
        self.Bind(wx.EVT_SLIDER, self._on_delay_changed, self.slider_delay)
        update_sizer.Add(self.slider_delay, 0, wx.ALL | wx.EXPAND, 3)
        
        self.lbl_delay_value = wx.StaticText(self, wx.ID_ANY, "100 ms")
        update_sizer.Add(self.lbl_delay_value, 0, wx.ALL | wx.ALIGN_CENTER, 3)
        
        main_sizer.Add(update_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Brush Mode
        # =================
        box_brush = wx.StaticBox(self, wx.ID_ANY, _("Brush Mode"))
        brush_sizer = wx.StaticBoxSizer(box_brush, wx.VERTICAL)
        
        # Brush size
        size_label = wx.StaticText(self, wx.ID_ANY, _("Brush Size:"))
        brush_sizer.Add(size_label, 0, wx.ALL, 3)
        
        self.slider_brush_size = wx.Slider(
            self, wx.ID_ANY, 5, 1, 50,
            style=wx.SL_HORIZONTAL | wx.SL_VALUE_LABEL
        )
        self.Bind(wx.EVT_SLIDER, self._on_brush_size_changed, self.slider_brush_size)
        brush_sizer.Add(self.slider_brush_size, 0, wx.ALL | wx.EXPAND, 3)
        
        self.lbl_brush_size = wx.StaticText(self, wx.ID_ANY, "5 px")
        brush_sizer.Add(self.lbl_brush_size, 0, wx.ALL | wx.ALIGN_CENTER, 3)
        
        # Brush shape
        shape_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_circle = wx.RadioButton(self, wx.ID_ANY, _("Circle"), style=wx.RB_GROUP)
        self.rb_circle.SetValue(True)
        shape_row.Add(self.rb_circle, 0, wx.ALL, 3)
        
        self.rb_square = wx.RadioButton(self, wx.ID_ANY, _("Square"))
        shape_row.Add(self.rb_square, 0, wx.ALL, 3)
        
        brush_sizer.Add(shape_row, 0, wx.EXPAND, 3)
        
        main_sizer.Add(brush_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Status
        # =================
        self.status_text = wx.StaticText(
            self, wx.ID_ANY,
            _("Status: Ready"),
            style=wx.ST_NO_AUTORESIZE
        )
        main_sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(main_sizer)
        
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
        at the CURRENT position immediately, not a stale one.
        """
        self.controller.show_slice_planes = event.IsChecked()
        self.controller.slice_planes_3d.set_visible(self.controller.show_slice_planes)
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
        Section 8/13: strictly opt-in, default OFF. Turning texture mode
        ON hides C8's existing geometric planes and shows the textured
        ones instead (never both at once - avoids the z-fighting Section
        13 explicitly calls out); turning it OFF restores the geometric
        planes to whatever "Show slice planes in 3D" is currently set to
        - texture mode never changes that checkbox's own stored state.
        """
        enabled = self.cb_texture_planes.GetValue()
        self.controller.show_texture_planes = enabled
        if enabled:
            self.controller.slice_planes_3d.set_visible(False)
            try:
                from ..interface.view_interface import ViewInterface

                viewer = ViewInterface().get_volume_viewer()
                if viewer is not None and hasattr(viewer, "ren"):
                    self.controller.textured_slice_planes_3d.attach(viewer.ren)
                    # Section 11: rebuild immediately from the last known
                    # real crosshair position, if any, rather than
                    # waiting for the next 2D interaction - so enabling
                    # the checkbox shows CURRENT content immediately.
                    if self.controller._last_cross_focal_point is not None:
                        self.controller.update_textured_slice_planes(
                            self.controller._last_cross_focal_point
                        )
                    self.controller.textured_slice_planes_3d.set_visible(True)
            except Exception as e:
                print(f"ROI Viewer: E5A texture planes enable failed - {e}")
        else:
            self.controller.textured_slice_planes_3d.set_visible(False)
            self.controller.slice_planes_3d.set_visible(self.controller.show_slice_planes)
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
                _("Clipping target: Live Preview (E4)") if mapper is not None
                else _("Live Preview has no mesh yet.")
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
            self.lbl_e5_status.SetLabel(_("Clipping target: Current ROI Final Surface"))
        else:
            self.lbl_e5_status.SetLabel(_("No final surface for selected ROI."))

    def _on_realtime_changed(self, event):
        """Handle real-time update checkbox change."""
        self.realtime_update_enabled = event.IsChecked()
        self._update_status()

    def _on_delay_changed(self, event):
        """Handle update delay slider change."""
        self.update_delay = event.GetInt()
        self.lbl_delay_value.SetLabel(f"{self.update_delay} ms")
        self.controller.sync_mgr.set_update_delay(self.update_delay)

    def _on_brush_size_changed(self, event):
        """Handle brush size slider change."""
        size = event.GetInt()
        self.lbl_brush_size.SetLabel(f"{size} px")

    def _on_point_picked(self, world_point):
        """
        Called by PointPicker3D with a real-world (x, y, z) mm
        coordinate every time the user clicks in the 3D view.
        """
        x, y, z = world_point
        wx.CallAfter(self.update_coordinates, x, y, z)

        if not self.sync_3d_2d_enabled:
            return

        try:
            from ..interface.project_interface import ProjectInterface
            from ..interface.view_interface import ViewInterface

            self.controller.sync_mgr.set_volume_info(
                ProjectInterface().get_spacing(), ProjectInterface().get_shape()
            )
            self.controller.sync_mgr.set_world_coords(x, y, z)
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
            self.status_text.SetLabel(_("Status: No 3D view available yet"))
            return
        if not self._callback_registered:
            self.controller.picker.add_callback(self._on_point_picked)
            self._callback_registered = True
        self.controller.picker.enable()
        self.status_text.SetLabel(_("Click a point in the 3D view..."))
        
    def _update_status(self):
        """Update status text."""
        sync_mode = []
        if self.sync_3d_2d_enabled:
            sync_mode.append("3D->2D")
        if self.sync_2d_3d_enabled:
            sync_mode.append("2D->3D")
        
        if sync_mode:
            status = f"Sync: {', '.join(sync_mode)}"
        else:
            status = "Sync: None"
            
        if self.realtime_update_enabled:
            status += f" | RT: {self.update_delay}ms"
            
        self.status_text.SetLabel(status)
        
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
            self.txt_coords.SetValue(f"X: {x:.2f}, Y: {y:.2f}, Z: {z:.2f}")
        except RuntimeError:
            pass
        
    def get_brush_config(self):
        """Get current brush configuration."""
        return {
            'size': self.slider_brush_size.GetValue(),
            'shape': 'circle' if self.rb_circle.GetValue() else 'square'
        }
        
    def set_status(self, message):
        """Set status message."""
        self.status_text.SetLabel(message)
