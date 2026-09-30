# --------------------------------------------------------------------------
# E6 job controller (core/ai/job_controller.py): one real worker thread per
# job; QueueDispatch stands in for wx.CallAfter so the test thread plays the
# GUI thread and decides when marshalled calls run.
# --------------------------------------------------------------------------
import threading

import numpy as np
import pytest

from ai_stub_provider import QueueDispatch, StubAIProvider
from plugins.roi_viewer.core.ai import job_controller as jc
from plugins.roi_viewer.core.ai import provider as ai_provider
from plugins.roi_viewer.core.ai.prompts import AIPromptSet
from plugins.roi_viewer.core.ai.types import AIInferenceRequest, read_only_volume

S = jc.AIJobState


def _request():
    prompts = AIPromptSet()
    prompts.add_point((3.0, 3.0, 2.0), (1.0, 1.0, 1.0), (5, 8, 8), positive=True)
    return AIInferenceRequest(volume=read_only_volume(np.zeros((5, 8, 8), np.int16), (1.0, 1.0, 1.0)),
                              prompts=prompts.snapshot())


@pytest.fixture
def ctl():
    dispatch = QueueDispatch()
    controller = jc.AIInferenceJobController(dispatch=dispatch)
    events = []
    main = threading.get_ident()

    def listener(event, job, payload):
        assert threading.get_ident() == main  # never called from the worker thread
        events.append((event, job, payload))

    controller.listener = listener
    controller.events = events
    controller.pump = dispatch.pump
    return controller


def _finish(controller):
    assert controller.wait(10)
    controller.pump()


def _events(controller, kind):
    return [e for e in controller.events if e[0] == kind]


def test_initial_idle(ctl):
    assert ctl.state == S.IDLE and ctl.job_id == 0 and not ctl.is_busy()


def test_run_delivers_result_on_gui_thread_only(ctl):
    stub = StubAIProvider()
    job = ctl.start(stub, _request())
    assert job == 1 and ctl.state == S.RUNNING and ctl.is_busy()
    assert ctl.wait(10)
    assert _events(ctl, jc.EVENT_RESULT) == []  # nothing delivered until the GUI thread runs it
    ctl.pump()
    assert ctl.state == S.RESULT_READY and not ctl.is_busy()
    [(_, rjob, result)] = _events(ctl, jc.EVENT_RESULT)
    assert rjob == job and result.mask.dtype == bool
    assert ctl.consume_result() is result and ctl.state == S.IDLE
    states = [p for e, _, p in ctl.events if e == jc.EVENT_STATE]
    assert states == [S.PREPARING, S.RUNNING, S.RESULT_READY, S.IDLE]


def test_progress_reported(ctl):
    ctl.start(StubAIProvider(), _request())
    _finish(ctl)
    progress = [p for e, _, p in ctl.events if e == jc.EVENT_PROGRESS]
    assert progress[0][0] == 0.25 and progress[-1][0] == 1.0


def test_one_job_maximum(ctl):
    stub = StubAIProvider(block=True)
    assert ctl.start(stub, _request()) == 1
    assert ctl.start(stub, _request()) is None  # refused, not queued
    assert ctl.start(StubAIProvider(provider_id="other"), _request()) is None
    assert stub.calls <= 1
    stub.release.set()
    _finish(ctl)
    assert stub.calls == 1


def test_generation_increments(ctl):
    stub = StubAIProvider()
    first = ctl.start(stub, _request())
    _finish(ctl)
    ctl.consume_result()
    second = ctl.start(stub, _request())
    _finish(ctl)
    assert second == first + 1


def test_cancel_discards_late_result(ctl):
    stub = StubAIProvider(block=True)
    job = ctl.start(stub, _request())
    assert ctl.cancel() is True
    assert ctl.state == S.CANCELLING and ctl.job_id == job + 1
    assert ctl.start(stub, _request()) is None  # old worker still alive - nothing new starts
    stub.release.set()
    _finish(ctl)
    assert stub.seen_cancel is True  # the provider saw the cancel request
    assert _events(ctl, jc.EVENT_RESULT) == []
    assert ctl.discarded_results == 1
    assert ctl.state == S.IDLE and ctl.result is None


def test_stale_result_never_replaces_new_job(ctl):
    old = StubAIProvider(provider_id="old", block=True)
    ctl.start(old, _request())
    ctl.cancel()
    old.release.set()
    _finish(ctl)
    new = StubAIProvider(provider_id="new")
    job = ctl.start(new, _request())
    _finish(ctl)
    [(_, rjob, _result)] = _events(ctl, jc.EVENT_RESULT)
    assert rjob == job and new.calls == 1


def test_project_close_cancels(ctl):
    stub = StubAIProvider(block=True)
    ctl.start(stub, _request())
    ctl.cancel()  # what SegmentationPanel.reset_ai_session() does
    stub.release.set()
    _finish(ctl)
    assert _events(ctl, jc.EVENT_RESULT) == [] and ctl.state == S.IDLE


def test_plugin_close_shutdown_drops_everything(ctl):
    stub = StubAIProvider(block=True)
    ctl.start(stub, _request())
    before = len(ctl.events)
    ctl.shutdown()
    stub.release.set()
    _finish(ctl)
    assert len(ctl.events) == before  # no listener call after shutdown
    assert ctl.start(StubAIProvider(), _request()) is None  # closed for good


def test_provider_failure(ctl):
    ctl.start(StubAIProvider(fail=True), _request())
    _finish(ctl)
    assert ctl.state == S.FAILED
    [(_, _, error)] = _events(ctl, jc.EVENT_FAILED)
    assert isinstance(error, RuntimeError)
    ctl.consume_result()
    assert ctl.state == S.IDLE


def test_request_check_failure_starts_no_thread(ctl):
    before = {t.name for t in threading.enumerate()}
    empty = AIInferenceRequest(volume=read_only_volume(np.zeros((5, 8, 8), np.int16), (1.0, 1.0, 1.0)))
    assert ctl.start(StubAIProvider(), empty) is None
    assert ctl.state == S.FAILED and ctl.error == ai_provider.REQUEST_NEEDS_PROMPT
    assert not ctl.is_busy()
    assert not any(n.startswith("roi-viewer-ai") for n in {t.name for t in threading.enumerate()} - before)


def test_cancel_when_idle_is_harmless(ctl):
    assert ctl.cancel() is False
    assert ctl.state == S.IDLE and ctl.job_id == 0
