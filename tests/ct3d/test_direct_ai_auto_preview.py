# --------------------------------------------------------------------------
# Direct interaction: one click -> marker at once -> automatic quick slice
# view -> automatic 3D candidate -> click again -> automatic update ->
# Accept exactly the candidate. Real ROIViewerPanel, real MedSAM2 provider
# module, deterministic FakeInteractiveAIWorker (not model evidence).
# --------------------------------------------------------------------------
import numpy as np
import pytest

from helpers.interactive_env import ball, check, drain, enable, logical, make_env, provider, world, write_config

pytestmark = pytest.mark.integration


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    from plugins.roi_viewer.gui import segmentation_panel as sp

    # the fake worker's 2D disks are tiny (13 px); scale the "real region"
    # threshold to the test volume so both policy branches are reachable
    monkeypatch.setattr(sp, "DIRECT_SMART_MIN_FAST_2D_PIXELS", 5)
    e, teardown = make_env(real_slice_and_project_singleton, monkeypatch, tmp_path)
    write_config(e.config, radius=2)
    enable(e)
    check(e)
    yield e
    teardown()


def _count_infer(e):
    prov = provider(e)
    calls = []
    real = prov.infer

    def counting(request, *a, **k):
        calls.append(dict(request.options))
        return real(request, *a, **k)

    prov.infer = counting
    return calls


def test_direct_mode_is_the_default_for_the_interactive_model(env):
    p = env.panel
    assert p.cb_ai_direct.GetValue() and p.cb_ai_direct.IsShown()
    assert not p.btn_ai_run.IsShown()  # no Run button in normal use
    assert p.lbl_ai_direct_hint.GetLabel().startswith("Nhấp vào cấu trúc cần lấy.")
    assert p.cb_ai_direct.GetToolTipText().startswith("Nhấp trực tiếp trên ảnh CT để phân đoạn.")


def test_click_marker_first_then_automatic_slice_and_3d(env):
    p, pm = env.panel, env.panel.preview_mgr
    calls = _count_infer(env)
    masks0 = len(env.proj.mask_dict)
    p._direct_point(world(4, 10, 12), True)
    # marker and prompt exist BEFORE any model result arrived
    assert env.frame.ai_prompt_overlay.points == [((4, 10, 12), True)]
    assert p._ai_jobs.is_busy() and p.lbl_ai_status.GetLabel() == "Đang xem nhanh trên lát hiện tại…"
    assert len(env.proj.mask_dict) == masks0
    # stage 1: quick slice view, provisional, not Accept-able
    p._ai_jobs.wait(60)
    env.dispatch.pump()
    assert pm.ai_metadata["provisional"] is True and pm.ai_metadata["stage"] == "slice"
    quick = np.asarray(pm.preview_array) > 0
    assert quick[4].any() and not np.delete(quick, 4, axis=0).any()  # only the clicked slice
    assert not p.btn_preview_accept.IsEnabled()
    p._on_preview_accept(None)  # even a forced Accept does nothing on a provisional preview
    assert len(env.proj.mask_dict) == masks0
    assert p._ai_jobs.is_busy() and p.lbl_ai_status.GetLabel() == "Đang phân đoạn vùng đã chọn trong 3D…"
    # stage 2: the 3D candidate, automatically
    drain(env)
    assert pm.ai_metadata["provisional"] is False and pm.ai_metadata["stage"] == "volume"
    assert pm.state == "PREVIEW_READY" and p.btn_preview_accept.IsEnabled()
    details = pm.ai_metadata["provider_details"]
    # point_first: the quick 2D mask is a real region containing the click -> the point alone
    assert details["auto_box"]["strategy"] == "point_only" and details["auto_box"]["box_yx"] is None
    assert pm.ai_metadata["box"] is False
    assert [c.get("scope") for c in calls] == ["slice", "volume"] and calls[1]["smart_init"] is True
    assert calls[1]["smart_policy"] == "point_first" and calls[1]["smart_fallback_half_px"] == 64
    assert len(env.proj.mask_dict) == masks0  # still no native mask
    assert p.lbl_ai_status.GetLabel().startswith("Đã hoàn thành phân đoạn 3D")


def test_second_click_refines_automatically(env):
    p, pm = env.panel, env.panel.preview_mgr
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    first = np.asarray(pm.preview_array) > 0
    gen1 = pm.ai_metadata["generation"]
    p._direct_point(world(4, 10, 15), True)  # a missed part
    drain(env)
    second = np.asarray(pm.preview_array) > 0
    assert pm.ai_metadata["generation"] > gen1 and pm.ai_metadata["stage"] == "volume"
    assert second.sum() > first.sum() and second[ball((4, 10, 15), 1)].all()
    assert pm.ai_metadata["positive_points"] == 2


def test_accept_commits_exactly_the_3d_candidate(env):
    from plugins.roi_viewer.core.ai.providers.medsam2_external_provider import candidate_sha256

    p, pm = env.panel, env.panel.preview_mgr
    calls = _count_infer(env)
    masks0, surfaces0 = len(env.proj.mask_dict), len(env.proj.surface_dict)
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    candidate = np.asarray(pm.preview_array) > 0
    expected = pm.ai_metadata["candidate_sha256"]
    assert expected == candidate_sha256(candidate)
    n = len(calls)
    p._on_preview_accept(None)
    assert len(calls) == n  # no inference at Accept
    assert len(env.proj.mask_dict) == masks0 + 1 and len(env.proj.surface_dict) == surfaces0
    mask = env.s.current_mask
    assert mask.name == "AI - MedSAM2 1" and candidate_sha256(logical(mask)) == expected
    assert np.array_equal(np.asarray(env.base.matrix), env.base_before)


def test_cancel_keeps_prompts_restart_clears_everything(env):
    p, pm = env.panel, env.panel.preview_mgr
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    p._on_preview_cancel(None)
    assert pm.state == "IDLE" and env.aux_key not in env.s.aux_matrices and p._ai_prompts.count == 1
    p._direct_point(world(4, 10, 15), True)
    drain(env)
    assert pm.state == "PREVIEW_READY"
    p._on_ai_restart(None)
    assert pm.state == "IDLE" and p._ai_prompts.count == 0 and env.frame.ai_prompt_overlay.attached == 0
    assert env.aux_key not in env.s.aux_matrices


def test_negative_click_refused_when_not_declared(env):
    import dataclasses

    from plugins.roi_viewer.core.ai.types import PromptType

    p = env.panel
    info = p._ai_registry.info("medsam2")
    p._ai_registry.update_info("medsam2", dataclasses.replace(
        info, supported_prompt_types=(PromptType.POSITIVE_POINT, PromptType.BOX)))
    p._direct_point(world(4, 10, 12), False)
    assert p._ai_prompts.count == 0 and not p._ai_jobs.is_busy()
    assert p.lbl_ai_status.GetLabel() == "Mô hình này không hỗ trợ điểm loại trừ."


def test_empty_quick_view_still_runs_3d_with_click_centred_box(env, tmp_path):
    p = env.panel
    p.shutdown_ai()
    write_config(env.config, radius=2, fast2d_empty=True)
    p._ai_shut_down = False
    from ai_stub_provider import QueueDispatch
    from plugins.roi_viewer.core.ai import job_controller as ai_jobs

    p._ai_jobs = ai_jobs.AIInferenceJobController(dispatch=QueueDispatch())
    p._ai_jobs.listener = p._on_ai_event
    env.dispatch = p._ai_jobs._dispatch
    check(env)
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    pm = p.preview_mgr
    assert pm.ai_metadata["stage"] == "volume"
    assert pm.ai_metadata["provider_details"]["auto_box"]["strategy"] == "click_centred_box"


def test_window_change_invalidates_the_preview(env):
    p, pm = env.panel, env.panel.preview_mgr
    p._direct_point(world(4, 10, 12), True)
    drain(env)
    p.choice_ai_window.SetSelection(1)
    p._on_ai_window_changed(None)
    assert pm.state == "IDLE" and env.aux_key not in env.s.aux_matrices and not p._ai_jobs.is_busy()
    assert p.lbl_ai_status.GetLabel().startswith("Đã đổi cửa sổ CT")
    assert p._ai_prompts.count == 1  # prompts kept; nothing reruns until the next click


def test_direct_off_restores_the_manual_workflow(env):
    p = env.panel
    p.cb_ai_direct.SetValue(False)
    p._on_ai_direct_toggled()
    assert p.btn_ai_run.IsShown() and bool(p._ai_sizer.IsShown(p._ai_prompt_sizer))
    p.frame = None
    env.frame._last_cross_focal_point = world(4, 10, 12)
    p._on_ai_cursor_point(None)
    assert p._ai_prompts.count == 1 and not p._ai_jobs.is_busy()  # no automatic run


def test_click_to_marker_latency_does_not_wait_for_the_model(env):
    """Marker feedback is independent of model speed: the prompt and its
    marker exist when _direct_point returns, while the job is still running."""
    import time

    p = env.panel
    t0 = time.perf_counter()
    p._direct_point(world(4, 10, 12), True)
    latency = time.perf_counter() - t0
    assert env.frame.ai_prompt_overlay.points == [((4, 10, 12), True)] and p._ai_jobs.is_busy()
    print(f"\nclick->marker latency (headless panel, incl. starting the job thread): {latency * 1000:.1f} ms")
    assert latency < 0.5
    drain(env)
