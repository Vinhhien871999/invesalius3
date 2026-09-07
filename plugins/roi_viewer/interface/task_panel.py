# --------------------------------------------------------------------------
# Task Panel Module
# Description: Custom task panel for ROI Viewer
# --------------------------------------------------------------------------

import wx
import os

try:
    from invesalius.i18n import tr as _
    from invesalius import inv_paths
except ImportError:
    def _(s):
        return s
    inv_paths = None


class ROITaskPanel(wx.Panel):
    """
    Custom task panel that integrates ROI Viewer into InVesalius task flow.
    This panel appears in the left sidebar of InVesalius.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        
        # State
        self.project_loaded = False
        
        self._init_ui()
        self._bind_events()
        
    def _init_ui(self):
        """Initialize the UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("ROI Viewer"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Separator
        line = wx.StaticLine(self, wx.ID_ANY, style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.EXPAND | wx.ALL, 5)
        
        # Import section
        self._create_import_section(sizer)
        
        # Navigation section
        self._create_navigation_section(sizer)
        
        # Quick tools section
        self._create_tools_section(sizer)
        
        # Status
        self.status_text = wx.StaticText(
            self, wx.ID_ANY, 
            _("Status: No project loaded"),
            style=wx.ST_NO_AUTORESIZE
        )
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)
        
    def _create_import_section(self, parent_sizer):
        """Create the import section."""
        box = wx.StaticBox(self, wx.ID_ANY, _("Import"))
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        btn_import = wx.Button(self, wx.ID_ANY, _("Import DICOM Folder"))
        btn_import.Bind(wx.EVT_BUTTON, self._on_import_dicom)
        box_sizer.Add(btn_import, 0, wx.ALL | wx.EXPAND, 3)
        
        btn_open = wx.Button(self, wx.ID_ANY, _("Open Project"))
        btn_open.Bind(wx.EVT_BUTTON, self._on_open_project)
        box_sizer.Add(btn_open, 0, wx.ALL | wx.EXPAND, 3)
        
        parent_sizer.Add(box_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
    def _create_navigation_section(self, parent_sizer):
        """Create the navigation section."""
        box = wx.StaticBox(self, wx.ID_ANY, _("Navigation"))
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        # Plane selection
        plane_row = wx.BoxSizer(wx.HORIZONTAL)
        plane_row.Add(wx.StaticText(self, wx.ID_ANY, _("Plane:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.plane_choice = wx.Choice(self, wx.ID_ANY, choices=["Axial", "Coronal", "Sagittal"])
        self.plane_choice.SetSelection(0)
        self.plane_choice.Bind(wx.EVT_CHOICE, self._on_plane_change)
        plane_row.Add(self.plane_choice, 1, wx.ALL, 3)
        
        box_sizer.Add(plane_row, 0, wx.EXPAND, 3)
        
        # Slice slider
        self.slice_slider = wx.Slider(
            self, wx.ID_ANY, 0, 0, 100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        self.slice_slider.Bind(wx.EVT_SLIDER, self._on_slice_change)
        box_sizer.Add(self.slice_slider, 0, wx.ALL | wx.EXPAND, 3)
        
        # Slice info
        self.slice_info = wx.StaticText(self, wx.ID_ANY, _("Slice: 0 / 0"))
        box_sizer.Add(self.slice_info, 0, wx.ALL | wx.ALIGN_CENTER, 3)
        
        parent_sizer.Add(box_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
    def _create_tools_section(self, parent_sizer):
        """Create the quick tools section."""
        box = wx.StaticBox(self, wx.ID_ANY, _("Quick Tools"))
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        
        # Window/Level presets
        wl_row = wx.BoxSizer(wx.HORIZONTAL)
        wl_row.Add(wx.StaticText(self, wx.ID_ANY, _("Preset:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.wl_choice = wx.Choice(self, wx.ID_ANY, choices=[
            "Bone", "Soft Tissue", "Lung", "Brain", "Custom"
        ])
        self.wl_choice.SetSelection(0)
        self.wl_choice.Bind(wx.EVT_CHOICE, self._on_wl_preset_change)
        wl_row.Add(self.wl_choice, 1, wx.ALL, 3)
        
        box_sizer.Add(wl_row, 0, wx.EXPAND, 3)
        
        # 3D view toggle
        self.cb_show_3d = wx.CheckBox(self, wx.ID_ANY, _("Show 3D View"))
        self.cb_show_3d.SetValue(True)
        self.cb_show_3d.Bind(wx.EVT_CHECKBOX, self._on_3d_toggle)
        box_sizer.Add(self.cb_show_3d, 0, wx.ALL, 3)
        
        # Sync 2D-3D toggle
        self.cb_sync = wx.CheckBox(self, wx.ID_ANY, _("Sync 2D-3D"))
        self.cb_sync.SetValue(True)
        box_sizer.Add(self.cb_sync, 0, wx.ALL, 3)
        
        parent_sizer.Add(box_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
    def _bind_events(self):
        """Bind pubsub events."""
        try:
            from invesalius.pubsub import pub as Publisher
            
            Publisher.subscribe(self._on_project_load, "Load project data")
            Publisher.subscribe(self._on_project_close, "Close project data")
            Publisher.subscribe(self._on_slice_update, "Reload actual slice")
            
        except ImportError:
            pass
            
    def _on_import_dicom(self, event):
        """Handle import DICOM button click."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show import directory dialog")
        except ImportError:
            pass
            
    def _on_open_project(self, event):
        """Handle open project button click."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show open project dialog")
        except ImportError:
            pass
            
    def _on_plane_change(self, event):
        """Handle plane selection change."""
        # NOTE: InVesalius core spells this plane "SAGITAL" (one T) - see
        # invesalius/control.py and invesalius/data/viewer_slice.py. The
        # extra T here meant this plane's messages never reached any real
        # listener.
        planes = ["AXIAL", "CORONAL", "SAGITAL"]
        plane = planes[self.plane_choice.GetSelection()]
        
        try:
            from invesalius.pubsub import pub as Publisher
            # NOTE: real subscribers listen on the per-plane tuple topic
            # with a single `index` kwarg - see the fix explained in
            # main.py's _subscribe_events().
            Publisher.sendMessage(("Set scroll position", plane), index=self.slice_slider.GetValue())
        except ImportError:
            pass
            
    def _on_slice_change(self, event):
        """Handle slice slider change."""
        # NOTE: InVesalius core spells this plane "SAGITAL" (one T) - see
        # invesalius/control.py and invesalius/data/viewer_slice.py. The
        # extra T here meant this plane's messages never reached any real
        # listener.
        planes = ["AXIAL", "CORONAL", "SAGITAL"]
        plane = planes[self.plane_choice.GetSelection()]
        index = self.slice_slider.GetValue()
        
        self.slice_info.SetLabel(f"Slice: {index} / {self.slice_slider.GetMax()}")
        
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage(("Set scroll position", plane), index=index)
        except ImportError:
            pass
            
    def _on_wl_preset_change(self, event):
        """Handle window/level preset change."""
        presets = {
            0: (2000, 500),    # Bone
            1: (400, 40),      # Soft Tissue
            2: (1500, -600),  # Lung
            3: (80, 40),      # Brain
            4: (400, 40),     # Custom
        }
        
        window, level = presets.get(self.wl_choice.GetSelection(), (400, 40))
        
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Update window level value", window=window, level=level)
        except ImportError:
            pass
            
    def _on_3d_toggle(self, event):
        """Handle 3D view toggle."""
        show = self.cb_show_3d.GetValue()
        try:
            from invesalius.pubsub import pub as Publisher
            if show:
                Publisher.sendMessage("Show volume viewer")
            else:
                Publisher.sendMessage("Hide volume viewer")
        except ImportError:
            pass
            
    def _on_project_load(self, create_default_mask=True, end_busy_cursor=True):
        """
        Handle project load event.

        NOTE: pypubsub infers this topic's accepted arguments from
        invesalius.control.Controller.LoadProject, the first subscriber
        (`create_default_mask=True, end_busy_cursor=True` - see
        invesalius/control.py:853), and requires every subscriber to
        accept them. A zero-arg handler here raised ListenerMismatchError
        the moment anything tried to instantiate this panel.
        """
        self.project_loaded = True
        self.status_text.SetLabel(_("Status: Project loaded"))
        
        # Update slice slider range
        try:
            import invesalius.data.slice_ as sl
            slice_data = sl.Slice()
            if slice_data.matrix is not None:
                shape = slice_data.matrix.shape
                plane = ["AXIAL", "CORONAL", "SAGITTAL"][self.plane_choice.GetSelection()]
                
                if plane == "AXIAL":
                    max_slice = shape[0] - 1
                elif plane == "CORONAL":
                    max_slice = shape[1] - 1
                else:
                    max_slice = shape[2] - 1
                    
                self.slice_slider.SetRange(0, max_slice)
                self.slice_slider.SetValue(max_slice // 2)
                self.slice_info.SetLabel(f"Slice: {max_slice // 2} / {max_slice}")
                
        except ImportError:
            pass
            
    def _on_project_close(self):
        """Handle project close event."""
        self.project_loaded = False
        self.status_text.SetLabel(_("Status: No project loaded"))
        self.slice_slider.SetRange(0, 100)
        self.slice_slider.SetValue(0)
        self.slice_info.SetLabel("Slice: 0 / 0")
        
    def _on_slice_update(self):
        """Handle slice update event."""
        pass  # Can be used to refresh UI elements
