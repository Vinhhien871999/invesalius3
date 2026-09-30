# --------------------------------------------------------------------------
# ROI Viewer - Main Panel
# Description: The ROI Viewer's main panel. Hosts the tool pages
#              (Phân đoạn, ROI & 3D, Hiển thị, Công cụ) and owns the
#              shared core/ manager instances they all operate on.
#              Shown docked in InVesalius's main window as a sidebar pane
#              (gui/sidebar.py); it was a separate wx.Frame
#              ("ROIViewerFrame") before 30/09/2026.
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

from ..i18n import _

# Import core modules
from ..core import (
    roi_manager, picker_3d, sync_2d3d, segmentation, mask_editor, measurement,
    annotation, exporters, marker_3d, slice_planes_3d, preview_surface_3d,
    textured_slice_planes_3d, surface_clipping_3d,
)

# Import the real, wired tool panels.
from .interaction_panel import InteractionPanel
from .segmentation_panel import SegmentationPanel
from .measurement_panel import MeasurementPanel
from .annotation_panel import AnnotationPanel
from .export_panel import ExportPanel


def tab_label(text: str) -> str:
    """wx treats '&' in a notebook tab label as a keyboard mnemonic and
    hides it ("ROI & 3D" rendered as "ROI 3D") - double it."""
    return text.replace("&", "&&")


class ROIViewerPanel(wx.Panel):
    """
    The ROI Viewer's main panel: all ROI editing tools and visualization
    controls, and the `controller` every tool page talks to. Hosted by
    gui/sidebar.py - docked in InVesalius's main window, floating, or (when
    the host window has no AUI manager) in a plain frame.
    """

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, id=wx.ID_ANY)
        self._shut_down = False

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
        # E4 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch ONLY): fast, non-authoritative
        # live 3D preview mesh - see core/preview_surface_3d.py's module
        # docstring for the core invariant (never the final surface) and
        # docs/CT3D_ADVANCED_E4_LIVE_3D_PREVIEW_REPORT.md for the full
        # design. Owned here (not on SegmentationPanel) for the same
        # reason marker_3d/slice_planes_3d are owned here - all 3
        # renderer-attached objects share one real Volume renderer that
        # outlives any single SegmentationPanel instance.
        self.preview_surface_3d = preview_surface_3d.PreviewSurfaceManager3D()
        # E5 (Advanced Segmentation Enhancement Track, enhancement/
        # advanced-segmentation branch ONLY): both default OFF/inert -
        # see core/textured_slice_planes_3d.py and core/surface_
        # clipping_3d.py module docstrings for the full source audit.
        # Owned here for the same reason as marker_3d/slice_planes_3d/
        # preview_surface_3d above (shared real Volume renderer that
        # outlives any single SegmentationPanel/InteractionPanel
        # instance).
        self.textured_slice_planes_3d = textured_slice_planes_3d.TexturedSlicePlanes3D()
        self.surface_clipping_3d = surface_clipping_3d.SurfaceClipping3D()
        self.show_texture_planes = False
        # Where the textured planes were last actually built. Deliberately
        # NOT _last_cross_focal_point: that one keeps tracking the crosshair
        # even while Sync 2D->3D is off (annotation fallback, see F3),
        # while the 3D planes stay frozen - a W/L refresh from it would
        # silently move frozen planes.
        self._texture_planes_position = None
        self._wl_texture_refresh_scheduled = False
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

        # Cleanup (picker observer, renderer-attached actors, AI) runs in
        # shutdown(): gui/sidebar.py calls it when the sidebar pane or the
        # floating window is closed - see shutdown().

    def shutdown(self):
        """Detach everything this panel attached to InVesalius's shared
        objects - the picker observer on the real VTK interactor, the
        renderer-attached actors (marker, C8 planes, E4 mesh, E5 textures/
        clipping) and any AI job - before the panel goes away. Idempotent.
        The 3D renderer and interactor outlive this panel, so skipping this
        leaves stale observers/actors (the real crash Phase 09 fixed)."""
        if self._shut_down:
            return
        self._shut_down = True
        try:
            # E6: stop AI before anything else. wx destroys the window at
            # idle time, so the panel's own destroy hook comes too late to
            # stop a wx.CallAfter'd AI result from reaching its widgets.
            self.segmentation_panel.shutdown_ai()
        except Exception as e:
            print(f"ROI Viewer: AI shutdown on close failed - {e}")
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
        try:
            # E4: same leak class as marker_3d/slice_planes_3d above.
            self.preview_surface_3d.detach()
        except Exception as e:
            print(f"ROI Viewer: 3D preview surface cleanup on close failed - {e}")
        try:
            # E5: same leak class as marker_3d/slice_planes_3d/
            # preview_surface_3d above.
            self.textured_slice_planes_3d.detach()
        except Exception as e:
            print(f"ROI Viewer: E5 textured slice planes cleanup on close failed - {e}")
        try:
            self.surface_clipping_3d.detach()
        except Exception as e:
            print(f"ROI Viewer: E5 surface clipping cleanup on close failed - {e}")

    def _on_close(self, event):
        """Shut down and destroy the panel (plain-frame host and tests)."""
        self.shutdown()
        self.Destroy()

    def _init_ui(self):
        """Initialize the user interface."""
        # Create notebook for organizing tools
        self.notebook = wx.Notebook(self)

        # Create panels - each gets `self` as `controller` so it can
        # reach the shared managers above and the interface/ bridge to
        # real InVesalius data.
        self.interaction_panel = InteractionPanel(self.notebook, self)
        # "ROI & 3D" is a plain page; SegmentationPanel builds its ROI
        # management and 3D-surface widgets onto it (one class, two pages -
        # see SegmentationPanel._init_ui()).
        self.roi_3d_page = scrolled.ScrolledPanel(self.notebook)
        self.segmentation_panel = SegmentationPanel(self.notebook, self, roi_page=self.roi_3d_page)
        # "Công cụ": measurements, annotations and export stacked on one
        # scrolling page. Six tabs did not fit a sidebar (~400 px): the last
        # ones were only reachable through the tab-scroll arrows.
        self.tools_page = scrolled.ScrolledPanel(self.notebook)
        self.measurement_panel = MeasurementPanel(self.tools_page, self)
        self.annotation_panel = AnnotationPanel(self.tools_page, self)
        self.export_panel = ExportPanel(self.tools_page, self)
        tools_sizer = wx.BoxSizer(wx.VERTICAL)
        for index, tool in enumerate((self.measurement_panel, self.annotation_panel, self.export_panel)):
            if index:
                tools_sizer.Add(wx.StaticLine(self.tools_page), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            tools_sizer.Add(tool, 0, wx.EXPAND | wx.BOTTOM, 4)
        self.tools_page.SetSizer(tools_sizer)
        self.tools_page.SetupScrolling(scroll_x=False)

        # Workflow order: segment -> manage ROIs / 3D -> display -> tools.
        self.notebook.AddPage(self.segmentation_panel, tab_label(_("Segmentation")))
        self.notebook.AddPage(self.roi_3d_page, tab_label(_("ROI & 3D")))
        self.notebook.AddPage(self.interaction_panel, tab_label(_("Display")))
        self.notebook.AddPage(self.tools_page, tab_label(_("Tools")))

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

    def ensure_preview_surface_attached(self) -> bool:
        """E4: same real "find the volume viewer, attach to viewer.ren"
        pattern as ensure_picker_initialized()/on_cross_focal_point_
        changed()'s marker_3d/slice_planes_3d attach calls above - reused
        here rather than duplicated, called from SegmentationPanel via
        self.controller before scheduling any preview mesh build."""
        from ..interface.view_interface import ViewInterface

        viewer = ViewInterface().get_volume_viewer()
        if viewer is None or not hasattr(viewer, "ren"):
            return False
        return self.preview_surface_3d.attach(viewer.ren)

    def request_render(self):
        """Shared real "please repaint the 3D view" trigger - same real
        pubsub message marker_3d/slice_planes_3d updates already send
        (on_cross_focal_point_changed() above), reused here so E4 has no
        second render-request mechanism."""
        try:
            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Render volume viewer")
        except ImportError:
            pass

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
        bounds = self._compute_volume_bounds()  # already view frame
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
            # E6: prompts/jobs refer to the old volume's grid.
            self.segmentation_panel.reset_ai_session()
        # E4: same reasoning - a fast preview mesh built for the OLD
        # project's voxel data is meaningless (wrong shape/coordinate
        # space) once a different project is loaded. detach() (not just
        # clear()) so a stale actor is never left attached to the wrong
        # project's renderer session.
        self.preview_surface_3d.detach()
        # E5: same reasoning as E4 above - a textured plane showing the
        # OLD project's image content, or a clipping plane attached to
        # the OLD project's surface mapper, is meaningless once a
        # different project is loaded.
        self.textured_slice_planes_3d.detach()
        self.surface_clipping_3d.detach()
        self._texture_planes_position = None

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
        # E4: same reasoning as marker_3d/slice_planes_3d.detach() above.
        self.preview_surface_3d.detach()
        # E5: same reasoning as E4 above.
        self.textured_slice_planes_3d.detach()
        self.surface_clipping_3d.detach()
        self._texture_planes_position = None
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
            # E6: no AI job, prompt or loaded model survives a project close.
            self.segmentation_panel.reset_ai_session()
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
        Always returned in the SLICE frame (the frame the 2D crosshair and
        voxel conversion use): a 3D pick comes back in the Y-flipped view
        frame and is converted here - before this, A and B were in
        different frames and a picked annotation's voxel clamped to
        coronal row 0 (see core/coordinates.py).
        """
        picked = self.picker.get_last_point()
        if picked is not None:
            from ..core.coordinates import view_to_slice

            return view_to_slice(picked)
        return self._last_cross_focal_point

    def get_crosshair_position(self):
        """E6: the last 2D crosshair position (slice frame), or None - the
        position "Điểm tại con trỏ 2D" / "Chọn góc 1/2" use."""
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
            from ..core.coordinates import slice_to_view

            # world_position is in the slice frame (2D viewers); everything
            # this method draws lives in the 3D view frame (y negated) -
            # see core/coordinates.py. Textures still use the slice-frame
            # position, because it selects voxels.
            x, y, z = (float(c) for c in world_position[:3])
            view_pos = slice_to_view((x, y, z))
            self.marker_3d.update_position(*view_pos)

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
                        self.slice_planes_3d.update_position(view_pos)
                        self.apply_slice_plane_visibility()
                    except ValueError as e:
                        print(f"ROI Viewer: slice planes geometry update skipped - {e}")

            # E5B (Section 19/21): the SAME real C8 crosshair position -
            # not a second, independent slider - is the one spatial
            # source of truth the clipping plane's origin follows. Cheap
            # (a plain SetOrigin()), so updated unconditionally here;
            # disable() already keeps the plane fully detached from any
            # mapper when clipping itself is off, so this has zero
            # visual effect until the user actually enables it.
            self.surface_clipping_3d.set_origin(view_pos)

            # E5A (Section 11): only rebuild textures when texture mode
            # is actually on - real image extraction + Window/Level +
            # colour-table lookup per plane is not free, so this must
            # not run on every crosshair event unconditionally (unlike
            # the cheap clipping-origin update above).
            if self.show_texture_planes:
                self.update_textured_slice_planes((x, y, z))

            from invesalius.pubsub import pub as Publisher

            Publisher.sendMessage("Render volume viewer")
        except Exception as e:
            print(f"ROI Viewer: Sync 2D->3D marker update failed - {e}")

    def update_textured_slice_planes(self, world_position):
        """
        E5A (Section 11): rebuilds all 3 textured planes' geometry +
        texture in place from the real, already-correct per-slice
        vtkImageData the native 2D viewer itself displays for the
        CURRENT real crosshair position - see core/textured_slice_
        planes_3d.py's module docstring for the full real source audit
        behind reusing Slice().GetSlices() rather than reimplementing
        Window/Level. Never touches the camera. Swallows its own
        exceptions (printed, not raised) so a texture-rebuild failure
        can never break the marker/geometric-plane update that already
        succeeded above it in on_cross_focal_point_changed().
        """
        try:
            from ..interface.view_interface import ViewInterface
            from ..interface.project_interface import ProjectInterface
            import invesalius.data.slice_ as sl

            viewer = ViewInterface().get_volume_viewer()
            if viewer is None or not hasattr(viewer, "ren"):
                return
            if not self.textured_slice_planes_3d.attach(viewer.ren):
                return

            pi = ProjectInterface()
            x, y, z = world_position
            self._texture_planes_position = (float(x), float(y), float(z))
            axial_idx, coronal_idx, sagital_idx = pi.world_to_voxel(x, y, z)
            slice_ = sl.Slice()
            for orientation, index in (
                ("AXIAL", axial_idx),
                ("CORONAL", coronal_idx),
                ("SAGITAL", sagital_idx),
            ):
                try:
                    image = slice_.GetSlices(orientation, index, 1, False, 0)
                except Exception as e:
                    print(f"ROI Viewer: E5A GetSlices({orientation}) failed - {e}")
                    continue
                self.textured_slice_planes_3d.update_plane(orientation, image)
            self.apply_slice_plane_visibility()
        except Exception as e:
            print(f"ROI Viewer: E5A textured slice planes update failed - {e}")

    def apply_slice_plane_visibility(self):
        """
        The single place that decides which slice-plane set is drawn.
        Every caller (crosshair updates, texture rebuilds, both
        checkboxes) goes through here - a real operator hit the bug where
        a crosshair update re-showed C8's coloured planes on top of the
        textures because each call site applied only its own flag.

        "Show slice planes in 3D" is the master switch; texture mode only
        chooses which set it shows, and never bypasses it:
          master OFF              -> neither set
          master ON,  texture OFF -> geometric (C8) planes only
          master ON,  texture ON  -> textured planes only
        """
        self.slice_planes_3d.set_visible(self.show_slice_planes and not self.show_texture_planes)
        self.textured_slice_planes_3d.set_visible(self.show_slice_planes and self.show_texture_planes)

    def on_window_level_changed(self):
        """
        Real native W/L change (main.py forwards "Update window level
        value"). While texture mode is on, schedules exactly one texture
        refresh per event-loop turn: native W/L dragging sends this topic
        on every mouse-move (data/styles.py), so without coalescing a
        single drag would queue one 3-plane rebuild per move. wx.CallAfter
        also defers the refresh until the whole native pubsub chain for
        this change has finished.
        """
        if not self.show_texture_planes or self._texture_planes_position is None:
            return
        if self._wl_texture_refresh_scheduled:
            return
        self._wl_texture_refresh_scheduled = True
        wx.CallAfter(self._run_scheduled_wl_texture_refresh)

    def _run_scheduled_wl_texture_refresh(self):
        try:
            self._wl_texture_refresh_scheduled = False
            self.refresh_slice_textures()
        except RuntimeError:
            pass  # frame destroyed between scheduling and running

    def refresh_slice_textures(self) -> bool:
        """Re-fetch all 3 textures at the position they were last built
        at - never at the live crosshair (see _texture_planes_position's
        NOTE). Same in-place update_plane() path, so geometry, camera, C8
        planes, masks and surfaces are untouched. Returns whether a
        refresh actually ran."""
        if not self.show_texture_planes or self._texture_planes_position is None:
            return False
        self.update_textured_slice_planes(self._texture_planes_position)
        self.request_render()
        return True

    def _compute_volume_bounds(self):
        """
        Bounds (xmin, xmax, ymin, ymax, zmin, zmax) of the whole loaded
        volume in the 3D VIEW frame - the frame C8's planes are drawn in,
        where y runs over [-Ymax, 0] exactly like the native surfaces and
        volume rendering (see core/coordinates.py). Computed from the real
        Slice() shape/spacing via the canonical convention. Returns None if
        no volume shape is known yet (e.g. no project loaded).
        """
        try:
            from ..core.coordinates import slice_bounds_to_view, volume_bounds_world
            from ..interface.project_interface import ProjectInterface

            pi = ProjectInterface()
            shape = pi.get_shape()
            if not shape or shape == (0, 0, 0):
                return None
            return slice_bounds_to_view(volume_bounds_world(shape, pi.get_spacing()))
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
