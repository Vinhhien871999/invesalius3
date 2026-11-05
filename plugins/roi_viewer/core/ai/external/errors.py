# --------------------------------------------------------------------------
# Host-side exceptions of the interactive-AI external runtime. Each carries
# one protocol error code (protocol.E_*); the panel shows a Vietnamese
# message per code and prints `detail` to the console only (no traceback
# in the GUI).
# --------------------------------------------------------------------------
from . import protocol


class RuntimeFailure(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class WorkerExited(RuntimeFailure):
    def __init__(self, detail=""):
        super().__init__(protocol.E_WORKER_EXITED, detail)


class WorkerTimeout(RuntimeFailure):
    def __init__(self, detail=""):
        super().__init__(protocol.E_TIMEOUT, detail)


class RequestCancelled(RuntimeFailure):
    def __init__(self, detail=""):
        super().__init__(protocol.E_CANCELLED, detail)
