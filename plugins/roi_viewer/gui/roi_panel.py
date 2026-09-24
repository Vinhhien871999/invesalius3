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

# Import constants
try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s

# Import core modules
from ..core import (
    roi_manager, picker_3d, sync_2d3d, segmentation, mask_editor, measurement,
    annotation, exporters, marker_3d, slice_planes_3d,
)

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
        # Phase 09 (Sync 2D -> 3D): visual counterpart to the real 2D
        # crosshair - see on_cross_focal_point_changed() below.
        self.marker_3d = marker_3d.CrosshairMarker3D()
        # Phase 13.5 (pre-Phase-14, visual enhancement of the same C8
        # feature - not a new C9): 3 geometric planes showing the
        # current Axial/Coronal/Sagital slice positions inside the
        # Volume view. Driven by the exact same event as marker_3d
        # above (see on_cross_focal_point_changed()). Default ON, per
        # the "Show slice planes in 3D" checkbox in interaction_panel.py
        # (a separate concern from whether Sync 2D->3D itself is on).
        self.slice_planes_3d = slice_planes_3d.SlicePlanes3D()
        self.show_slice_planes = True
        # Phase 09 (F3 fix): tracked independently of the Sync 2D->3D
        # checkbox/visual marker above - this is "the last real,
        # trustworthy world position InVesalius told us about", used
        # by annotation_panel.py._on_add_annotation() as a fallback
        # when no 3D pick has happened yet, so it never has to invent a
        # fake (0, 0, 0) position. See get_current_reference_position().
        self._last_cross_focal_point = None

        # State variables
        #
        # Phase 09 bug found via Sync 2D->3D testing (same class of bug
        # as the Round-2 ROI-List one documented just below, but missed
        # for this flag): project_loaded defaulted to False here and
        # was ONLY ever set True reactively by on_project_load() (a
        # FUTURE "Load project data" event) - never initialized from
        # whatever real project state already exists at construction
        # time. In the single most common real workflow (import DICOM,
        # THEN open this plugin from the menu), that event already
        # fired before this window/its pubsub subscriptions even
        # existed, so project_loaded silently stayed False for the
        # window's entire lifetime - breaking on_slice_change(),
        # on_mask_update(), and Sync 2D->3D's
        # on_cross_focal_point_changed() (all three gate on this flag)
        # even though a project was genuinely open. Initialize it from
        # real current state via the same real check
        # interface/project_interface.py.ProjectInterface.
        # is_project_loaded() already uses (Project().name != "").
        try:
            from ..interface.project_interface import ProjectInterface

            self.project_loaded = ProjectInterface().is_project_loaded()
        except Exception:
            self.project_loaded = False
        self.current_mask_index = None
        self._picker_initialized = False

        # Build UI
        self._init_ui()
        self.Centre()

        # Round-2 audit, section E: a real gap found via
        # test_roi_rebuild_after_project_load.py - if the user imports
        # DICOM (or opens a project) FIRST and only THEN opens this
        # plugin from the Plugins menu (the single most common real
        # workflow), on_roi_source_changed()/rebuild_from_project_masks()
        # had never run for THIS window yet - they only fire reactively
        # on FUTURE mask/project events (main.py's pubsub
        # subscriptions), not retroactively for state that already
        # existed when the window was created. The ROI List started
        # empty even though Project().mask_dict already had the
        # DICOM-import default mask in it. Populate the cache (and the
        # ROI List widget, already built by _init_ui() above) from
        # whatever real masks already exist right away.
        self.on_roi_source_changed()

        # Detach the shared picker from the real VTK interactor when
        # this window closes (e.g. the user hits the [X] button) - see
        # picker_3d.PointPicker3D.cleanup()'s docstring for the real
        # crash this prevents (a stale observer from a closed-and-
        # reopened ROI Viewer window firing into destroyed widgets).
        #
        # NOTE: uses EVT_CLOSE, not EVT_WINDOW_DESTROY. EVT_CLOSE is the
        # event a wx.Frame's own [X] button (and any Close() call)
        # actually raises, with the default handler then calling
        # Destroy(). EVT_WINDOW_DESTROY turned out to be unreliable
        # here in testing - a plain Bind() on the frame did not
        # consistently fire when the window was torn down, so cleanup()
        # never ran. Handling EVT_CLOSE ourselves and calling Destroy()
        # after cleanup covers the real user-facing path (clicking the
        # window's close button) deterministically.
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_close(self, event):
        try:
            self.picker.cleanup()
        except Exception as e:
            print(f"ROI Viewer: picker cleanup on close failed - {e}")
        try:
            # Same leak class as the picker observer above (Phase
            # 09 SYNC-T6): the real 3D renderer is a singleton that
            # outlives this window - an un-detached marker actor
            # would linger in the scene (and get duplicated on the
            # next reopen) if not removed here.
            self.marker_3d.detach()
        except Exception as e:
            print(f"ROI Viewer: 3D marker cleanup on close failed - {e}")
        try:
            # Same leak class as marker_3d above (Phase 13.5) - all 3
            # plane actors must be removed here too.
            self.slice_planes_3d.detach()
        except Exception as e:
            print(f"ROI Viewer: 3D slice planes cleanup on close failed - {e}")
        self.Destroy()

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
        # Phase 13.5: a freshly-loaded project may have entirely
        # different dimensions/spacing than whatever the slice planes
        # were last sized for (e.g. opening a second, different
        # dataset in the same InVesalius session) - refresh bounds now
        # rather than only lazily inside on_cross_focal_point_changed()
        # (which also does this defensively - see that method's NOTE -
        # but doing it eagerly here too means the planes are correctly
        # sized the moment a real crosshair event arrives, not one
        # event behind).
        bounds = self._compute_volume_bounds()
        if bounds is not None:
            try:
                self.slice_planes_3d.set_bounds(bounds)
            except ValueError as e:
                print(f"ROI Viewer: slice planes bounds refresh on project load skipped - {e}")
        # ROIManager is a cache over real Project().mask_dict, not an
        # independent source of truth (see core/roi_manager.py's module
        # docstring) - rebuild it now so the ROI List reflects whatever
        # masks the just-loaded project actually has (including a
        # freshly-opened .inv3 with masks created in a previous
        # session, which this plugin's own session never created).
        self.on_roi_source_changed()
        # E2 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch only): a preview computed for the
        # OLD project's volume is meaningless (wrong shape/content) once
        # a different project is loaded - never carry it over. Defensive
        # even though on_project_close() already does this in the normal
        # open-a-different-project flow.
        if hasattr(self, "segmentation_panel"):
            self.segmentation_panel.cancel_preview()

        # NOTE: "Load project data" (which drives this call) fires
        # synchronously from *inside* invesalius.control.Controller.
        # OpenProject(), before that method's own `session.OpenProject
        # (path)` call runs a couple of lines later - so
        # invesalius.session.Session().GetState("project_path") is
        # still the *previous* project's path (or None) right now, not
        # the one that was just opened. Deferring via wx.CallAfter runs
        # after OpenProject() has fully returned to the event loop
        # (including that session.OpenProject(path) call), so the path
        # is correct by the time this fires - see
        # core/annotation.py.AnnotationManager's module docstring for
        # why a sidecar file (keyed off this exact path) is how
        # annotations are persisted.
        import wx
        wx.CallAfter(self._try_load_annotation_sidecar)

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
        # A marker positioned in the OLD project's coordinate space is
        # meaningless (and could even point outside the new volume's
        # bounds) once a different project is loaded - detach() here;
        # on_cross_focal_point_changed() will re-attach() lazily the
        # next real 2D interaction in the new project.
        self.marker_3d.detach()
        # Phase 13.5: same reasoning as marker_3d.detach() above - a
        # plane positioned/sized for the OLD project's bounds is
        # meaningless once a different (or no) project is loaded.
        self.slice_planes_3d.detach()
        self._last_cross_focal_point = None
        # NOTE: the managers above were already cleared before this
        # round, but the widgets that display them were not - closing
        # a project used to leave stale ROI/annotation rows visible in
        # both list widgets even though the underlying data was gone.
        if hasattr(self, "segmentation_panel"):
            self.segmentation_panel._refresh_roi_list()
            # E2: same reasoning as on_project_load()'s call above - a
            # preview tied to the volume that's now closing must not
            # survive into whatever project (if any) opens next.
            self.segmentation_panel.cancel_preview()
        if hasattr(self, "annotation_panel"):
            self.annotation_panel.refresh_from_manager()
        print("ROI Viewer: Project closed")

    def get_current_reference_position(self):
        """
        Phase 09 (F3 fix): the single real, trustworthy "current
        position" annotation_panel.py._on_add_annotation() should use -
        never a fake (0, 0, 0) placeholder. Priority order matches the
        plan exactly:
          A) the last real 3D pick (picker_3d.PointPicker3D.
             get_last_point()) - most specific, user explicitly clicked
             a point;
          B) the last real 2D crosshair position ("Set cross focal
             point" - see on_cross_focal_point_changed() above) -
             tracked regardless of the Sync 2D->3D checkbox;
          C) None - caller must refuse to create the annotation and
             tell the user to pick a position first.
        """
        picked = self.picker.get_last_point()
        if picked is not None:
            return picked
        return self._last_cross_focal_point

    def on_roi_source_changed(self):
        """
        Called whenever a real mask was created/renamed/shown-hidden/
        removed, through this plugin or InVesalius's native Masks tab
        (see main.py's extra pubsub subscriptions). Resyncs the
        ROIManager cache and refreshes the ROI List widget.
        """
        self.roi_mgr.rebuild_from_project_masks()
        if hasattr(self, "segmentation_panel"):
            self.segmentation_panel._refresh_roi_list()

    def _try_load_annotation_sidecar(self):
        """See on_project_load()'s NOTE on why this is deferred."""
        try:
            import invesalius.session as ses

            project_path = ses.Session().GetState("project_path")
            if not project_path:
                return
            dirpath, filename = project_path
            if self.annotation_mgr.load_sidecar(dirpath, filename):
                if hasattr(self, "annotation_panel"):
                    self.annotation_panel.refresh_from_manager()
                print(f"ROI Viewer: loaded annotations from sidecar for {filename}")
        except Exception as e:
            print(f"ROI Viewer: annotation sidecar load on project-load failed - {e}")

    def on_slice_change(self, plane, index):
        """Handle slice position change."""
        if self.project_loaded:
            # Update sync manager
            self.sync_mgr.set_slice_position(plane, index)

    def on_cross_focal_point_changed(self, world_position):
        """
        Phase 09 - Sync 2D -> 3D: the user changed position on a real
        2D view (main.py forwards InVesalius's real "Set cross focal
        point" topic here - see that subscription's NOTE for why this
        exact topic). Moves a small 3D marker (core/marker_3d.
        CrosshairMarker3D) to the same real world position, so the 3D
        view shows a visual counterpart to the 2D crosshair - without
        auto-rotating the camera or building a new MPR system (out of
        scope per the plan).

        Phase 13.5 (pre-Phase-14 visual enhancement, same C8 feature -
        not a new C9): ALSO updates core/slice_planes_3d.SlicePlanes3D,
        3 semi-transparent geometric planes showing where the current
        Axial/Coronal/Sagital 2D slices sit within the real volume -
        driven by the exact same event, same sync_2d_3d guard, same
        real-viewer/renderer lookup as the marker above (no second
        event path, no new pubsub topic). Visibility of the PLANES
        specifically is additionally gated by self.show_slice_planes
        (the "Show slice planes in 3D" checkbox - a separate concern
        from whether Sync 2D->3D itself is on, see interaction_panel.py)
        - the marker's own visibility is unaffected by this flag.
        Does NOT touch the camera (no rotate/zoom/pan/reset) and does
        NOT rebuild any surface - only actor geometry moves.

        Guarded by self.sync_mgr.sync_2d_3d - the EXACT SAME flag the
        "Sync 2D -> 3D" checkbox in interaction_panel.py already toggles
        via sync_mgr.enable_sync_2d_3d()/disable_sync_2d_3d() (that
        checkbox existed since before Phase 09 but nothing ever read
        the flag it set - see CT3D_FEATURE_AUDIT.md's Sync 2D->3D row).
        When disabled, this method does nothing at all: an
        already-placed marker/planes stay exactly where they were
        (frozen, not hidden), and never-yet-placed ones stay
        never-placed - both satisfy "checkbox OFF -> 2D change -> 3D
        target does not change" without needing extra state.

        No event-loop risk: this method only ever READS pubsub (it
        never calls Publisher.sendMessage() with a topic that could
        feed back into itself - "Render volume viewer" only repaints,
        it carries no position and is not among this method's own
        triggers) - a one-directional consumer cannot form a cycle by
        construction, so no suppress-flag/debounce machinery is needed.
        """
        if not self.project_loaded:
            return
        # Track this regardless of the Sync 2D->3D checkbox - tracking
        # "where is the crosshair right now" for annotation purposes
        # (F3) is a different concern than the checkbox's own job
        # (whether to show/move the visual 3D marker).
        try:
            self._last_cross_focal_point = tuple(float(c) for c in world_position)
        except (TypeError, ValueError):
            pass
        if not self.sync_mgr.sync_2d_3d:
            return
        try:
            from ..interface.view_interface import ViewInterface

            viewer = ViewInterface().get_volume_viewer()
            if viewer is None or not hasattr(viewer, "ren"):
                return
            if not self.marker_3d.attach(viewer.ren):
                return
            x, y, z = world_position
            self.marker_3d.update_position(x, y, z)

            # Slice planes: same event, same renderer, real bounds
            # derived from real project data every time (not cached
            # only at project-load time) - a crosshair event can
            # legitimately arrive before any "Load project data" event
            # this window ever saw (same class of eager-init gap
            # self.project_loaded itself was fixed for in Phase 09 -
            # see __init__'s NOTE), so bounds are (re)computed here
            # defensively rather than relying solely on
            # on_project_load()'s refresh.
            if self.slice_planes_3d.attach(viewer.ren):
                bounds = self._compute_volume_bounds()
                if bounds is not None:
                    try:
                        self.slice_planes_3d.set_bounds(bounds)
                        self.slice_planes_3d.update_position((x, y, z))
                        self.slice_planes_3d.set_visible(self.show_slice_planes)
                    except ValueError as e:
                        print(f"ROI Viewer: slice planes geometry update skipped - {e}")

            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Render volume viewer")
        except Exception as e:
            print(f"ROI Viewer: Sync 2D->3D marker update failed - {e}")

    def _compute_volume_bounds(self):
        """
        Real world-space bounds (xmin, xmax, ymin, ymax, zmin, zmax) of
        the whole loaded volume (not just a mask/surface, which may
        only occupy part of it) - reuses the exact same real, already
        unit-tested voxel_to_world() convention
        interface/project_interface.py.ProjectInterface already
        implements (see its docstring for the axis mapping: world X =
        SAGITAL, Y = CORONAL, Z = AXIAL). Never hardcodes dimensions/
        spacing/origin. Returns None if no real volume shape is known
        yet (e.g. no project loaded).
        """
        try:
            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            shape = pi.get_shape()
            if not shape or shape == (0, 0, 0):
                return None
            corner_a = pi.voxel_to_world(0, 0, 0)
            corner_b = pi.voxel_to_world(shape[0] - 1, shape[1] - 1, shape[2] - 1)
            return (
                min(corner_a[0], corner_b[0]), max(corner_a[0], corner_b[0]),
                min(corner_a[1], corner_b[1]), max(corner_a[1], corner_b[1]),
                min(corner_a[2], corner_b[2]), max(corner_a[2], corner_b[2]),
            )
        except Exception as e:
            print(f"ROI Viewer: could not compute real volume bounds - {e}")
            return None

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
