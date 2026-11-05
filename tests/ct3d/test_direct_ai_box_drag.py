# --------------------------------------------------------------------------
# Direct interaction - drag a box on the Axial view: identical geometry to
# the manual corner buttons, live cyan rectangle, automatic prediction,
# previous candidate replaced, no mask.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from helpers.interactive_env import SHAPE, SPACING, check, drain, enable, make_env, world, write_config
from plugins.roi_viewer.core.ai.prompts import AIPromptSet

pytestmark = pytest.mark.integration


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    e, teardown = make_env(real_slice_and_project_singleton, monkeypatch, tmp_path)
    write_config(e.config, radius=2)
    enable(e)
    check(e)
    yield e
    teardown()


def test_dragged_box_equals_the_manual_corner_box(env):
    p = env.panel
    a, b = world(4, 15, 18), world(4, 6, 7)  # reversed corners on purpose
    p._direct_drag(a, world(4, 10, 10))
    overlay = env.frame.ai_prompt_overlay
    assert overlay.drag == ((4, 10, 10), (4, 15, 18))  # live rectangle while dragging
    p._direct_drag(None, None)
    assert overlay.drag is None
    p._direct_box(a, b)
    manual = AIPromptSet()
    manual.set_corner(1, a, SPACING, SHAPE)
    manual.set_corner(2, b, SPACING, SHAPE)
    assert p._ai_prompts.box == manual.box
    assert overlay.box == ((4, 6, 7), (4, 15, 18))
    assert p._ai_jobs.is_busy()  # prediction started automatically
    drain(env)
    pm = p.preview_mgr
    assert pm.ai_metadata["stage"] == "volume" and pm.ai_metadata["box"] is True
    assert "auto_box" not in (pm.ai_metadata["provider_details"] or {}) or \
        pm.ai_metadata["provider_details"]["auto_box"] is None  # the operator's box is used, not a smart one
    cand = np.asarray(pm.preview_array) > 0
    assert cand.any() and not cand[:, :6].any() and not cand[:, :, 19:].any()
    assert len(env.proj.mask_dict) == 1  # only the Base mask


def test_new_box_replaces_the_previous_candidate(env):
    p, pm = env.panel, env.panel.preview_mgr
    p._direct_box(world(4, 6, 7), world(4, 15, 18))
    drain(env)
    first_gen = pm.ai_metadata["generation"]
    p._direct_box(world(4, 8, 9), world(4, 12, 12))
    assert p._ai_prompts.box.voxel_min_zyx == (4, 8, 9)  # the old box is gone, not combined
    drain(env)
    cand = np.asarray(pm.preview_array) > 0
    assert pm.ai_metadata["generation"] > first_gen and not cand[:, :8].any() and not cand[:, :, 13:].any()
