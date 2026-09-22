# --------------------------------------------------------------------------
# Persistent unit tests for plugins/roi_viewer/core/measurement.py
# (E1 distance, E3 area, E4 volume). CT3D_P11_TEST_AUTOMATION, Section VI.
# Pure numpy - no wx/InVesalius dependency.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.measurement import MeasurementManager

pytestmark = pytest.mark.unit


def test_m_u1_distance_3d_3_4_0_triangle():
    """Classic 3-4-5 right triangle: distance((0,0,0), (3,4,0)) == 5."""
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    mgr.start_distance_measurement()
    mgr.add_point(0, 0, 0)
    mgr.add_point(3, 4, 0)
    result = mgr.finish_distance_measurement("3D")
    assert result is not None
    assert result.distance == pytest.approx(5.0)


def test_m_u2_distance_spacing_aware_uneven_spacing():
    """Spacing must scale each axis independently before the Euclidean
    distance is computed, not just be a uniform multiplier."""
    mgr = MeasurementManager()
    mgr.set_spacing((2.0, 0.5, 1.0))  # uneven, deliberately not a simple scalar
    mgr.start_distance_measurement()
    mgr.add_point(0, 0, 0)
    mgr.add_point(3, 4, 0)  # dx=3*2=6, dy=4*0.5=2, dz=0
    result = mgr.finish_distance_measurement("3D")
    # independent reference calculation, not copied from the implementation
    expected = (6.0**2 + 2.0**2 + 0.0**2) ** 0.5
    assert result.distance == pytest.approx(expected)


def test_m_u2b_distance_2d_ignores_z():
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    mgr.start_distance_measurement()
    mgr.add_point(0, 0, 0)
    mgr.add_point(3, 4, 100)  # large z difference must be ignored in 2D mode
    result = mgr.finish_distance_measurement("2D")
    assert result.distance == pytest.approx(5.0)


def test_m_u3_volume_uneven_spacing():
    """10x10x10 foreground block, spacing (0.5, 0.5, 2.0) mm."""
    mgr = MeasurementManager()
    mgr.set_spacing((0.5, 0.5, 2.0))
    mask = np.zeros((20, 20, 20), dtype=np.uint8)
    mask[0:10, 0:10, 0:10] = 255
    volume = mgr.calculate_volume(mask)
    expected = 1000 * (0.5 * 0.5 * 2.0)  # 1000 voxels * voxel volume in mm^3
    assert volume == pytest.approx(expected)


def test_m_u4_padding_not_counted_e4_regression():
    """
    Direct regression test for the real E4 bug found+fixed via the user
    guide verification round (Round 3): mask.matrix carries a 1-voxel
    padding border (Mask.create_mask() pads every axis by 1) whose
    corner cells (matrix[n,0,0]) double as Slice.do_threshold_to_all_
    slices()'s lazy-threshold "already processed" sentinel and can be
    set to 1 even though they are not real image data. The real fix
    (plugins/roi_viewer/gui/measurement_panel.py._on_measure_volume)
    passes mask.matrix[1:, 1:, 1:] - the logical payload only - instead
    of the full padded matrix. This test proves the underlying
    calculate_volume() sees a real, measurable difference between the
    two, confirming the padding-exclusion contract that fix depends on.
    """
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))

    payload_shape = (10, 10, 10)
    padded_shape = tuple(d + 1 for d in payload_shape)
    matrix = np.zeros(padded_shape, dtype=np.uint8)
    matrix[1:, 1:, 1:] = 0  # no real foreground in the payload for this test
    # Simulate sentinel cells set in the padding column, as
    # do_threshold_to_all_slices() really does per axial slice.
    matrix[1:, 0, 0] = 1

    volume_full_matrix = mgr.calculate_volume(matrix)  # WRONG (pre-fix behavior)
    volume_payload_only = mgr.calculate_volume(matrix[1:, 1:, 1:])  # correct (post-fix)

    assert volume_full_matrix > volume_payload_only  # sentinel cells inflate the count
    assert volume_payload_only == 0.0  # real payload has no foreground in this test
    assert volume_full_matrix == pytest.approx(payload_shape[0] * 1.0)  # exactly the sentinel count


def test_add_volume_measurement_records_mask_index():
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    mask = np.zeros((5, 5, 5), dtype=np.uint8)
    mask[0:2, 0:2, 0:2] = 255
    measurement = mgr.add_volume_measurement(name="", mask_index=3, mask=mask)
    assert measurement.mask_index == 3
    assert measurement.volume == pytest.approx(8.0)
    assert mgr.get_volume_count() == 1


def test_calculate_area_shoelace_unit_square():
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    # Unit square, area should be 1.0 mm^2 at spacing 1.0
    area = mgr.calculate_area([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert area == pytest.approx(1.0)


def test_calculate_area_scales_with_spacing():
    mgr = MeasurementManager()
    mgr.set_spacing((2.0, 3.0, 1.0))
    area = mgr.calculate_area([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert area == pytest.approx(2.0 * 3.0)  # unit square scaled by spacing_x * spacing_y


def test_calculate_area_fewer_than_3_points_is_zero():
    mgr = MeasurementManager()
    assert mgr.calculate_area([(0, 0), (1, 1)]) == 0.0


def test_delete_measurement_by_type_and_index():
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    mgr.add_volume_measurement("", 0, np.ones((2, 2, 2), dtype=np.uint8))
    mgr.add_volume_measurement("", 1, np.ones((2, 2, 2), dtype=np.uint8))
    assert mgr.get_volume_count() == 2
    mgr.delete_measurement("volume", 0)
    assert mgr.get_volume_count() == 1
    assert mgr.volume_measurements[0].mask_index == 1


def test_clear_resets_everything():
    mgr = MeasurementManager()
    mgr.set_spacing((1.0, 1.0, 1.0))
    mgr.add_volume_measurement("", 0, np.ones((2, 2, 2), dtype=np.uint8))
    mgr.start_distance_measurement()
    mgr.add_point(0, 0, 0)
    mgr.clear()
    assert mgr.get_volume_count() == 0
    assert mgr.get_distance_count() == 0
    assert mgr.current_distance_points == []
    assert mgr.measurement_counter == 0


def test_finish_distance_measurement_with_fewer_than_2_points_returns_none():
    mgr = MeasurementManager()
    mgr.start_distance_measurement()
    mgr.add_point(0, 0, 0)
    assert mgr.finish_distance_measurement() is None
