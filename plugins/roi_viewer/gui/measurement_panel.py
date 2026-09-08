# --------------------------------------------------------------------------
# Measurement Panel Module
# Description: Panel for measurement tools
# --------------------------------------------------------------------------

import wx

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s


class MeasurementPanel(wx.Panel):
    """
    Panel for measurement tools.

    `controller` is the owning ROIViewerFrame, giving access to the
    shared picker_3d.PointPicker3D (for picking distance endpoints) and
    core/measurement.MeasurementManager.
    """

    def __init__(self, parent, controller):
        wx.Panel.__init__(self, parent)
        self.controller = controller
        self._collecting_distance = False
        self._init_ui()
        # Safety net: don't leave InVesalius's 2D canvas stuck in a
        # measurement tool mode if this window closes mid-measurement.
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    def _on_destroy(self, event):
        event.Skip()
        if event.GetEventObject() is not self:
            return
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const

            Publisher.sendMessage("Disable style", style=const.STATE_MEASURE_DISTANCE)
            Publisher.sendMessage("Disable style", style=const.STATE_MEASURE_DENSITY_POLYGON)
        except ImportError:
            pass
        except Exception as e:
            # NOTE: during whole-app shutdown, window destruction order
            # is not guaranteed - the real 3D viewer's
            # wxVTKRenderWindowInteractor can already be gone by the
            # time this fires, and OnDisableStyle()'s cleanup path
            # (invesalius/data/styles_3d.py's CleanUp -> Unbind) then
            # raises RuntimeError: "wrapped C/C++ object ... has been
            # deleted". That's a real crash InVesalius's own error
            # dialog reported (crash_report_20260907_153620.txt) the
            # first time this ran, right as the app was closing. This
            # cleanup is best-effort only - it must never crash the app
            # it's trying to leave in a clean state.
            print(f"ROI Viewer: style cleanup on destroy failed (likely app shutdown) - {e}")
        if self._collecting_distance:
            self.controller.picker.remove_callback(self._on_distance_point_picked)
            self._collecting_distance = False

    def _init_ui(self):
        """Initialize the measurement panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("Measurement Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Distance measurement section
        box_dist = wx.StaticBox(self, wx.ID_ANY, _("Distance Measurement"))
        dist_sizer = wx.StaticBoxSizer(box_dist, wx.VERTICAL)
        
        # Mode selection
        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        
        self.rb_dist_2d = wx.RadioButton(self, wx.ID_ANY, _("2D"), style=wx.RB_GROUP)
        mode_row.Add(self.rb_dist_2d, 0, wx.ALL, 3)
        
        self.rb_dist_3d = wx.RadioButton(self, wx.ID_ANY, _("3D"))
        self.rb_dist_3d.SetValue(True)
        mode_row.Add(self.rb_dist_3d, 0, wx.ALL, 3)
        
        dist_sizer.Add(mode_row, 0, wx.EXPAND, 5)
        
        # Start button
        self.btn_start_dist = wx.Button(self, wx.ID_ANY, _("Start Distance"))
        self.btn_start_dist.Bind(wx.EVT_BUTTON, self._on_start_distance)
        dist_sizer.Add(self.btn_start_dist, 0, wx.ALL | wx.EXPAND, 5)
        
        # Current measurement
        self.txt_distance = wx.TextCtrl(
            self, wx.ID_ANY, "",
            style=wx.TE_READONLY
        )
        dist_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Result:")), 0, wx.ALL, 3)
        dist_sizer.Add(self.txt_distance, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(dist_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Area/Volume measurement section
        box_vol = wx.StaticBox(self, wx.ID_ANY, _("Area / Volume"))
        vol_sizer = wx.StaticBoxSizer(box_vol, wx.VERTICAL)
        
        # Area measurement
        self.btn_measure_area = wx.Button(self, wx.ID_ANY, _("Measure Area (2D)"))
        self.btn_measure_area.Bind(wx.EVT_BUTTON, self._on_measure_area)
        vol_sizer.Add(self.btn_measure_area, 0, wx.ALL | wx.EXPAND, 3)
        
        # Volume measurement
        self.btn_measure_vol = wx.Button(self, wx.ID_ANY, _("Measure Volume"))
        self.btn_measure_vol.Bind(wx.EVT_BUTTON, self._on_measure_volume)
        vol_sizer.Add(self.btn_measure_vol, 0, wx.ALL | wx.EXPAND, 3)
        
        # Result
        self.txt_volume = wx.TextCtrl(
            self, wx.ID_ANY, "",
            style=wx.TE_READONLY
        )
        vol_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Result:")), 0, wx.ALL, 3)
        vol_sizer.Add(self.txt_volume, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(vol_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Measurement list section
        box_list = wx.StaticBox(self, wx.ID_ANY, _("Saved Measurements"))
        list_sizer = wx.StaticBoxSizer(box_list, wx.VERTICAL)
        
        self.measure_list = wx.ListBox(self, wx.ID_ANY, size=(-1, 100))
        list_sizer.Add(self.measure_list, 1, wx.ALL | wx.EXPAND, 5)
        
        btn_clear = wx.Button(self, wx.ID_ANY, _("Clear All"))
        btn_clear.Bind(wx.EVT_BUTTON, self._on_clear_all)
        list_sizer.Add(btn_clear, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(list_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)
        
    def _on_start_distance(self, event):
        """Handle start distance button click."""
        if not self.rb_dist_3d.GetValue():
            # NOTE: rather than reimplementing 2D point-picking on
            # InVesalius's own 2D canvas (which would need a mouse-drag
            # hook fighting the canvas's existing interactor), this
            # delegates to InVesalius's own real distance-measurement
            # tool the exact same way its toolbar button does - see
            # invesalius/gui/frame.py's _ToggleLinearMeasure(). The
            # result appears in InVesalius's own "Measures" tab; this
            # plugin does not duplicate it into its own list.
            try:
                from invesalius.pubsub import pub as Publisher
                import invesalius.constants as const

                Publisher.sendMessage("Enable style", style=const.STATE_MEASURE_DISTANCE)
                self.txt_distance.SetValue(
                    _("Click 2 points on a 2D slice - result appears in "
                      "InVesalius's Measures tab")
                )
            except ImportError as e:
                print(f"ROI Viewer: could not enable 2D distance tool - {e}")
            return

        if not self.controller.ensure_picker_initialized():
            self.txt_distance.SetValue(_("No 3D view available yet"))
            return

        self.controller.measure_mgr.set_spacing((1.0, 1.0, 1.0))
        self.controller.measure_mgr.start_distance_measurement()
        self._collecting_distance = True
        self.controller.picker.add_callback(self._on_distance_point_picked)
        self.controller.picker.enable()
        self.btn_start_dist.SetLabel(_("Click 2 points in 3D view..."))

    def _on_distance_point_picked(self, world_point):
        """
        Called by the shared PointPicker3D while collecting a 3D
        distance measurement. world_point is already a real (x, y, z)
        mm coordinate from VTK, so MeasurementManager's spacing is left
        at (1, 1, 1) - see _on_start_distance() - to avoid re-scaling an
        already-physical distance.
        """
        if not self._collecting_distance:
            return

        self.controller.measure_mgr.add_point(*world_point)
        if len(self.controller.measure_mgr.current_distance_points) < 2:
            return

        measurement = self.controller.measure_mgr.finish_distance_measurement("3D")
        self._collecting_distance = False
        self.controller.picker.remove_callback(self._on_distance_point_picked)
        wx.CallAfter(self._on_distance_finished, measurement)

    def _on_distance_finished(self, measurement):
        # NOTE: reached via wx.CallAfter from _on_distance_point_picked(),
        # so - same as interaction_panel.py's update_coordinates() - this
        # can run after this panel was destroyed if the ROI Viewer window
        # closed between the pick and this callback firing. Guarded as
        # defense in depth alongside the picker-observer cleanup in
        # picker_3d.PointPicker3D.cleanup().
        try:
            self.btn_start_dist.SetLabel(_("Start Distance"))
            if measurement is None:
                return
            self.set_distance_result(measurement.distance)
            self.add_measurement(measurement.name, measurement.distance, measurement.unit)
        except RuntimeError:
            pass

    def _on_measure_area(self, event):
        """
        Handle measure area button click - delegates to InVesalius's
        real "density polygon" tool (draw a polygon on a 2D slice; it
        reports area and density stats for the enclosed region in
        InVesalius's own Measures tab). Same delegation approach as 2D
        distance above - see that method's NOTE.
        """
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.constants as const

            Publisher.sendMessage("Enable style", style=const.STATE_MEASURE_DENSITY_POLYGON)
            self.txt_volume.SetValue(
                _("Draw a polygon on a 2D slice - result appears in "
                  "InVesalius's Measures tab")
            )
        except ImportError as e:
            print(f"ROI Viewer: could not enable area tool - {e}")

    def _on_measure_volume(self, event):
        """Handle measure volume button click - real current-mask volume."""
        try:
            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            mask = pi.get_current_mask()
            if mask is None or mask.matrix is None:
                self.txt_volume.SetValue(_("No mask selected"))
                return

            self.controller.measure_mgr.set_spacing(pi.get_spacing())
            # NOTE (bug found + fixed via runtime guide verification):
            # mask.matrix carries a 1-voxel padding border that is not
            # real image data - each axial slice's matrix[n, 0, 0] cell
            # in particular doubles as Slice.do_threshold_to_all_slices()'s
            # lazy-threshold "already processed" sentinel and gets set
            # to 1 for real thresholded masks (see
            # core/annotation.py/ARCHITECTURE.md notes on this same
            # padding contract elsewhere). Passing the full padded
            # matrix here made calculate_volume()'s `np.sum(mask > 0)`
            # count those non-image sentinel/padding cells as if they
            # were real foreground voxels, inflating the reported
            # volume slightly (confirmed for real: UI showed 9575.83mm3
            # vs 9574.80mm3 independently computed from the real
            # interior voxels only). Use the interior only.
            measurement = self.controller.measure_mgr.add_volume_measurement(
                name="", mask_index=mask.index, mask=mask.matrix[1:, 1:, 1:]
            )
            self.txt_volume.SetValue(f"{measurement.volume:.2f} {measurement.unit}")
            self.add_measurement(measurement.name, measurement.volume, measurement.unit)
        except Exception as e:
            self.txt_volume.SetValue(_("Volume measurement failed"))
            print(f"ROI Viewer: volume measurement failed - {e}")

    def _on_clear_all(self, event):
        """Handle clear all button click."""
        self.measure_list.Clear()
        self.txt_distance.SetValue("")
        self.txt_volume.SetValue("")
        self.controller.measure_mgr.clear()
        
    def add_measurement(self, name, value, unit):
        """Add a measurement to the list."""
        text = f"{name}: {value:.2f} {unit}"
        self.measure_list.Append(text)
        
    def set_distance_result(self, distance):
        """Set the distance measurement result."""
        self.txt_distance.SetValue(f"{distance:.2f} mm")
