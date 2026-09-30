# --------------------------------------------------------------------------
# E6b TotalSegmentatorProvider without TotalSegmentator: the provider gets
# FAKE module objects (TEST-ONLY) shaped like the official API -
# python_api.totalsegmentator(input, output=None, ..., task, roi_subset,
# device, fast, quiet, ml), map_to_binary.class_map["total"],
# config.get_weights_dir(). The fake "model" reproduces TotalSegmentator's
# geometry (canonical reorientation, predict, reorient back to the input)
# and labels voxels by an intensity code, so exact results are known.
# Nothing here says anything about real segmentation quality.
# --------------------------------------------------------------------------
import threading
import types

import numpy as np
import pytest

nib = pytest.importorskip("nibabel")

from ai_stub_provider import QueueDispatch  # noqa: E402
from plugins.roi_viewer.core.ai import job_controller as jc  # noqa: E402
from plugins.roi_viewer.core.ai import provider as ai_provider  # noqa: E402
from plugins.roi_viewer.core.ai.prompts import AIPromptSet  # noqa: E402
from plugins.roi_viewer.core.ai.providers import totalsegmentator_provider as ts  # noqa: E402
from plugins.roi_viewer.core.ai.types import AIInferenceRequest, Capability, DeviceKind, read_only_volume  # noqa: E402

CLASS_MAP = {1: "spleen", 2: "kidney_right", 5: "liver"}  # non-contiguous ids on purpose
IOP_0051 = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
SHAPE = (6, 10, 12)
SPACING = (0.5, 0.8, 2.3)


# Shaped like TotalSegmentator 2.18.0's map_tasks_config (read from its wheel).
SUB_MODES = {"default": {"task_id": [291, 292, 293, 294, 295]}, "fast": {"task_id": 297},
             "fastest": {"task_id": 298}}
WEIGHT_FOLDERS = {291: "Dataset291_TotalSegmentator_part1_organs_1559subj",
                  292: "Dataset292_TotalSegmentator_part2_vertebrae_1532subj",
                  293: "Dataset293_TotalSegmentator_part3_cardiac_1559subj",
                  294: "Dataset294_TotalSegmentator_part4_muscles_1559subj",
                  295: "Dataset295_TotalSegmentator_part5_ribs_1559subj",
                  297: "Dataset297_TotalSegmentator_total_3mm_1559subj",
                  298: "Dataset298_TotalSegmentator_total_6mm_1559subj"}


def fake_modules(tmp_path, weights=True, cuda=False, signature="full", block=None, fail=False,
                 bad_affine=False, missing=()):
    calls = {"ts": [], "download": 0, "usage": 0, "empty_cache": 0}
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir(exist_ok=True)
    if weights:
        for task_id, folder in WEIGHT_FOLDERS.items():
            if task_id not in missing:
                (weights_dir / folder).mkdir(exist_ok=True)

    api = types.ModuleType("totalsegmentator.python_api")

    def download_pretrained_weights(task_id):  # the real one downloads when the folder is missing
        if not (weights_dir / WEIGHT_FOLDERS[task_id]).is_dir():
            calls["download"] += 1

    def send_usage_stats(*a, **k):
        calls["usage"] += 1

    def run(input, output=None, ml=False, fast=False, task="total", roi_subset=None, quiet=False, device="gpu"):
        calls["ts"].append({"output": output, "ml": ml, "fast": fast, "task": task, "roi_subset": roi_subset,
                            "quiet": quiet, "device": device, "input_type": type(input).__name__})
        # As 2.18.0 does on EVERY run (module-global lookup): the sub-mode's
        # weights, then the 6 mm crop model because roi_subset is set.
        ids = SUB_MODES["fast" if fast else "default"]["task_id"]
        for task_id in (ids if isinstance(ids, list) else [ids]):
            api.download_pretrained_weights(task_id)
        if roi_subset is not None:
            api.download_pretrained_weights(298)
        api.send_usage_stats({}, {"task": task})
        if block is not None:
            block.wait(10)
        if fail:
            raise RuntimeError("fake model crashed")
        canonical = nib.as_closest_canonical(input)
        data = np.asanyarray(canonical.dataobj)
        seg = np.zeros(data.shape, dtype=np.uint8)
        for cid, name in CLASS_MAP.items():
            if roi_subset is None or name in roi_subset:
                seg[data == 100 + cid] = cid
        back = nib.Nifti1Image(seg, canonical.affine).as_reoriented(
            nib.orientations.ornt_transform(nib.io_orientation(canonical.affine), nib.io_orientation(input.affine)))
        if bad_affine:
            wrong = back.affine.copy()
            wrong[:3, 0] *= -1
            back = nib.Nifti1Image(np.asanyarray(back.dataobj), wrong)
        return back

    if signature == "no_roi_subset":
        def run_old(input, output=None, task="total", device="gpu"):
            return None
        api.totalsegmentator = run_old
    else:
        api.totalsegmentator = run
    api.download_pretrained_weights = download_pretrained_weights
    api.send_usage_stats = send_usage_stats

    config = types.ModuleType("totalsegmentator.config")
    config.get_weights_dir = lambda: weights_dir
    mapping = types.ModuleType("totalsegmentator.map_to_binary")
    mapping.class_map = {"total": dict(CLASS_MAP)}
    tasks = types.ModuleType("totalsegmentator.map_tasks_config")
    tasks.TASK_CONFIGS = {"total": {"sub_modes": SUB_MODES}}
    tasks.TASK_ID_WEIGHTS_CONFIGS = {t: {"foldername": f, "version": "v2.0.0-weights"}
                                     for t, f in WEIGHT_FOLDERS.items()}

    torch = types.SimpleNamespace(cuda=types.SimpleNamespace(
        is_available=lambda: cuda, device_count=lambda: 1 if cuda else 0,
        empty_cache=lambda: calls.__setitem__("empty_cache", calls["empty_cache"] + 1)))
    modules = {"totalsegmentator": types.ModuleType("totalsegmentator"), "totalsegmentator.python_api": api,
               "totalsegmentator.config": config, "totalsegmentator.map_to_binary": mapping,
               "totalsegmentator.map_tasks_config": tasks,
               "nibabel": nib, "torch": torch}
    return modules, calls


def _volume():
    v = np.zeros(SHAPE, dtype=np.int16)
    v[1:3, 2:5, 3:7] = 101  # "spleen"
    v[4, 6:9, 8:11] = 102  # "kidney_right"
    v[5, 0, 0] = 105  # "liver", corner voxel
    return v


def _request(structure="spleen", device=DeviceKind.AUTO, mode="standard", iop=IOP_0051, acq="AXIAL", prompts=None):
    return AIInferenceRequest(
        volume=read_only_volume(_volume(), SPACING), prompts=(prompts or AIPromptSet()).snapshot(), device=device,
        options={ai_provider.OPTION_STRUCTURE: structure, ai_provider.OPTION_MODE: mode,
                 ai_provider.OPTION_PATIENT_ORIENTATION: iop, ai_provider.OPTION_ACQUISITION: acq})


def _provider(tmp_path, **kw):
    modules, calls = fake_modules(tmp_path, **kw)
    return ts.TotalSegmentatorProvider(modules=modules, version="2.x-fake"), calls


def _infer(provider, request):
    return provider.infer(request, lambda f, m="": None, threading.Event())


# ------------------------------------------------------------------ probe
def test_package_missing():
    info = ts.TotalSegmentatorProvider(modules={}).probe()
    assert info.available is False and info.unavailable_reason.startswith(ai_provider.REASON_PACKAGE_MISSING)


def test_dependency_missing(tmp_path):
    modules, _ = fake_modules(tmp_path)
    del modules["torch"]
    info = ts.TotalSegmentatorProvider(modules=modules).probe()
    assert not info.available and info.unavailable_reason.startswith(ai_provider.REASON_DEPENDENCY)


def test_incompatible_api(tmp_path):
    info = _provider(tmp_path, signature="no_roi_subset")[0].probe()
    assert not info.available and info.unavailable_reason.startswith(ai_provider.REASON_API)


def test_weights_missing(tmp_path):
    info = _provider(tmp_path, weights=False)[0].probe()
    assert not info.available and info.unavailable_reason.startswith(ai_provider.REASON_WEIGHTS)


def test_available_probe_is_truthful(tmp_path):
    info = _provider(tmp_path)[0].probe()
    assert info.available and info.provider_id == "totalsegmentator" and info.version == "2.x-fake"
    assert info.capabilities == (Capability.AUTOMATIC,)  # no prompts, not interruptible
    assert info.supported_prompt_types == () and info.requires_weights is True
    assert info.parameter_choices[ai_provider.OPTION_STRUCTURE] == ("spleen", "kidney_right", "liver")
    assert info.parameter_choices[ai_provider.OPTION_MODE] == ("standard", "fast")
    assert info.supported_devices == (DeviceKind.CPU,)


def test_probe_reports_cuda_only_when_really_available(tmp_path):
    assert _provider(tmp_path, cuda=True)[0].probe().supported_devices == (DeviceKind.CPU, DeviceKind.CUDA)


def test_probe_does_not_run_the_model(tmp_path):
    provider, calls = _provider(tmp_path)
    provider.probe()
    assert calls["ts"] == [] and calls["download"] == 0


# ------------------------------------------------------------------ requests
def test_device_mapping():
    assert ts.TotalSegmentatorProvider.ts_device(DeviceKind.AUTO, True) == "gpu"
    assert ts.TotalSegmentatorProvider.ts_device(DeviceKind.AUTO, False) == "cpu"
    assert ts.TotalSegmentatorProvider.ts_device(DeviceKind.CPU, True) == "cpu"
    assert ts.TotalSegmentatorProvider.ts_device(DeviceKind.CUDA, True) == "gpu"
    with pytest.raises(ValueError):
        ts.TotalSegmentatorProvider.ts_device(DeviceKind.CUDA, False)  # never a silent CPU fallback


@pytest.mark.parametrize("kwargs, code", [
    ({}, None),
    ({"structure": "not_a_class"}, ai_provider.REQUEST_STRUCTURE_UNKNOWN),
    ({"mode": "fastest"}, ai_provider.REQUEST_MODE_UNSUPPORTED),
    ({"acq": "CORONAL"}, ai_provider.REQUEST_ORIENTATION_UNKNOWN),
    ({"iop": None}, ai_provider.REQUEST_ORIENTATION_UNKNOWN),
    ({"device": DeviceKind.CUDA}, ai_provider.REQUEST_DEVICE_UNSUPPORTED),
])
def test_validate_request(tmp_path, kwargs, code):
    assert _provider(tmp_path)[0].validate_request(_request(**kwargs)) == code


def test_prompts_are_not_accepted(tmp_path):
    prompts = AIPromptSet()
    prompts.add_point((1.0, 1.0, 1.0), SPACING, SHAPE, True)
    assert _provider(tmp_path)[0].validate_request(_request(prompts=prompts)) == \
        ai_provider.REQUEST_PROMPT_UNSUPPORTED


# ------------------------------------------------------------------ inference
@pytest.mark.parametrize("structure, value", [("spleen", 101), ("kidney_right", 102), ("liver", 105)])
def test_infer_returns_exactly_the_selected_class_on_the_native_grid(tmp_path, structure, value):
    provider, calls = _provider(tmp_path)
    result = _infer(provider, _request(structure=structure))
    assert result.mask.shape == SHAPE and result.mask.dtype == bool
    assert np.array_equal(result.mask, _volume() == value)
    [call] = calls["ts"]
    assert call["roi_subset"] == [structure] and call["task"] == "total" and call["output"] is None
    assert call["input_type"] == "Nifti1Image"  # in memory - no temp NIfTI written by the plugin
    assert call["device"] == "cpu" and call["fast"] is False and call["quiet"] is True and call["ml"] is True
    assert result.extra["label_id"] == {"spleen": 1, "kidney_right": 2, "liver": 5}[structure]
    assert result.extra["foreground_voxels"] == int((_volume() == value).sum())
    assert result.device_used == DeviceKind.CPU


def test_fast_mode_and_gpu_are_passed_only_when_chosen(tmp_path):
    provider, calls = _provider(tmp_path, cuda=True)
    _infer(provider, _request(mode="fast", device=DeviceKind.CUDA))
    assert calls["ts"][0]["fast"] is True and calls["ts"][0]["device"] == "gpu"


def test_missing_class_in_output_gives_empty_mask(tmp_path):
    provider, _ = _provider(tmp_path)
    request = AIInferenceRequest(volume=read_only_volume(np.zeros(SHAPE, np.int16), SPACING),
                                 options=_request().options)
    assert not _infer(provider, request).mask.any()


def test_run_with_all_weights_present_succeeds(tmp_path):
    """Regression (30/09/2026): TotalSegmentator calls its download function
    on every run; the first guard always raised there, so every real run
    would have failed although all weights were on disk."""
    provider, calls = _provider(tmp_path)
    result = _infer(provider, _request())
    assert result.mask.any() and calls["download"] == 0


def test_missing_weights_during_the_run_raise_and_never_download(tmp_path):
    provider, calls = _provider(tmp_path)
    api = provider._modules["totalsegmentator.python_api"]
    original_download, original_usage = api.download_pretrained_weights, api.send_usage_stats
    (tmp_path / "weights" / WEIGHT_FOLDERS[298]).rmdir()  # e.g. deleted after the probe
    with pytest.raises(ts.WeightsNotReady):
        _infer(provider, _request())
    assert calls["download"] == 0  # the real download function was never reached
    assert api.download_pretrained_weights is original_download and api.send_usage_stats is original_usage


@pytest.mark.parametrize("missing, modes", [
    ((), ("standard", "fast")),
    ((297,), ("standard",)),  # fast model absent
    ((293,), ("fast",)),  # one standard part absent
    ((298,), None),  # the crop model every roi_subset run needs
])
def test_modes_offered_only_with_their_weights(tmp_path, missing, modes):
    info = _provider(tmp_path, missing=missing)[0].probe()
    if modes is None:
        assert not info.available and info.unavailable_reason.startswith(ai_provider.REASON_WEIGHTS)
        assert "298" in info.unavailable_reason
    else:
        assert info.available and info.parameter_choices[ai_provider.OPTION_MODE] == modes


def test_usage_stats_not_sent(tmp_path):
    provider, calls = _provider(tmp_path)
    _infer(provider, _request())
    assert calls["usage"] == 0


def test_output_grid_mismatch_is_a_clean_failure(tmp_path):
    provider, _ = _provider(tmp_path, bad_affine=True)
    with pytest.raises(ts.OutputGridMismatch):
        _infer(provider, _request())


def test_provider_failure_through_job_controller(tmp_path):
    provider, _ = _provider(tmp_path, fail=True)
    dispatch = QueueDispatch()
    ctl = jc.AIInferenceJobController(dispatch=dispatch)
    events = []
    ctl.listener = lambda e, j, p: events.append((e, p))
    assert ctl.start(provider, _request()) is not None
    assert ctl.wait(10)
    dispatch.pump()
    assert ctl.state == jc.AIJobState.FAILED
    stages = [p[1] for e, p in events if e == jc.EVENT_PROGRESS]
    assert stages == [ai_provider.STAGE_PREPARING, ai_provider.STAGE_RUNNING]
    assert all(p[0] is None for e, p in events if e == jc.EVENT_PROGRESS)  # no invented percentage


def test_close_releases_cuda_cache(tmp_path):
    provider, calls = _provider(tmp_path, cuda=True)
    provider.close()
    provider.close()
    assert calls["empty_cache"] == 2


def test_module_import_is_light_and_touches_no_project():
    import ast
    import inspect as _inspect

    tree = ast.parse(_inspect.getsource(ts))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"torch", "totalsegmentator", "nnunetv2", "nibabel", "invesalius", "wx", "vtkmodules"}


def test_real_environment_probe_is_truthful():
    """Whatever this machine has, probe() must not raise and must say why."""
    import importlib.util

    info = ts.TotalSegmentatorProvider().probe()
    if importlib.util.find_spec("totalsegmentator") is None:
        assert not info.available and info.unavailable_reason.startswith(ai_provider.REASON_PACKAGE_MISSING)
    else:
        assert info.available or info.unavailable_reason.split(":")[0] in (
            ai_provider.REASON_DEPENDENCY, ai_provider.REASON_API, ai_provider.REASON_WEIGHTS)


# ------------------------------------------------------------------ real frame, end to end
@pytest.fixture
def frame_env(real_slice_and_project_singleton, monkeypatch, tmp_path):
    import wx
    from invesalius.pubsub import pub as Publisher

    from plugins.roi_viewer.gui.roi_panel import ROIViewerPanel
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY
    from plugins.roi_viewer.interface.project_interface import ProjectInterface

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    proj.mask_dict, proj.image_versions, proj.surface_dict = {}, [], {}
    monkeypatch.setattr(proj, "patient_orientation", list(IOP_0051), raising=False)
    monkeypatch.setattr(proj, "original_orientation", 1, raising=False)  # const.AXIAL
    s.current_mask = None
    s.matrix = _volume()
    s._spacing = SPACING
    ProjectInterface()._refresh_project_data()
    s.to_show_aux = ""
    s.aux_matrices.pop(PREVIEW_AUX_KEY, None)
    for buffer in s.buffer_slices.values():
        buffer.index = -1
        buffer.discard_mask()
        buffer.discard_vtk_mask()
    Publisher.sendMessage("Create new mask", mask_name="Base", thresh=(100, 200), colour=(1.0, 0.0, 0.0))
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.YES)

    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.segmentation_panel
    panel.cb_enable_ai.SetValue(True)
    panel._on_enable_ai_toggle(None)
    block = threading.Event()
    block.set()
    modules, calls = fake_modules(tmp_path, block=block)
    from plugins.roi_viewer.core.ai.registry import AIProviderRegistry

    panel._ai_registry = AIProviderRegistry()
    panel._ai_registry.register(ts.TotalSegmentatorProvider(modules=modules, version="2.x-fake"))
    panel._ai_registry.probe_all()
    panel._refresh_ai_models()
    panel._update_ai_controls()
    dispatch = QueueDispatch()
    panel._ai_jobs._dispatch = dispatch
    yield types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, calls=calls, dispatch=dispatch,
                                block=block, aux_key=PREVIEW_AUX_KEY)
    frame.Destroy()
    top.Destroy()
    # leave the shared session Project/Slice empty for later tests
    proj.mask_dict = {}
    s.current_mask = None


def _run(e, structure="spleen"):
    e.panel.combo_ai_structure.SetValue(structure)
    e.panel._on_ai_run(None)
    assert e.panel._ai_jobs.wait(10)
    e.dispatch.pump()


def test_ui_for_totalsegmentator(frame_env):
    p = frame_env.panel
    assert p.choice_ai_model.GetStrings() == ["TotalSegmentator"]
    assert p.combo_ai_structure.GetStrings() == ["spleen", "kidney_right", "liver"]
    assert p.combo_ai_structure.IsEnabled() and p.choice_ai_mode.IsEnabled()
    assert p.choice_ai_mode.GetStrings() == ["Chính xác tiêu chuẩn", "Nhanh / ít bộ nhớ hơn"]
    for w in (p.btn_ai_pick_point, p.btn_ai_cursor_point, p.btn_ai_corner1, p.btn_ai_corner2, p.rb_ai_positive):
        assert not w.IsEnabled()  # no fake prompts for an automatic model
    assert not p._ai_sizer.IsShown(p._ai_prompt_sizer)  # ...and not even shown
    assert p._ai_sizer.IsShown(p._ai_structure_row) and p._ai_sizer.IsShown(p._ai_mode_row)
    assert p.btn_ai_run.IsEnabled()


def test_structure_must_be_chosen_from_the_list(frame_env):
    frame_env.panel.combo_ai_structure.SetValue("spl")
    frame_env.panel._on_ai_run(None)
    assert frame_env.calls["ts"] == []
    assert frame_env.panel.lbl_ai_status.GetLabel() == "Hãy chọn một cấu trúc trong danh sách."


def test_end_to_end_preview_e4_accept(frame_env):
    e = frame_env
    masks = len(e.proj.mask_dict)
    _run(e, "kidney_right")
    pm = e.panel.preview_mgr
    expected = _volume() == 102
    assert pm.state == "PREVIEW_READY" and pm.preview_kind == "ai"
    assert np.array_equal(np.asarray(pm.preview_array) > 0, expected)
    assert len(e.proj.mask_dict) == masks  # no Project mask before Accept
    assert e.s.aux_matrices[e.aux_key] is pm.preview_array  # the E2 overlay
    assert e.panel._select_preview_3d_source()[2] == "ai_preview"  # the E4 source
    assert pm.ai_metadata["structure"] == "kidney_right"
    assert e.calls["ts"][0]["roi_subset"] == ["kidney_right"]
    assert e.panel.lbl_ai_status.GetLabel().startswith("Đã hoàn thành trong")
    e.panel._on_preview_accept(None)
    e.panel._on_preview_accept(None)
    assert len(e.proj.mask_dict) == masks + 1
    mask = e.s.current_mask
    assert mask.name == "AI - kidney_right"
    assert np.array_equal(np.asarray(mask.matrix[1:, 1:, 1:]) > 127, expected)
    assert len(e.calls["ts"]) == 1  # TotalSegmentator was not run again


def test_cancel_is_reported_truthfully(frame_env):
    e = frame_env
    e.block.clear()
    e.panel.combo_ai_structure.SetValue("spleen")
    e.panel._on_ai_run(None)
    e.panel._on_ai_cancel(None)
    assert e.panel.lbl_ai_status.GetLabel() == (
        "Đã yêu cầu hủy - mô hình đang chạy sẽ tự kết thúc ở chế độ nền, kết quả sẽ bị bỏ qua.")
    e.block.set()
    assert e.panel._ai_jobs.wait(10)
    e.dispatch.pump()
    assert e.panel.preview_mgr.state == "IDLE" and e.aux_key not in e.s.aux_matrices
    assert e.panel._ai_jobs.discarded_results == 1


def test_stage_texts_without_percent(frame_env):
    e = frame_env
    labels = []
    original = e.panel.lbl_ai_status.SetLabel
    e.panel.lbl_ai_status.SetLabel = lambda text: (labels.append(text), original(text))
    try:
        _run(e)
    finally:
        del e.panel.lbl_ai_status.SetLabel
    assert "Đang chuẩn bị dữ liệu…" in labels and "Đang chạy TotalSegmentator…" in labels
    assert "Đang ánh xạ kết quả…" in labels
    assert not any("%" in t for t in labels)


def test_non_axial_or_unknown_orientation_is_refused(frame_env, monkeypatch):
    monkeypatch.setattr(frame_env.proj, "patient_orientation", None, raising=False)
    frame_env.panel.combo_ai_structure.SetValue("spleen")
    frame_env.panel._on_ai_run(None)
    assert frame_env.calls["ts"] == []
    assert frame_env.panel.lbl_ai_status.GetLabel() == (
        "Không xác định được hướng bệnh nhân của khối ảnh - hiện chỉ hỗ trợ chuỗi DICOM lát ngang.")
