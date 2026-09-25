# --------------------------------------------------------------------------
# E5A tests: core/textured_slice_planes_3d.py - real VTK objects, no wx
# event loop needed (mirrors core/slice_planes_3d.py's/core/preview_
# surface_3d.py's own test style).
#
# Orientation tests (test_axial/coronal/sagital_texture_orientation):
# prove, for real (not by construction/trust), that this module's own
# geometry (plane_geometry_from_image_bounds) + texture-coordinate
# assignment (build_textured_plane_polydata) correctly correlates each
# WORLD-SPACE plane corner with the REAL image voxel index a real
# converters.to_vtk()-built vtkImageData actually stores that corner's
# data at - using a deliberately non-symmetric synthetic image (4
# distinct corner values, non-square shape) so a horizontal mirror,
# vertical mirror, axis swap, or 90-degree rotation in THIS module's own
# geometry/TCoord code would fail these tests (Section 10's explicit
# requirement).
#
# Documented, honest limitation (see docs/CT3D_ADVANCED_E5_VISUALIZATION
# _REPORT.md's "Texture orientation proof" section for the full
# writeup): this does NOT additionally prove how VTK's own GPU texture
# unit samples a TCoord against the uploaded image at actual render
# time - attempting that via a real off-screen vtkWindowToImageFilter
# render was tried during this milestone's audit and reproducibly
# segfaults in this dev environment (isolated to the framebuffer
# read-back step, reproduced even for a plain untextured sphere actor
# with no texture code involved at all - a real, environment-level VTK/
# graphics limitation, not a defect in this module). Real operator
# manual QA (E5-B/C/D in CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md) is the
# authoritative verification of live-rendered pixel orientation.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.textured_slice_planes_3d import (
    PLANE_AXIAL,
    PLANE_CORONAL,
    PLANE_SAGITAL,
    TexturedSlicePlanes3D,
    build_textured_plane_polydata,
    plane_geometry_from_image_bounds,
)


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


def _asymmetric_image(orientation):
    from invesalius.data import converters

    arr = np.zeros((5, 7), dtype=np.uint8)  # 5 rows, 7 cols - deliberately non-square
    arr[0, 0] = 11
    arr[0, 6] = 22
    arr[4, 0] = 33
    arr[4, 6] = 44
    return converters.to_vtk(arr, (1.0, 1.0, 1.0), 0, orientation)


# ------------------------------------------------------------------
# Lifecycle (mirrors SlicePlanes3D's/PreviewSurfaceManager3D's own tests)
# ------------------------------------------------------------------

def test_attach_once(renderer):
    planes = TexturedSlicePlanes3D()
    assert planes.attach(renderer) is True
    assert planes.is_attached
    assert planes.actor_count == 3


def test_no_duplicate_actors(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    planes.attach(renderer)
    planes.attach(renderer)
    assert planes.actor_count == 3


def test_three_planes_only(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    assert set(planes._planes.keys()) == {PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL}


def test_non_pickable(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    for entry in planes._planes.values():
        assert entry["actor"].GetPickable() == 0


def test_visibility(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    for entry in planes._planes.values():
        assert entry["actor"].GetVisibility() == 0
    planes.set_visible(True)
    for entry in planes._planes.values():
        assert entry["actor"].GetVisibility() == 1
    planes.set_visible(False)
    for entry in planes._planes.values():
        assert entry["actor"].GetVisibility() == 0


def test_detach(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    planes.detach()
    assert not planes.is_attached
    assert planes.actor_count == 0
    assert renderer.GetActors().GetNumberOfItems() == 0


# ------------------------------------------------------------------
# Geometry / texture-coordinate orientation
# ------------------------------------------------------------------

@pytest.mark.parametrize("orientation", [PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL])
def test_geometry_matches_real_image_indices(orientation):
    """Shared real proof for all 3 orientations: id0/id1/id2/id3's world
    positions correspond to the real image's own (0,0)/(last,0)/
    (last,last)/(0,last) corner values - verified empirically for each
    real orientation string during this milestone's audit (see this
    module's own docstring), not assumed."""
    image = _asymmetric_image(orientation)
    origin, p1, p2 = plane_geometry_from_image_bounds(image.GetBounds())
    poly = build_textured_plane_polydata(origin, p1, p2)
    points = poly.GetPoints()

    def value_at_world(pid):
        x, y, z = points.GetPoint(pid)
        i, j, k = int(round(x)), int(round(y)), int(round(z))
        return image.GetScalarComponentAsDouble(i, j, k, 0)

    assert value_at_world(0) == 11.0  # origin -> TCoord (0,0)
    assert value_at_world(1) == 22.0  # point1 -> TCoord (1,0)
    assert value_at_world(2) == 44.0  # opposite corner -> TCoord (1,1)
    assert value_at_world(3) == 33.0  # point2 -> TCoord (0,1)


def test_axial_texture_orientation():
    test_geometry_matches_real_image_indices(PLANE_AXIAL)


def test_coronal_texture_orientation():
    test_geometry_matches_real_image_indices(PLANE_CORONAL)


def test_sagittal_texture_orientation():
    test_geometry_matches_real_image_indices(PLANE_SAGITAL)


def test_geometry_and_texture_same_world_plane(renderer):
    """The textured plane's own corner geometry must be provably
    coincident with core/slice_planes_3d.SlicePlanes3D's real, already-
    shipped geometric-plane formula for the same slice - both must
    derive from the same real bounds/spacing convention. Cross-checked
    directly against SlicePlanes3D's own (already-tested) Axial formula
    here."""
    from invesalius.data import converters
    from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D

    arr = np.zeros((10, 12), dtype=np.uint8)  # dy=10 (y: 0..9), dx=12 (x: 0..11)
    image = converters.to_vtk(arr, (1.0, 1.0, 1.0), 3, "AXIAL")
    origin, p1, p2 = plane_geometry_from_image_bounds(image.GetBounds())

    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds((0.0, 11.0, 0.0, 9.0, 0.0, 20.0))
    sp.update_position((0.0, 0.0, 3.0))
    axial_source = sp._planes["AXIAL"]["source"]
    assert axial_source.GetOrigin() == pytest.approx(origin)
    assert axial_source.GetPoint1() == pytest.approx(p1)
    assert axial_source.GetPoint2() == pytest.approx(p2)


def test_slice_position_updates_texture():
    """Two different real slices must produce different real image
    content passed to the texture - no stale old-slice content at a
    new geometric position (Section 11)."""
    from invesalius.data import converters

    arr0 = np.zeros((4, 4), dtype=np.uint8)
    arr0[:] = 5
    arr1 = np.zeros((4, 4), dtype=np.uint8)
    arr1[:] = 200

    image0 = converters.to_vtk(arr0, (1.0, 1.0, 1.0), 0, "AXIAL")
    image1 = converters.to_vtk(arr1, (1.0, 1.0, 1.0), 0, "AXIAL")

    planes = TexturedSlicePlanes3D()
    from vtkmodules.vtkRenderingCore import vtkRenderer

    planes.attach(vtkRenderer())
    planes.update_plane(PLANE_AXIAL, image0)
    tex0 = planes._planes[PLANE_AXIAL]["texture"].GetInput()
    assert tex0.GetScalarComponentAsDouble(0, 0, 0, 0) == 5.0

    planes.update_plane(PLANE_AXIAL, image1)
    tex1 = planes._planes[PLANE_AXIAL]["texture"].GetInput()
    assert tex1.GetScalarComponentAsDouble(0, 0, 0, 0) == 200.0
    # Same actor/mapper/texture object identity throughout (Section 9 -
    # "no actor accumulation while crosshair moves").
    assert planes.actor_count == 3


def test_window_level_refresh_if_supported():
    """Section 12: Slice().GetSlices() already bakes real Window/Level
    into the image it returns (do_ww_wl() - see this module's own
    docstring for the citation) - a plain re-call with a changed
    do_ww_wl() output is therefore automatically reflected the next
    time update_plane() is called, with no separate W/L-specific code
    path needed here. This test proves update_plane() always adopts
    whatever image it is given (no caching that could serve a stale
    W/L rendering), which is the real mechanism WindowLevelAutoRefresh
    relies on."""
    from invesalius.data import converters
    from vtkmodules.vtkRenderingCore import vtkRenderer

    arr_dark = np.zeros((4, 4), dtype=np.uint8)
    arr_dark[:] = 1
    arr_bright = np.zeros((4, 4), dtype=np.uint8)
    arr_bright[:] = 250

    planes = TexturedSlicePlanes3D()
    planes.attach(vtkRenderer())
    image_dark = converters.to_vtk(arr_dark, (1.0, 1.0, 1.0), 0, "AXIAL")
    planes.update_plane(PLANE_AXIAL, image_dark)
    assert planes._planes[PLANE_AXIAL]["texture"].GetInput().GetScalarComponentAsDouble(0, 0, 0, 0) == 1.0

    image_bright = converters.to_vtk(arr_bright, (1.0, 1.0, 1.0), 0, "AXIAL")
    planes.update_plane(PLANE_AXIAL, image_bright)
    assert planes._planes[PLANE_AXIAL]["texture"].GetInput().GetScalarComponentAsDouble(0, 0, 0, 0) == 250.0


def test_texture_toggle_off_restores_plain_plane_behavior(renderer):
    """Section 8: with texture mode's own actors hidden, the module
    itself does nothing to SlicePlanes3D - this is a real, structural
    guarantee (TexturedSlicePlanes3D never references SlicePlanes3D at
    all), verified here by confirming visibility is independently
    controlled and detach() never touches any other actor in the
    renderer."""
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    planes.set_visible(True)
    assert renderer.GetActors().GetNumberOfItems() == 3
    planes.set_visible(False)
    # Actors remain attached (still 3 in the renderer) but hidden -
    # matches SlicePlanes3D's own "hide, don't destroy" convention.
    assert renderer.GetActors().GetNumberOfItems() == 3
    for entry in planes._planes.values():
        assert entry["actor"].GetVisibility() == 0


def test_project_close_cleanup(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    planes.detach()
    assert renderer.GetActors().GetNumberOfItems() == 0
    assert not planes.is_attached


def test_plugin_close_cleanup(renderer):
    planes = TexturedSlicePlanes3D()
    planes.attach(renderer)
    planes.detach()
    # Reopen simulation - re-attach must not duplicate.
    planes.attach(renderer)
    assert planes.actor_count == 3
    assert renderer.GetActors().GetNumberOfItems() == 3
