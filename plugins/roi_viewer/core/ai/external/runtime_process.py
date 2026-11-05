# --------------------------------------------------------------------------
# The plugin-owned worker process (one subprocess.Popen) and its JSON Lines
# channel. Standard library + protocol.py only.
#
# * Reader thread: worker stdout lines -> queue (EOF -> _EOF sentinel).
#   stderr thread: kept as a short tail for the console (never the GUI).
# * receive() waits for the response to ONE request_id; responses for any
#   other request id (a late answer to a request that was given up on) are
#   counted in `stale_responses` and dropped.
# * terminate() kills only self._proc - the Popen this object started.
#   Nothing here enumerates or signals other processes.
# * The worker exits on its own when its stdin closes (host gone).
# --------------------------------------------------------------------------
import collections
import queue
import subprocess
import sys
import threading
import time
from typing import Callable, List, Optional

from . import protocol
from .errors import RequestCancelled, RuntimeFailure, WorkerExited, WorkerTimeout

_EOF = object()
STDERR_TAIL_LINES = 60


class RuntimeProcess:
    def __init__(self, command: List[str], cwd: Optional[str] = None, env: Optional[dict] = None):
        if not command or not all(isinstance(c, str) and c for c in command):
            raise RuntimeFailure(protocol.E_NOT_CONFIGURED, "runtime_command must be a non-empty list of strings")
        self.command = list(command)
        self.cwd = cwd
        self.env = env
        self._proc: Optional[subprocess.Popen] = None
        self._lines: "queue.Queue" = queue.Queue()
        self._write_lock = threading.Lock()
        self.stderr_tail = collections.deque(maxlen=STDERR_TAIL_LINES)
        self.stale_responses = 0
        self.malformed_lines = 0
        self.started_at: Optional[float] = None

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self.is_alive():
            return
        self._lines = queue.Queue()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            self._proc = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.cwd, env=self.env, creationflags=flags, bufsize=0, close_fds=True,
            )
        except (OSError, ValueError) as e:
            self._proc = None
            raise RuntimeFailure(protocol.E_WORKER_START, f"{self.command[0]}: {e}") from None
        self.started_at = time.perf_counter()
        proc = self._proc
        threading.Thread(target=self._read_stdout, args=(proc, self._lines), name="roi-viewer-iai-stdout",
                         daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(proc,), name="roi-viewer-iai-stderr", daemon=True).start()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return None if self._proc is None else self._proc.pid

    def terminate(self, wait_seconds: float = 5.0) -> None:
        """Kill this object's own worker (if running). Idempotent."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        for stream in (proc.stdin,):
            try:
                stream.close()
            except Exception:
                pass
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(wait_seconds)
            except subprocess.TimeoutExpired:
                print(f"ROI Viewer: interactive AI worker pid {proc.pid} did not exit after kill")

    def shutdown(self, request_id: int, timeout: float = 10.0) -> bool:
        """Polite SHUTDOWN, then kill if it does not exit in time. Returns
        True if the worker exited by itself."""
        if not self.is_alive():
            self._proc = None
            return True
        proc = self._proc
        clean = False
        try:
            self.send(protocol.request(protocol.SHUTDOWN, request_id))
            proc.wait(timeout)
            clean = True
        except (RuntimeFailure, subprocess.TimeoutExpired, OSError):
            clean = False
        self.terminate()
        return clean

    # ------------------------------------------------------------- channel
    def send(self, message: dict) -> None:
        line = protocol.encode(message).encode("utf-8")
        proc = self._proc
        if proc is None or proc.poll() is not None:
            raise WorkerExited(self._exit_detail(proc))
        with self._write_lock:
            try:
                proc.stdin.write(line)
                proc.stdin.flush()
            except (OSError, ValueError):
                raise WorkerExited(self._exit_detail(proc)) from None

    def receive(self, request_id: int, timeout: float, cancel_event=None, on_cancel: Optional[Callable] = None,
                on_progress: Optional[Callable] = None, cancel_grace: float = 10.0) -> dict:
        """The final (ok/error) response to request_id. Progress responses
        go to on_progress. When cancel_event gets set, on_cancel() is called
        once (sends CANCEL); if no final answer arrives within cancel_grace
        seconds the worker is killed. Raises WorkerExited, WorkerTimeout,
        RequestCancelled or RuntimeFailure(E_MALFORMED)."""
        deadline = time.monotonic() + float(timeout)
        cancel_deadline = None
        while True:
            now = time.monotonic()
            if cancel_event is not None and cancel_event.is_set() and cancel_deadline is None:
                cancel_deadline = now + cancel_grace
                if on_cancel is not None:
                    try:
                        on_cancel()
                    except RuntimeFailure:
                        pass
            if cancel_deadline is not None and now > cancel_deadline:
                self.terminate()
                raise RequestCancelled("worker killed: no answer to CANCEL in time")
            if now > deadline:
                self.terminate()
                raise WorkerTimeout(f"no response to request {request_id} within {timeout:.0f} s")
            try:
                item = self._lines.get(timeout=0.1)
            except queue.Empty:
                if not self.is_alive() and self._lines.empty():
                    raise WorkerExited(self._exit_detail(self._proc))
                continue
            if item is _EOF:
                raise WorkerExited(self._exit_detail(self._proc))
            try:
                message = protocol.check_response(protocol.decode(item))
            except protocol.ProtocolError as e:
                self.malformed_lines += 1
                self.terminate()
                raise RuntimeFailure(protocol.E_MALFORMED, str(e)) from None
            if message["request_id"] != request_id:
                self.stale_responses += 1
                continue
            if message["status"] == protocol.STATUS_PROGRESS:
                if on_progress is not None:
                    on_progress(message)
                continue
            if cancel_deadline is not None and message["status"] == protocol.STATUS_ERROR \
                    and message["error_code"] == protocol.E_CANCELLED:
                raise RequestCancelled(message.get("message", ""))
            return message

    # ------------------------------------------------------------- threads
    @staticmethod
    def _read_stdout(proc, lines):
        try:
            for raw in iter(proc.stdout.readline, b""):
                lines.put(raw)
        except (OSError, ValueError):
            pass
        lines.put(_EOF)

    def _read_stderr(self, proc):
        try:
            for raw in iter(proc.stderr.readline, b""):
                text = raw.decode("utf-8", "replace").rstrip()
                if text:
                    self.stderr_tail.append(text)
                    print(f"ROI Viewer [AI worker]: {text}")
        except (OSError, ValueError):
            pass

    def _exit_detail(self, proc) -> str:
        code = None
        if proc is not None:
            try:
                code = proc.wait(2.0)  # stdout closed: the exit is imminent - reap it for the code
            except subprocess.TimeoutExpired:
                code = proc.poll()
        tail = " | ".join(list(self.stderr_tail)[-3:])
        return f"worker not running (exit code {code}){': ' + tail if tail else ''}"
