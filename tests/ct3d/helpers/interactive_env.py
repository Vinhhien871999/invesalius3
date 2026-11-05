# --------------------------------------------------------------------------
# Shared environment for the interactive / direct-interaction panel tests:
# the REAL ROIViewerPanel on a real Slice()/Project(), the REAL MedSAM2
# external provider module loaded by the registry, configured (read-only
# JSON via the environment variable) to start the deterministic
# FakeInteractiveAIWorker. Protocol fixture only - not model evidence.
# --------------------------------------------------------------------------
import json
import pathlib
import sys
import time
import types

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
FAKE_WORKER = str(ROOT / "tests" / "ct3d" / "helpers" / "fake_interactive_ai_worker.py")
SHAPE = (8, 20, 24)  # (z, y, x)
SPACING = (0.5, 0.8, 2.0)  # (x, y, z)


def world(z, y, x):
    return (x * SPACING[0], y * SPACING[1], z * SPACING[2])


def ball(center, radius, shape=SHAPE):
    zz, yy, xx = np.ogrid[:shape[0], :shape[1], :shape[2]]
    return (zz - center[0]) ** 2 + (yy - center[1]) ** 2 + (xx - center[2]) ** 2 <= radius ** 2


def write_config(path, **provider_config):
    path.write_text(json.dumps({
        "enabled": True, "provider": "medsam2", "runtime_command": [sys.executable, FAKE_WORKER],
        "provider_config": provider_config, "predict_timeout_s": 60,
    }), encoding="utf-8")


def owned_dirs(root):
    return [p for p in pathlib.Path(root).iterdir() if p.name.startswith("roiviewer-iai-")]


def make_env(real_slice_and_project_singleton, monkeypatch, tmp_path, modules=(".providers.medsam2_external_provider",)):
    """Returns (env, teardown)."""
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
    volume = np.full(SHAPE, -50, dtype=np.int16)
    volume[2:6, 5:15, 5:19] = 60
    s.matrix = volume
    s._spacing = SPACING
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
    monkeypatch.setattr(ai_registry, "KNOWN_PROVIDER_MODULES", tuple(modules))
    top = wx.Frame(None)
    frame = ROIViewerPanel(top)
    panel = frame.segmentation_panel
    env = types.SimpleNamespace(s=s, proj=proj, frame=frame, panel=panel, base=base, config=config_path,
                                temp_root=temp_root, base_before=np.asarray(base.matrix).copy(),
                                aux_key=PREVIEW_AUX_KEY)

    def teardown():
        try:
            panel.shutdown_ai()
        finally:
            frame.Destroy()
            top.Destroy()
            proj.mask_dict, proj.surface_dict = {}, {}
            s.current_mask = None

    return env, teardown


def enable(env):
    from ai_stub_provider import QueueDispatch

    env.panel.cb_enable_ai.SetValue(True)
    env.panel._on_enable_ai_toggle(None)
    env.dispatch = QueueDispatch()
    env.panel._ai_jobs._dispatch = env.dispatch


def check(env):
    import wx

    env.panel._on_ai_check_environment(None)
    deadline = time.time() + 60
    while env.panel._ai_env_checking and time.time() < deadline:
        wx.GetApp().Yield(True)
        time.sleep(0.02)
    assert not env.panel._ai_env_checking


def provider(env):
    return env.panel._ai_registry.get("medsam2")


def drain(env, timeout=60):
    """Run every job the panel starts (slice -> volume chains included)
    until the AI is idle: join the worker thread, deliver its result on
    this (GUI) thread, repeat."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        jobs = env.panel._ai_jobs
        if not jobs.is_busy() and not env.dispatch.pump():
            return
        jobs.wait(timeout)
        env.dispatch.pump()
    raise AssertionError("AI jobs did not settle")


def logical(mask):
    return np.asarray(mask.matrix[1:, 1:, 1:]) > 127
