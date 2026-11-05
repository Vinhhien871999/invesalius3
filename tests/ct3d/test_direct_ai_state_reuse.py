# --------------------------------------------------------------------------
# Direct interaction - the REAL MedSAM2 worker provider's state reuse
# (tools/interactive_ai_runtime/providers/medsam2_provider.py) with a
# stand-in predictor that reproduces SAM2's feature-cache contract
# (sam2_video_predictor_npz._get_image_feature: ONE frame kept, the dict
# is REASSIGNED on every miss) and computes masks FROM the features, so a
# wrong cache entry would change the result. torch on CPU; no model.
# --------------------------------------------------------------------------
import pathlib
import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "interactive_ai_runtime"))
from providers import medsam2_provider as m2w  # noqa: E402

SHAPE = (12, 32, 40)


class StandInPredictor:
    def __init__(self):
        self.forward_calls = 0
        self.init_calls = 0
        self.propagations = 0

    # SAM2's own caching logic, verbatim in behaviour
    def forward_image(self, image):
        self.forward_calls += 1
        return {"backbone_fpn": [image.mean().reshape(1, 1, 1, 1)], "vision_pos_enc": [image.std().reshape(1, 1, 1, 1)]}

    def _get_image_feature(self, inference_state, frame_idx, batch_size):
        image, backbone_out = inference_state["cached_features"].get(frame_idx, (None, None))
        if backbone_out is None:
            image = inference_state["images"][frame_idx].float().unsqueeze(0)
            backbone_out = self.forward_image(image)
            inference_state["cached_features"] = {frame_idx: (image, backbone_out)}
        return (image, backbone_out)

    def init_state(self, images, video_height, video_width):
        self.init_calls += 1
        return {"images": images, "cached_features": {}, "h": video_height, "w": video_width, "prompts": {}}

    def reset_state(self, state):
        state["prompts"] = {}

    def _mask(self, state, frame_idx, inputs):
        _image, feats = self._get_image_feature(state, frame_idx, 1)
        level = float(feats["backbone_fpn"][0].reshape(()))  # depends on THIS frame's image
        h, w = state["h"], state["w"]
        yy, xx = np.ogrid[:h, :w]
        m = np.zeros((h, w), bool)
        r = 3 + int(level > 0)  # a feature from another frame changes the radius
        for (x, y), lab in zip(inputs.get("points") or [], inputs.get("labels") or []):
            if lab == 1:
                m |= (yy - y) ** 2 + (xx - x) ** 2 <= r ** 2
        if inputs.get("box") is not None:
            x0, y0, x1, y1 = inputs["box"]
            m[int(y0):int(y1) + 1, int(x0):int(x1) + 1] |= True
        return torch.from_numpy(np.where(m, 5.0, -5.0)).float().reshape(1, 1, h, w)

    def add_new_points_or_box(self, state, frame_idx, obj_id, points=None, labels=None, box=None):
        inputs = {"points": None if points is None else points.tolist(),
                  "labels": None if labels is None else labels.tolist(),
                  "box": None if box is None else box.tolist()}
        state["prompts"][frame_idx] = inputs
        return frame_idx, [obj_id], self._mask(state, frame_idx, inputs)

    def propagate_in_video(self, state, reverse=False):
        self.propagations += 1
        cond = sorted(state["prompts"])
        start = cond[-1] if reverse else cond[0]
        frames = range(start, -1, -1) if reverse else range(start, len(state["images"]))
        anchor = state["prompts"][start]
        for f in frames:
            yield f, [1], self._mask(state, f, anchor if abs(f - start) <= 3 else {})


def provider(cache=True):
    p = m2w.MedSAM2Provider({"checkpoint": "", "largest_component": False, "cache_features": cache})
    stand_in = StandInPredictor()
    p._predictors = {"cpu": stand_in}
    vol = (np.random.default_rng(0).integers(-1000, 1000, SHAPE)).astype(np.int16)
    p.load_volume(vol, {}, "cpu")
    return p, stand_in, vol


def predict(p, vol, prompts, **options):
    return p.predict(vol, {}, prompts, "cpu", options, lambda: False, lambda *a: None)


POINT = {"points": [{"zyx": [6, 16, 20], "label": 1}], "box": None}
BOX = {"points": [], "box": {"min_zyx": [6, 10, 12], "max_zyx": [6, 22, 28]}}


def test_state_and_features_are_reused_across_refinements():
    p, s, vol = provider()
    m1, d1 = predict(p, vol, BOX)
    assert s.init_calls == 1 and d1["state_reused"] is False and d1["cached_frames"] == SHAPE[0]
    first_forward = s.forward_calls
    assert first_forward == SHAPE[0]  # every frame encoded once despite SAM2 keeping one
    m2, d2 = predict(p, vol, dict(BOX, points=[{"zyx": [6, 16, 20], "label": 1}]))
    assert s.init_calls == 1 and d2["state_reused"] is True
    assert s.forward_calls == first_forward  # refinement: no image encoder work at all
    m3, _ = predict(p, vol, BOX)
    assert np.array_equal(m1, m3)  # replay of the same prompt set: same candidate


def test_cached_and_uncached_results_are_identical():
    cached, _, vol = provider(cache=True)
    plain, plain_s, _ = provider(cache=False)
    for prompts in (BOX, dict(BOX, points=[{"zyx": [6, 16, 20], "label": 1}])):
        a, _ = predict(cached, vol, prompts)
        b, _ = predict(plain, vol, prompts)
        assert np.array_equal(a, b)
    assert plain_s.forward_calls > SHAPE[0]  # without the cache every refinement re-encodes


def test_window_change_rebuilds_the_state():
    p, s, vol = provider()
    predict(p, vol, BOX, hu_window="soft_tissue")
    predict(p, vol, BOX, hu_window="lung")
    assert s.init_calls == 2
    p.release_volume()
    assert p._state is None and p._prepared == {}


def test_slice_scope_is_one_frame_without_propagation():
    p, s, vol = provider()
    mask, d = predict(p, vol, POINT, scope="slice", target_z=6)
    assert d["scope"] == "slice" and d["slice_z"] == 6 and s.propagations == 0
    assert mask[6].any() and not np.delete(mask, 6, axis=0).any()


def test_point_first_keeps_the_lone_point_when_the_quick_mask_is_a_region():
    p, s, vol = provider()
    mask, d = predict(p, vol, POINT, smart_init=True, smart_min_fast_2d_pixels=20)
    assert d["auto_box"]["strategy"] == "point_only" and d["auto_box"]["box_yx"] is None and mask.any()
    mask2, d2 = predict(p, vol, POINT, smart_init=True, smart_min_fast_2d_pixels=10_000, smart_fallback_half_px=8)
    assert d2["auto_box"]["strategy"] == "click_centred_box" and d2["auto_box"]["box_yx"] == [8, 12, 24, 28]


def test_smart_init_uses_the_current_frame_output():
    p, s, vol = provider()
    mask, d = predict(p, vol, POINT, smart_init=True, smart_policy="fast_2d_box", smart_padding_fraction=0.1,
                      smart_min_padding_px=2)
    auto = d["auto_box"]
    assert auto["strategy"] == "fast_2d_mask" and auto["z"] == 6 and auto["click_in_fast_2d"] is True
    y0, x0, y1, x1 = auto["box_yx"]
    assert y0 <= 16 <= y1 and x0 <= 20 <= x1 and mask.any()
    assert d["key_frames"] == [6]


def test_row_flip_is_applied_to_the_fast_2d_mask():
    """The quick 2D mask comes back in NATIVE rows (the model sees DICOM rows)."""
    p, s, vol = provider()
    mask, _ = predict(p, vol, POINT, scope="slice", target_z=6)
    ys, xs = np.nonzero(mask[6])
    assert abs(ys.mean() - 16) < 0.6 and abs(xs.mean() - 20) < 0.6  # centred on the click, not mirrored
