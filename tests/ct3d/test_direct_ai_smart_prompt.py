# --------------------------------------------------------------------------
# Direct interaction - smart initial prompt (tools/interactive_ai_runtime/
# smart_prompt.py, numpy only): one click -> box + point.
# --------------------------------------------------------------------------
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "interactive_ai_runtime"))
import smart_prompt as sp  # noqa: E402


def disk(shape, cy, cx, r):
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2


def test_bbox_and_padding_clamped():
    m = disk((100, 120), 50, 60, 10)
    assert sp.bbox_2d(m) == (40, 50, 60, 70)
    assert sp.pad_box((40, 50, 60, 70), (100, 120), 0.1) == (38, 48, 62, 72)  # 10% of 21 px -> 2 px
    assert sp.pad_box((0, 0, 9, 9), (10, 10), 0.5) == (0, 0, 9, 9)  # never outside the image
    assert sp.pad_box((40, 50, 41, 51), (100, 120), 0.1, min_padding_px=3) == (37, 47, 44, 54)
    assert sp.bbox_2d(np.zeros((5, 5), bool)) is None


def test_fast_2d_mask_gives_its_padded_box_and_contains_the_click():
    m = disk((100, 120), 50, 60, 10)
    box, strategy, details = sp.initial_box(m, (52, 61), (100, 120), padding_fraction=0.1, min_padding_px=2)
    assert strategy == sp.STRATEGY_FAST_2D and box == (38, 48, 62, 72)
    assert sp.box_contains(box, (52, 61)) and details["click_in_fast_2d"] is True
    assert details["tight_box"] == [40, 50, 60, 70] and details["fast_2d_pixels"] == int(m.sum())


@pytest.mark.parametrize("why", ["empty", "click_outside", "none"])
def test_fallback_click_centred_box(why):
    shape = (100, 120)
    m = {"empty": np.zeros(shape, bool), "click_outside": disk(shape, 20, 20, 5), "none": None}[why]
    box, strategy, details = sp.initial_box(m, (50, 60), shape, fallback_half_px=16)
    assert strategy == sp.STRATEGY_CLICK_BOX and box == (34, 44, 66, 76) and sp.box_contains(box, (50, 60))
    edge, _, _ = sp.initial_box(None, (2, 118), shape, fallback_half_px=16)
    assert edge == (0, 102, 18, 119)  # clamped at the border, click still inside
    assert sp.box_contains(edge, (2, 118))


def test_point_first_policy_branches():
    shape = (100, 120)
    region = disk(shape, 50, 60, 15)  # 709 px
    box, strategy, d = sp.initial_prompt(region, (50, 60), shape, min_fast_2d_pixels=400)
    assert box is None and strategy == sp.STRATEGY_POINT_ONLY and d["fast_2d_pixels"] == int(region.sum())
    tiny = disk(shape, 50, 60, 3)  # 29 px: like the lung click on 0543 (28 px)
    box, strategy, d = sp.initial_prompt(tiny, (50, 60), shape, min_fast_2d_pixels=400, fallback_half_px=64)
    assert strategy == sp.STRATEGY_CLICK_BOX and box == (0, 0, 99, 119) and d["fallback_half_px"] == 64
    outside = disk(shape, 20, 20, 15)
    assert sp.initial_prompt(outside, (50, 60), shape)[1] == sp.STRATEGY_CLICK_BOX
    assert sp.initial_prompt(None, (50, 60), shape)[1] == sp.STRATEGY_CLICK_BOX
    assert sp.initial_prompt(region, (50, 60), shape, policy=sp.POLICY_FAST_2D_BOX)[1] == sp.STRATEGY_FAST_2D
    with pytest.raises(ValueError):
        sp.initial_prompt(region, (50, 60), shape, policy="guess")


def test_box_prompt_is_a_valid_protocol_box():
    from plugins.roi_viewer.core.ai.external import protocol as P

    b = sp.box_prompt(7, (3, 4, 9, 10))
    assert b == {"min_zyx": [7, 3, 4], "max_zyx": [7, 9, 10]}
    assert P.check_prompts({"points": [], "box": b}, (8, 20, 24))["box"] == b


def test_smart_init_through_the_runtime(tmp_path):
    """The fake worker runs the REAL smart_prompt module on its 2D mask."""
    from test_interactive_ai_provider import make_provider, point, request

    from plugins.roi_viewer.core.ai.provider import OPTION_SMART_INIT, OPTION_SMART_PADDING, OPTION_SMART_POLICY

    vol = np.zeros((20, 30, 40), dtype=np.int16)
    prov = make_provider(tmp_path, radius=3)
    prov.check_environment()
    result = prov.infer(request(vol, [point((10, 15, 20))], **{OPTION_SMART_INIT: True, OPTION_SMART_PADDING: 0.5,
                                                              OPTION_SMART_POLICY: "fast_2d_box"}),
                        lambda *a: None, __import__("threading").Event())
    auto = result.extra["auto_box"]
    assert auto["strategy"] == "fast_2d_mask" and auto["z"] == 10 and auto["tight_box"] == [12, 17, 18, 23]
    assert auto["box_yx"] == [8, 13, 22, 27]  # +50 % of 7 px = 4 px each side (rounded)
    empty = make_provider(tmp_path, radius=3, fast2d_empty=True)
    empty.check_environment()
    r2 = empty.infer(request(vol, [point((10, 15, 20))], **{OPTION_SMART_INIT: True}), lambda *a: None,
                     __import__("threading").Event())
    assert r2.extra["auto_box"]["strategy"] == "click_centred_box" and r2.extra["auto_box"]["policy"] == "point_first"
    prov.close()
    empty.close()
