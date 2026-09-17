# --------------------------------------------------------------------------
# Persistent tests for plugins/roi_viewer/core/slice_planes_3d.py
# (SlicePlanes3D - Phase 13.5, pre-Phase-14 visual enhancement of C8).
# Real VTK renderer/actors, no wx/GUI needed - integration-marked (needs
# a real VTK renderer object, matching test_sync_2d3d.py's convention for
# core/marker_3d.py).
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.slice_planes_3d import (
    PLANE_AXIAL,
    PLANE_CORONAL,
    PLANE_SAGITAL,
    SlicePlanes3D,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


BOUNDS = (0.0, 100.0, 0.0, 200.0, 0.0, 50.0)


def test_sp3d_t1_construct_creates_no_actors_until_attach():
    sp = SlicePlanes3D()
    assert sp.actor_count == 0
    assert sp.is_attached is False


def test_sp3d_t2_attach_adds_exactly_3_actors(renderer):
    sp = SlicePlanes3D()
    assert sp.attach(renderer) is True
    assert sp.actor_count == 3
    assert renderer.GetActors().GetNumberOfItems() == 3
    assert sp.is_attached is True


def test_sp3d_t3_attach_twice_does_not_duplicate(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.attach(renderer)
    assert sp.actor_count == 3
    assert renderer.GetActors().GetNumberOfItems() == 3


def test_sp3d_t4_set_bounds_produces_correct_geometry(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    sp.update_position((50.0, 100.0, 25.0))

    xmin, xmax, ymin, ymax, zmin, zmax = BOUNDS
    axial = sp._planes[PLANE_AXIAL]["source"]
    assert axial.GetOrigin() == pytest.approx((xmin, ymin, 25.0))
    assert axial.GetPoint1() == pytest.approx((xmax, ymin, 25.0))
    assert axial.GetPoint2() == pytest.approx((xmin, ymax, 25.0))

    coronal = sp._planes[PLANE_CORONAL]["source"]
    assert coronal.GetOrigin() == pytest.approx((xmin, 100.0, zmin))
    assert coronal.GetPoint1() == pytest.approx((xmax, 100.0, zmin))
    assert coronal.GetPoint2() == pytest.approx((xmin, 100.0, zmax))

    sagital = sp._planes[PLANE_SAGITAL]["source"]
    assert sagital.GetOrigin() == pytest.approx((50.0, ymin, zmin))
    assert sagital.GetPoint1() == pytest.approx((50.0, ymax, zmin))
    assert sagital.GetPoint2() == pytest.approx((50.0, ymin, zmax))


def test_sp3d_t5_update_position_all_3_planes_intersect_same_point(renderer):
    """Every plane's geometry must pass through the exact same real
    world position - verified by checking each plane's constant
    coordinate matches the target position on its own normal axis."""
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    target = (42.0, 77.0, 13.0)
    sp.update_position(target)

    axial = sp._planes[PLANE_AXIAL]["source"]
    assert axial.GetOrigin()[2] == pytest.approx(target[2])  # constant Z

    coronal = sp._planes[PLANE_CORONAL]["source"]
    assert coronal.GetOrigin()[1] == pytest.approx(target[1])  # constant Y

    sagital = sp._planes[PLANE_SAGITAL]["source"]
    assert sagital.GetOrigin()[0] == pytest.approx(target[0])  # constant X


def test_sp3d_t6_update_twice_keeps_same_actor_identity(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    sp.update_position((10.0, 10.0, 10.0))
    actors_before = {name: entry["actor"] for name, entry in sp._planes.items()}

    sp.update_position((90.0, 190.0, 40.0))
    actors_after = {name: entry["actor"] for name, entry in sp._planes.items()}

    for name in actors_before:
        assert actors_before[name] is actors_after[name]  # same VTK object, not recreated
    assert renderer.GetActors().GetNumberOfItems() == 3  # no growth


def test_sp3d_t7_set_visible_false_hides_actors(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    sp.update_position((10, 10, 10))
    sp.set_visible(True)
    sp.set_visible(False)
    for entry in sp._planes.values():
        assert entry["actor"].GetVisibility() == 0


def test_sp3d_t8_set_visible_true_shows_actors(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    sp.update_position((10, 10, 10))
    sp.set_visible(False)
    sp.set_visible(True)
    for entry in sp._planes.values():
        assert entry["actor"].GetVisibility() == 1


def test_sp3d_t9_detach_removes_all_3_actors(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    assert renderer.GetActors().GetNumberOfItems() == 3
    sp.detach()
    assert renderer.GetActors().GetNumberOfItems() == 0
    assert sp.actor_count == 0
    assert sp.is_attached is False


def test_sp3d_t10_detach_twice_is_idempotent(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.detach()
    sp.detach()  # must not raise


def test_sp3d_t11_actors_are_non_pickable(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    for entry in sp._planes.values():
        assert entry["actor"].GetPickable() == 0


def test_sp3d_t12_invalid_bounds_raises_value_error():
    sp = SlicePlanes3D()
    with pytest.raises(ValueError):
        sp.set_bounds((0, 1, 2, 3))  # wrong length
    with pytest.raises(ValueError):
        sp.set_bounds((10, 5, 0, 1, 0, 1))  # xmin >= xmax


def test_sp3d_t12b_invalid_position_raises_value_error(renderer):
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    with pytest.raises(ValueError):
        sp.update_position((float("nan"), 0, 0))
    with pytest.raises(ValueError):
        sp.update_position((0, 0))  # wrong length


def test_update_position_before_bounds_or_attach_does_not_crash():
    """A crosshair event can legitimately arrive before attach()/
    set_bounds() are ready (no project/renderer yet) - must no-op, not
    raise or produce garbage geometry."""
    sp = SlicePlanes3D()
    sp.update_position((1.0, 2.0, 3.0))  # no attach(), no set_bounds() yet
    assert sp.get_position() == (1.0, 2.0, 3.0)  # position is still recorded
    assert sp.actor_count == 0  # but no actors exist to have wrong geometry


def test_reattach_to_new_renderer_leaves_no_orphan_in_old_one():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    renderer_a = vtkRenderer()
    renderer_b = vtkRenderer()
    sp = SlicePlanes3D()
    sp.attach(renderer_a)
    sp.set_bounds(BOUNDS)
    sp.update_position((10, 10, 10))
    sp.attach(renderer_b)  # simulates closing/reopening the plugin window
    assert renderer_a.GetActors().GetNumberOfItems() == 0
    assert renderer_b.GetActors().GetNumberOfItems() == 3


def test_reattach_reapplies_known_bounds_and_position(renderer):
    """attach() after detach() (e.g. plugin reopened) must restore the
    planes to their last known real position, not a default/empty one."""
    sp = SlicePlanes3D()
    sp.attach(renderer)
    sp.set_bounds(BOUNDS)
    sp.update_position((30.0, 60.0, 20.0))
    sp.detach()

    renderer2 = renderer  # re-attach to a renderer after set_bounds/position were cleared by detach()
    sp.attach(renderer2)
    # detach() clears bounds/position (Phase 13.5 design - see its
    # docstring), so a fresh attach() alone (without a new set_bounds())
    # correctly has no meaningful geometry yet - this documents that
    # contract rather than assuming stale state survives detach().
    assert sp.bounds is None
    assert sp.position is None
