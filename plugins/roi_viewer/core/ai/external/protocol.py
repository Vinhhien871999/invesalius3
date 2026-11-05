# --------------------------------------------------------------------------
# Interactive AI external-runtime protocol (feature/interactive-ai-medsam2).
#
# STANDARD LIBRARY ONLY. This file exists twice, byte-identical:
#   plugins/roi_viewer/core/ai/external/protocol.py   (InVesalius side)
#   tools/interactive_ai_runtime/protocol.py           (worker side)
# tests/ct3d/test_interactive_ai_protocol.py fails if they differ.
#
# Transport: the worker is a persistent child process. Control messages
# are JSON Lines - one JSON object per line, UTF-8 - on the worker's
# stdin (requests) and on a private copy of its original stdout
# (responses). The worker redirects its own sys.stdout to stderr, so a
# library that prints cannot corrupt the protocol. Large arrays never go
# in JSON: the host writes volume.npy and the worker writes candidate.npy
# in a private temporary directory, and the messages carry only paths.
# json.loads is the only deserializer - no pickle, no eval.
#
# Every request carries request_id (unique per host session),
# generation_id (the host's prompt-set generation - a response for an old
# generation is stale and ignored) and volume_id (fingerprint of the
# volume the request is about, "" if none). Every response echoes the
# three ids and carries status ("ok" | "error" | "progress"), error_code
# ("" when ok) and message (human-readable, English, console only).
# --------------------------------------------------------------------------
import json

PROTOCOL_NAME = "roi-viewer-interactive-ai"
PROTOCOL_VERSION = 1

# Commands
HELLO = "HELLO"
PROBE = "PROBE"
LOAD_VOLUME = "LOAD_VOLUME"
SET_PROMPTS = "SET_PROMPTS"
PREDICT = "PREDICT"
CLEAR_PROMPTS = "CLEAR_PROMPTS"
RELEASE_VOLUME = "RELEASE_VOLUME"
CANCEL = "CANCEL"
SHUTDOWN = "SHUTDOWN"
COMMANDS = (HELLO, PROBE, LOAD_VOLUME, SET_PROMPTS, PREDICT, CLEAR_PROMPTS, RELEASE_VOLUME, CANCEL, SHUTDOWN)

# Response status
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_PROGRESS = "progress"  # intermediate; the final response follows
STATUSES = (STATUS_OK, STATUS_ERROR, STATUS_PROGRESS)

# Error codes (worker -> host). The host maps each to a Vietnamese message.
E_UNKNOWN_COMMAND = "unknown_command"
E_BAD_REQUEST = "bad_request"
E_PROTOCOL_VERSION = "protocol_version"
E_DEPENDENCY = "dependency_missing"
E_CHECKPOINT_MISSING = "checkpoint_missing"
E_MODEL_LOAD = "model_load_failed"
E_CUDA_UNAVAILABLE = "cuda_unavailable"
E_CUDA_OOM = "cuda_oom"
E_HOST_OOM = "host_out_of_memory"
E_NO_VOLUME = "volume_not_loaded"
E_VOLUME_MISMATCH = "volume_mismatch"
E_PROMPT_UNSUPPORTED = "prompt_unsupported"
E_NEEDS_PROMPT = "needs_prompt"
E_INTERNAL = "internal_error"
# Host-side only (never sent by a worker)
E_WORKER_START = "worker_start_failed"
E_WORKER_EXITED = "worker_exited"
E_TIMEOUT = "timeout"
E_CANCELLED = "cancelled"
E_MALFORMED = "malformed_response"
E_INVALID_OUTPUT = "invalid_output"
E_NOT_CONFIGURED = "not_configured"

# Prompt encoding inside SET_PROMPTS / PREDICT (voxel indices, (z, y, x),
# integers, inclusive box bounds). World mm positions are informational.
#   {"points": [{"zyx": [z, y, x], "label": 1 | 0}, ...],
#    "box": {"min_zyx": [z, y, x], "max_zyx": [z, y, x]} | null}
LABEL_POSITIVE = 1
LABEL_NEGATIVE = 0

MAX_LINE_BYTES = 1 << 20  # a control line is small; anything larger is malformed


class ProtocolError(ValueError):
    pass


def encode(message: dict) -> str:
    """One JSON line (with trailing newline). Raises ProtocolError for
    values JSON cannot represent exactly (NaN, objects)."""
    try:
        text = json.dumps(message, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as e:
        raise ProtocolError(f"cannot encode message: {e}") from None
    return text + "\n"


def decode(line) -> dict:
    """Parse one line into a dict. Raises ProtocolError on anything that is
    not a single JSON object."""
    if isinstance(line, bytes):
        if len(line) > MAX_LINE_BYTES:
            raise ProtocolError("line too long")
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            raise ProtocolError("line is not UTF-8") from None
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError("line too long")
    line = line.strip()
    if not line:
        raise ProtocolError("empty line")
    try:
        message = json.loads(line, parse_constant=_reject_constant)
    except ValueError as e:
        raise ProtocolError(f"invalid JSON: {e}") from None
    if not isinstance(message, dict):
        raise ProtocolError("message is not a JSON object")
    return message


def _reject_constant(name):
    raise ValueError(f"{name} is not allowed")


def request(command: str, request_id: int, generation_id: int = 0, volume_id: str = "", **payload) -> dict:
    if command not in COMMANDS:
        raise ProtocolError(f"unknown command {command!r}")
    message = {"protocol": PROTOCOL_VERSION, "command": command, "request_id": int(request_id),
               "generation_id": int(generation_id), "volume_id": str(volume_id)}
    for key in payload:
        if key in message:
            raise ProtocolError(f"payload key {key!r} is reserved")
    message.update(payload)
    return message


def response(req: dict, status: str = STATUS_OK, error_code: str = "", message: str = "", **payload) -> dict:
    if status not in STATUSES:
        raise ProtocolError(f"unknown status {status!r}")
    out = {"request_id": req.get("request_id", -1), "generation_id": req.get("generation_id", 0),
           "volume_id": req.get("volume_id", ""), "status": status, "error_code": str(error_code),
           "message": str(message)}
    for key in payload:
        if key in out:
            raise ProtocolError(f"payload key {key!r} is reserved")
    out.update(payload)
    return out


def check_request(message: dict) -> dict:
    """Worker side: validate the envelope. Raises ProtocolError."""
    for key, kind in (("command", str), ("request_id", int), ("generation_id", int), ("volume_id", str)):
        if not isinstance(message.get(key), kind) or isinstance(message.get(key), bool):
            raise ProtocolError(f"request field {key!r} missing or not {kind.__name__}")
    if message.get("protocol") != PROTOCOL_VERSION:
        raise ProtocolError(f"protocol version {message.get('protocol')!r}, expected {PROTOCOL_VERSION}")
    return message


def check_response(message: dict) -> dict:
    """Host side: validate the envelope. Raises ProtocolError."""
    for key, kind in (("request_id", int), ("generation_id", int), ("volume_id", str), ("status", str),
                      ("error_code", str), ("message", str)):
        value = message.get(key)
        if not isinstance(value, kind) or isinstance(value, bool):
            raise ProtocolError(f"response field {key!r} missing or not {kind.__name__}")
    if message["status"] not in STATUSES:
        raise ProtocolError(f"unknown status {message['status']!r}")
    if message["status"] == STATUS_ERROR and not message["error_code"]:
        raise ProtocolError("error response without error_code")
    return message


def check_prompts(prompts, shape_zyx) -> dict:
    """Validate the prompt payload against the volume shape (both sides).
    Returns it normalized: integer voxel indices, ordered inclusive box."""
    if not isinstance(prompts, dict):
        raise ProtocolError("prompts must be an object")
    shape = [int(n) for n in shape_zyx]

    def voxel(value, what):
        if (not isinstance(value, list) or len(value) != 3
                or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
            raise ProtocolError(f"{what} must be 3 integers")
        if not all(0 <= v < n for v, n in zip(value, shape)):
            raise ProtocolError(f"{what} {value} outside volume {shape}")
        return list(value)

    points = []
    for i, p in enumerate(prompts.get("points") or []):
        label = p.get("label") if isinstance(p, dict) else None
        if not isinstance(label, int) or isinstance(label, bool) or label not in (LABEL_POSITIVE, LABEL_NEGATIVE):
            raise ProtocolError(f"point {i} needs label 1 or 0")
        points.append({"zyx": voxel(p.get("zyx"), f"point {i}"), "label": p["label"]})
    box = prompts.get("box")
    if box is not None:
        if not isinstance(box, dict):
            raise ProtocolError("box must be an object")
        lo, hi = voxel(box.get("min_zyx"), "box min"), voxel(box.get("max_zyx"), "box max")
        lo, hi = [min(a, b) for a, b in zip(lo, hi)], [max(a, b) for a, b in zip(lo, hi)]
        box = {"min_zyx": lo, "max_zyx": hi}
    return {"points": points, "box": box}
