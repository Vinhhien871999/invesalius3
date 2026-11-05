# --------------------------------------------------------------------------
# Direct interaction - input capture on the 2D views: ownership by
# InVesalius state, click -> point, Shift -> negative, hover -> nothing,
# observers attached only while active, events never consumed. Real VTK
# interactors; viewer geometry from a stand-in with InVesalius's methods.
# --------------------------------------------------------------------------
import types

import pytest

from plugins.roi_viewer.gui import direct_ai_input as dai

STATE_DEFAULT, SLICE_STATE_CROSS = 1000, 3006


class FakeViewer:
    """get_coordinate_cursor: display (mx, my) -> slice-frame world, like the
    real 2D viewer (here: 1 px = 0.5 mm, AXIAL plane z = 3 mm)."""

    def __init__(self, orientation="AXIAL", state=STATE_DEFAULT):
        from vtkmodules.vtkRenderingCore import vtkRenderWindowInteractor

        self.orientation = orientation
        self.state = state
        self.interactor = vtkRenderWindowInteractor()

    def get_coordinate_cursor(self, mx, my, picker=None):
        return (mx * 0.5, my * 0.5, 3.0)


@pytest.fixture
def capture():
    got = types.SimpleNamespace(points=[], boxes=[], drags=[])
    inp = dai.DirectAIInput(lambda: [], lambda w, pos: got.points.append((w, pos)),
                            lambda a, b: got.boxes.append((a, b)), lambda a, b: got.drags.append((a, b)))
    return inp, got


def test_ownership_by_invesalius_state():
    import invesalius.constants as const

    assert (dai.STATE_DEFAULT, dai.SLICE_STATE_CROSS) == (const.STATE_DEFAULT, const.SLICE_STATE_CROSS)
    assert dai.click_owner(const.STATE_DEFAULT) == dai.OWNER_DIRECT_POINT
    assert dai.click_owner(const.SLICE_STATE_CROSS) == dai.OWNER_DIRECT_POINT
    for other in (const.STATE_WL, const.STATE_PAN, const.STATE_ZOOM, const.STATE_MEASURE_DISTANCE,
                  const.STATE_MEASURE_ANGLE, const.SLICE_STATE_EDITOR, const.SLICE_STATE_WATERSHED):
        assert dai.click_owner(other) == dai.OWNER_NATIVE, other
    assert dai.click_owner(const.STATE_DEFAULT, ctrl=True) == dai.OWNER_NATIVE
    assert dai.click_owner(const.STATE_DEFAULT, alt=True) == dai.OWNER_NATIVE


def test_click_is_a_positive_point_shift_click_negative(capture):
    inp, got = capture
    v = FakeViewer()
    assert inp.handle_press(v, 40, 60) and inp.owner == dai.OWNER_DIRECT_POINT
    inp.handle_move(v, 42, 61)  # a small jitter is still a click
    assert inp.handle_release(v, 42, 61) == "point"
    inp.handle_press(v, 10, 10, shift=True)
    inp.handle_release(v, 10, 10)
    assert got.points == [((20.0, 30.0, 3.0), True), ((5.0, 5.0, 3.0), False)]  # the PRESS position
    assert got.boxes == [] and inp.owner == dai.OWNER_NONE


def test_brush_or_measure_owns_the_mouse(capture):
    import invesalius.constants as const

    inp, got = capture
    for state in (const.SLICE_STATE_EDITOR, const.STATE_MEASURE_DISTANCE):
        v = FakeViewer(state=state)
        assert inp.handle_press(v, 40, 60) is False and inp.owner == dai.OWNER_NATIVE
        assert inp.handle_release(v, 40, 60) is None
    assert got.points == []


def test_hover_does_nothing(capture):
    inp, got = capture
    v = FakeViewer()
    for x in range(0, 100, 7):
        inp._vtk_move(v)  # no press -> returns before touching the mouse
        inp.handle_move(v, x, x)
    assert got.points == [] and got.drags == [] and got.boxes == []


def test_drag_on_axial_is_a_box_elsewhere_not(capture):
    inp, got = capture
    v = FakeViewer("AXIAL")
    inp.handle_press(v, 10, 20)
    inp.handle_move(v, 30, 50)
    assert inp.dragging and inp.owner == dai.OWNER_DIRECT_BOX and got.drags[-1] == ((5.0, 10.0, 3.0), (15.0, 25.0, 3.0))
    assert inp.handle_release(v, 40, 60) == "box"
    assert got.boxes == [((5.0, 10.0, 3.0), (20.0, 30.0, 3.0))] and got.drags[-1] == (None, None)
    for viewer in (FakeViewer("CORONAL"), FakeViewer("AXIAL", state=SLICE_STATE_CROSS)):
        inp.handle_press(viewer, 10, 20)
        inp.handle_move(viewer, 40, 60)  # a native drag (cross move / not Axial): cancelled
        assert inp.handle_release(viewer, 40, 60) is None
    assert len(got.boxes) == 1 and got.points == []


def test_observers_attached_only_while_active_and_removed():
    v1, v2 = FakeViewer(), FakeViewer("CORONAL")
    inp = dai.DirectAIInput(lambda: [v1, v2], lambda *a: None, lambda *a: None)
    before = [v.interactor.HasObserver("LeftButtonPressEvent") for v in (v1, v2)]
    inp.set_active(True)
    assert inp.active and all(v.interactor.HasObserver("LeftButtonPressEvent") for v in (v1, v2))
    inp.set_active(True)  # idempotent: one set of observers per view
    assert len(inp._tags) == 2
    inp.set_active(False)
    assert not inp.active and [v.interactor.HasObserver("LeftButtonPressEvent") for v in (v1, v2)] == before


def test_events_are_not_consumed():
    """A native observer on the same interactor still receives the click."""
    v = FakeViewer()
    native = []
    v.interactor.AddObserver("LeftButtonPressEvent", lambda o, e: native.append(e))
    inp = dai.DirectAIInput(lambda: [v], lambda *a: None, lambda *a: None)
    inp.set_active(True)
    v.get_vtk_mouse_position = lambda: (10, 10)
    v.interactor.InvokeEvent("LeftButtonPressEvent")
    v.interactor.InvokeEvent("LeftButtonReleaseEvent")
    assert native == ["LeftButtonPressEvent"]
    inp.detach()
