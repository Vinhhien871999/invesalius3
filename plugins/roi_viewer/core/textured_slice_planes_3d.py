# --------------------------------------------------------------------------
# E5A - Textured Slice Planes Module (Advanced Segmentation Enhancement
#       Track, enhancement/advanced-segmentation branch ONLY)
# Description: an OPT-IN alternative rendering of the existing C8
#              geometric slice planes (core/slice_planes_3d.SlicePlanes3D,
#              unchanged, still the default) that shows the REAL CT image
#              content (already reflecting native Window/Level + the
#              current mask's blend/E2 preview overlay, exactly as the
#              native 2D views show it) on the 3 Axial/Coronal/Sagital
#              planes, instead of a flat colour.
#
# CORE INVARIANT this module exists to protect: texture mode is
# DISPLAY-ONLY and strictly opt-in/additive. With "Show CT texture on
# slice planes" left at its default (OFF), C8's existing geometric
# planes render byte-identically to before this module existed. Nothing
# here ever creates/reads a Project().surface_dict entry, never touches
# a mask, never rebuilds the final surface, never moves the camera.
#
# Real source-first audit (see docs/CT3D_ADVANCED_E5_VISUALIZATION_
# REPORT.md's "Native slice display audit" section for the full
# citations): the native 2D viewer (invesalius/data/viewer_slice.py's
# `actor.SetInputData(image)` inside SliceViewer.set_slice_number(),
# where `actor` is a real vtkImageActor) gets that `image` from
# `invesalius.data.slice_.Slice.GetSlices(orientation, slice_number,
# number_slices=1, inverted=False, border_size=0)` - a real, already-
# used, already-correct accessor that internally calls
# `converters.to_vtk()` + `do_ww_wl()` (real Window/Level application)
# + `do_colour_image()` (real greyscale->RGB colour-table lookup) +,
# if a current mask is shown, `do_blend()` with the mask's own colour
# overlay AND (Section 12's "aux_matrices"/"to_show_aux" mechanism, the
# same real one E2's preview overlay uses) any active E2 preview
# overlay. This module REUSES that exact real output rather than
# reimplementing Window/Level math independently (Section 7's explicit
# preference) - the texture a user sees is, by construction, pixel-for-
# pixel the same real display data the 2D view already shows for that
# slice, including any temporary preview overlay.
# --------------------------------------------------------------------------
from typing import Tuple

PLANE_AXIAL = "AXIAL"
PLANE_CORONAL = "CORONAL"
PLANE_SAGITAL = "SAGITAL"


def plane_geometry_from_image_bounds(
    bounds: Tuple[float, float, float, float, float, float],
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Derives (origin, point1, point2) world-space corners for a single
    real per-slice vtkImageData's own GetBounds() - never independently
    recomputed from spacing/shape, so a textured plane is provably
    positioned at the EXACT same real-world footprint as the source
    image InVesalius's own 2D viewer displays for that slice (Section
    24/"test_geometry_and_texture_same_world_plane"), and (since that
    image's bounds are derived from the exact same real
    converters.to_vtk() extent/spacing convention core/slice_planes_3d.
    py.SlicePlanes3D._update_geometry() already uses) coincides with
    C8's own existing geometric plane for the same slice.

    Which axis is degenerate (min == max) self-describes the
    orientation - a real per-slice image is always flat along exactly
    one axis (Axial: flat in Z: AXIAL slice stack per project_interface.
    py's proven world-axis mapping; Coronal: flat in Y; Sagittal: flat
    in X), so no separate orientation string is needed to build the
    correct 3 corners; the exact same (origin, point1, point2) formula
    per axis as SlicePlanes3D._update_geometry() is reused here so both
    planes are provably coincident, not independently re-derived.

    Raises ValueError if no axis is (numerically, within a tiny
    tolerance) degenerate - a malformed/non-single-slice bounds tuple,
    never silently guessed.
    """
    if len(bounds) != 6:
        raise ValueError(f"bounds must have 6 values, got {len(bounds)}")
    xmin, xmax, ymin, ymax, zmin, zmax = (float(b) for b in bounds)
    tol = 1e-6

    if abs(xmax - xmin) <= tol:
        x = (xmin + xmax) / 2.0
        return (x, ymin, zmin), (x, ymax, zmin), (x, ymin, zmax)
    if abs(ymax - ymin) <= tol:
        y = (ymin + ymax) / 2.0
        return (xmin, y, zmin), (xmax, y, zmin), (xmin, y, zmax)
    if abs(zmax - zmin) <= tol:
        z = (zmin + zmax) / 2.0
        return (xmin, ymin, z), (xmax, ymin, z), (xmin, ymax, z)

    raise ValueError(
        f"bounds is not a single flat slice on any axis (not degenerate): {bounds}"
    )


def build_textured_plane_polydata(origin, point1, point2):
    """
    Builds a single flat quad vtkPolyData spanning (origin, point1,
    point2, opposite-corner) with explicit per-corner texture
    coordinates - NOT vtkPlaneSource's auto-generated TCoords, so the
    image-to-world mapping is fully explicit and independently testable
    (Section 10 - "must catch horizontal mirror / vertical mirror /
    axis swap / 90-degree rotation", verified for real by this module's
    own tests/ct3d/test_textured_slice_planes_3d.py orientation tests
    using a deliberately non-symmetric synthetic image and a real
    off-screen VTK render, not just constructed-and-trusted).

    Point order / TCoord convention (matches vtkTexture's real,
    documented sampling: texture coordinate (0,0) samples the image's
    own first (i=0, j=0) point - the SAME point converters.to_vtk()
    places at the image's own `origin`):
      id0 = origin              -> TCoord (0, 0)
      id1 = point1               -> TCoord (1, 0)
      id2 = point1+point2-origin -> TCoord (1, 1)
      id3 = point2               -> TCoord (0, 1)
    """
    from vtkmodules.vtkCommonCore import vtkFloatArray, vtkPoints
    from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData

    ox, oy, oz = origin
    p1x, p1y, p1z = point1
    p2x, p2y, p2z = point2
    opposite = (p1x + p2x - ox, p1y + p2y - oy, p1z + p2z - oz)

    points = vtkPoints()
    points.InsertNextPoint(*origin)
    points.InsertNextPoint(*point1)
    points.InsertNextPoint(*opposite)
    points.InsertNextPoint(*point2)

    quad = vtkCellArray()
    quad.InsertNextCell(4)
    for pid in (0, 1, 2, 3):
        quad.InsertCellPoint(pid)

    tcoords = vtkFloatArray()
    tcoords.SetNumberOfComponents(2)
    tcoords.SetName("TCoords")
    for u, v in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
        tcoords.InsertNextTuple2(u, v)

    polydata = vtkPolyData()
    polydata.SetPoints(points)
    polydata.SetPolys(quad)
    polydata.GetPointData().SetTCoords(tcoords)
    return polydata


class TexturedSlicePlanes3D:
    """
    Owns exactly 3 vtkActor objects (Axial/Coronal/Sagital), each with
    its own vtkPlaneSource-free explicit quad polydata (see
    build_textured_plane_polydata()) and a vtkTexture wrapping the real
    per-slice image. Mirrors core/marker_3d.CrosshairMarker3D's/
    core/slice_planes_3d.SlicePlanes3D's attach()/detach() lifecycle
    pattern exactly, for the same reason (the real 3D renderer is a
    singleton that outlives any single ROIViewerFrame).

    Geometry/texture are both updated IN PLACE on the same 3 actors on
    every update_textures() call - never recreated - so scrolling
    through slices or toggling texture mode repeatedly never grows the
    renderer's actor count (same real invariant SlicePlanes3D/
    CrosshairMarker3D/PreviewSurfaceManager3D all already guarantee).
    """

    def __init__(self, opacity: float = 1.0):
        self.opacity = opacity
        self.renderer = None
        self.visible = False
        # plane -> {"mapper": vtkPolyDataMapper, "actor": vtkActor,
        #           "texture": vtkTexture}
        self._planes = {}

    @property
    def is_attached(self) -> bool:
        return self.renderer is not None

    @property
    def actor_count(self) -> int:
        return len(self._planes)

    def attach(self, renderer) -> bool:
        try:
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkTexture

            if self._planes and self.renderer is not None and self.renderer is not renderer:
                self.detach()

            if not self._planes:
                for plane_name in (PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL):
                    mapper = vtkPolyDataMapper()
                    texture = vtkTexture()
                    texture.InterpolateOn()

                    actor = vtkActor()
                    actor.SetMapper(mapper)
                    actor.SetTexture(texture)
                    actor.GetProperty().SetOpacity(self.opacity)
                    # Section 14 (texture pickability): must never
                    # intercept 3D point picking / Region Growing seed
                    # pick / 3D distance measurement, same real
                    # mechanism every other renderer-attached plugin
                    # actor already uses (marker_3d/slice_planes_3d/
                    # preview_surface_3d).
                    actor.SetPickable(False)
                    actor.VisibilityOff()

                    self._planes[plane_name] = {
                        "mapper": mapper,
                        "actor": actor,
                        "texture": texture,
                    }

            if self.renderer is not renderer:
                for entry in self._planes.values():
                    renderer.AddActor(entry["actor"])
                self.renderer = renderer

            return True
        except Exception as e:
            print(f"ROI Viewer: textured slice planes attach failed - {e}")
            return False

    def detach(self):
        """Remove all 3 actors from their renderer (if any). Idempotent."""
        if self.renderer is not None:
            for entry in self._planes.values():
                try:
                    self.renderer.RemoveActor(entry["actor"])
                except Exception:
                    pass
        self.renderer = None
        self._planes = {}
        self.visible = False

    def update_plane(self, plane_name: str, image) -> bool:
        """
        Updates ONE plane's geometry + texture in place from a real
        per-slice vtkImageData (see this module's docstring for exactly
        where that image must come from - Slice().GetSlices()). No-op
        (returns False) if not attached yet or `image` is None (e.g. no
        project loaded) - never raises for "nothing to draw yet",
        matching SlicePlanes3D.update_position()'s own convention.
        """
        if plane_name not in self._planes or image is None:
            return False
        try:
            origin, point1, point2 = plane_geometry_from_image_bounds(image.GetBounds())
        except ValueError as e:
            print(f"ROI Viewer: textured plane '{plane_name}' geometry skipped - {e}")
            return False

        entry = self._planes[plane_name]
        polydata = build_textured_plane_polydata(origin, point1, point2)
        entry["mapper"].SetInputData(polydata)
        entry["texture"].SetInputData(image)
        entry["mapper"].Modified()
        entry["texture"].Modified()
        return True

    def set_visible(self, visible: bool):
        """Show/hide all 3 textured planes without destroying them -
        drives the "Show CT texture on slice planes" checkbox. Safe to
        call before attach()/any update - just records the desired
        state for when actors do exist (same convention as
        SlicePlanes3D.set_visible())."""
        self.visible = bool(visible)
        for entry in self._planes.values():
            if self.visible:
                entry["actor"].VisibilityOn()
            else:
                entry["actor"].VisibilityOff()
