# --------------------------------------------------------------------------
# E6 prompts - session-only store for point and box prompts.
#
# Input positions are SLICE-frame world (x, y, z) mm: a 3D pick must go
# through core/coordinates.view_to_slice() first, the 2D crosshair already
# is in that frame. Voxel indices use the same rounding as native and as
# core/coordinates.world_xyz_to_voxel_zyx(), but a position outside the
# volume is REJECTED (PromptOutOfVolume) instead of clamped to the edge -
# a clamped prompt would silently point at a different place.
#
# Never serialized: prompts live on the panel for the session and are
# cleared on project close/load and plugin close.
# --------------------------------------------------------------------------
from typing import List, Optional, Tuple

from .types import AIPrompts, BoxPrompt, PointPrompt


class PromptOutOfVolume(ValueError):
    pass


def world_to_voxel_strict(world_xyz, spacing_xyz, shape_zyx) -> Tuple[int, int, int]:
    wx, wy, wz = (float(c) for c in world_xyz)
    sx, sy, sz = (float(s) for s in spacing_xyz)
    nz, ny, nx = shape_zyx
    index = []
    for w, s, n in ((wz, sz, nz), (wy, sy, ny), (wx, sx, nx)):
        if s <= 0:
            raise ValueError(f"spacing must be positive, got {spacing_xyz}")
        i = int(round(w / s))
        if not 0 <= i < n:
            raise PromptOutOfVolume(f"{world_xyz} is outside the volume {shape_zyx} at spacing {spacing_xyz}")
        index.append(i)
    return tuple(index)


def make_point_prompt(world_xyz, spacing_xyz, shape_zyx, positive: bool) -> PointPrompt:
    world = tuple(float(c) for c in world_xyz)
    return PointPrompt(world_xyz=world, voxel_zyx=world_to_voxel_strict(world, spacing_xyz, shape_zyx),
                       positive=bool(positive))


def make_box_prompt(corner1_world, corner2_world, spacing_xyz, shape_zyx) -> BoxPrompt:
    """Two opposite corners in any order -> normalized inclusive voxel
    bounds z_min..z_max, y_min..y_max, x_min..x_max."""
    c1 = tuple(float(c) for c in corner1_world)
    c2 = tuple(float(c) for c in corner2_world)
    v1 = world_to_voxel_strict(c1, spacing_xyz, shape_zyx)
    v2 = world_to_voxel_strict(c2, spacing_xyz, shape_zyx)
    return BoxPrompt(
        corner1_world=c1,
        corner2_world=c2,
        voxel_min_zyx=tuple(min(a, b) for a, b in zip(v1, v2)),
        voxel_max_zyx=tuple(max(a, b) for a, b in zip(v1, v2)),
    )


class AIPromptSet:
    """Mutable session store. snapshot() hands providers an immutable copy."""

    def __init__(self):
        self.points: List[PointPrompt] = []
        self.corner1: Optional[Tuple[float, float, float]] = None
        self.corner2: Optional[Tuple[float, float, float]] = None
        self.box: Optional[BoxPrompt] = None

    def add_point(self, world_xyz, spacing_xyz, shape_zyx, positive: bool) -> PointPrompt:
        prompt = make_point_prompt(world_xyz, spacing_xyz, shape_zyx, positive)
        self.points.append(prompt)
        return prompt

    def set_corner(self, which: int, world_xyz, spacing_xyz, shape_zyx) -> Optional[BoxPrompt]:
        """Sets corner 1 or 2 (validated against the volume). Returns the box
        once both corners exist, else None."""
        if which not in (1, 2):
            raise ValueError("corner must be 1 or 2")
        world = tuple(float(c) for c in world_xyz)
        world_to_voxel_strict(world, spacing_xyz, shape_zyx)
        if which == 1:
            self.corner1 = world
        else:
            self.corner2 = world
        self.box = None
        if self.corner1 is not None and self.corner2 is not None:
            self.box = make_box_prompt(self.corner1, self.corner2, spacing_xyz, shape_zyx)
        return self.box

    def clear(self):
        self.points = []
        self.corner1 = None
        self.corner2 = None
        self.box = None

    @property
    def positive_count(self) -> int:
        return sum(1 for p in self.points if p.positive)

    @property
    def negative_count(self) -> int:
        return sum(1 for p in self.points if not p.positive)

    @property
    def count(self) -> int:
        return len(self.points) + (1 if self.box is not None else 0)

    def snapshot(self) -> AIPrompts:
        return AIPrompts(points=tuple(self.points), box=self.box)
