# --------------------------------------------------------------------------
# InteractiveAIRuntimeClient - the host's only handle on the external AI
# runtime. It knows subprocess, the JSON Lines protocol, .npy files and
# provider metadata; it never imports torch, sam2 or a model.
#
# One request at a time (self._io). Lifecycle:
#   ensure_started()  lazily start the worker + HELLO (protocol check)
#   probe()           PROBE: provider name/version/capabilities/devices
#   ensure_volume()   LOAD_VOLUME once per volume fingerprint (the worker
#                     keeps it, and its model state, resident)
#   predict()         PREDICT -> candidate .npy -> validated array
#   release_volume()  RELEASE_VOLUME + delete volume.npy
#   close()           SHUTDOWN (kill after timeout) + delete the session dir
# A worker that died (crash, kill after cancel/timeout) is restarted by the
# next ensure_started(); its volume must then be loaded again.
# --------------------------------------------------------------------------
import itertools
import threading
import time
from typing import Callable, Optional

import numpy as np

from . import protocol, volume_cache
from .config import InteractiveAIConfig
from .errors import RuntimeFailure, WorkerExited
from .runtime_process import RuntimeProcess


class InteractiveAIRuntimeClient:
    def __init__(self, config: InteractiveAIConfig, temp_root: Optional[str] = None, process_factory=None):
        self.config = config
        self.session = volume_cache.SessionDirectory(temp_root)
        self._process_factory = process_factory or (lambda cmd: RuntimeProcess(list(cmd)))
        self._process: Optional[RuntimeProcess] = None
        self._ids = itertools.count(1)
        self._io = threading.Lock()
        self._closed = False
        self.hello: Optional[dict] = None
        self.probe_info: Optional[dict] = None
        self.volume_id: Optional[str] = None
        self.volume_shape = None
        self.timings = {}
        self.starts = 0
        self.temp_root = temp_root
        self.cancel_grace_s = 10.0  # after CANCEL, kill the worker if it has not answered

    # ------------------------------------------------------------- helpers
    def _next_id(self) -> int:
        return next(self._ids)

    def _worker_path(self, path) -> str:
        return volume_cache.to_worker_path(path, self.config.path_style)

    def _call(self, command, timeout, generation_id=0, volume_id="", cancel_event=None, on_progress=None,
              **payload) -> dict:
        """Send one request and wait for its final response (caller holds
        self._io). Raises RuntimeFailure for an error response."""
        rid = self._next_id()
        process = self._process
        if process is None:
            raise WorkerExited("no worker")
        process.send(protocol.request(command, rid, generation_id, volume_id, **payload))

        def send_cancel():
            process.send(protocol.request(protocol.CANCEL, self._next_id(), generation_id, volume_id,
                                          target_request_id=rid))

        message = process.receive(rid, timeout, cancel_event=cancel_event, on_cancel=send_cancel,
                                  on_progress=on_progress, cancel_grace=self.cancel_grace_s)
        if message["status"] == protocol.STATUS_ERROR:
            raise RuntimeFailure(message["error_code"], message.get("message", ""))
        return message

    @property
    def worker_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    # ------------------------------------------------------------- lifecycle
    def ensure_started(self) -> dict:
        """Caller holds self._io."""
        if self._closed:
            raise RuntimeFailure(protocol.E_CANCELLED, "client closed")
        if self.worker_alive and self.hello is not None:
            return self.hello
        if self._process is not None:
            self._process.terminate()
        self.hello = None
        self.probe_info = None
        self.volume_id = None
        self.volume_shape = None
        volume_cache.cleanup_abandoned(self.temp_root)
        self.session.create()
        t0 = time.perf_counter()
        self._process = self._process_factory(self.config.runtime_command)
        self._process.start()
        self.starts += 1
        try:
            hello = self._call(protocol.HELLO, self.config.start_timeout_s,
                               provider=self.config.provider, provider_config=self.config.provider_config)
        except RuntimeFailure:
            self._process.terminate()
            raise
        if hello.get("protocol_name") != protocol.PROTOCOL_NAME or hello.get("protocol") != protocol.PROTOCOL_VERSION:
            self._process.terminate()
            raise RuntimeFailure(protocol.E_PROTOCOL_VERSION,
                                 f"worker speaks {hello.get('protocol_name')!r} v{hello.get('protocol')!r}")
        self.timings["worker_start_s"] = time.perf_counter() - t0
        self.hello = hello
        return hello

    def probe(self) -> dict:
        with self._io:
            self.ensure_started()
            t0 = time.perf_counter()
            info = self._call(protocol.PROBE, self.config.probe_timeout_s)
            self.timings["probe_s"] = time.perf_counter() - t0
            self.probe_info = info
            return info

    def ensure_volume(self, array, spacing_xyz, orientation=None, device="auto", cancel_event=None) -> str:
        """Caller holds self._io. Returns the volume_id loaded in the worker."""
        volume_id = volume_cache.fingerprint(array, spacing_xyz, orientation)
        if self.volume_id == volume_id and self.worker_alive:
            return volume_id
        if self.volume_id is not None and self.worker_alive:
            try:
                self._call(protocol.RELEASE_VOLUME, 60, volume_id=self.volume_id)
            except RuntimeFailure as e:
                print(f"ROI Viewer: interactive AI release of the old volume failed - {e}")
        self.volume_id = None
        t0 = time.perf_counter()
        path, metadata = volume_cache.write_volume(self.session, array, spacing_xyz, orientation, volume_id)
        self.timings["volume_write_s"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        self._call(protocol.LOAD_VOLUME, self.config.load_timeout_s, volume_id=volume_id, cancel_event=cancel_event,
                   volume_path=self._worker_path(path), metadata=metadata, device=device)
        self.timings["volume_load_s"] = time.perf_counter() - t0
        self.volume_id = volume_id
        self.volume_shape = tuple(int(n) for n in np.asarray(array).shape)
        return volume_id

    def predict(self, array, spacing_xyz, prompts: dict, generation_id: int, device="auto", orientation=None,
                options: Optional[dict] = None, cancel_event=None, on_progress: Optional[Callable] = None):
        """Returns (candidate uint8 array on the native grid, response).
        The candidate is validated here (shape, dtype, binary); anything
        else raises RuntimeFailure(E_INVALID_OUTPUT)."""
        with self._io:
            self.ensure_started()
            if self.probe_info is None:
                self.probe_info = self._call(protocol.PROBE, self.config.probe_timeout_s)
            volume_id = self.ensure_volume(array, spacing_xyz, orientation, device, cancel_event)
            shape = self.volume_shape
            prompts = protocol.check_prompts(prompts, shape)
            rid_name = f"candidate_{generation_id}_{int(time.time() * 1000)}.npy"
            out_path = self.session.file(rid_name)
            t0 = time.perf_counter()
            try:
                response = self._call(protocol.PREDICT, self.config.predict_timeout_s, generation_id=generation_id,
                                      volume_id=volume_id, cancel_event=cancel_event, on_progress=on_progress,
                                      prompts=prompts, device=device, options=dict(options or {}),
                                      output_path=self._worker_path(out_path))
                self.timings["predict_s"] = time.perf_counter() - t0
                if response.get("volume_id") != volume_id or response.get("generation_id") != generation_id:
                    raise RuntimeFailure(protocol.E_MALFORMED, "response is for another volume/generation")
                candidate = load_candidate(out_path, shape)
            finally:
                self.session.remove_file(rid_name)
            return candidate, response

    def release_volume(self) -> None:
        with self._io:
            if self.volume_id is not None and self.worker_alive:
                try:
                    self._call(protocol.RELEASE_VOLUME, 60, volume_id=self.volume_id)
                except RuntimeFailure as e:
                    print(f"ROI Viewer: interactive AI release failed - {e}")
            self.volume_id = None
            self.volume_shape = None
            self.session.remove_file(volume_cache.VOLUME_FILE)
            self.session.remove_file(volume_cache.METADATA_FILE)

    def kill(self) -> None:
        """Immediate, lock-free: kill the worker (e.g. project closed while
        it runs). The thread waiting on it gets WorkerExited."""
        process = self._process
        if process is not None:
            process.terminate()

    def close(self, timeout: float = 10.0) -> None:
        """SHUTDOWN (kill after timeout), delete temp data. Idempotent. If
        another thread is mid-request, the worker is killed instead of
        waiting for it."""
        self._closed = True
        acquired = self._io.acquire(timeout=0.5)
        try:
            process, self._process = self._process, None
            if process is not None:
                if acquired:
                    process.shutdown(self._next_id(), timeout)
                else:
                    process.terminate()
            self.hello = None
            self.probe_info = None
            self.volume_id = None
            self.volume_shape = None
            self.session.cleanup()
        finally:
            if acquired:
                self._io.release()

    def reopen(self) -> None:
        """Allow use again after close() (a new project)."""
        self._closed = False


def load_candidate(path, shape_zyx) -> np.ndarray:
    """Read the worker's candidate file safely: .npy without pickle, exact
    native shape, binary values. Returns a uint8 0/1 array."""
    try:
        arr = np.load(str(path), allow_pickle=False)
    except (OSError, ValueError) as e:
        raise RuntimeFailure(protocol.E_INVALID_OUTPUT, f"cannot read candidate: {e}") from None
    if tuple(arr.shape) != tuple(shape_zyx):
        raise RuntimeFailure(protocol.E_INVALID_OUTPUT, f"candidate shape {arr.shape}, volume {tuple(shape_zyx)}")
    if arr.dtype == np.bool_:
        return arr.astype(np.uint8)
    if not np.issubdtype(arr.dtype, np.integer):
        raise RuntimeFailure(protocol.E_INVALID_OUTPUT, f"candidate dtype {arr.dtype} (bool/uint8 expected)")
    if arr.size and (int(arr.min()) < 0 or int(arr.max()) > 1):  # no full-size temporaries
        raise RuntimeFailure(protocol.E_INVALID_OUTPUT, "candidate values other than 0/1")
    return arr.astype(np.uint8, copy=False)
