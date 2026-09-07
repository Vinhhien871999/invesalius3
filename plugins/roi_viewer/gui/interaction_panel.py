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
    """
    
    def __init__(self, parent):
        scrolled.ScrolledPanel.__init__(self, parent)
        
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
        self._update_status()
        
    def _on_sync_2d_3d_changed(self, event):
        """Handle sync 2D to 3D checkbox change."""
        self.sync_2d_3d_enabled = event.IsChecked()
        self._update_status()
        
    def _on_realtime_changed(self, event):
        """Handle real-time update checkbox change."""
        self.realtime_update_enabled = event.IsChecked()
        self._update_status()
        
    def _on_delay_changed(self, event):
        """Handle update delay slider change."""
        self.update_delay = event.GetInt()
        self.lbl_delay_value.SetLabel(f"{self.update_delay} ms")
        
    def _on_brush_size_changed(self, event):
        """Handle brush size slider change."""
        size = event.GetInt()
        self.lbl_brush_size.SetLabel(f"{size} px")
        
    def _on_pick_point(self, event):
        """Handle pick point button click."""
        self.status_text.SetLabel(_("Pick a point in the 3D view..."))
        # This will be connected to the actual picker
        
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
        """Update coordinate display."""
        self.txt_coords.SetValue(f"X: {x:.2f}, Y: {y:.2f}, Z: {z:.2f}")
        
    def get_brush_config(self):
        """Get current brush configuration."""
        return {
            'size': self.slider_brush_size.GetValue(),
            'shape': 'circle' if self.rb_circle.GetValue() else 'square'
        }
        
    def set_status(self, message):
        """Set status message."""
        self.status_text.SetLabel(message)
