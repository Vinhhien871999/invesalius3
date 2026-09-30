# --------------------------------------------------------------------------
# Canonical world <-> voxel conversion - the single source of truth for the
# plugin's coordinate convention. core/sync_2d3d.py and
# interface/project_interface.py delegate here; nothing else should
# re-derive these formulas.
#
# Convention, taken from InVesalius's own code (not from docstrings):
#   voxel index   (z, y, x)    Slice().matrix axes: AXIAL, CORONAL, SAGITAL
#   spacing       (sx, sy, sz) Slice().spacing - x FIRST. The DICOM import
#                              sets (xyspacing[0], xyspacing[1], zspacing)
#                              (control.py:1300); the Slice.spacing setter
#                              pairs it with matrix.shape[::-1]
#                              (slice_.py:202); converters.to_vtk() passes it
#                              straight to vtkImageData.SetSpacing().
#   world         (wx, wy, wz) mm, origin 0 - every converters.to_vtk() call
#                              in the native surface/volume/slice pipelines
#                              uses the default origin (0, 0, 0).
#
# world -> voxel uses round-to-nearest, matching native slice selection
# (viewer_slice.py:1848-1850: round(pos[2] / spacing[2]) etc.), then clamps
# into the volume.
# --------------------------------------------------------------------------
from typing import Tuple

VOXEL_INDEX_ORDER = ("z", "y", "x")
SPACING_ORDER = ("x", "y", "z")
WORLD_ORDER = ("x", "y", "z")


def voxel_zyx_to_world_xyz(
    voxel_zyx: Tuple[float, float, float], spacing_xyz: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    z, y, x = voxel_zyx
    sx, sy, sz = spacing_xyz
    return (x * sx, y * sy, z * sz)


def world_xyz_to_voxel_zyx(
    world_xyz: Tuple[float, float, float],
    spacing_xyz: Tuple[float, float, float],
    shape_zyx: Tuple[int, int, int],
) -> Tuple[int, int, int]:
    wx, wy, wz = world_xyz
    sx, sy, sz = spacing_xyz

    def _index(w: float, s: float, n: int) -> int:
        i = int(round(w / s)) if s != 0 else 0
        return max(0, min(i, n - 1))

    nz, ny, nx = shape_zyx
    return (_index(wz, sz, nz), _index(wy, sy, ny), _index(wx, sx, nx))


# Two world frames, differing only in the sign of y:
#   slice frame - the 2D viewers, "Set cross focal point" positions and
#                 converters.to_vtk() images: y in [0, +Ymax]. All the voxel
#                 conversions above are in this frame.
#   view frame  - the 3D volume viewer's renderer: surfaces
#                 (surface_process.py:156), volume rendering (volume.py:597)
#                 and mask volumes (volume_mask.py:70) all apply
#                 vtkImageFlip(FilteredAxis=1, FlipAboutOriginOn): y in
#                 [-Ymax, 0].
# Native converts with -y in both directions: styles.py:555 (2D crosshair
# -> 3D pointer) and styles_3d.py:994 (3D pick -> 2D). Anything the plugin
# draws in the 3D view must be in the view frame; anything picked in the 3D
# view must go back to the slice frame before voxel conversion.


def slice_to_view(world_xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = world_xyz
    return (x, -y, z)


def view_to_slice(world_xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = world_xyz
    return (x, -y, z)


def slice_bounds_to_view(
    bounds: Tuple[float, float, float, float, float, float],
) -> Tuple[float, float, float, float, float, float]:
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    return (xmin, xmax, -ymax, -ymin, zmin, zmax)


def volume_bounds_world(
    shape_zyx: Tuple[int, int, int], spacing_xyz: Tuple[float, float, float]
) -> Tuple[float, float, float, float, float, float]:
    """(xmin, xmax, ymin, ymax, zmin, zmax) of the voxel centres - identical
    to vtkImageData.GetBounds() for converters.to_vtk() of the whole volume."""
    nz, ny, nx = shape_zyx
    x1, y1, z1 = voxel_zyx_to_world_xyz((nz - 1, ny - 1, nx - 1), spacing_xyz)
    return (0.0, x1, 0.0, y1, 0.0, z1)
