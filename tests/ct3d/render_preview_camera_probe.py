# --------------------------------------------------------------------------
# Rendered proof for place_3d_camera_if_unset() (30/09/2026). Run as a
# subprocess by test_preview_camera_render.py; prints one JSON line.
#
# Real application symptom: live 3D preview built (11,646 points) but the
# Volume view stayed black - no surface had been shown yet, so InVesalius
# had never placed its 3D camera. Here: the production E4 mesh of a
# trachea-like tube placed like 0801's (far from the world origin), in an
# off-screen renderer with the default VTK camera, then InVesalius's own
# Viewer.SetViewAngle() through the plugin helper.
# --------------------------------------------------------------------------
import json
import os
import pathlib
import sys
import tempfile
import types

if not os.environ.get("XDG_CONFIG_HOME"):  # never the user's real config
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="roi_viewer_probe_")

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    import importlib

    import numpy as np
    from vtkmodules.util.numpy_support import vtk_to_numpy
    from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow, vtkWindowToImageFilter

    importlib.import_module("vtkmodules.vtkRenderingOpenGL2")  # registers the render window
    importlib.import_module("invesalius.data.slice_")  # InVesalius's own import order (avoids a cycle)
    import invesalius.data.viewer_volume as viewer_volume
    from plugins.roi_viewer.core.preview_surface_3d import PreviewSurfaceManager3D, build_preview_mesh
    from plugins.roi_viewer.interface.view_interface import place_3d_camera_if_unset

    spacing = (0.9765625, 0.9765625, 1.0)
    mask = np.zeros((80, 300, 300), dtype=np.uint8)
    zz, yy, xx = np.ogrid[:80, :300, :300]
    mask[((yy - 200) ** 2 + (xx - 250) ** 2 <= 64) & (zz >= 10) & (zz < 70)] = 255
    polydata = build_preview_mesh(mask, spacing)

    renderer = vtkRenderer()
    renderer.SetBackground(0.0, 0.0, 0.0)
    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(160, 160)
    window.AddRenderer(renderer)
    manager = PreviewSurfaceManager3D()
    manager.attach(renderer)
    manager.set_polydata_if_current(manager.new_generation(), polydata, source_kind="current_roi")

    def lit_pixels():
        window.Render()
        grab = vtkWindowToImageFilter()
        grab.SetInput(window)
        grab.ReadFrontBufferOff()
        grab.Update()
        rgb = vtk_to_numpy(grab.GetOutput().GetPointData().GetScalars())[:, :3]
        return int((rgb.max(axis=1) > 10).sum())

    # Stand-in for the wx Viewer: the real SetViewAngle/RepositionCamera
    # methods on the attributes they use.
    viewer = types.SimpleNamespace(ren=renderer, view_angle=None, nav_status=True)
    viewer.SetViewAngle = types.MethodType(viewer_volume.Viewer.SetViewAngle, viewer)
    viewer.RepositionCamera = types.MethodType(viewer_volume.Viewer.RepositionCamera, viewer)

    camera = renderer.GetActiveCamera()
    result = {"mesh_points": polydata.GetNumberOfPoints(), "actor_bounds": list(manager.actor.GetBounds())}
    result["default_camera_position"] = list(camera.GetPosition())
    result["lit_before"] = lit_pixels()
    result["placed"] = place_3d_camera_if_unset(viewer)
    result["lit_after"] = lit_pixels()
    position = camera.GetPosition()
    result["placed_again"] = place_3d_camera_if_unset(viewer)
    result["unchanged_on_second_call"] = camera.GetPosition() == position

    # A camera InVesalius or the user already placed is left alone.
    camera.SetPosition(10.0, 20.0, 30.0)
    placed_view = types.SimpleNamespace(ren=renderer, view_angle=1, SetViewAngle=None)
    result["placed_when_set"] = place_3d_camera_if_unset(placed_view)
    result["user_camera_kept"] = camera.GetPosition() == (10.0, 20.0, 30.0)
    result["placed_without_attribute"] = place_3d_camera_if_unset(types.SimpleNamespace(ren=renderer))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
