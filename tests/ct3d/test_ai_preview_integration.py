# --------------------------------------------------------------------------
# E6 end to end through the REAL ROIViewerPanel/SegmentationPanel on a real
# Slice()/Project(): AI -> E2 preview (2D overlay) -> E4 source -> Accept /
# Cancel -> real Project().mask_dict. The provider is the TEST-ONLY stub
# (tests/ct3d/ai_stub_provider.py) - this proves the orchestration, not any
# real model. QueueDispatch plays wx.CallAfter so the test decides when
# worker results reach the GUI thread.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

from ai_stub_provider import QueueDispatch, StubAIProvider, stub_candidate

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)  # (z, y, x)
_SPACING = (0.5, 0.8, 2.0)  # (x, y, z)


def _world(z, y, x):
    return (x * _SPACING[0], y * _SPACING[1], z * _SPACING[2])


@pytest.fixture
def env(real_slice_and_project_singleton, monkeypatch):
    import wx
    from invesalius.pubsub import pub as Publisher

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict = {}
    proj.image_versions = []
    proj.surface_dict = {}
    s.current_mask = None
    volume = np.zeros(_SHAPE, dtype=np.int16)
    volume[1:5, 2:10, 2:10] = 300
    s.matrix = volume
    s._spacing = _SPACING
    # What "Load project data" does in the app: ProjectInterface (a
    # singleton) re-reads shape/spacing - otherwise it keeps an earlier test's.
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    ProjectInterface()._refresh_project_data()
    s.to_show_aux = ""
    s.aux_matrices.pop(PREVIEW_AUX_KEY, None)
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()
    Publisher.sendMessage("Create new mask", mask_name="Base", thresh=(200, 400), colour=(1.0, 0.0, 0.0))
    base = s.current_mask
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.YES)
    # Only the stub: ticking AI would otherwise also load the real
    # TotalSegmentator provider, available or not depending on the machine.
    from plugins.roi_viewer.core.ai import registry as ai_registry

    monkeypatch.setattr(ai_registry, "KNOWN_PROVIDER_MODULES", ())

    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.segmentation_panel
    panel.cb_enable_ai.SetValue(True)
    panel._on_enable_ai_toggle(None)
    stub = StubAIProvider()
    panel._ai_registry.register(stub)
    panel._ai_registry.probe_all()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    dispatch = QueueDispatch()
    panel._ai_jobs._dispatch = dispatch
    e = types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, stub=stub, dispatch=dispatch, base=base,
                              aux_key=PREVIEW_AUX_KEY)
    yield e
    if frame:
        frame.Destroy()
    top.Destroy()


def _add_prompts(e):
    """Two points and a box, entered the way the UI does: via the 2D cursor."""
    e.frame._last_cross_focal_point = _world(2, 5, 5)
    e.panel.rb_ai_positive.SetValue(True)
    e.panel._on_ai_cursor_point(None)
    e.frame._last_cross_focal_point = _world(3, 5, 6)
    e.panel.rb_ai_negative.SetValue(True)
    e.panel._on_ai_cursor_point(None)
    e.frame._last_cross_focal_point = _world(1, 8, 8)
    e.panel._on_ai_corner(1)
    e.frame._last_cross_focal_point = _world(2, 10, 11)
    e.panel._on_ai_corner(2)
    return e.panel._ai_prompts.snapshot()


def _run(e, finish=True):
    e.panel._on_ai_run(None)
    if finish:
        assert e.panel._ai_jobs.wait(10)
        e.dispatch.pump()


def _logical(mask):
    return np.asarray(mask.matrix[1:, 1:, 1:]) > 127


def _show_every_slice(s):
    nz, ny, nx = _SHAPE
    for orientation, n in (("AXIAL", nz), ("CORONAL", ny), ("SAGITAL", nx)):
        for k in range(n):
            s.buffer_slices[orientation].index = -1
            s.buffer_slices[orientation].discard_mask()
            s.get_mask_slice(orientation, k)


def test_prompts_from_2d_cursor(env):
    snap = _add_prompts(env)
    assert [p.voxel_zyx for p in snap.points] == [(2, 5, 5), (3, 5, 6)]
    assert [p.positive for p in snap.points] == [True, False]
    assert snap.box.voxel_min_zyx == (1, 8, 8) and snap.box.voxel_max_zyx == (2, 10, 11)
    assert env.panel.lbl_ai_prompts.GetLabel() == "Điểm: 1 thuộc vùng, 1 loại trừ · Hộp: đã đặt"


def test_ai_result_enters_e2_preview_without_creating_a_mask(env):
    snap = _add_prompts(env)
    masks_before = len(env.proj.mask_dict)
    _run(env)
    pm = env.panel.preview_mgr
    expected = stub_candidate(_SHAPE, snap)
    assert pm.state == "PREVIEW_READY" and pm.preview_kind == "ai"
    assert np.array_equal(np.asarray(pm.preview_array) > 0, expected)
    assert set(np.unique(np.asarray(pm.preview_array))) == {0, 255}
    assert len(env.proj.mask_dict) == masks_before  # no Project mask before Accept
    assert pm.ai_metadata["provider_id"] == "stub" and pm.ai_metadata["prompt_count"] == 3
    # the same 2D overlay path E2 uses
    assert env.s.to_show_aux == env.aux_key and env.s.aux_matrices[env.aux_key] is pm.preview_array
    assert env.panel.btn_preview_accept.IsEnabled()
    assert env.panel.lbl_preview_status.GetLabel().startswith("Đã tạo xem trước AI:")


def test_request_is_the_real_volume(env):
    _add_prompts(env)
    _run(env)
    request = env.stub.requests[0]
    assert np.shares_memory(request.volume.array, env.s.matrix)  # not a rendered/texture image
    assert request.volume.array.flags.writeable is False
    assert request.volume.spacing_xyz == _SPACING and request.volume.shape_zyx == _SHAPE


def test_ai_preview_becomes_e4_source(env):
    _add_prompts(env)
    _run(env)
    array, spacing, kind = env.panel._select_preview_3d_source()
    assert kind == "ai_preview"
    assert array is env.panel.preview_mgr.preview_array
    assert env.panel._e4_source_label(kind) == "Xem trước AI"


def test_accept_commits_exactly_the_preview_once(env):
    snap = _add_prompts(env)
    _run(env)
    preview = np.asarray(env.panel.preview_mgr.preview_array) > 0
    count = len(env.proj.mask_dict)
    env.panel._on_preview_accept(None)
    env.panel._on_preview_accept(None)  # double Accept is a no-op
    assert len(env.proj.mask_dict) == count + 1
    mask = env.s.current_mask
    assert mask.name.startswith("AI Segmentation")
    assert np.array_equal(_logical(mask), preview)  # Accept == Preview, bit for bit
    assert np.array_equal(_logical(mask), stub_candidate(_SHAPE, snap))
    _show_every_slice(env.s)
    assert np.array_equal(_logical(mask), preview)  # and it stays so when every slice is shown
    assert env.stub.calls == 1  # the model was not run again
    assert env.panel.preview_mgr.state == "IDLE" and env.aux_key not in env.s.aux_matrices
    assert mask.was_edited is True


def test_cancel_preview_creates_no_mask_and_no_checkpoint(env):
    _add_prompts(env)
    _run(env)
    count = len(env.proj.mask_dict)
    env.panel._on_preview_cancel(None)
    assert len(env.proj.mask_dict) == count
    assert env.panel.preview_mgr.state == "IDLE" and env.aux_key not in env.s.aux_matrices
    editor = env.frame.mask_mgr.get_editor(env.base.index)
    assert editor is None or not editor.undo_manager.can_undo()
    assert env.panel._ai_prompts.count == 3  # prompts kept for another run
    array, _, kind = env.panel._select_preview_3d_source()
    assert kind == "current_roi"  # E4 falls back to the current ROI


def test_clear_ai_points(env):
    _add_prompts(env)
    env.panel._on_ai_clear(None)
    assert env.panel._ai_prompts.count == 0 and env.panel._ai_prompts.corner1 is None


@pytest.mark.parametrize("how", ["e2_cancel", "ai_cancel", "project_close"])
def test_late_result_after_cancel_is_discarded(env, how):
    env.stub.release.clear()
    _add_prompts(env)
    count = len(env.proj.mask_dict)
    _run(env, finish=False)
    assert env.panel.preview_mgr.state == "COMPUTING" and env.panel.btn_ai_cancel.IsEnabled()
    if how == "e2_cancel":
        env.panel._on_preview_cancel(None)
    elif how == "ai_cancel":
        env.panel._on_ai_cancel(None)
    else:
        env.frame.on_project_close()
    env.stub.release.set()
    assert env.panel._ai_jobs.wait(10)
    env.dispatch.pump()
    assert env.panel.preview_mgr.state == "IDLE"
    assert env.aux_key not in env.s.aux_matrices
    assert len(env.proj.mask_dict) == count  # (native project close empties mask_dict itself, not the plugin)
    assert env.panel._ai_jobs.discarded_results == 1
    assert env.panel._ai_jobs.state == "IDLE"


def test_project_close_clears_prompts_and_releases_provider(env):
    _add_prompts(env)
    env.frame.on_project_close()
    assert env.panel._ai_prompts.count == 0
    assert env.stub.closed >= 1


def test_plugin_close_during_inference_is_safe(env):
    env.stub.release.clear()
    _add_prompts(env)
    _run(env, finish=False)
    jobs = env.panel._ai_jobs
    env.frame._on_close(None)  # the real close handler (ends in Destroy())
    env.frame = None
    env.stub.release.set()
    assert jobs.wait(10)
    env.dispatch.pump()  # late result arrives after the window is gone: dropped, no widget touched
    assert jobs.listener is None and jobs.state in ("CANCELLING", "IDLE")
    assert env.stub.closed >= 1


def test_locked_roi_ai_still_runs_and_accept_creates_unlocked_roi(env):
    roi_mgr = env.frame.roi_mgr
    roi_mgr.rebuild_from_project_masks()
    for rid, roi in roi_mgr.rois.items():
        if roi.mask_index == env.base.index:
            roi_mgr.set_locked(rid, True)
    base_before = np.array(env.base.matrix)
    _add_prompts(env)
    _run(env)
    env.panel._on_preview_accept(None)
    new = env.s.current_mask
    assert new is not env.base
    assert np.array_equal(np.array(env.base.matrix), base_before)  # the locked ROI is untouched
    roi_mgr.rebuild_from_project_masks()
    assert roi_mgr.is_locked_for_mask_index(new.index) is False


@pytest.mark.parametrize("output, message", [
    (lambda r: np.ones((2, 2, 2), dtype=bool), "Kết quả AI bị từ chối: kích thước không khớp khối ảnh."),
    (lambda r: np.full(r.volume.shape_zyx, 0.7), "Kết quả AI bị từ chối: không phải mặt nạ nhị phân."),
    (lambda r: np.full(r.volume.shape_zyx, np.nan), "Kết quả AI bị từ chối: có giá trị không hợp lệ."),
    (lambda r: np.zeros(r.volume.shape_zyx, dtype=bool), "AI không tìm thấy vùng nào."),
])
def test_bad_or_empty_candidate_never_reaches_preview(env, output, message):
    env.stub.output = output
    _add_prompts(env)
    count = len(env.proj.mask_dict)
    _run(env)
    assert env.panel.preview_mgr.state == "IDLE"
    assert env.aux_key not in env.s.aux_matrices
    assert len(env.proj.mask_dict) == count
    assert env.panel.lbl_ai_status.GetLabel() == message


def test_ai_candidate_accepted_as_0_255_integers(env):
    env.stub.output = lambda r: stub_candidate(r.volume.shape_zyx, r.prompts).astype(np.uint8) * 255
    snap = _add_prompts(env)
    _run(env)
    env.panel._on_preview_accept(None)
    assert np.array_equal(_logical(env.s.current_mask), stub_candidate(_SHAPE, snap))


def test_provider_failure_shows_message_and_no_preview(env):
    env.stub.fail = True
    _add_prompts(env)
    _run(env)
    assert env.panel.preview_mgr.state == "IDLE"
    assert env.panel.lbl_ai_status.GetLabel() == "Xử lý AI thất bại."


def test_run_without_prompts_is_refused_with_message(env):
    _run(env)
    assert env.stub.calls == 0
    assert env.panel.lbl_ai_status.GetLabel() == "Hãy thêm ít nhất một điểm hoặc hộp giới hạn."
    assert env.panel.preview_mgr.state == "IDLE"


def test_e5_display_state_does_not_change_the_candidate(env):
    """Textures/clipping are display only; the AI input is the volume and
    the prompts. Same prompts -> same candidate with E5 flags on or off."""
    snap = _add_prompts(env)
    _run(env)
    first = np.asarray(env.panel.preview_mgr.preview_array).copy()
    env.panel._on_preview_cancel(None)
    env.frame.interaction_panel.cb_texture_planes.SetValue(True)
    env.frame.interaction_panel.cb_clip_enabled.SetValue(True)
    _run(env)
    assert np.array_equal(np.asarray(env.panel.preview_mgr.preview_array), first)
    assert np.array_equal(first > 0, stub_candidate(_SHAPE, snap))


def test_nothing_ai_is_stored_on_the_project(env):
    _add_prompts(env)
    _run(env)
    env.panel._on_preview_accept(None)
    assert not [k for k in vars(env.proj) if "ai" in k.lower().split("_")]
    assert all(type(m).__name__ == "Mask" for m in env.proj.mask_dict.values())


def test_ai_accepted_mask_save_open_round_trip(tmp_path):
    """Save/Open unchanged: a mask written by the Accept commit
    (native_mask.write_logical_region) round-trips through a real .inv3
    bit for bit - including the computed flags, so the reopened mask never
    re-thresholds - and the project carries nothing AI-specific. Same real
    SavePlistProject/OpenPlistProject harness as test_serialization.py."""
    import os
    import types as _types

    import invesalius.project as prj
    from invesalius.data.mask import Mask

    from plugins.roi_viewer.core import native_mask

    shape = (6, 8, 8)
    img_path = str(tmp_path / "image.dat")
    image = np.memmap(img_path, mode="w+", dtype="int16", shape=shape)
    image[:] = 0
    image.flush()
    proj = prj.Project()
    proj.matrix_shape, proj.matrix_dtype, proj.matrix_filename = shape, "int16", img_path
    proj.mask_dict, proj.surface_dict, proj.image_versions = {}, {}, []
    proj.spacing = (1.0, 1.0, 1.0)

    candidate = np.zeros(shape, dtype=bool)
    candidate[1:4, 2:6, 3:7] = True
    mask = Mask()
    mask.create_mask(shape)
    mask.name = "AI Segmentation 1"
    mask.index = 0
    native_mask.write_logical_region(_types.SimpleNamespace(buffer_slices={}), mask, candidate)
    proj.mask_dict[0] = mask
    before = np.array(mask.matrix)

    save_dir = str(tmp_path / "save")
    os.makedirs(save_dir)
    proj.SavePlistProject(save_dir, "p.inv3", compress=False)
    proj.Close()
    assert proj.OpenPlistProject(os.path.join(save_dir, "p.inv3")) is not False
    [reloaded] = list(proj.mask_dict.values())
    assert reloaded.name == "AI Segmentation 1" and reloaded.was_edited is True
    assert np.array_equal(np.array(reloaded.matrix), before)
    assert np.array_equal(np.asarray(reloaded.matrix[1:, 1:, 1:]) > 127, candidate)
    assert not [k for k in vars(proj) if "ai" in k.lower().split("_")]
