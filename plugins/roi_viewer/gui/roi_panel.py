# --------------------------------------------------------------------------
# ROI Viewer - Main Panel
# Description: Main panel for the ROI Viewer plugin
# --------------------------------------------------------------------------

import wx
import wx.lib.scrolledpanel as scrolled

# Import constants
try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s

# Import core modules
from ..core import roi_manager, picker_3d, sync_2d3d, segmentation, mask_editor, measurement, annotation, exporters


class ROIViewerFrame(wx.Frame):
    """
    Main frame for the ROI Viewer plugin.
    This frame contains all the ROI editing tools and visualization controls.
    """
    
    def __init__(self, parent):
        wx.Frame.__init__(
            self, 
            parent, 
            id=wx.ID_ANY,
            title=_("ROI Viewer - CT 3D Visualization"),
            size=wx.Size(400, 600)
        )
        
        # Initialize core managers
        self.roi_mgr = roi_manager.ROIManager()
        self.picker = picker_3d.PointPicker3D()
        self.sync_mgr = sync_2d3d.SyncManager2D3D()
        self.seg_mgr = segmentation.SegmentationManager()
        self.mask_mgr = mask_editor.MaskEditorManager()
        self.measure_mgr = measurement.MeasurementManager()
        self.annotation_mgr = annotation.AnnotationManager()
        self.exporter = exporters.ExporterManager()
        
        # State variables
        self.project_loaded = False
        self.current_mask_index = None
        
        # Build UI
        self._init_ui()
        self.Centre()
        
    def _init_ui(self):
        """Initialize the user interface."""
        # Create notebook for organizing tools
        self.notebook = wx.Notebook(self)
        
        # Create panels
        self.interaction_panel = InteractionPanel(self.notebook)
        self.segmentation_panel = SegmentationPanel(self.notebook)
        self.measurement_panel = MeasurementPanel(self.notebook)
        self.annotation_panel = AnnotationPanel(self.notebook)
        self.export_panel = ExportPanel(self.notebook)
        
        # Add panels to notebook
        self.notebook.AddPage(self.interaction_panel, _("Interaction"))
        self.notebook.AddPage(self.segmentation_panel, _("Segmentation"))
        self.notebook.AddPage(self.measurement_panel, _("Measurements"))
        self.notebook.AddPage(self.annotation_panel, _("Annotations"))
        self.notebook.AddPage(self.export_panel, _("Export"))
        
        # Main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(sizer)
        
    def on_project_load(self):
        """Handle project load event."""
        self.project_loaded = True
        print("ROI Viewer: Project loaded")
        # Refresh all panels
        self.Refresh()
        
    def on_project_close(self):
        """Handle project close event."""
        self.project_loaded = False
        self.current_mask_index = None
        # Clear all managers
        self.measure_mgr.clear()
        self.annotation_mgr.clear()
        print("ROI Viewer: Project closed")
        
    def on_slice_change(self, plane, index):
        """Handle slice position change."""
        if self.project_loaded:
            # Update sync manager
            self.sync_mgr.set_slice_position(plane, index)
            
    def on_mask_update(self):
        """Handle mask update event."""
        if self.project_loaded:
            # Trigger 3D update
            self.sync_mgr.request_3d_update()
            
    def on_mask_created(self, mask_name, thresh, colour):
        """Handle mask created event."""
        print(f"ROI Viewer: Mask created - {mask_name}")
        
    def on_mask_selected(self, index):
        """Handle mask selected event."""
        self.current_mask_index = index
        print(f"ROI Viewer: Mask selected - {index}")


class InteractionPanel(wx.Panel):
    """
    Panel for 2D-3D interaction tools.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the interaction panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("2D-3D Interaction Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # 3D Picking section
        box_pick = wx.StaticBox(self, wx.ID_ANY, _("3D Point Picking"))
        pick_sizer = wx.StaticBoxSizer(box_pick, wx.VERTICAL)
        
        self.cb_sync_3d_2d = wx.CheckBox(self, wx.ID_ANY, _("Sync 3D to 2D"))
        self.cb_sync_3d_2d.SetValue(True)
        pick_sizer.Add(self.cb_sync_3d_2d, 0, wx.ALL, 5)
        
        self.cb_sync_2d_3d = wx.CheckBox(self, wx.ID_ANY, _("Sync 2D to 3D"))
        self.cb_sync_2d_3d.SetValue(True)
        pick_sizer.Add(self.cb_sync_2d_3d, 0, wx.ALL, 5)
        
        btn_pick = wx.Button(self, wx.ID_ANY, _("Pick Point"))
        pick_sizer.Add(btn_pick, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(pick_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Real-time update section
        box_update = wx.StaticBox(self, wx.ID_ANY, _("Real-time Update"))
        update_sizer = wx.StaticBoxSizer(box_update, wx.VERTICAL)
        
        self.cb_realtime_mask = wx.CheckBox(self, wx.ID_ANY, _("Update mask in real-time"))
        self.cb_realtime_mask.SetValue(True)
        update_sizer.Add(self.cb_realtime_mask, 0, wx.ALL, 5)
        
        self.slider_update_delay = wx.Slider(
            self, wx.ID_ANY, 100, 0, 500,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        update_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Update delay (ms):")), 0, wx.ALL, 5)
        update_sizer.Add(self.slider_update_delay, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(update_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Status
        self.status_text = wx.StaticText(self, wx.ID_ANY, _("Status: Ready"))
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)


class SegmentationPanel(wx.Panel):
    """
    Panel for segmentation tools.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the segmentation panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("ROI Segmentation Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Threshold section
        box_thresh = wx.StaticBox(self, wx.ID_ANY, _("Threshold"))
        thresh_sizer = wx.StaticBoxSizer(box_thresh, wx.VERTICAL)
        
        self.cb_auto_thresh = wx.CheckBox(self, wx.ID_ANY, _("Auto threshold"))
        thresh_sizer.Add(self.cb_auto_thresh, 0, wx.ALL, 5)
        
        thresh_row = wx.BoxSizer(wx.HORIZONTAL)
        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("Min:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.spin_min = wx.SpinCtrl(self, wx.ID_ANY, "0", min=-1024, max=3071)
        thresh_row.Add(self.spin_min, 1, wx.ALL, 5)
        
        thresh_row.Add(wx.StaticText(self, wx.ID_ANY, _("Max:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.spin_max = wx.SpinCtrl(self, wx.ID_ANY, "100", min=-1024, max=3071)
        thresh_row.Add(self.spin_max, 1, wx.ALL, 5)
        
        thresh_sizer.Add(thresh_row, 0, wx.EXPAND, 5)
        
        btn_apply_thresh = wx.Button(self, wx.ID_ANY, _("Apply Threshold"))
        thresh_sizer.Add(btn_apply_thresh, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(thresh_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Brush tools section
        box_brush = wx.StaticBox(self, wx.ID_ANY, _("Brush Tools"))
        brush_sizer = wx.StaticBoxSizer(box_brush, wx.VERTICAL)
        
        brush_row = wx.BoxSizer(wx.HORIZONTAL)
        
        self.rb_brush_draw = wx.RadioButton(self, wx.ID_ANY, _("Draw"), style=wx.RB_GROUP)
        brush_row.Add(self.rb_brush_draw, 0, wx.ALL, 5)
        
        self.rb_brush_erase = wx.RadioButton(self, wx.ID_ANY, _("Erase"))
        brush_row.Add(self.rb_brush_erase, 0, wx.ALL, 5)
        
        brush_sizer.Add(brush_row, 0, wx.EXPAND, 5)
        
        brush_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Brush Size:")), 0, wx.ALL, 5)
        self.slider_brush_size = wx.Slider(
            self, wx.ID_ANY, 5, 1, 50,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        brush_sizer.Add(self.slider_brush_size, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(brush_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Undo/Redo
        undo_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_undo = wx.Button(self, wx.ID_ANY, _("Undo"))
        undo_row.Add(btn_undo, 1, wx.ALL, 5)
        
        btn_redo = wx.Button(self, wx.ID_ANY, _("Redo"))
        undo_row.Add(btn_redo, 1, wx.ALL, 5)
        
        sizer.Add(undo_row, 0, wx.EXPAND, 5)
        
        self.SetSizer(sizer)


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
        
        # Distance measurement
        box_dist = wx.StaticBox(self, wx.ID_ANY, _("Distance Measurement"))
        dist_sizer = wx.StaticBoxSizer(box_dist, wx.VERTICAL)
        
        self.rb_dist_2d = wx.RadioButton(self, wx.ID_ANY, _("2D Distance"), style=wx.RB_GROUP)
        dist_sizer.Add(self.rb_dist_2d, 0, wx.ALL, 5)
        
        self.rb_dist_3d = wx.RadioButton(self, wx.ID_ANY, _("3D Distance"))
        dist_sizer.Add(self.rb_dist_3d, 0, wx.ALL, 5)
        
        self.rb_dist_3d.SetValue(True)
        
        btn_measure_dist = wx.Button(self, wx.ID_ANY, _("Start Distance"))
        dist_sizer.Add(btn_measure_dist, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(dist_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Area/Volume measurement
        box_vol = wx.StaticBox(self, wx.ID_ANY, _("Area / Volume"))
        vol_sizer = wx.StaticBoxSizer(box_vol, wx.VERTICAL)
        
        btn_measure_area = wx.Button(self, wx.ID_ANY, _("Measure Area (2D)"))
        vol_sizer.Add(btn_measure_area, 0, wx.ALL | wx.EXPAND, 5)
        
        btn_measure_vol = wx.Button(self, wx.ID_ANY, _("Measure Volume"))
        vol_sizer.Add(btn_measure_vol, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(vol_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Measurement list
        box_list = wx.StaticBox(self, wx.ID_ANY, _("Measurements"))
        list_sizer = wx.StaticBoxSizer(box_list, wx.VERTICAL)
        
        self.measure_list = wx.ListBox(self, wx.ID_ANY, size=(-1, 100))
        list_sizer.Add(self.measure_list, 1, wx.ALL | wx.EXPAND, 5)
        
        btn_clear_measures = wx.Button(self, wx.ID_ANY, _("Clear All"))
        list_sizer.Add(btn_clear_measures, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(list_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)


class AnnotationPanel(wx.Panel):
    """
    Panel for annotation tools.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the annotation panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("Annotation Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Add annotation
        box_add = wx.StaticBox(self, wx.ID_ANY, _("Add Annotation"))
        add_sizer = wx.StaticBoxSizer(box_add, wx.VERTICAL)
        
        self.txt_annotation = wx.TextCtrl(
            self, wx.ID_ANY, "",
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP,
            size=(-1, 60)
        )
        add_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Text:")), 0, wx.ALL, 5)
        add_sizer.Add(self.txt_annotation, 0, wx.ALL | wx.EXPAND, 5)
        
        add_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Color:")), 0, wx.ALL, 5)
        self.color_picker = wx.ColourPickerCtrl(self)
        self.color_picker.SetColour(wx.Colour(255, 0, 0))
        add_sizer.Add(self.color_picker, 0, wx.ALL, 5)
        
        btn_add_annotation = wx.Button(self, wx.ID_ANY, _("Add at Current Position"))
        add_sizer.Add(btn_add_annotation, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(add_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Annotation list
        box_list = wx.StaticBox(self, wx.ID_ANY, _("Annotations"))
        list_sizer = wx.StaticBoxSizer(box_list, wx.VERTICAL)
        
        self.annotation_list = wx.ListBox(self, wx.ID_ANY, size=(-1, 100))
        list_sizer.Add(self.annotation_list, 1, wx.ALL | wx.EXPAND, 5)
        
        btn_delete_annotation = wx.Button(self, wx.ID_ANY, _("Delete Selected"))
        list_sizer.Add(btn_delete_annotation, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(list_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)


class ExportPanel(wx.Panel):
    """
    Panel for export tools.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the export panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("Export Options"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Export mask
        box_mask = wx.StaticBox(self, wx.ID_ANY, _("Export Mask"))
        mask_sizer = wx.StaticBoxSizer(box_mask, wx.VERTICAL)
        
        format_row = wx.BoxSizer(wx.HORIZONTAL)
        format_row.Add(wx.StaticText(self, wx.ID_ANY, _("Format:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.choice_mask_format = wx.Choice(
            self, wx.ID_ANY,
            choices=["NIfTI (.nii.gz)", "NRRD (.nrrd)", "MetaImage (.mhd)"]
        )
        self.choice_mask_format.SetSelection(0)
        format_row.Add(self.choice_mask_format, 1, wx.ALL, 5)
        
        mask_sizer.Add(format_row, 0, wx.EXPAND, 5)
        
        btn_export_mask = wx.Button(self, wx.ID_ANY, _("Export Mask"))
        mask_sizer.Add(btn_export_mask, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(mask_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Export surface
        box_surf = wx.StaticBox(self, wx.ID_ANY, _("Export Surface"))
        surf_sizer = wx.StaticBoxSizer(box_surf, wx.VERTICAL)
        
        surf_format_row = wx.BoxSizer(wx.HORIZONTAL)
        surf_format_row.Add(wx.StaticText(self, wx.ID_ANY, _("Format:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.choice_surf_format = wx.Choice(
            self, wx.ID_ANY,
            choices=["STL (.stl)", "PLY (.ply)", "OBJ (.obj)", "VTK (.vtk)"]
        )
        self.choice_surf_format.SetSelection(0)
        surf_format_row.Add(self.choice_surf_format, 1, wx.ALL, 5)
        
        surf_sizer.Add(surf_format_row, 0, wx.EXPAND, 5)
        
        btn_export_surf = wx.Button(self, wx.ID_ANY, _("Export Surface"))
        surf_sizer.Add(btn_export_surf, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(surf_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Save project
        box_proj = wx.StaticBox(self, wx.ID_ANY, _("Save Project"))
        proj_sizer = wx.StaticBoxSizer(box_proj, wx.VERTICAL)
        
        self.cb_compress = wx.CheckBox(self, wx.ID_ANY, _("Compress project"))
        self.cb_compress.SetValue(True)
        proj_sizer.Add(self.cb_compress, 0, wx.ALL, 5)
        
        btn_save_proj = wx.Button(self, wx.ID_ANY, _("Save Project"))
        proj_sizer.Add(btn_save_proj, 0, wx.ALL | wx.EXPAND, 5)
        
        sizer.Add(proj_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)
