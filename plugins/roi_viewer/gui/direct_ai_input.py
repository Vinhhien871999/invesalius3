# --------------------------------------------------------------------------
# Direct interaction: clicks / drags on InVesalius's 2D slice views become
# interactive-AI prompts (feature/interactive-ai-direct-click).
#
# Input ownership (explicit, never guessed from mouse state):
#   * observers are attached to the 2D views' interactors ONLY while direct
#     interaction is active (interactive model ready + "Tương tác trực tiếp"
#     ticked), and removed otherwise / on project close / plugin close;
#   * a click is taken only when that view's InVesalius state is
#     STATE_DEFAULT (no tool: InVesalius's default style only records the
#     button - styles.BaseImageInteractorStyle.OnPressLeftButton) or
#     SLICE_STATE_CROSS (the cross moves to the clicked point; the AI point
#     is the same point). Every other state - brush/eraser editor, linear /
#     angular / density measures, WW/WL, pan, zoom, spin, watershed, flood
#     fill, crop, reorient - means another tool owns the mouse: nothing is
#     taken. With Ctrl or Alt held nothing is taken either;
#   * events are never consumed: the native style still receives them.
# Gestures: left click -> positive point; Shift + left click -> negative
# point (the panel refuses it when the model does not declare negatives);
# left drag beyond DRAG_THRESHOLD_PX on the AXIAL view in STATE_DEFAULT ->
# a box from the press and release positions (the same two-corner path as
# "Chọn góc 1/2", so the geometry is identical). Mouse moves without a
# pressed button do nothing. Positions: the view's own
# get_vtk_mouse_position() + get_coordinate_cursor() (what the cross tool
# uses), i.e. slice-frame world (x, y, z) mm -> core/coordinates via the
# prompt store.
# --------------------------------------------------------------------------
import math

DRAG_THRESHOLD_PX = 6
STATE_DEFAULT = 1000  # invesalius.constants.STATE_DEFAULT
SLICE_STATE_CROSS = 3006  # invesalius.constants.SLICE_STATE_CROSS
CLICK_STATES = (STATE_DEFAULT, SLICE_STATE_CROSS)
DRAG_STATES = (STATE_DEFAULT,)
DRAG_ORIENTATIONS = ("AXIAL",)

OWNER_NONE = "NONE"
OWNER_DIRECT_POINT = "DIRECT_AI_POINT"
OWNER_DIRECT_BOX = "DIRECT_AI_BOX"
OWNER_NATIVE = "OTHER_NATIVE"


def _constants():
    try:
        import invesalius.constants as const

        return (const.STATE_DEFAULT, const.SLICE_STATE_CROSS)
    except Exception:
        return (STATE_DEFAULT, SLICE_STATE_CROSS)


def click_owner(view_state, ctrl=False, alt=False) -> str:
    """Who owns a left press on a 2D view in InVesalius state `view_state`."""
    default, cross = _constants()
    if ctrl or alt or view_state not in (default, cross):
        return OWNER_NATIVE
    return OWNER_DIRECT_POINT


class DirectAIInput:
    def __init__(self, viewer_lookup, on_point, on_box, on_drag=None):
        """viewer_lookup() -> 2D slice viewers; on_point(world, positive);
        on_box(world1, world2); on_drag(world1, world2 | None) live rectangle."""
        self._viewer_lookup = viewer_lookup
        self.on_point = on_point
        self.on_box = on_box
        self.on_drag = on_drag
        self._tags = {}  # id(viewer) -> (viewer, interactor, [tags])
        self._press = None  # (viewer, mx, my, world, shift, state)
        self.dragging = False
        self.owner = OWNER_NONE
        self._picker = None

    @property
    def active(self) -> bool:
        return bool(self._tags)

    # ------------------------------------------------------------- attach
    def set_active(self, on: bool):
        if on:
            self._attach()
        else:
            self.detach()

    def _attach(self):
        for viewer in list(self._viewer_lookup() or []):
            if id(viewer) in self._tags:
                continue
            iren = getattr(viewer, "interactor", None)
            if iren is None:
                continue
            tags = [
                iren.AddObserver("LeftButtonPressEvent", lambda o, e, v=viewer: self._vtk_press(v), 1.0),
                iren.AddObserver("MouseMoveEvent", lambda o, e, v=viewer: self._vtk_move(v), 1.0),
                iren.AddObserver("LeftButtonReleaseEvent", lambda o, e, v=viewer: self._vtk_release(v), 1.0),
            ]
            self._tags[id(viewer)] = (viewer, iren, tags)

    def detach(self):
        for viewer, iren, tags in list(self._tags.values()):
            for tag in tags:
                try:
                    iren.RemoveObserver(tag)
                except Exception:
                    pass
        self._tags = {}
        self._cancel_press()

    def _cancel_press(self):
        had_drag = self.dragging
        self._press = None
        self.dragging = False
        self.owner = OWNER_NONE
        if had_drag and self.on_drag is not None:
            self.on_drag(None, None)

    # ------------------------------------------------------------- VTK glue
    def _mouse(self, viewer):
        mx, my = viewer.get_vtk_mouse_position()
        iren = viewer.interactor
        return mx, my, bool(iren.GetShiftKey()), bool(iren.GetControlKey()), bool(getattr(iren, "GetAltKey", lambda: 0)())

    def _world(self, viewer, mx, my):
        if self._picker is None:
            from vtkmodules.vtkRenderingCore import vtkWorldPointPicker

            self._picker = vtkWorldPointPicker()
        return tuple(float(c) for c in viewer.get_coordinate_cursor(mx, my, self._picker))

    def _vtk_press(self, viewer):
        try:
            mx, my, shift, ctrl, alt = self._mouse(viewer)
            self.handle_press(viewer, mx, my, shift=shift, ctrl=ctrl, alt=alt)
        except Exception as e:  # never break the native interaction
            print(f"ROI Viewer: direct AI press ignored - {e}")
            self._cancel_press()

    def _vtk_move(self, viewer):
        if self._press is None:
            return  # hover: nothing (never runs the model)
        try:
            mx, my, *_ = self._mouse(viewer)
            self.handle_move(viewer, mx, my)
        except Exception as e:
            print(f"ROI Viewer: direct AI move ignored - {e}")
            self._cancel_press()

    def _vtk_release(self, viewer):
        if self._press is None:
            return
        try:
            mx, my, *_ = self._mouse(viewer)
            self.handle_release(viewer, mx, my)
        except Exception as e:
            print(f"ROI Viewer: direct AI release ignored - {e}")
            self._cancel_press()

    # ------------------------------------------------------------- logic
    def handle_press(self, viewer, mx, my, shift=False, ctrl=False, alt=False):
        state = getattr(viewer, "state", None)
        if click_owner(state, ctrl, alt) != OWNER_DIRECT_POINT:
            self.owner = OWNER_NATIVE
            self._press = None
            return False
        self._press = (viewer, mx, my, self._world(viewer, mx, my), bool(shift), state)
        self.dragging = False
        self.owner = OWNER_DIRECT_POINT
        return True

    def _can_drag(self, viewer, state):
        default, _cross = _constants()
        return state == default and str(getattr(viewer, "orientation", "")).upper() in DRAG_ORIENTATIONS

    def handle_move(self, viewer, mx, my):
        if self._press is None or viewer is not self._press[0]:
            return
        pviewer, px, py, pworld, _shift, state = self._press
        if not self.dragging:
            if math.hypot(mx - px, my - py) < DRAG_THRESHOLD_PX:
                return
            if not self._can_drag(viewer, state):
                # a native drag (e.g. moving the cross, or a drag off Axial):
                # this gesture is not an AI click at all
                self._cancel_press()
                return
            self.dragging = True
            self.owner = OWNER_DIRECT_BOX
        if self.on_drag is not None:
            self.on_drag(pworld, self._world(viewer, mx, my))

    def handle_release(self, viewer, mx, my):
        if self._press is None:
            return None
        pviewer, px, py, pworld, shift, _state = self._press
        dragging = self.dragging
        self._press = None
        self.dragging = False
        self.owner = OWNER_NONE
        if viewer is not pviewer:
            return None
        if dragging:
            end = self._world(viewer, mx, my)
            if self.on_drag is not None:
                self.on_drag(None, None)
            self.on_box(pworld, end)
            return "box"
        self.on_point(pworld, not shift)
        return "point"
