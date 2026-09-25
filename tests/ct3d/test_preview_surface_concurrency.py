# --------------------------------------------------------------------------
# E5 Section 5 hardening tests: bounded E4 live-preview worker
# concurrency ("max 1 running build + max 1 latest pending request").
#
# Exercises the real, unmodified SegmentationPanel._trigger_preview_3d_
# rebuild()/_finish_preview_3d_build() methods (bound via the same
# descriptor-protocol technique test_preview_surface_integration.py's
# own _panel_like() already established) against a stubbed
# _run_preview_3d_rebuild() that only RECORDS calls instead of actually
# spawning a real threading.Thread - this makes "is a build currently
# running" a fact the test fully controls (via when it calls
# _finish_preview_3d_build() to simulate that build's real completion),
# rather than depending on real wall-clock thread-timing (which would
# be flaky). This is the real gating logic under test, not a
# reimplementation of it.
# --------------------------------------------------------------------------
import types

from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel


def _panel_like():
    fake = types.SimpleNamespace()
    fake.run_calls = []
    fake._e4_build_busy = False
    fake._e4_pending_reason = None
    fake._e4_enabled = lambda: True
    fake._run_preview_3d_rebuild = lambda reason: fake.run_calls.append(reason)
    fake._trigger_preview_3d_rebuild = SegmentationPanel._trigger_preview_3d_rebuild.__get__(fake)
    fake._finish_preview_3d_build = SegmentationPanel._finish_preview_3d_build.__get__(fake)
    return fake


def test_only_one_worker_running():
    panel = _panel_like()
    panel._trigger_preview_3d_rebuild("edit1")
    assert panel.run_calls == ["edit1"]
    assert panel._e4_build_busy is True

    # A second dirty-mark while the first build is still "running" must
    # NOT start a second real build.
    panel._trigger_preview_3d_rebuild("edit2")
    assert panel.run_calls == ["edit1"]
    assert panel._e4_pending_reason == "edit2"


def test_dirty_while_running_coalesces():
    panel = _panel_like()
    panel._trigger_preview_3d_rebuild("a")
    panel._trigger_preview_3d_rebuild("b")
    panel._trigger_preview_3d_rebuild("c")

    # Still exactly one real build started - "b" and "c" coalesced into
    # a single remembered "latest" reason, not three separate builds.
    assert panel.run_calls == ["a"]
    assert panel._e4_pending_reason == "c"


def test_latest_pending_runs_after_current():
    panel = _panel_like()
    panel._trigger_preview_3d_rebuild("a")
    panel._trigger_preview_3d_rebuild("b")
    assert panel.run_calls == ["a"]

    # Simulate "a" finishing (what _on_preview_3d_built()/the worker's
    # own failure branch always does via wx.CallAfter in real code).
    panel._finish_preview_3d_build()

    # Exactly one more build starts, for the latest coalesced reason.
    assert panel.run_calls == ["a", "b"]
    assert panel._e4_pending_reason is None
    assert panel._e4_build_busy is True


def test_pending_cancelled_on_disable():
    panel = _panel_like()
    panel._trigger_preview_3d_rebuild("a")
    panel._trigger_preview_3d_rebuild("b")
    assert panel._e4_pending_reason == "b"

    # Real _on_enable_live_3d_preview_toggle()'s disable branch clears
    # the pending reason immediately AND _e4_enabled() would report
    # False from then on (checkbox now unchecked).
    panel._e4_pending_reason = None
    panel._e4_enabled = lambda: False

    panel._finish_preview_3d_build()

    # "b" never runs - preview was turned off before "a" finished.
    assert panel.run_calls == ["a"]
    assert panel._e4_build_busy is False


def test_pending_cancelled_on_project_close():
    panel = _panel_like()
    panel._trigger_preview_3d_rebuild("a")
    panel._trigger_preview_3d_rebuild("b")
    assert panel._e4_pending_reason == "b"

    # Real cancel_live_preview_3d() (called on project close/plugin
    # close) drops any coalesced pending request.
    panel._e4_pending_reason = None

    panel._finish_preview_3d_build()

    assert panel.run_calls == ["a"]
