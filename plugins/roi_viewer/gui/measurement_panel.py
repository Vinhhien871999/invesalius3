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
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self._init_ui()
        
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
        mode = "3D" if self.rb_dist_3d.GetValue() else "2D"
        self.btn_start_dist.SetLabel(_("Click 2 points..."))
        # TODO: Connect to actual measurement tool
        
    def _on_measure_area(self, event):
        """Handle measure area button click."""
        self.txt_volume.SetValue(_("Draw a polygon to measure area"))
        # TODO: Connect to actual area measurement tool
        
    def _on_measure_volume(self, event):
        """Handle measure volume button click."""
        self.txt_volume.SetValue(_("Select a mask to measure volume"))
        # TODO: Connect to actual volume calculation
        
    def _on_clear_all(self, event):
        """Handle clear all button click."""
        self.measure_list.Clear()
        self.txt_distance.SetValue("")
        self.txt_volume.SetValue("")
        
    def add_measurement(self, name, value, unit):
        """Add a measurement to the list."""
        text = f"{name}: {value:.2f} {unit}"
        self.measure_list.Append(text)
        
    def set_distance_result(self, distance):
        """Set the distance measurement result."""
        self.txt_distance.SetValue(f"{distance:.2f} mm")
