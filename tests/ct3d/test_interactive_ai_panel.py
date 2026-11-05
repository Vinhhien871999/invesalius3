# --------------------------------------------------------------------------
# Interactive AI end to end through the REAL ROIViewerPanel on a real
# Slice()/Project(), with the REAL MedSAM2 external provider module loaded
# by the registry and configured (read-only JSON via the environment
# variable) to start the deterministic FakeInteractiveAIWorker:
#   not configured -> configured -> environment check -> 2D prompts ->
#   E2 preview (no mask) -> E4 source -> refine -> cancel -> Accept (exactly
#   the candidate, one mask) -> lifecycle (project close / plugin close
#   during a job) -> another provider unaffected.
# Proves the orchestration and the contracts, not model quality.
# --------------------------------------------------------------------------
import json
import pathlib
import sys
import time
import types

import numpy as np
import pytest

from ai_stub_provider import QueueDispatch, StubAIProvider

pytestmark = pytest.mark.integration

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAKE_WORKER = str(ROOT / "tests" / "ct3d" / "helpers" / "fake_interactive_ai_worker.py")
_SHAPE = (8, 20, 24)  # (z, y, x)
_SPACING = (0.5, 0.8, 2.0)  # (x, y, z)


def _world(z, y, x):
    return (x * _SPACING[0], y * _SPACING[1], z * _SPACING[2])


def _ball(center, radius):
    zz, yy, xx = np.ogrid[:_SHAPE[0], :_SHAPE[1], :_SHAPE[2]]
    return (zz - center[0]) ** 2 + (yy - center[1]) ** 2 + (xx - center[2]) ** 2 <= radius ** 2


def _write_config(path, **provider_config):
    path.write_text(json.dumps({
        "enabled": True, "provider": "medsam2", "runtime_command": [sys.executable, FAKE_WORKER],
        "provider_config": provider_config, "predict_timeout_s": 60,
    }), encoding="utf-8")


def _owned_dirs(tmp_path):
    return [p for p in tmp_path.iterdir() if p.name.startswith("roiviewer-iai-")]


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    import wx
    from invesalius.pubsub import pub as Publisher

    from plugins.roi_viewer.core.ai import registry as ai_registry
    from plugins.roi_viewer.core.ai.external import volume_cache
    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict, proj.image_versions, proj.surface_dict = {}, [], {}
    s.current_mask = None
    volume = np.full(_SHAPE, -50, dtype=np.int16)
    volume[2:6, 5:15, 5:19] = 60
    s.matrix = volume
    s._spacing = _SPACING
    ProjectInterface()._refresh_project_data()
    s.to_show_aux = ""
    s.aux_matrices.pop(PREVIEW_AUX_KEY, None)
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()
    Publisher.sendMessage("Create new mask", mask_name="Base", thresh=(0, 100), colour=(1.0, 0.0, 0.0))
    base = s.current_mask
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.YES)
    config_path = tmp_path / "roi_viewer_interactive_ai.json"
    monkeypatch.setenv("ROI_VIEWER_INTERACTIVE_AI_CONFIG", str(config_path))
    temp_root = tmp_path / "tmp"
    temp_root.mkdir()
    monkeypatch.setattr(volume_cache.tempfile, "gettempdir", lambda: str(temp_root))
    monkeypatch.setattr(ai_registry, "KNOWN_PROVIDER_MODULES", (".providers.medsam2_external_provider",))
    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.segmentation_panel
    e = types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, base=base, config=config_path,
                              temp_root=temp_root, base_before=np.asarray(base.matrix).copy(), aux_key=PREVIEW_AUX_KEY)
    yield e
    try:
        panel.shutdown_ai()
    finally:
        frame.Destroy()
        top.Destroy()
        proj.mask_dict, proj.surface_dict = {}, {}
        s.current_mask = None


def _enable(e):
    e.panel.cb_enable_ai.SetValue(True)
    e.panel._on_enable_ai_toggle(None)
    e.dispatch = QueueDispatch()
    e.panel._ai_jobs._dispatch = e.dispatch


def _check(e):
    import wx

    e.panel._on_ai_check_environment(None)
    deadline = time.time() + 60
    while e.panel._ai_env_checking and time.time() < deadline:
        wx.GetApp().Yield(True)
        time.sleep(0.02)
    assert not e.panel._ai_env_checking


def _shown(panel, item):
    return bool(panel._ai_sizer.IsShown(item))


def _provider(e):
    return e.panel._ai_registry.get("medsam2")


def _point(e, voxel, positive=True):
    e.frame._last_cross_focal_point = _world(*voxel)
    (e.panel.rb_ai_positive if positive else e.panel.rb_ai_negative).SetValue(True)
    e.panel._on_ai_cursor_point(None)


def _run(e):
    e.panel._on_ai_run(None)
    assert e.panel._ai_jobs.wait(60)
    e.dispatch.pump()


def _logical(mask):
    return np.asarray(mask.matrix[1:, 1:, 1:]) > 127


# ------------------------------------------------------------------ availability
def test_not_configured_is_shown_and_safe(env):
    _enable(env)
    p = env.panel
    assert p.choice_ai_model.GetString(p.choice_ai_model.GetSelection()) == "Phân đoạn AI tương tác (MedSAM2)"
    assert p.lbl_ai_status.GetLabel() == "MedSAM2 chưa được cấu hình."
    assert _shown(p, p._ai_env_sizer) and "không tự cài đặt hoặc tải mô hình" in p.lbl_ai_env.GetLabel()
    assert p.btn_ai_check_env.IsEnabled() and not p.btn_ai_run.IsEnabled()
    assert not _shown(p, p._ai_prompt_sizer)
    assert _provider(env)._client is None and _owned_dirs(env.temp_root) == []  # nothing started
    _check(env)  # the check re-reads the (still missing) configuration and starts nothing
    assert p.lbl_ai_status.GetLabel() == "MedSAM2 chưa được cấu hình." and _provider(env)._client is None
    _write_config(env.config, radius=2)  # the operator writes the file: no need to re-tick AI
    _check(env)
    assert p.lbl_ai_status.GetLabel() == "Môi trường đã sẵn sàng." and p.btn_ai_run.IsEnabled()


def test_plugin_closed_while_checking_leaves_no_worker(env):
    _write_config(env.config)
    _enable(env)
    p = env.panel
    provider = _provider(env)
    import threading

    import wx

    p._on_ai_check_environment(None)
    p.shutdown_ai()  # plugin closed before the check finished
    for t in [t for t in threading.enumerate() if t.name == "roi-viewer-ai-envcheck"]:
        t.join(60)
    for _ in range(20):  # deliver the check's wx.CallAfter
        wx.GetApp().Yield(True)
        time.sleep(0.02)
    client = provider._client
    assert client is None or not client.worker_alive


def test_configured_then_checked(env):
    _write_config(env.config, radius=2)
    _enable(env)
    p = env.panel
    assert p.lbl_ai_status.GetLabel() == "MedSAM2 đã được cấu hình - hãy bấm Kiểm tra môi trường."
    assert p.btn_ai_check_env.IsEnabled() and not p.btn_ai_run.IsEnabled()
    assert _provider(env)._client is None  # ticking AI on starts no worker
    _check(env)
    assert p.lbl_ai_status.GetLabel() == "Môi trường đã sẵn sàng."
    assert p.btn_ai_run.IsEnabled() and _shown(p, p._ai_prompt_sizer) and not _shown(p, p._ai_env_sizer)
    assert p.rb_ai_negative.IsEnabled() and p.btn_ai_corner1.IsEnabled()  # declared by the worker
    assert _shown(p, p._ai_window_row) and p.choice_ai_window.GetString(0) == "Mô mềm"
    assert "FakeInteractiveAIWorker" in p.lbl_ai_env_info.GetLabel()
    assert p.btn_ai_cursor_point.GetToolTipText().startswith("Đặt điểm chính xác bên trong cấu trúc")
    assert "thường nằm ở biên" in p.btn_ai_pick_point.GetToolTipText()


def test_positive_only_provider_disables_negative(env):
    _write_config(env.config, radius=2)
    _enable(env)
    _check(env)
    from plugins.roi_viewer.core.ai.types import PromptType

    info = env.panel._ai_registry.info("medsam2")
    import dataclasses

    env.panel._ai_registry.update_info("medsam2", dataclasses.replace(
        info, supported_prompt_types=(PromptType.POSITIVE_POINT, PromptType.BOX)))
    env.panel.rb_ai_negative.SetValue(True)
    env.panel._update_ai_controls()
    assert not env.panel.rb_ai_negative.IsEnabled() and env.panel.rb_ai_positive.GetValue()


# ------------------------------------------------------------------ workflow
def test_prompt_preview_refine_cancel_accept(env):
    _write_config(env.config, radius=2)
    _enable(env)
    _check(env)
    p, pm = env.panel, env.panel.preview_mgr
    provider = _provider(env)
    calls = {"n": 0}
    real_infer = provider.infer

    def counting_infer(*a, **k):
        calls["n"] += 1
        return real_infer(*a, **k)

    provider.infer = counting_infer
    masks0, surfaces0 = len(env.proj.mask_dict), len(env.proj.surface_dict)

    _point(env, (4, 10, 12))
    assert p.lbl_ai_prompts.GetLabel() == "Điểm: 1 thuộc vùng, 0 loại trừ · Hộp: chưa có"
    assert env.frame.ai_prompt_overlay.points == [((4, 10, 12), True)]
    assert len(env.proj.mask_dict) == masks0
    _run(env)
    first = np.asarray(pm.preview_array) > 0
    assert pm.preview_kind == "ai" and pm.state == "PREVIEW_READY"
    assert np.array_equal(first, _ball((4, 10, 12), 2))  # candidate on the native grid at the prompt
    assert len(env.proj.mask_dict) == masks0  # no Project mask after the prediction
    assert env.s.to_show_aux == env.aux_key  # the E2 2D overlay
    _, _, kind = p._select_preview_3d_source()
    assert kind == "ai_preview" and p._e4_source_label(kind) == "Xem trước AI tương tác"
    assert p.btn_ai_run.GetLabel() == "Cập nhật xem trước"
    gen1 = pm.ai_metadata["generation"]

    # refinement: a negative point, Update preview replaces the preview
    _point(env, (4, 10, 14), positive=False)
    assert env.frame.ai_prompt_overlay.points[-1] == ((4, 10, 14), False)
    _run(env)
    second = np.asarray(pm.preview_array) > 0
    assert pm.ai_metadata["generation"] > gen1 and second.sum() < first.sum()
    assert not second[_ball((4, 10, 14), 2)].any()
    assert len(env.proj.mask_dict) == masks0  # still no mask, no stacked previews

    # undo restores the previous prompt set
    p._on_ai_undo(None)
    assert [q.voxel_zyx for q in p._ai_prompts.points] == [(4, 10, 12)]

    # cancel: overlay gone, prompts kept
    p._on_preview_cancel(None)
    assert pm.state == "IDLE" and env.aux_key not in env.s.aux_matrices and p._ai_prompts.count == 1
    assert len(env.proj.mask_dict) == masks0
    assert p.btn_ai_run.GetLabel() == "Xem trước bằng AI"

    _run(env)
    candidate = np.asarray(pm.preview_array) > 0
    expected_hash = pm.ai_metadata["candidate_sha256"]
    from plugins.roi_viewer.core.ai.providers.medsam2_external_provider import candidate_sha256

    assert expected_hash == candidate_sha256(candidate)
    n_infer = calls["n"]
    p._on_preview_accept(None)
    assert calls["n"] == n_infer  # no inference at Accept
    assert len(env.proj.mask_dict) == masks0 + 1
    mask = env.s.current_mask
    assert mask.name == "AI - MedSAM2 1"
    assert candidate_sha256(_logical(mask)) == expected_hash  # byte identical
    assert np.array_equal(np.asarray(env.base.matrix), env.base_before)  # parent ROI untouched
    assert len(env.proj.surface_dict) == surfaces0  # no automatic surface
    record = env.frame.roi_provenance[mask]
    assert record["source"] == "AI" and record["ai"]["interactive"] is True
    assert record["ai"]["positive_points"] == 1 and record["ai"]["box"] is False

    # a second accepted candidate never overwrites the first name
    _run(env)
    p._on_preview_accept(None)
    assert env.s.current_mask.name == "AI - MedSAM2 2" and len(env.proj.mask_dict) == masks0 + 2


def test_provider_change_clears_prompts(env):
    _write_config(env.config)
    _enable(env)
    _check(env)
    p = env.panel
    stub = StubAIProvider(provider_id="auto_stub", prompt_types=())  # TotalSegmentator-like: no prompts
    p._ai_registry.register(stub)
    p._ai_registry.probe("auto_stub")
    p._refresh_ai_models(keep_provider_id="medsam2")
    _point(env, (4, 10, 12))
    assert p._ai_prompts.count == 1
    p.choice_ai_model.SetSelection(p._ai_provider_ids.index("auto_stub"))
    p._on_ai_model_changed(None)
    assert p._ai_prompts.count == 0 and env.frame.ai_prompt_overlay.attached == 0
    assert not _shown(p, p._ai_prompt_sizer) and not _shown(p, p._ai_env_sizer)
    assert not p.rb_ai_positive.IsEnabled() and not p.btn_ai_corner1.IsEnabled()
    assert p.lbl_ai_status.GetLabel() == "Sẵn sàng."


# ------------------------------------------------------------------ lifecycle
def test_project_close_during_inference(env):
    _write_config(env.config, delay_s=0.2, steps=100, ignore_cancel=True)
    _enable(env)
    _check(env)
    p = env.panel
    _point(env, (4, 10, 12))
    masks0 = len(env.proj.mask_dict)
    p._on_ai_run(None)
    time.sleep(0.8)
    p.reset_ai_session()  # what project close/load does
    assert p._ai_jobs.wait(30)
    env.dispatch.pump()
    assert p.preview_mgr.state != "PREVIEW_READY" and env.aux_key not in env.s.aux_matrices
    assert len(env.proj.mask_dict) == masks0
    assert p._ai_prompts.count == 0 and env.frame.ai_prompt_overlay.attached == 0
    assert _owned_dirs(env.temp_root) == []
    client = _provider(env)._client
    assert client is None or not client.worker_alive
    # the next project works again (worker restarted lazily)
    _point(env, (3, 9, 9))
    _run(env)
    assert p.preview_mgr.state == "PREVIEW_READY"


def test_plugin_close_during_inference(env):
    _write_config(env.config, delay_s=0.2, steps=100)
    _enable(env)
    _check(env)
    p = env.panel
    _point(env, (4, 10, 12))
    masks0 = len(env.proj.mask_dict)
    p._on_ai_run(None)
    time.sleep(0.6)
    client = _provider(env)._client
    proc = client._process._proc
    p.shutdown_ai()
    p._ai_jobs.wait(30)
    env.dispatch.pump()
    assert p.preview_mgr.state != "PREVIEW_READY" and len(env.proj.mask_dict) == masks0
    deadline = time.time() + 20
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    assert proc.poll() is not None and _owned_dirs(env.temp_root) == []


def test_runtime_crash_leaves_the_ui_usable(env):
    _write_config(env.config, crash_on_predict=True)
    _enable(env)
    _check(env)
    p = env.panel
    _point(env, (4, 10, 12))
    masks0 = len(env.proj.mask_dict)
    _run(env)
    assert p.lbl_ai_status.GetLabel().startswith("Môi trường AI dừng bất ngờ")
    assert p.preview_mgr.state == "IDLE" and len(env.proj.mask_dict) == masks0
    assert p.btn_ai_run.IsEnabled() and p._ai_prompts.count == 1


# ------------------------------------------------------------------ TotalSegmentator regression
def test_totalsegmentator_unaffected_by_the_interactive_provider(env, monkeypatch):
    """Both REAL provider modules, as shipped. TotalSegmentator keeps its own
    info, its place in the dropdown and its no-prompt UI; MedSAM2 (not
    configured here) is only listed after it."""
    from plugins.roi_viewer.core.ai import registry as ai_registry
    from plugins.roi_viewer.core.ai.providers import totalsegmentator_provider as ts

    monkeypatch.setattr(ai_registry, "KNOWN_PROVIDER_MODULES",
                        (".providers.totalsegmentator_provider", ".providers.medsam2_external_provider"))
    _enable(env)
    p = env.panel
    ts_info = p._ai_registry.info(ts.PROVIDER_ID)
    assert ts_info.show_when_unavailable is False and ts_info.checkable is False and ts_info.details == {}
    assert ts_info.supported_prompt_types == ()
    if ts_info.available:
        assert p._ai_provider_ids == [ts.PROVIDER_ID, "medsam2"] and p.choice_ai_model.GetSelection() == 0
        assert p.choice_ai_model.GetString(0) == ts_info.display_name
        assert not _shown(p, p._ai_prompt_sizer) and not _shown(p, p._ai_env_sizer)
        assert not _shown(p, p._ai_window_row)
        assert not p.rb_ai_positive.IsEnabled() and not p.btn_ai_corner1.IsEnabled()
        assert _shown(p, p._ai_structure_row) and p.combo_ai_structure.IsEnabled()
        assert p.btn_ai_run.IsEnabled() and p.lbl_ai_status.GetLabel() == "Sẵn sàng."
        assert p.btn_ai_run.GetLabel() == "Xem trước bằng AI"
    else:  # as before: an unavailable TotalSegmentator is not listed
        assert ts.PROVIDER_ID not in p._ai_provider_ids and p._ai_provider_ids == ["medsam2"]
    assert _provider(env)._client is None  # MedSAM2 started nothing
