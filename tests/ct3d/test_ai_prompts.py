# --------------------------------------------------------------------------
# E6 prompts (core/ai/prompts.py) - on the existing coordinate contract
# (core/coordinates.py): world (x, y, z) mm slice frame, voxel (z, y, x),
# spacing (x, y, z). Out-of-volume positions are rejected, not clamped.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.ai.prompts import AIPromptSet, PromptOutOfVolume, make_box_prompt, make_point_prompt
from plugins.roi_viewer.core.ai.types import PromptType
from plugins.roi_viewer.core.coordinates import view_to_slice, voxel_zyx_to_world_xyz

SPACING_0051 = (0.4785, 0.4785, 1.5)  # (x, y, z)
SHAPE_0051 = (108, 512, 512)  # (z, y, x)


def test_positive_point():
    p = make_point_prompt((10.0, 20.0, 30.0), (1.0, 1.0, 1.0), (40, 40, 40), positive=True)
    assert p.positive and p.prompt_type == PromptType.POSITIVE_POINT
    assert p.voxel_zyx == (30, 20, 10)
    assert p.world_xyz == (10.0, 20.0, 30.0)


def test_negative_point():
    p = make_point_prompt((1.0, 2.0, 3.0), (1.0, 1.0, 1.0), (10, 10, 10), positive=False)
    assert not p.positive and p.prompt_type == PromptType.NEGATIVE_POINT


@pytest.mark.parametrize("voxel", [(0, 0, 0), (53, 255, 255), (107, 511, 511), (12, 400, 7)])
def test_world_voxel_roundtrip_anisotropic(voxel):
    world = voxel_zyx_to_world_xyz(voxel, SPACING_0051)
    assert make_point_prompt(world, SPACING_0051, SHAPE_0051, True).voxel_zyx == voxel


def test_anisotropic_axes_use_their_own_spacing():
    # x = 100 mm -> 209 (0.4785), y = 50 mm -> 104 (0.4785), z = 30 mm -> 20 (1.5)
    p = make_point_prompt((100.0, 50.0, 30.0), SPACING_0051, SHAPE_0051, True)
    assert p.voxel_zyx == (20, 104, 209)


def test_3d_pick_goes_through_view_to_slice():
    """A pick in the y-flipped 3D view frame (y <= 0) lands on the right
    voxel once converted - the same rule as 3D->2D sync and seeds."""
    view_pick = (142.9, -107.3, 154.4)  # Phase 09's real recorded pick on 0051
    p = make_point_prompt(view_to_slice(view_pick), SPACING_0051, SHAPE_0051, True)
    assert p.voxel_zyx == (103, 224, 299)


def test_box_normalization():
    shape, spacing = (20, 30, 40), (1.0, 1.0, 1.0)
    box = make_box_prompt((30.0, 5.0, 12.0), (10.0, 25.0, 2.0), spacing, shape)
    assert box.voxel_min_zyx == (2, 5, 10)
    assert box.voxel_max_zyx == (12, 25, 30)
    assert box.corner1_world == (30.0, 5.0, 12.0)


@pytest.mark.parametrize("world", [(-1.0, 5.0, 5.0), (5.0, -0.6, 5.0), (5.0, 5.0, 10.0), (50.0, 5.0, 5.0)])
def test_out_of_bounds_rejected_not_clamped(world):
    prompts = AIPromptSet()
    with pytest.raises(PromptOutOfVolume):
        prompts.add_point(world, (1.0, 1.0, 1.0), (10, 10, 10), True)
    with pytest.raises(PromptOutOfVolume):
        prompts.set_corner(1, world, (1.0, 1.0, 1.0), (10, 10, 10))
    assert prompts.count == 0 and prompts.corner1 is None


def test_half_voxel_edge_rounds_like_native():
    p = make_point_prompt((-0.4, 9.4, 0.0), (1.0, 1.0, 1.0), (10, 10, 10), True)
    assert p.voxel_zyx == (0, 9, 0)


def test_box_needs_both_corners():
    prompts = AIPromptSet()
    assert prompts.set_corner(1, (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (10, 10, 10)) is None
    assert prompts.box is None and prompts.count == 0
    box = prompts.set_corner(2, (4.0, 5.0, 6.0), (1.0, 1.0, 1.0), (10, 10, 10))
    assert box is prompts.box and prompts.count == 1
    assert prompts.snapshot().prompt_types == (PromptType.BOX,)


def test_counts_and_clear():
    prompts = AIPromptSet()
    prompts.add_point((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (10, 10, 10), True)
    prompts.add_point((2.0, 2.0, 2.0), (1.0, 1.0, 1.0), (10, 10, 10), True)
    prompts.add_point((3.0, 3.0, 3.0), (1.0, 1.0, 1.0), (10, 10, 10), False)
    prompts.set_corner(1, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (10, 10, 10))
    prompts.set_corner(2, (9.0, 9.0, 9.0), (1.0, 1.0, 1.0), (10, 10, 10))
    assert (prompts.positive_count, prompts.negative_count, prompts.count) == (2, 1, 4)
    prompts.clear()
    assert prompts.count == 0 and prompts.box is None and prompts.corner1 is None and prompts.corner2 is None


def test_snapshot_is_immutable_copy():
    prompts = AIPromptSet()
    prompts.add_point((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (10, 10, 10), True)
    snap = prompts.snapshot()
    prompts.add_point((2.0, 2.0, 2.0), (1.0, 1.0, 1.0), (10, 10, 10), False)
    prompts.clear()
    assert snap.count == 1 and snap.points[0].voxel_zyx == (1, 1, 1)
    with pytest.raises(Exception):
        snap.points[0].positive = False  # frozen


def test_scribble_and_lasso_are_reserved_only():
    assert PromptType.SCRIBBLE in PromptType.RESERVED and PromptType.LASSO in PromptType.RESERVED
    assert PromptType.SCRIBBLE not in PromptType.SUPPORTED and PromptType.LASSO not in PromptType.SUPPORTED
