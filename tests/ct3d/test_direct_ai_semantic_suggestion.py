# --------------------------------------------------------------------------
# Direct interaction - optional structure-name suggestion from an EXISTING
# TotalSegmentator full-run cache of the same volume. TotalSegmentator is
# never run for it; no cache / other volume / weak / ambiguous -> nothing.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from plugins.roi_viewer.core.ai import semantic_suggestion as ss
from plugins.roi_viewer.core.ai.providers import totalsegmentator_provider as tsm

SHAPE = (6, 10, 12)
CLASSES = {1: "spleen", 2: "kidney_right", 3: "liver"}


def labels():
    lab = np.zeros(SHAPE, dtype=np.uint8)
    lab[1:5, 2:6, 2:6] = 1  # spleen 64 voxels
    lab[1:5, 2:6, 6:8] = 2  # kidney 32 voxels, next to it
    lab[0:6, 6:10, :] = 3  # liver
    return lab


def fake_ts(volume, lab, digest=None):
    """A TotalSegmentator provider object whose cache holds a finished full
    run (same layout as TotalSegmentatorProvider._cache)."""
    prov = tsm.TotalSegmentatorProvider()
    key = (digest or ss.volume_digest(volume),) + (None,) * 5
    prov._cache = (key, tsm.to_nifti_data(lab), np.eye(4), 1.0)
    prov._class_map = lambda: dict(CLASSES)
    prov.infer = lambda *a, **k: pytest.fail("TotalSegmentator must not run for a suggestion")
    return prov


def test_clear_match_is_suggested():
    lab = labels()
    cand = lab == 1
    sug = ss.suggest(cand, lab, CLASSES)
    assert sug.label == "spleen" and sug.reason == "" and sug.coverage == 1.0 and sug.dice == 1.0


def test_weak_and_ambiguous_and_empty():
    lab = labels()
    cand = np.zeros(SHAPE, bool)
    cand[1:5, 2:6, 2:8] = True  # half spleen-ish, half kidney
    assert ss.suggest(cand, lab, CLASSES).reason in (ss.WEAK, ss.AMBIGUOUS)
    tiny = np.zeros(SHAPE, bool)
    tiny[1, 2, 2] = True  # 1 voxel of a 64-voxel spleen: coverage 1, dice tiny
    assert ss.suggest(tiny, lab, CLASSES).reason == ss.WEAK
    assert ss.suggest(np.zeros(SHAPE, bool), lab, CLASSES).reason == ss.EMPTY
    background = np.zeros(SHAPE, bool)
    background[5, 0:2, 0:2] = True
    assert ss.suggest(background, lab, CLASSES).label is None


def test_cache_used_only_for_the_same_volume():
    vol = np.arange(np.prod(SHAPE), dtype=np.int16).reshape(SHAPE)
    lab = labels()
    found, reason = ss.cached_labels(fake_ts(vol, lab), vol)
    assert reason == "" and np.array_equal(found[0], lab) and found[1] == CLASSES
    other = vol.copy()
    other[0, 0, 0] += 1
    assert ss.cached_labels(fake_ts(vol, lab), other) == (None, ss.OTHER_VOLUME)
    assert ss.cached_labels(tsm.TotalSegmentatorProvider(), vol) == (None, ss.NO_CACHE)
    assert ss.cached_labels(None, vol) == (None, ss.NO_CACHE)


def test_digest_matches_the_totalsegmentator_key():
    vol = np.arange(np.prod(SHAPE), dtype=np.int16).reshape(SHAPE)
    key = tsm.TotalSegmentatorProvider.volume_key(vol, np.eye(4), False, "gpu")
    assert key[0] == ss.volume_digest(vol)


# ------------------------------------------------------------------ panel
@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    from helpers.interactive_env import check, enable, make_env, write_config

    e, teardown = make_env(real_slice_and_project_singleton, monkeypatch, tmp_path)
    write_config(e.config, radius=2)
    enable(e)
    check(e)
    yield e
    teardown()


def test_panel_suggestion_and_confirmed_name(env):
    from helpers.interactive_env import ball, drain, world

    p = env.panel
    vol = np.asarray(env.s.matrix)
    lab = np.zeros(vol.shape, dtype=np.uint8)
    lab[ball((4, 10, 12), 2, vol.shape)] = 1  # "spleen" = exactly what the fake worker returns
    p._ai_registry.register(fake_ts(vol, lab))  # an EXISTING full run of this volume
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    assert p._ai_suggestion.label == "spleen"
    assert p.lbl_ai_suggestion.GetLabel().startswith("Gợi ý cấu trúc: spleen")
    assert "TotalSegmentator đã có" in p.lbl_ai_suggestion.GetLabel()
    assert p.btn_ai_use_suggestion.IsShown() and p.btn_ai_use_suggestion.IsEnabled()
    p._on_ai_use_suggestion(None)
    p._on_preview_accept(None)
    assert env.s.current_mask.name == "AI - MedSAM2 - spleen"


def test_panel_without_cache_says_not_identified_and_names_generically(env):
    from helpers.interactive_env import drain, world

    p = env.panel
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    assert p._ai_suggestion.label is None and p.lbl_ai_suggestion.GetLabel() == "Chưa xác định cấu trúc."
    assert not p.btn_ai_use_suggestion.IsShown()
    p._on_preview_accept(None)
    assert env.s.current_mask.name == "AI - MedSAM2 1"
