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
    spacing = (0.7, 1.3, 2.1)  # (axial, coronal, sagital) mm/voxel
    dims = (50, 60, 70)
    mgr = _mgr(spacing=spacing, dimensions=dims)
    axial, coronal, sagital = 20, 25, 30
    world = mgr.voxel_to_world(axial, coronal, sagital)
    expected_x = sagital * spacing[2]
    expected_y = coronal * spacing[1]
    expected_z = axial * spacing[0]
    assert world == pytest.approx((expected_x, expected_y, expected_z))
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (axial, coronal, sagital)


def test_roundtrip_near_end_of_volume():
    dims = (108, 512, 512)  # matches the real sample series (0051) used throughout this project
    spacing = (1.0, 0.9765625, 0.9765625)  # matches a plausible real CT spacing
    mgr = _mgr(spacing=spacing, dimensions=dims)
    axial, coronal, sagital = dims[0] - 1, dims[1] - 1, dims[2] - 1
    world = mgr.voxel_to_world(axial, coronal, sagital)
    voxel = mgr.world_to_voxel(*world)
    assert voxel == (axial, coronal, sagital)


def test_world_to_voxel_non_integer_world_coordinate_floors_toward_voxel():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(100, 100, 100))
    # a non-integer world coordinate (real 2D crosshair clicks are never
    # exactly on a voxel boundary) - implementation uses int() truncation
    voxel = mgr.world_to_voxel(x=10.9, y=5.4, z=3.1)
    assert voxel == (3, 5, 10)  # (axial=z, coronal=y, sagital=x), truncated toward 0


def test_world_to_voxel_clamps_out_of_bounds_to_valid_range():
    mgr = _mgr(spacing=(1.0, 1.0, 1.0), dimensions=(10, 10, 10))
    voxel = mgr.world_to_voxel(x=1000.0, y=-50.0, z=1000.0)
    assert voxel == (9, 0, 9)  # clamped to [0, dim-1] on every axis


def test_world_to_voxel_zero_spacing_does_not_divide_by_zero():
    mgr = _mgr(spacing=(0.0, 1.0, 1.0), dimensions=(10, 10, 10))
    # must not raise ZeroDivisionError - falls back to 0 for that axis
    voxel = mgr.world_to_voxel(x=5.0, y=5.0, z=5.0)
    assert voxel[0] == 0


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
