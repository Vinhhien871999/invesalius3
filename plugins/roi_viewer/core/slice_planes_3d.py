# --------------------------------------------------------------------------
# 3D Slice Planes Module (Phase 13.5, pre-Phase-14 visual enhancement of
# C8 - Sync 2D -> 3D)
# Description: Three semi-transparent VTK plane actors that show, inside
#              the 3D Volume view, where the current Axial/Coronal/Sagital
#              2D slices sit within the real volume - a more visually
#              obvious counterpart to the small CrosshairMarker3D sphere
#              (core/marker_3d.py, kept unchanged, not replaced).
#
# Pure VTK, no wx/invesalius import (same convention as core/marker_3d.py
# and core/picker_3d.py) - unit-testable in isolation, and the only thing
# gui/ code needs to drive is attach()/set_bounds()/update_position()/
# set_visible()/detach().
#
# NOT texture-mapped CT imagery in this phase (per the spec's explicit
# scope) - just geometric planes, to show POSITION, not slice content.
# --------------------------------------------------------------------------
from typing import Optional, Tuple

PLANE_AXIAL = "AXIAL"
PLANE_CORONAL = "CORONAL"
PLANE_SAGITAL = "SAGITAL"

# Colours chosen to be visually distinct from each other and from
# CrosshairMarker3D's yellow marker - a common medical-imaging convention
# (not invented arbitrarily): red=sagittal, green=coronal, blue=axial.
_DEFAULT_COLOURS = {
    PLANE_AXIAL: (0.2, 0.4, 1.0),
    PLANE_CORONAL: (0.2, 1.0, 0.4),
    PLANE_SAGITAL: (1.0, 0.3, 0.3),
}
_DEFAULT_OPACITY = 0.25


class SlicePlanes3D:
    """
    Owns exactly 3 vtkActor objects (Axial/Coronal/Sagital planes) in a
    given renderer, representing the current 2D crosshair position as
    three full-volume-sized geometric planes.

    Lifecycle (mirrors core/marker_3d.CrosshairMarker3D's pattern for the
    same reason - the real 3D renderer is a singleton that outlives any
    single ROIViewerFrame):
      - attach(renderer): create the 3 actors once and add them to the
        renderer. Calling this again (e.g. the ROI Viewer window was
        closed and reopened) first detaches any previous actors from
        whatever renderer they were in, so repeated attach() calls never
        leave duplicate/orphaned actors behind.
      - set_bounds(bounds): set the real volume's world-space bounds
        (xmin, xmax, ymin, ymax, zmin, zmax) - callers must derive this
        from real project/spacing/shape data (see
        gui/roi_panel.py._compute_volume_bounds()), never hardcode it.
      - update_position(world_position): move the SAME 3 actors' plane
        geometry (via their vtkPlaneSource, not by recreating actors) -
        so repeated crosshair movement never grows the renderer's actor
        count.
      - set_visible(bool): show/hide all 3 planes without destroying
        them (used by the "Show slice planes in 3D" checkbox - a
        separate concern from the Sync 2D->3D checkbox itself, see
        gui/roi_panel.py.on_cross_focal_point_changed()).
      - detach(): remove all 3 actors from their renderer and clear
        cached bounds/position. Must be called when the owning
        ROIViewerFrame closes (see roi_panel.py's _on_close(), same
        place CrosshairMarker3D.detach()/PointPicker3D.cleanup() are
        called) so stale actors never linger in the shared, persistent
        3D scene after the plugin window that created them is gone.
    """

    def __init__(self, colours: Optional[dict] = None, opacity: float = _DEFAULT_OPACITY):
        self.colours = colours or dict(_DEFAULT_COLOURS)
        self.opacity = opacity
        self.renderer = None
        self.bounds: Optional[Tuple[float, float, float, float, float, float]] = None
        self.position: Optional[Tuple[float, float, float]] = None
        self.visible = False
        # plane -> {"source": vtkPlaneSource, "actor": vtkActor}
        self._planes = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_attached(self) -> bool:
        return self.renderer is not None

    @property
    def actor_count(self) -> int:
        return len(self._planes)

    def attach(self, renderer) -> bool:
        """
        Create (or move) the 3 plane actors into `renderer`. Safe to
        call multiple times - always ends up with exactly 3 actors in
        exactly one renderer (the most recent one passed in).
        """
        try:
            from vtkmodules.vtkFiltersSources import vtkPlaneSource
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

            if self._planes and self.renderer is not None and self.renderer is not renderer:
                self.detach()

            if not self._planes:
                for plane_name in (PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL):
                    source = vtkPlaneSource()
                    mapper = vtkPolyDataMapper()
                    mapper.SetInputConnection(source.GetOutputPort())

                    actor = vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(*self.colours[plane_name])
                    actor.GetProperty().SetOpacity(self.opacity)
                    # Semi-transparent planes must never steal a pick
                    # meant for surfaces/seeds behind them (Section XV).
                    actor.SetPickable(False)
                    actor.VisibilityOff()

                    self._planes[plane_name] = {"source": source, "actor": actor}

            if self.renderer is not renderer:
                for entry in self._planes.values():
                    renderer.AddActor(entry["actor"])
                self.renderer = renderer

            # Re-apply any bounds/position already known (e.g. attach()
            # called again after a reopen, with set_bounds() previously
            # called) so the planes don't sit at stale/default geometry.
            if self.bounds is not None and self.position is not None:
                self._update_geometry()

            return True
        except Exception as e:
            print(f"ROI Viewer: 3D slice planes attach failed - {e}")
            return False

    def detach(self):
        """Remove all 3 actors from their renderer (if any) and clear
        cached bounds/position. Idempotent."""
        if self.renderer is not None:
            for entry in self._planes.values():
                try:
                    self.renderer.RemoveActor(entry["actor"])
                except Exception:
                    pass
        self.renderer = None
        self._planes = {}
        self.bounds = None
        self.position = None
        self.visible = False

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def set_bounds(self, bounds: Tuple[float, float, float, float, float, float]):
        """
        Set the real volume's world-space bounds:
        (xmin, xmax, ymin, ymax, zmin, zmax). Callers must derive this
        from real project/spacing/shape data - never hardcode.

        Raises ValueError for a malformed bounds tuple (wrong length,
        or a min >= its corresponding max) rather than silently
        producing degenerate/invisible plane geometry.
        """
        if len(bounds) != 6:
            raise ValueError(f"bounds must have 6 values (xmin,xmax,ymin,ymax,zmin,zmax), got {len(bounds)}")
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        for lo, hi, name in ((xmin, xmax, "x"), (ymin, ymax, "y"), (zmin, zmax, "z")):
            if not (lo < hi):
                raise ValueError(f"bounds.{name}: min ({lo}) must be < max ({hi}), got bounds={bounds}")
        self.bounds = tuple(float(b) for b in bounds)
        if self.position is not None:
            self._update_geometry()

    def update_position(self, world_position: Tuple[float, float, float]):
        """
        Move all 3 planes to intersect the given real world-space
        (x, y, z) mm position and show them (if set_visible(True) was
        the last visibility call - matches CrosshairMarker3D's own
        "first update makes it visible" convention).

        No-op (does not raise) if attach()/set_bounds() have not
        happened yet - there is nothing meaningful to draw without a
        real renderer and real volume bounds, and a crosshair event can
        legitimately arrive before either is ready (Section XI - no
        project, no renderer, no bounds yet).

        Raises ValueError for a non-finite (x, y, z) position -
        distinguishes "not ready yet" (silent no-op above) from "given
        a genuinely invalid value" (loud failure), matching this
        project's established convention (core/evaluation.py's spacing
        validation, core/segmentation.py's negative-tolerance check).
        """
        if len(world_position) != 3:
            raise ValueError(f"world_position must have 3 values (x,y,z), got {len(world_position)}")
        x, y, z = (float(c) for c in world_position)
        import math

        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            raise ValueError(f"world_position must be finite, got {world_position}")

        self.position = (x, y, z)
        if not self._planes or self.bounds is None:
            return
        self._update_geometry()

    def _update_geometry(self):
        """
        Real geometry update - moves the SAME 3 vtkPlaneSource objects
        (SetOrigin/SetPoint1/SetPoint2 + Modified()), never recreates
        them. Convention (verified against the real, already-tested
        core/sync_2d3d.py.voxel_to_world() / interface/project_interface.
        py.ProjectInterface.voxel_to_world() mapping - world X is the
        fastest-varying image axis = SAGITAL, Y = CORONAL, Z = AXIAL
        slice stack): the Sagital plane is constant in X (= current x),
        spanning the full Y/Z bounds; Coronal is constant in Y, spanning
        X/Z; Axial is constant in Z, spanning X/Y.
        """
        xmin, xmax, ymin, ymax, zmin, zmax = self.bounds
        x, y, z = self.position

        # Clamp the crosshair position into the real volume bounds so a
        # position slightly outside (e.g. from a picked point right at
        # the edge) still produces a plane INSIDE the visible volume,
        # rather than a plane that has silently drifted outside it.
        x = min(max(x, xmin), xmax)
        y = min(max(y, ymin), ymax)
        z = min(max(z, zmin), zmax)

        geometries = {
            PLANE_AXIAL: ((xmin, ymin, z), (xmax, ymin, z), (xmin, ymax, z)),
            PLANE_CORONAL: ((xmin, y, zmin), (xmax, y, zmin), (xmin, y, zmax)),
            PLANE_SAGITAL: ((x, ymin, zmin), (x, ymax, zmin), (x, ymin, zmax)),
        }
        for plane_name, (origin, point1, point2) in geometries.items():
            source = self._planes[plane_name]["source"]
            source.SetOrigin(*origin)
            source.SetPoint1(*point1)
            source.SetPoint2(*point2)
            source.Modified()
        # NOTE: visibility is intentionally NOT touched here (unlike
        # CrosshairMarker3D, which shows itself on first update) - the
        # "Show slice planes in 3D" checkbox is a separate concern from
        # whether a position update happened, so callers (see
        # gui/roi_panel.py.on_cross_focal_point_changed()) always call
        # set_visible() explicitly with the checkbox's current state
        # right after update_position(). This keeps the planes hidden
        # while "Show slice planes" is OFF even though their geometry
        # keeps tracking the real crosshair position underneath (so
        # toggling the checkbox back ON shows them at the CURRENT
        # position immediately, not a stale one - see Section X/TEST F/G).

    def set_visible(self, visible: bool):
        """
        Show/hide all 3 planes without destroying them - drives the
        "Show slice planes in 3D" checkbox, independent of the "Sync 2D
        -> 3D" checkbox (which gates whether update_position() is
        called at all - see gui/roi_panel.py.on_cross_focal_point_
        changed()). Safe to call before attach()/any position update -
        just records the desired state for when actors do exist.
        """
        self.visible = bool(visible)
        for entry in self._planes.values():
            if self.visible:
                entry["actor"].VisibilityOn()
            else:
                entry["actor"].VisibilityOff()

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """Return the planes' current world position, or None if never set."""
        return self.position
