# --------------------------------------------------------------------------
# E6 inference job controller - at most ONE inference exists at a time.
#
# * The provider runs on a daemon worker thread. The worker never touches
#   the GUI or this object's state: it hands progress and its outcome to
#   `dispatch` (wx.CallAfter in the plugin), so every state change and
#   every listener call happens on the GUI thread.
# * job_id is the generation guard (same pattern as E2/E4): cancel(),
#   a new run and shutdown() move it on, and a result arriving for an old
#   job_id is discarded - never shown.
# * cancel() sets the provider's cancel_event and invalidates the job; it
#   does not kill the thread (Python threads cannot be killed safely). The
#   state stays CANCELLING until the old worker returns, and no new job can
#   start meanwhile, so two full-volume inferences never run at once and
#   nothing is queued.
# --------------------------------------------------------------------------
import threading
from typing import Callable, Optional


class AIJobState:
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    RESULT_READY = "RESULT_READY"
    FAILED = "FAILED"


# Listener events: listener(event, job_id, payload)
EVENT_STATE = "state"
EVENT_PROGRESS = "progress"
EVENT_RESULT = "result"
EVENT_FAILED = "failed"

REQUEST_CHECK_FAILED = "request_check_failed"


class AIInferenceJobController:
    def __init__(self, dispatch: Callable):
        """dispatch(fn, *args) must run fn(*args) later on the GUI thread
        (wx.CallAfter in the plugin; a queue that tests drain)."""
        self._dispatch = dispatch
        self.state = AIJobState.IDLE
        self.job_id = 0
        self.progress = (0.0, "")
        self.result = None
        self.error = None  # request-check code (str) or the provider's exception
        self.discarded_results = 0
        self.listener: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._cancel_event: Optional[threading.Event] = None
        self._closed = False

    # ---------------------------------------------------------------
    def is_busy(self) -> bool:
        """True while a worker thread exists (running or being cancelled)."""
        return self._thread is not None

    def start(self, provider, request) -> Optional[int]:
        """Validate the request and start one worker. Returns the job id, or
        None if refused (busy/closed) or the request check failed - then
        state is FAILED and `error` holds the provider's check code."""
        if self._closed or self.is_busy():
            return None
        self.job_id += 1
        job = self.job_id
        self.result = None
        self.error = None
        self.progress = (0.0, "")
        self._set_state(AIJobState.PREPARING)
        try:
            code = provider.validate_request(request)
        except Exception as e:
            print(f"ROI Viewer: AI request check failed - {e}")
            code = REQUEST_CHECK_FAILED
        if code is not None:
            self.error = code
            self._set_state(AIJobState.FAILED)
            self._notify(EVENT_FAILED, job, code)
            return None

        cancel_event = threading.Event()
        dispatch = self._dispatch

        def progress(fraction, message=""):
            dispatch(self._on_progress, job, float(fraction), str(message))

        def worker():
            try:
                outcome = ("ok", provider.infer(request, progress, cancel_event))
            except Exception as e:  # provider failure must never escape the thread
                outcome = ("error", e)
            dispatch(self._on_finished, job, outcome)

        self._cancel_event = cancel_event
        self._thread = threading.Thread(target=worker, name=f"roi-viewer-ai-{job}", daemon=True)
        self._set_state(AIJobState.RUNNING)
        self._thread.start()
        return job

    def cancel(self) -> bool:
        """Invalidate the current job. Returns True if a worker was running
        (its late result will be discarded)."""
        if self._thread is None:
            if self.state != AIJobState.IDLE:
                self.result = None
                self._set_state(AIJobState.IDLE)
            return False
        if self._cancel_event is not None:
            self._cancel_event.set()
        self.job_id += 1
        self.result = None
        self._set_state(AIJobState.CANCELLING)
        return True

    def consume_result(self):
        """Take the RESULT_READY result (the caller moves it into the E2
        preview) and return to IDLE."""
        result, self.result = self.result, None
        if self.state in (AIJobState.RESULT_READY, AIJobState.FAILED):
            self._set_state(AIJobState.IDLE)
        return result

    def shutdown(self):
        """Plugin close / window destroy: cancel, then never call the
        listener again (the widgets it updates may be gone)."""
        self.listener = None
        self._closed = True
        self.cancel()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Test helper: join the worker thread (does not dispatch)."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    # --------------------------------------------------------------- GUI thread
    def _on_progress(self, job, fraction, message):
        if self._closed or job != self.job_id or self.state != AIJobState.RUNNING:
            return
        self.progress = (fraction, message)
        self._notify(EVENT_PROGRESS, job, self.progress)

    def _on_finished(self, job, outcome):
        self._thread = None
        self._cancel_event = None
        if self._closed:
            return
        if job != self.job_id:
            self.discarded_results += 1
            print(f"ROI Viewer: discarded stale AI result (job {job})")
            if self.state == AIJobState.CANCELLING:
                self._set_state(AIJobState.IDLE)
            return
        kind, payload = outcome
        if kind == "ok":
            self.result = payload
            self._set_state(AIJobState.RESULT_READY)
            self._notify(EVENT_RESULT, job, payload)
        else:
            print(f"ROI Viewer: AI inference failed - {payload!r}")
            self.error = payload
            self._set_state(AIJobState.FAILED)
            self._notify(EVENT_FAILED, job, payload)

    def _set_state(self, state):
        self.state = state
        self._notify(EVENT_STATE, self.job_id, state)

    def _notify(self, event, job, payload):
        if self.listener is not None and not self._closed:
            try:
                self.listener(event, job, payload)
            except Exception as e:
                print(f"ROI Viewer: AI listener failed on '{event}' - {e}")
