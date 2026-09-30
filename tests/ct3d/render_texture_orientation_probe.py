# --------------------------------------------------------------------------
# E5A texture orientation - REAL rendered proof (run as a subprocess by
# tests/ct3d/test_texture_orientation_render.py; not collected by pytest).
#
# Builds each per-slice image exactly as the native 2D viewer's source does
# (Slice.get_image_slice() slicing of a (z, y, x) volume + converters.to_vtk
# with the real (x, y, z) spacing and slice number), feeds it to the
# PRODUCTION TexturedSlicePlanes3D.update_plane() (which moves the plane
# into the y-flipped 3D view frame), renders it with VTK, reads the real
# framebuffer back and checks, at the centre of every block of the
# pattern, that
#
#     rendered colour at 3D view point P == volume value at view_to_slice(P)
#
# i.e. every texel lands on the 3D position of its own voxel - the same
# position the native surface puts that voxel. A mirror, axis swap or
# rotation of the texture moves blocks and fails this check; the probe
# also renders deliberately mirrored textures (u and v controls) to show
# that it would. Lighting is turned off on the probe's actors only so the rendered
# grey equals the texel value; orientation does not depend on lighting.
#
# Prints one JSON line. Run in a subprocess because an earlier environment
# crashed VTK framebuffer read-back; a crash there must not take down the
# pytest run.
# --------------------------------------------------------------------------
import importlib
import json
import os
import sys
import tempfile

# Never touch the user's InVesalius config (same rule as conftest.py): under
# pytest XDG_CONFIG_HOME is already a temp dir; standalone, use a fresh one.
if "XDG_CONFIG_HOME" not in os.environ:
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="ct3d_probe_xdg_")

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SPACING = (0.4785, 0.4785, 1.5)  # (x, y, z) mm - dataset 0051's anisotropy
BLOCK = 4
SHAPE = (12, 16, 20)  # (z, y, x) voxels: 3 x 4 x 5 blocks - every axis a different length
WINDOW = 480


def make_volume():
    """Every 4x4x4 block has its own grey value, distinct within any
    axial, coronal or sagittal slice: 20 + 3 * block id (max 197)."""
    z, y, x = np.indices(SHAPE)
    bz, by, bx = z // BLOCK, y // BLOCK, x // BLOCK
    nby, nbx = SHAPE[1] // BLOCK, SHAPE[2] // BLOCK
    return (20 + 3 * ((bz * nby + by) * nbx + bx)).astype(np.uint8)


def native_slice(volume, orientation, index):
    """Same slicing as invesalius.data.slice_.Slice.get_image_slice() for
    PROJECTION_NORMAL with number_slices=1."""
    if orientation == "AXIAL":
        return np.ascontiguousarray(volume[index])
    if orientation == "CORONAL":
        return np.ascontiguousarray(volume[:, index, :])
    return np.ascontiguousarray(volume[:, :, index])


def block_centres(orientation, index):
    """Voxel (z, y, x) at the centre of each pattern block of one slice."""
    nz, ny, nx = SHAPE
    half = BLOCK // 2
    zs = [b * BLOCK + half for b in range(nz // BLOCK)]
    ys = [b * BLOCK + half for b in range(ny // BLOCK)]
    xs = [b * BLOCK + half for b in range(nx // BLOCK)]
    if orientation == "AXIAL":
        return [(index, y, x) for y in ys for x in xs]
    if orientation == "CORONAL":
        return [(z, index, x) for z in zs for x in xs]
    return [(z, y, index) for z in zs for y in ys]


def render_plane(orientation, index, volume, mirror=None):
    from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow, vtkWindowToImageFilter
    from vtkmodules.util import numpy_support
    importlib.import_module("vtkmodules.vtkRenderingOpenGL2")  # registers the OpenGL render window

    from invesalius.data import converters
    from plugins.roi_viewer.core import textured_slice_planes_3d as tsp
    from plugins.roi_viewer.core.coordinates import slice_to_view, voxel_zyx_to_world_xyz

    image = converters.to_vtk(native_slice(volume, orientation, index), SPACING, index, orientation)

    renderer = vtkRenderer()
    renderer.SetBackground(0.0, 0.0, 1.0)
    planes = tsp.TexturedSlicePlanes3D()
    planes.attach(renderer)
    original = tsp.build_textured_plane_polydata
    if mirror:
        def mirrored(origin, point1, point2):
            poly = original(origin, point1, point2)
            tc = poly.GetPointData().GetTCoords()
            for pid in range(tc.GetNumberOfTuples()):
                u, v = tc.GetTuple2(pid)
                tc.SetTuple2(pid, 1.0 - u if mirror == "u" else u, 1.0 - v if mirror == "v" else v)
            return poly
        tsp.build_textured_plane_polydata = mirrored
    try:
        assert planes.update_plane(orientation, image)
    finally:
        tsp.build_textured_plane_polydata = original
    planes.set_visible(True)
    entry = planes._planes[orientation]
    entry["actor"].GetProperty().LightingOff()
    entry["texture"].InterpolateOff()

    # Head-on orthographic camera along the plane normal.
    bounds = entry["actor"].GetBounds()
    centre = [(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2]
    normal = {"AXIAL": (0, 0, 1), "CORONAL": (0, 1, 0), "SAGITAL": (1, 0, 0)}[orientation]
    view_up = {"AXIAL": (0, 1, 0), "CORONAL": (0, 0, 1), "SAGITAL": (0, 0, 1)}[orientation]
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetFocalPoint(*centre)
    camera.SetPosition(*(c + 100 * n for c, n in zip(centre, normal)))
    camera.SetViewUp(*view_up)
    renderer.ResetCamera()
    renderer.ResetCameraClippingRange()

    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(WINDOW, WINDOW)
    window.AddRenderer(renderer)
    window.Render()

    grab = vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.ReadFrontBufferOff()
    grab.Update()
    shot = grab.GetOutput()
    w, h, _ = shot.GetDimensions()
    pixels = numpy_support.vtk_to_numpy(shot.GetPointData().GetScalars()).reshape(h, w, -1)

    checked, mismatches, samples = 0, [], []
    for zyx in block_centres(orientation, index):
        world_slice = voxel_zyx_to_world_xyz(zyx, SPACING)
        view = slice_to_view(world_slice)
        renderer.SetWorldPoint(view[0], view[1], view[2], 1.0)
        renderer.WorldToDisplay()
        dx, dy, _ = renderer.GetDisplayPoint()
        px, py = int(round(dx)), int(round(dy))
        if not (0 <= px < w and 0 <= py < h):
            mismatches.append({"voxel": zyx, "reason": "off-screen"})
            continue
        rendered = [int(c) for c in pixels[py, px, :3]]
        expected = int(volume[zyx])
        checked += 1
        if len(samples) < 3:
            samples.append({"voxel": list(zyx), "view_mm": [round(c, 3) for c in view],
                            "rendered": rendered, "expected": expected})
        if max(abs(c - expected) for c in rendered) > 1:
            mismatches.append({"voxel": list(zyx), "rendered": rendered, "expected": expected})
    window.Finalize()
    return {"checked": checked, "mismatches": len(mismatches), "first_mismatches": mismatches[:3],
            "samples": samples, "image_bounds": [round(b, 4) for b in image.GetBounds()],
            "actor_bounds": [round(b, 4) for b in bounds]}


def main():
    volume = make_volume()
    indices = {"AXIAL": 7, "CORONAL": 10, "SAGITAL": 13}
    result = {"spacing_xyz": SPACING, "shape_zyx": SHAPE}
    for orientation, index in indices.items():
        result[orientation] = render_plane(orientation, index, volume)
        for axis in ("u", "v"):
            result[f"{orientation}_mirror_{axis}_control"] = render_plane(orientation, index, volume, mirror=axis)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
