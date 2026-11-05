#!/usr/bin/env python3
# --------------------------------------------------------------------------
# ROI Viewer interactive-AI worker - runs in its OWN Python environment
# (never InVesalius's). Started by the plugin as a persistent child
# process; speaks protocol.py (JSON Lines) on stdin / a private stdout.
#
#   python worker.py            (the provider is chosen by HELLO)
#
# Only numpy and the standard library are imported here. The provider
# module (providers/medsam2_provider.py) imports torch / sam2 when it is
# probed or used. Nothing is installed or downloaded by this program.
#
# Threads: a reader thread takes every stdin line. CANCEL is handled there
# at once (it marks the target request cancelled; the provider checks
# between slices); every other request is queued for the main thread,
# which runs one request at a time. When stdin closes (the host exited or
# killed its end), the worker exits - even in the middle of an inference.
# --------------------------------------------------------------------------
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import protocol  # noqa: E402  (this directory's copy; stdlib only)

WORKER_VERSION = "1"
NEWLINE = b"\n"


class WorkerError(Exception):
    """Raised by providers: code is a protocol.E_* error code."""

    def __init__(self, code, message=""):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def _default_factories():
    def medsam2(config):
        from providers.medsam2_provider import MedSAM2Provider

        return MedSAM2Provider(config)

    return {"medsam2": medsam2}


class Worker:
    def __init__(self, out_stream, factories=None):
        self._out = out_stream
        self._out_lock = threading.Lock()
        self._factories = dict(factories or _default_factories())
        self.provider = None
        self.provider_name = ""
        self.volume = None
        self.volume_meta = None
        self.volume_id = ""
        self.prompts = {"points": [], "box": None}
        self._cancelled = set()
        self._cancel_lock = threading.Lock()
        self.running = True

    # ------------------------------------------------------------- output
    def send(self, message):
        line = protocol.encode(message)
        with self._out_lock:
            self._out.write(line)
            self._out.flush()

    def is_cancelled(self, request_id) -> bool:
        with self._cancel_lock:
            return request_id in self._cancelled

    def mark_cancelled(self, request_id):
        with self._cancel_lock:
            self._cancelled.add(request_id)

    # ------------------------------------------------------------- dispatch
    def handle(self, req):
        command = req.get("command")
        handler = {
            protocol.HELLO: self.on_hello,
            protocol.PROBE: self.on_probe,
            protocol.LOAD_VOLUME: self.on_load_volume,
            protocol.SET_PROMPTS: self.on_set_prompts,
            protocol.CLEAR_PROMPTS: self.on_clear_prompts,
            protocol.PREDICT: self.on_predict,
            protocol.RELEASE_VOLUME: self.on_release_volume,
            protocol.SHUTDOWN: self.on_shutdown,
        }.get(command)
        if handler is None:
            self.send(protocol.response(req, protocol.STATUS_ERROR, protocol.E_UNKNOWN_COMMAND,
                                        f"unknown command {command!r}"))
            return
        try:
            payload = handler(req) or {}
            self.send(protocol.response(req, protocol.STATUS_OK, "", "", **payload))
        except WorkerError as e:
            self.send(protocol.response(req, protocol.STATUS_ERROR, e.code, e.message))
        except protocol.ProtocolError as e:
            self.send(protocol.response(req, protocol.STATUS_ERROR, protocol.E_BAD_REQUEST, str(e)))
        except MemoryError as e:
            self.send(protocol.response(req, protocol.STATUS_ERROR, protocol.E_INTERNAL, f"out of host memory: {e}"))
        except Exception as e:  # never let one request kill the worker
            traceback.print_exc(file=sys.stderr)
            code = protocol.E_CUDA_OOM if "out of memory" in str(e).lower() else protocol.E_INTERNAL
            self.send(protocol.response(req, protocol.STATUS_ERROR, code, f"{type(e).__name__}: {e}"))

    def _need_provider(self):
        if self.provider is None:
            raise WorkerError(protocol.E_BAD_REQUEST, "HELLO with a provider first")
        return self.provider

    def on_hello(self, req):
        name = req.get("provider")
        if name not in self._factories:
            raise WorkerError(protocol.E_BAD_REQUEST, f"unknown provider {name!r}; known: {sorted(self._factories)}")
        config = req.get("provider_config") or {}
        if not isinstance(config, dict):
            raise WorkerError(protocol.E_BAD_REQUEST, "provider_config must be an object")
        if self.provider is not None and self.provider_name != name:
            self.provider.close()
            self.provider = None
        if self.provider is None:
            self.provider = self._factories[name](config)
            self.provider_name = name
        return {"protocol_name": protocol.PROTOCOL_NAME, "protocol": protocol.PROTOCOL_VERSION,
                "worker_version": WORKER_VERSION, "python": sys.version.split()[0], "provider": name,
                "pid": os.getpid()}

    def on_probe(self, req):
        return {"provider_info": self._need_provider().probe()}

    def on_load_volume(self, req):
        import numpy as np

        provider = self._need_provider()
        path = req.get("volume_path")
        meta = req.get("metadata") or {}
        volume_id = req.get("volume_id")
        if not isinstance(path, str) or not volume_id:
            raise WorkerError(protocol.E_BAD_REQUEST, "volume_path and volume_id are required")
        t0 = time.perf_counter()
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        if list(array.shape) != list(meta.get("shape_zyx", [])) or array.dtype.str != meta.get("dtype"):
            raise WorkerError(protocol.E_VOLUME_MISMATCH,
                              f"file {array.shape} {array.dtype.str} != metadata {meta.get('shape_zyx')} "
                              f"{meta.get('dtype')}")
        array = np.array(array)  # own copy: the host may delete the file later
        self.release()
        details = provider.load_volume(array, meta, req.get("device", "auto")) or {}
        self.volume, self.volume_meta, self.volume_id = array, dict(meta), volume_id
        self.prompts = {"points": [], "box": None}
        return {"load_seconds": time.perf_counter() - t0, "details": details}

    def on_set_prompts(self, req):
        self._check_volume(req)
        self.prompts = protocol.check_prompts(req.get("prompts"), self.volume.shape)
        return {}

    def on_clear_prompts(self, req):
        self.prompts = {"points": [], "box": None}
        return {}

    def _check_volume(self, req):
        if self.volume is None:
            raise WorkerError(protocol.E_NO_VOLUME, "no volume loaded")
        if req.get("volume_id") != self.volume_id:
            raise WorkerError(protocol.E_VOLUME_MISMATCH, "request is for another volume")

    def on_predict(self, req):
        import numpy as np

        provider = self._need_provider()
        self._check_volume(req)
        prompts = req.get("prompts")
        prompts = self.prompts if prompts is None else protocol.check_prompts(prompts, self.volume.shape)
        if not prompts["points"] and prompts["box"] is None:
            raise WorkerError(protocol.E_NEEDS_PROMPT, "no prompt")
        out_path = req.get("output_path")
        if not isinstance(out_path, str):
            raise WorkerError(protocol.E_BAD_REQUEST, "output_path is required")
        rid = req["request_id"]

        def progress(stage, fraction=None):
            self.send(protocol.response(req, protocol.STATUS_PROGRESS, "", str(stage),
                                        fraction=None if fraction is None else float(fraction)))

        t0 = time.perf_counter()
        mask, details = provider.predict(self.volume, self.volume_meta, prompts, req.get("device", "auto"),
                                         req.get("options") or {}, lambda: self.is_cancelled(rid), progress)
        if self.is_cancelled(rid):
            raise WorkerError(protocol.E_CANCELLED, "cancelled")
        mask = np.asarray(mask)
        if mask.shape != self.volume.shape:
            raise WorkerError(protocol.E_INVALID_OUTPUT, f"provider returned {mask.shape}, volume {self.volume.shape}")
        mask = (mask > 0).astype(np.uint8)
        tmp = out_path + ".partial.npy"
        np.save(tmp, mask, allow_pickle=False)
        os.replace(tmp, out_path)
        voxels = int(mask.sum())
        bounds = None
        if voxels:
            idx = np.nonzero(mask)
            bounds = [[int(a.min()), int(a.max())] for a in idx]
        return {"predict_seconds": time.perf_counter() - t0, "voxels": voxels, "bounds_zyx": bounds,
                "details": details or {}}

    def release(self):
        if self.provider is not None and self.volume is not None:
            self.provider.release_volume()
        self.volume, self.volume_meta, self.volume_id = None, None, ""

    def on_release_volume(self, req):
        self.release()
        return {}

    def on_shutdown(self, req):
        self.running = False
        return {}

    def close(self):
        try:
            self.release()
            if self.provider is not None:
                self.provider.close()
        except Exception:
            traceback.print_exc(file=sys.stderr)


def _windows_pipe_peek(fd):
    """A function returning the bytes waiting on the pipe `fd` (-1 when the
    pipe is broken), or None if `fd` is not a pipe / PeekNamedPipe fails."""
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        handle = msvcrt.get_osfhandle(fd)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                           ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel32.PeekNamedPipe.restype = wintypes.BOOL
        avail = wintypes.DWORD()
        if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None):
            return None
    except (OSError, AttributeError, ValueError):
        return None

    def peek():
        if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None):
            return -1  # broken pipe: the host closed its end
        return avail.value

    return peek


def stdin_lines(poll_seconds=0.02):
    """Yield raw request lines from stdin until EOF.

    Windows: a synchronous ReadFile pending on the stdin pipe makes
    GetFileType() on that handle block, and every DLL that brings its own C
    runtime (numpy's OpenBLAS, torch, ...) calls GetFileType on the standard
    handles while it loads - so a reader thread blocked on stdin deadlocked
    the first lazy `import numpy` (real MedSAM2 environment, 05/11/2026).
    On a pipe the reader therefore never blocks: PeekNamedPipe says how
    many bytes are there and exactly those are read. Elsewhere (and if the
    handle is not a pipe) the plain blocking read is used."""
    fd = sys.stdin.fileno()
    peek = _windows_pipe_peek(fd) if sys.platform == "win32" else None
    if peek is None:
        yield from sys.stdin.buffer
        return
    pending = b""
    while True:
        n = peek()
        if n < 0:
            break
        if n == 0:
            time.sleep(poll_seconds)
            continue
        data = os.read(fd, n)
        if not data:
            break
        pending += data
        while NEWLINE in pending:
            line, pending = pending.split(NEWLINE, 1)
            yield line + NEWLINE
    if pending.strip():
        yield pending


def main(factories=None):
    # Private protocol stream = the ORIGINAL stdout; everything a library
    # prints (sys.stdout, or fd 1 from C code) goes to stderr instead.
    out_fd = os.dup(sys.stdout.fileno())
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    out = os.fdopen(out_fd, "w", encoding="utf-8", newline="\n")
    worker = Worker(out, factories)
    inbox = queue.Queue()
    stop = object()

    def reader():
        for raw in stdin_lines():
            try:
                req = protocol.check_request(protocol.decode(raw))
            except protocol.ProtocolError as e:
                worker.send(protocol.response({}, protocol.STATUS_ERROR, protocol.E_BAD_REQUEST, str(e)))
                continue
            if req["command"] == protocol.CANCEL:
                target = req.get("target_request_id")
                if isinstance(target, int):
                    worker.mark_cancelled(target)
                worker.send(protocol.response(req, protocol.STATUS_OK))
                continue
            inbox.put(req)
        inbox.put(stop)
        # Host gone: if the main thread is busy in a model call, do not
        # wait for it - nobody can receive the result.
        time.sleep(2.0)
        os._exit(0)

    threading.Thread(target=reader, name="iai-stdin", daemon=True).start()
    while worker.running:
        req = inbox.get()
        if req is stop:
            break
        worker.handle(req)
    worker.close()
    out.flush()
    sys.stderr.flush()
    # The stdin reader thread may be blocked in a read (POSIX); a normal
    # interpreter shutdown would abort on its buffer lock ("could not acquire
    # lock for <stdin> at interpreter shutdown"). Everything is flushed: leave.
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
