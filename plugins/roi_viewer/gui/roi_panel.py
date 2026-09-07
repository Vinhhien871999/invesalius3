# --------------------------------------------------------------------------
# ROI Viewer - Main Panel
# Description: Main frame for the ROI Viewer plugin. Hosts the 5 tool
#              panels (Interaction, Segmentation, Measurements,
#              Annotations, Export) and owns the shared core/ manager
#              instances they all operate on.
#
# NOTE: this used to define its own local, minimal InteractionPanel /
# SegmentationPanel / MeasurementPanel / AnnotationPanel / ExportPanel
# classes here instead of using the fully-implemented, already-wired
# ones in gui/interaction_panel.py, gui/measurement_panel.py,
# gui/annotation_panel.py and gui/export_panel.py - so none of those
# files' real event handlers, nor any of core/'s business logic, were
# ever reachable from a button click. That's fixed below: the real
# panels are used, each given a reference to this frame (as
# `controller`) so they can call into the shared managers and into
# InVesalius itself through interface/.
#
# Known gaps still open after this pass (see the individual panel
# modules for the specific NOTE comments):
#   - 2D distance/area measurement need a mouse-drag hook on
#     InVesalius's own 2D slice canvas, which isn't wired up.
#   - Brush/eraser painting (F9) likewise needs a mouse-drag hook on the
#     2D canvas; Undo/Redo instead snapshot/restore the real current
#     mask's full voxel data via button clicks.
#   - 3D point picking -> 2D slice sync uses a voxel/world coordinate
#     mapping that assumes an axis-aligned volume (no gantry-tilt/
#     rotation correction) - see core/sync_2d3d.py's world_to_voxel().
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

# Import the real, wired tool panels.
from .interaction_panel import InteractionPanel
from .segmentation_panel import SegmentationPanel
from .measurement_panel import MeasurementPanel
from .annotation_panel import AnnotationPanel
from .export_panel import ExportPanel


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

        # Initialize core managers - shared with every tool panel below
        # via `controller` (this frame).
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
        self._picker_initialized = False

        # Build UI
        self._init_ui()
        self.Centre()

    def _init_ui(self):
        """Initialize the user interface."""
        # Create notebook for organizing tools
        self.notebook = wx.Notebook(self)

        # Create panels - each gets `self` as `controller` so it can
        # reach the shared managers above and the interface/ bridge to
        # real InVesalius data.
        self.interaction_panel = InteractionPanel(self.notebook, self)
        self.segmentation_panel = SegmentationPanel(self.notebook, self)
        self.measurement_panel = MeasurementPanel(self.notebook, self)
        self.annotation_panel = AnnotationPanel(self.notebook, self)
        self.export_panel = ExportPanel(self.notebook, self)

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

    def ensure_picker_initialized(self) -> bool:
        """
        Hook the shared PointPicker3D up to InVesalius's real 3D
        renderer/interactor the first time it's needed (there's nothing
        to hook until a project with a 3D view actually exists). Shared
        by InteractionPanel (single-point picking) and MeasurementPanel
        (3D distance endpoint picking) so both operate on the exact same
        picker/callback list.
        """
        if self._picker_initialized:
            return True

        from ..interface.view_interface import ViewInterface

        viewer = ViewInterface().get_volume_viewer()
        if viewer is None or not hasattr(viewer, "ren") or not hasattr(viewer, "interactor"):
            return False

        self.picker.initialize_picker(viewer.ren, viewer.interactor)
        if self.picker.picker is None:
            # initialize_picker() catches ImportError internally and
            # leaves picker.picker as None on failure.
            return False

        self._picker_initialized = True
        return True

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
        self.roi_mgr.clear()
        self.mask_mgr.clear_all()
        self._picker_initialized = False
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
