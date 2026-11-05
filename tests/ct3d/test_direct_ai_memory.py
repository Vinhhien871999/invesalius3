# --------------------------------------------------------------------------
# Real-app report 05/11/2026: one click on 0543 ran out of host RAM
# (worker: ndimage.label int32 + bincount int64 of 300x512x512; plugin:
# np.where(fg, 255, 0) -> int32 300 MB), and the failure in the result
# handler left the direct-interaction scheduler waiting forever
# ("Đang cập nhật theo gợi ý mới nhất…"). Low-memory versions must give
# exactly the same numbers; a failure must leave the UI usable.
# --------------------------------------------------------------------------
import pathlib
import sys

import numpy as np
import pytest

from plugins.roi_viewer.core.ai import preview_bridge as pb

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "interactive_ai_runtime"))
from providers import medsam2_provider as m2w  # noqa: E402


def reference_lcc(mask):
    from scipy import ndimage

    labels, n = ndimage.label(mask, structure=np.ones((3, 3, 3), bool))
    if n <= 1:
        return mask.astype(bool)
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    return labels == int(np.argmax(counts))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_lean_largest_component_equals_the_reference(seed):
    rng = np.random.default_rng(seed)
    mask = rng.random((20, 40, 50)) > 0.7
    mask[:3] = False
    mask[:, -5:] = False  # an off-centre bounding box
    assert np.array_equal(m2w.largest_component(mask), reference_lcc(mask))
    assert m2w.largest_component(np.zeros((4, 4, 4), bool)).sum() == 0


def test_lean_window_equals_the_full_formula():
    rng = np.random.default_rng(3)
    vol = rng.integers(-1500, 3000, (37, 20, 24)).astype(np.int16)
    for lower, upper in ((-160, 240), (-1350, 150), (-500, 1300), (5000, 6000)):
        clipped = np.clip(vol.astype(np.float32), lower, upper)
        lo, hi = float(clipped.min()), float(clipped.max())
        expected = np.zeros(vol.shape, np.uint8) if hi <= lo else ((clipped - lo) / (hi - lo) * 255.0).astype(np.uint8)
        assert np.array_equal(m2w.window_to_uint8(vol, lower, upper, chunk=5), expected)


def test_preview_values_uint8_only_and_into_out():
    fg = np.zeros((3, 4, 5), bool)
    fg[1, 2, 3] = True
    v = pb.preview_values(fg)
    assert v.dtype == np.uint8 and np.array_equal(v, np.where(fg, 255, 0).astype(np.uint8))
    out = np.full(fg.shape, 7, np.uint8)
    r = pb.preview_values(fg, out=out)
    assert r is out and np.array_equal(out, v)


def test_uint8_candidate_fast_path():
    m = np.zeros((2, 3, 4), np.uint8)
    m[0, 1, 2] = 1
    assert np.array_equal(pb.validate_candidate(m, m.shape), m.astype(bool))
    m255 = m * 255
    assert np.array_equal(pb.validate_candidate(m255, m.shape), m.astype(bool))
    for bad in (m * 7, np.where(m == 1, 255, 1).astype(np.uint8)):
        with pytest.raises(pb.CandidateError) as e:
            pb.validate_candidate(bad, m.shape)
        assert e.value.code == pb.CANDIDATE_NOT_BINARY


def test_worker_reports_host_out_of_memory(tmp_path):
    from test_interactive_ai_provider import make_provider, point, request

    from plugins.roi_viewer.core.ai.external import protocol as P
    from plugins.roi_viewer.core.ai.providers import medsam2_external_provider as m2

    prov = make_provider(tmp_path, raise_memory_error=True)
    prov.check_environment()
    with pytest.raises(m2.InferenceFailed) as e:
        prov.infer(request(np.zeros((20, 30, 40), np.int16), [point((10, 15, 20))]), lambda *a: None,
                   __import__("threading").Event())
    assert e.value.code == P.E_HOST_OOM and prov.clients[0].worker_alive  # the worker survives
    prov.close()


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


def test_failure_while_showing_a_result_never_wedges_direct_interaction(env, monkeypatch):
    from helpers.interactive_env import drain, world

    from plugins.roi_viewer.gui import segmentation_panel as sp

    p = env.panel
    real = sp.ai_bridge.preview_values
    calls = {"n": 0}

    def failing_once(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MemoryError("Unable to allocate 300. MiB for an array with shape (300, 512, 512) and data type int32")
        return real(*a, **k)

    monkeypatch.setattr(sp.ai_bridge, "preview_values", failing_once)
    masks0 = len(env.proj.mask_dict)
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    assert p.lbl_ai_status.GetLabel().startswith("Không đủ bộ nhớ (RAM)")
    assert not p._direct_sched.busy and not p._direct_sched.pending
    assert p.preview_mgr.state == "IDLE" and env.aux_key not in env.s.aux_matrices
    assert len(env.proj.mask_dict) == masks0
    p._direct_point(world(4, 10, 14), True)  # the next click works again
    drain(env)
    assert p.preview_mgr.state == "PREVIEW_READY" and p.preview_mgr.ai_metadata["stage"] == "volume"


def test_stuck_scheduler_is_released_by_the_next_click(env):
    from helpers.interactive_env import drain, world

    p = env.panel
    p._direct_sched.request()  # simulate a stage that ended without telling the scheduler
    assert p._direct_sched.busy and not p._ai_jobs.is_busy()
    p._direct_point(world(4, 10, 12), True)
    assert p._ai_jobs.is_busy()  # not "deferred" forever
    drain(env)
    assert p.preview_mgr.state == "PREVIEW_READY"


def test_worker_out_of_memory_message(env):
    from helpers.interactive_env import check, drain, world, write_config

    p = env.panel
    write_config(env.config, radius=2, raise_memory_error=True)
    check(env)
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    assert p.lbl_ai_status.GetLabel() == "Môi trường AI hết bộ nhớ (RAM). Hãy đóng bớt chương trình rồi thử lại."
    assert not p._direct_sched.busy
