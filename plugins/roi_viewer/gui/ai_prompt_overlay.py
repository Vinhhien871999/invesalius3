# --------------------------------------------------------------------------
# Interactive AI prompt markers in InVesalius's 2D views.
#
#   positive point  green filled dot     (only on its own slice)
#   negative point  red filled dot
#   box             thin cyan rectangle  (on every slice it crosses)
#   single corner   small cyan ring      (box not complete yet)
#
# Drawn by ONE plugin object per 2D view, appended to that view's canvas
# draw list (invesalius/gui/widgets/canvas_renderer.CanvasRendererCTX) the
# same way InVesalius's own measurement handles are - positions go through
# the view's renderer (world slice frame -> display), so zoom/pan/slice
# changes are followed with no extra code. The object is transient: it is
# not Project data, never touches the image, never captures the mouse
# (is_over() is always None), and is removed when the prompts are cleared,
# on project close and on plugin close. Not used: the 3D view (the yellow
# crosshair marker stays as it is).
#
# The voxel of a prompt is authoritative; its marker is drawn at
# voxel_zyx_to_world_xyz(voxel, spacing) - core/coordinates.py.
# --------------------------------------------------------------------------
from typing import List, Optional, Tuple

from ..core.coordinates import voxel_zyx_to_world_xyz

POSITIVE_COLOUR = (40, 220, 40, 255)
NEGATIVE_COLOUR = (240, 40, 40, 255)
BOX_COLOUR = (0, 210, 230, 255)
POINT_RADIUS = 5
# 2D view orientation -> voxel axis index into (z, y, x)
ORIENTATION_AXIS = {"AXIAL": 0, "CORONAL": 1, "SAGITAL": 2, "SAGITTAL": 2}


def markers_for_slice(points, box, corners, orientation: str, slice_number: int, spacing_xyz):
    """What to draw on one 2D view showing `slice_number`.
    points: [(voxel_zyx, positive)], box: (min_zyx, max_zyx) | None,
    corners: [voxel_zyx] of a box with only one corner. Returns a list of
    ("point", world_xyz, positive) | ("box", [4 world corners]) |
    ("corner", world_xyz)."""
    axis = ORIENTATION_AXIS.get(str(orientation).upper())
    if axis is None or spacing_xyz is None:
        return []
    out = []
    for voxel, positive in points:
        if int(voxel[axis]) == int(slice_number):
            out.append(("point", voxel_zyx_to_world_xyz(voxel, spacing_xyz), bool(positive)))
    if box is not None:
        lo, hi = box
        if lo[axis] <= slice_number <= hi[axis]:
            a, b = [i for i in range(3) if i != axis]
            quad = []
            for ua, ub in ((lo[a], lo[b]), (hi[a], lo[b]), (hi[a], hi[b]), (lo[a], hi[b])):
                v = [0, 0, 0]
                v[axis], v[a], v[b] = slice_number, ua, ub
                quad.append(voxel_zyx_to_world_xyz(tuple(v), spacing_xyz))
            out.append(("box", quad))
    for voxel in corners:
        if int(voxel[axis]) == int(slice_number):
            out.append(("corner", voxel_zyx_to_world_xyz(voxel, spacing_xyz)))
    return out


def _make_handler_class():
    from invesalius.gui.widgets.canvas_renderer import CanvasHandlerBase

    class AIPromptCanvasHandler(CanvasHandlerBase):
        """One per 2D view; reads the overlay's current snapshot at draw time."""

        def __init__(self, overlay):
            super().__init__(None)
            self.layer = 50
            self.overlay = overlay
            self.bbox = (0, 0, 0, 0)

        def is_over(self, x, y):
            return None  # never intercepts the mouse

        def draw_to_canvas(self, gc, canvas):
            if not self.visible:
                return
            viewer = canvas.viewer
            try:
                number = viewer.slice_data.number
                orientation = viewer.orientation
            except AttributeError:
                return
            ov = self.overlay
            scale = viewer.GetContentScaleFactor() if hasattr(viewer, "GetContentScaleFactor") else 1.0
            for item in markers_for_slice(ov.points, ov.box, ov.corners, orientation, number, ov.spacing):
                if item[0] == "point":
                    colour = POSITIVE_COLOUR if item[2] else NEGATIVE_COLOUR
                    px, py = self._3d_to_2d(canvas.evt_renderer, item[1])
                    canvas.draw_circle((px, py), POINT_RADIUS * scale, width=2, line_colour=(255, 255, 255, 255),
                                       fill_colour=colour)
                elif item[0] == "box":
                    quad = [self._3d_to_2d(canvas.evt_renderer, w) for w in item[1]]
                    for i in range(4):
                        canvas.draw_line(quad[i], quad[(i + 1) % 4], colour=BOX_COLOUR, width=1)
                elif item[0] == "corner":
                    px, py = self._3d_to_2d(canvas.evt_renderer, item[1])
                    canvas.draw_circle((px, py), 4 * scale, width=1, line_colour=BOX_COLOUR,
                                       fill_colour=(0, 0, 0, 0))

    return AIPromptCanvasHandler


class AIPromptOverlay2D:
    def __init__(self, viewer_lookup):
        """viewer_lookup() -> the InVesalius 2D slice viewers (may be [])."""
        self._viewer_lookup = viewer_lookup
        self._handlers = {}  # id(viewer) -> (viewer, handler)
        self._handler_class = None
        self.points: List[Tuple[Tuple[int, int, int], bool]] = []
        self.box: Optional[Tuple[tuple, tuple]] = None
        self.corners: List[Tuple[int, int, int]] = []
        self.spacing = None

    @property
    def attached(self) -> int:
        return len(self._handlers)

    def update(self, prompt_set, spacing_xyz, shape_zyx=None):
        """Mirror the prompt set (voxels) and redraw the 2D views."""
        from ..core.coordinates import world_xyz_to_voxel_zyx

        self.points = [(tuple(p.voxel_zyx), bool(p.positive)) for p in prompt_set.points]
        self.box = None
        if prompt_set.box is not None:
            self.box = (tuple(prompt_set.box.voxel_min_zyx), tuple(prompt_set.box.voxel_max_zyx))
        self.corners = []
        if prompt_set.box is None and spacing_xyz is not None and shape_zyx is not None:
            # corners were validated inside the volume when set (prompts.py)
            for corner in (prompt_set.corner1, prompt_set.corner2):
                if corner is not None:
                    self.corners.append(world_xyz_to_voxel_zyx(corner, spacing_xyz, shape_zyx))
        self.spacing = tuple(spacing_xyz) if spacing_xyz is not None else None
        if self.points or self.box is not None or self.corners:
            self._attach()
        else:
            self.detach()
            return
        self._redraw([v for v, _h in self._handlers.values()])

    def _attach(self):
        viewers = list(self._viewer_lookup() or [])
        if self._handler_class is None and viewers:
            self._handler_class = _make_handler_class()
        for viewer in viewers:
            canvas = getattr(viewer, "canvas", None)
            if canvas is None:
                continue
            entry = self._handlers.get(id(viewer))
            if entry is None or entry[0] is not viewer:
                entry = (viewer, self._handler_class(self))
                self._handlers[id(viewer)] = entry
            if entry[1] not in canvas.draw_list:
                canvas.draw_list.append(entry[1])

    def detach(self):
        """Remove every marker object from every 2D view. Idempotent."""
        viewers = []
        for viewer, handler in list(self._handlers.values()):
            canvas = getattr(viewer, "canvas", None)
            try:
                if canvas is not None and handler in canvas.draw_list:
                    canvas.draw_list.remove(handler)
            except (RuntimeError, ValueError):
                pass
            viewers.append(viewer)
        self._handlers = {}
        self._redraw(viewers)

    def clear(self):
        self.points, self.box, self.corners = [], None, []
        self.detach()

    @staticmethod
    def _redraw(viewers):
        for viewer in viewers:
            try:
                canvas = getattr(viewer, "canvas", None)
                if canvas is not None:
                    canvas.modified = True
                if hasattr(viewer, "UpdateRender"):
                    viewer.UpdateRender()
            except RuntimeError:
                pass
