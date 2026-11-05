# --------------------------------------------------------------------------
# Direct interaction - rapid clicks: bounded work, latest prompt set wins.
# Pure scheduler logic + the real panel with a slow fake worker.
# --------------------------------------------------------------------------
import numpy as np
import pytest

from helpers.interactive_env import ball, check, drain, enable, make_env, provider, world, write_config
from plugins.roi_viewer.core.ai import direct_scheduler as ds


# ------------------------------------------------------------------ scheduler (pure)
def test_click_starts_slice_then_volume():
    s = ds.DirectPreviewScheduler()
    assert s.request() == ds.START_SLICE and s.stage == ds.STAGE_SLICE
    assert s.finished(ds.STAGE_SLICE) == ds.SHOW_THEN_VOLUME and s.stage == ds.STAGE_VOLUME
    assert s.finished(ds.STAGE_VOLUME) == ds.SHOW and not s.busy


def test_rapid_clicks_are_bounded_and_latest_wins():
    s = ds.DirectPreviewScheduler()
    assert s.request() == ds.START_SLICE
    assert [s.request() for _ in range(5)] == [ds.DEFERRED] * 5  # no queue: one pending flag
    assert s.pending is True and s.started[ds.STAGE_SLICE] == 1
    # the running (old) result is not shown; one new slice run with the newest prompts
    assert s.finished(ds.STAGE_SLICE) == ds.DISCARD_THEN_SLICE and s.started[ds.STAGE_SLICE] == 2
    assert s.discarded == 1 and not s.pending
    assert s.finished(ds.STAGE_SLICE) == ds.SHOW_THEN_VOLUME
    assert s.request() == ds.DEFERRED  # click during the 3D stage
    assert s.finished(ds.STAGE_VOLUME) == ds.DISCARD_THEN_SLICE


def test_failure_reset_and_single_stage():
    s = ds.DirectPreviewScheduler()
    s.request()
    assert s.finished(ds.STAGE_SLICE, ok=False) == ds.IDLE and not s.busy
    s.request()
    s.reset()
    assert not s.busy and s.finished(ds.STAGE_SLICE) == ds.IDLE  # a late end after reset is ignored
    one = ds.DirectPreviewScheduler(two_stage=False)
    assert one.request() == ds.START_VOLUME and one.finished(ds.STAGE_VOLUME) == ds.SHOW


# ------------------------------------------------------------------ real panel
@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    e, teardown = make_env(real_slice_and_project_singleton, monkeypatch, tmp_path)
    write_config(e.config, radius=2, delay_s=0.05, steps=6)
    enable(e)
    check(e)
    yield e
    teardown()


def test_three_rapid_clicks_show_only_the_last_prompt_set(env):
    p, pm = env.panel, env.panel.preview_mgr
    calls = []
    prov = provider(env)
    real = prov.infer

    def counting(request, *a, **k):
        calls.append(len(request.prompts.points))
        return real(request, *a, **k)

    prov.infer = counting
    masks0 = len(env.proj.mask_dict)
    for x in (8, 12, 16):  # A, B, C while the first job runs
        p._direct_point(world(4, 10, x), True)
    assert p._ai_jobs.is_busy() and p._direct_sched.pending
    drain(env)
    # A's slice job ran with 1 point; then the latest set (3 points) - never 2
    assert calls[0] == 1 and set(calls[1:]) == {3} and len(calls) == 3
    assert p._direct_sched.discarded == 1
    final = np.asarray(pm.preview_array) > 0
    assert pm.ai_metadata["stage"] == "volume" and pm.ai_metadata["positive_points"] == 3
    assert all(final[ball((4, 10, x), 1)].all() for x in (8, 12, 16))
    assert len(env.proj.mask_dict) == masks0


def test_cancel_during_rapid_clicks_leaves_nothing(env):
    p, pm = env.panel, env.panel.preview_mgr
    p._direct_point(world(4, 10, 8), True)
    p._direct_point(world(4, 10, 12), True)
    p._on_ai_cancel(None)
    drain(env)
    assert not p._direct_sched.busy and not p._direct_sched.pending
    assert pm.state != "PREVIEW_READY" or not pm.ai_metadata
