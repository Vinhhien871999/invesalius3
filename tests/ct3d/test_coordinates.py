# --------------------------------------------------------------------------
# Persistent unit tests for plugins/roi_viewer/core/sync_2d3d.py's
# voxel<->world coordinate transform (world_to_voxel/voxel_to_world).
# CT3D_P11_TEST_AUTOMATION, Section VII. Pure Python - no wx/VTK
# dependency.
#
# Reference calculations here are written independently from
# SyncManager2D3D.world_to_voxel()/voxel_to_world()'s own implementation
# (simple int()/multiplication, not copy-pasted from the source) per the
# spec's explicit instruction not to duplicate the implementation
# mechanically.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.sync_2d3d import SyncManager2D3D

pytestmark = pytest.mark.unit


def _mgr(spacing, dimensions):
    m = SyncManager2D3D()
    m.set_volume_info(spacing=spacing, dimensions=dimensions)
    return m


def test_roundtrip_origin():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    world = mgr.voxel_to_world(0, 0, 0)
    assert world == (0.0, 0.0, 0.0)
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (0, 0, 0)


def test_roundtrip_center_uniform_spacing():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    axial, coronal, sagital = 50, 40, 30
    world = mgr.voxel_to_world(axial, coronal, sagital)
    # independent reference: x=sagital*sx, y=coronal*sy, z=axial*sz
    assert world == pytest.approx((30 * 1.0, 40 * 1.0, 50 * 1.0))
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (axial, coronal, sagital)


def test_roundtrip_center_non_uniform_spacing():
    # Corrected 30/09/2026: this test used to label spacing as (axial,
    # coronal, sagital) and build its "independent" reference with that
    # same wrong mapping (x = sagital * spacing[2]), so it could only agree
    # with the bug. Slice().spacing is (x, y, z) - see core/coordinates.py.
    spacing = (0.7, 1.3, 2.1)  # (x, y, z) mm/voxel
    dims = (50, 60, 70)  # (z, y, x)
    mgr = _mgr(spacing=spacing, dimensions=dims)
    axial, coronal, sagital = 20, 25, 30
    world = mgr.voxel_to_world(axial, coronal, sagital)
    expected_x = sagital * spacing[0]
    expected_y = coronal * spacing[1]
    expected_z = axial * spacing[2]
    assert world == pytest.approx((expected_x, expected_y, expected_z))
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (axial, coronal, sagital)


def test_roundtrip_near_end_of_volume():
    dims = (108, 512, 512)  # (z, y, x) - the real sample series (0051)
    spacing = (0.9765625, 0.9765625, 1.0)  # (x, y, z) - a plausible real CT spacing
    mgr = _mgr(spacing=spacing, dimensions=dims)
    axial, coronal, sagital = dims[0] - 1, dims[1] - 1, dims[2] - 1
    world = mgr.voxel_to_world(axial, coronal, sagital)
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (axial, coronal, sagital)


def test_world_to_voxel_non_integer_world_coordinate_rounds_to_nearest_like_native():
    # Corrected 30/09/2026: this used to assert int() truncation. Native
    # InVesalius selects the slice with round() (viewer_slice.py:1848-1850),
    # so truncation made the plugin pick a different slice than the 2D
    # viewer for any point past a voxel's midpoint.
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    voxel = mgr.world_to_voxel(x=10.9, y=5.4, z=3.1)
    assert voxel == (3, 5, 11)  # (axial=z, coronal=y, sagital=x), nearest


def test_world_to_voxel_clamps_out_of_bounds_to_valid_range():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(10, 10, 10))
    voxel = mgr.world_to_voxel(x=1000.0, y=-50.0, z=1000.0)
    assert voxel == (9, 0, 9)  # clamped to [0, dim-1] on every axis


def test_world_to_voxel_zero_spacing_does_not_divide_by_zero():
    # Corrected 30/09/2026: spacing[0] is x (not axial), so a zero there
    # makes the SAGITAL index (voxel[2]) fall back to 0.
    mgr = _mgr(spacing=(0.0, 1.0, 1.0), dimensions=(10, 10, 10))
    voxel = mgr.world_to_voxel(x=5.0, y=5.0, z=5.0)
    assert voxel == (5, 5, 0)


def test_set_world_coords_updates_slice_index_for_current_plane():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    mgr.current_plane = "AXIAL"
    mgr.set_world_coords(10.0, 20.0, 30.0)
    assert mgr.current_slice_index == 30  # AXIAL slice index == axial voxel index == z/spacing_axial

    mgr.current_plane = "SAGITAL"
    mgr.set_world_coords(10.0, 20.0, 30.0)
    assert mgr.current_slice_index == 10  # SAGITAL index == sagital voxel index == x/spacing_sagital


def test_world_coords_callback_receives_correct_args():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    received = []
    mgr.add_world_coords_callback(lambda x, y, z, plane, idx: received.append((x, y, z, plane, idx)))
    mgr.set_world_coords(1.0, 2.0, 3.0)
    assert len(received) == 1
    x, y, z, plane, idx = received[0]
    assert (x, y, z) == (1.0, 2.0, 3.0)
    assert plane == "AXIAL"


# --------------------------------------------------------------------------
# Canonical convention (core/coordinates.py) - added 30/09/2026 with the
# world<->voxel spacing-order fix. voxel index (z, y, x), Slice().spacing
# (x, y, z), world (x, y, z) mm, origin 0. Anisotropic spacing is used on
# purpose: an axis swap is invisible with isotropic spacing, which is how
# the original bug survived.
# --------------------------------------------------------------------------
from plugins.roi_viewer.core import coordinates  # noqa: E402

SHAPE_0051 = (108, 512, 512)  # Slice().matrix.shape, (z, y, x)
SPACING_0051 = (0.4785, 0.4785, 1.5)  # Slice().spacing, (x, y, z)
ASYMMETRIC = (0.5, 0.8, 2.3)  # all three different, (x, y, z)


def test_spacing_order_xyz():
    assert coordinates.SPACING_ORDER == ("x", "y", "z")
    assert coordinates.VOXEL_INDEX_ORDER == ("z", "y", "x")
    assert coordinates.WORLD_ORDER == ("x", "y", "z")
    # One step along each voxel axis moves world by that axis's OWN spacing.
    sx, sy, sz = ASYMMETRIC
    assert coordinates.voxel_zyx_to_world_xyz((1, 0, 0), ASYMMETRIC) == pytest.approx((0, 0, sz))
    assert coordinates.voxel_zyx_to_world_xyz((0, 1, 0), ASYMMETRIC) == pytest.approx((0, sy, 0))
    assert coordinates.voxel_zyx_to_world_xyz((0, 0, 1), ASYMMETRIC) == pytest.approx((sx, 0, 0))


def test_voxel_zyx_to_world_xyz():
    assert coordinates.voxel_zyx_to_world_xyz((10, 20, 30), ASYMMETRIC) == pytest.approx(
        (30 * 0.5, 20 * 0.8, 10 * 2.3)
    )


def test_world_xyz_to_voxel_zyx():
    world = (30 * 0.5, 20 * 0.8, 10 * 2.3)
    assert coordinates.world_xyz_to_voxel_zyx(world, ASYMMETRIC, (50, 60, 70)) == (10, 20, 30)


@pytest.mark.parametrize("voxel", [(0, 0, 0), (53, 255, 255), (107, 511, 511), (1, 510, 2)])
def test_roundtrip_anisotropic(voxel):
    world = coordinates.voxel_zyx_to_world_xyz(voxel, SPACING_0051)
    assert coordinates.world_xyz_to_voxel_zyx(world, SPACING_0051, SHAPE_0051) == voxel


@pytest.mark.parametrize("voxel", [(0, 0, 0), (7, 13, 29), (49, 59, 69)])
def test_roundtrip_asymmetric_spacing(voxel):
    world = coordinates.voxel_zyx_to_world_xyz(voxel, ASYMMETRIC)
    assert coordinates.world_xyz_to_voxel_zyx(world, ASYMMETRIC, (50, 60, 70)) == voxel


def test_bounds_match_vtk():
    """Ground truth is the SAME converters.to_vtk() call the native
    surface/slice pipelines make with Slice().spacing."""
    import numpy as np

    from invesalius.data import converters

    for shape, spacing in ((SHAPE_0051, SPACING_0051), ((50, 60, 70), ASYMMETRIC)):
        image = converters.to_vtk(np.zeros(shape, dtype=np.uint8), spacing, 0, "AXIAL")
        assert coordinates.volume_bounds_world(shape, spacing) == pytest.approx(image.GetBounds())


def test_bounds_dataset_0051():
    assert coordinates.volume_bounds_world(SHAPE_0051, SPACING_0051) == pytest.approx(
        (0.0, 511 * 0.4785, 0.0, 511 * 0.4785, 0.0, 107 * 1.5)
    )


def test_midpoint_dataset_0051():
    # Before the fix this point mapped to (107, 255, 81).
    mid = (511 * 0.4785 / 2, 511 * 0.4785 / 2, 107 * 1.5 / 2)
    z, y, x = coordinates.world_xyz_to_voxel_zyx(mid, SPACING_0051, SHAPE_0051)
    assert (z, y, x) in {(53, 255, 255), (54, 256, 256), (53, 256, 256), (54, 255, 255)}
    assert abs(z - 53.5) <= 0.5 and abs(y - 255.5) <= 0.5 and abs(x - 255.5) <= 0.5


def test_last_voxel_dataset_0051():
    last = (107, 511, 511)
    world = coordinates.voxel_zyx_to_world_xyz(last, SPACING_0051)
    assert world == pytest.approx((511 * 0.4785, 511 * 0.4785, 107 * 1.5))
    assert coordinates.world_xyz_to_voxel_zyx(world, SPACING_0051, SHAPE_0051) == last


def test_rounding_boundary_selects_nearest_slice():
    # 0.6 of a slice past slice 10 along z (sz = 1.5) -> slice 11.
    assert coordinates.world_xyz_to_voxel_zyx((0, 0, 10.6 * 1.5), SPACING_0051, SHAPE_0051)[0] == 11
    # 0.4 past -> stays on slice 10.
    assert coordinates.world_xyz_to_voxel_zyx((0, 0, 10.4 * 1.5), SPACING_0051, SHAPE_0051)[0] == 10


def test_clamps_every_axis_into_volume():
    far = coordinates.world_xyz_to_voxel_zyx((1e6, 1e6, 1e6), SPACING_0051, SHAPE_0051)
    near = coordinates.world_xyz_to_voxel_zyx((-1e6, -1e6, -1e6), SPACING_0051, SHAPE_0051)
    assert far == (107, 511, 511)
    assert near == (0, 0, 0)


def test_project_interface_delegates_to_canonical_convention():
    """ProjectInterface and SyncManager2D3D must give the same answer -
    one convention, not two independent implementations."""
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    pi = ProjectInterface.__new__(ProjectInterface)
    pi._spacing, pi._shape = SPACING_0051, SHAPE_0051
    mgr = _mgr(spacing=SPACING_0051, dimensions=SHAPE_0051)
    for world in ((10.0, 20.0, 30.0), (122.3, 122.3, 80.2), (244.0, 1.0, 160.0)):
        assert ProjectInterface.world_to_voxel(pi, *world) == mgr.world_to_voxel(*world)
    assert ProjectInterface.voxel_to_world(pi, 53, 255, 255) == mgr.voxel_to_world(53, 255, 255)
