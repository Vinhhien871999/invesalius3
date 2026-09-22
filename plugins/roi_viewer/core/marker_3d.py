# --------------------------------------------------------------------------
# 3D Position Marker Module
# Description: A small VTK sphere actor that represents "where the user
#              currently is" in the 3D view - used by Sync 2D -> 3D
#              (Phase 09) to give a visual counterpart to InVesalius's
#              real 2D crosshair. Pure VTK, no wx/invesalius import (same
#              convention as core/picker_3d.py) - unit-testable, and the
#              only thing gui/ code needs to drive is attach()/
#              update_position()/detach().
# --------------------------------------------------------------------------

from typing import Optional, Tuple


class CrosshairMarker3D:
    """
    Owns exactly one vtkActor (a small sphere) in a given renderer,
    representing the current 2D crosshair position projected into 3D.

    Lifecycle (mirrors core/picker_3d.PointPicker3D's pattern for the
    same reason - the real 3D renderer is a singleton that outlives any
    single ROIViewerFrame):
      - attach(renderer): create the actor once and add it to the
        renderer. Calling this again (e.g. the ROI Viewer window was
        closed and reopened) first detaches any previous actor from
        whatever renderer it was in, so repeated attach() calls never
        leave duplicate/orphaned actors behind (Phase 09 SYNC-T5/T6).
      - update_position(x, y, z): move the SAME actor - never creates a
        new one - so scrolling through many slices never grows the
        renderer's actor count (SYNC-T5).
      - detach(): remove the actor from its renderer. Must be called
        when the owning ROIViewerFrame closes (see roi_panel.py's
        _on_close(), same place PointPicker3D.cleanup() is called) so a
        stale marker never lingers in the shared, persistent 3D scene
        after the plugin window that created it is gone.
    """

    def __init__(self, colour: Tuple[float, float, float] = (1.0, 1.0, 0.0), radius: float = 3.0):
        self.colour = colour
        self.radius = radius
        self.renderer = None
        self.actor = None
        self._sphere_source = None
        self.visible = False

    def attach(self, renderer) -> bool:
        """
        Create (or move) this marker's actor into `renderer`. Safe to
        call multiple times - always ends up with exactly one actor in
        exactly one renderer (the most recent one passed in).
        """
        try:
            from vtkmodules.vtkFiltersSources import vtkSphereSource
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

            if self.actor is not None and self.renderer is not None and self.renderer is not renderer:
                self.detach()

            if self.actor is None:
                self._sphere_source = vtkSphereSource()
                self._sphere_source.SetRadius(self.radius)
                self._sphere_source.SetThetaResolution(12)
                self._sphere_source.SetPhiResolution(12)

                mapper = vtkPolyDataMapper()
                mapper.SetInputConnection(self._sphere_source.GetOutputPort())

                self.actor = vtkActor()
                self.actor.SetMapper(mapper)
                self.actor.GetProperty().SetColor(*self.colour)
                self.actor.GetProperty().SetOpacity(0.85)
                self.actor.VisibilityOff()

            if self.renderer is not renderer:
                renderer.AddActor(self.actor)
                self.renderer = renderer

            return True
        except Exception as e:
            print(f"ROI Viewer: 3D marker attach failed - {e}")
            return False

    def update_position(self, x: float, y: float, z: float):
        """Move the marker to a real world-space (x, y, z) mm position and show it."""
        if self.actor is None:
            return
        self.actor.SetPosition(x, y, z)
        if not self.visible:
            self.actor.VisibilityOn()
            self.visible = True

    def hide(self):
        """Hide the marker without destroying it (used when sync is toggled off)."""
        if self.actor is not None:
            self.actor.VisibilityOff()
            self.visible = False

    def detach(self):
        """Remove the actor from its renderer (if any). Idempotent."""
        if self.actor is not None and self.renderer is not None:
            try:
                self.renderer.RemoveActor(self.actor)
            except Exception:
                pass
        self.renderer = None
        self.actor = None
        self._sphere_source = None
        self.visible = False

    def get_position(self) -> Optional[Tuple[float, float, float]]:
        """Return the marker's current world position, or None if not attached."""
        if self.actor is None:
            return None
        return tuple(self.actor.GetPosition())
