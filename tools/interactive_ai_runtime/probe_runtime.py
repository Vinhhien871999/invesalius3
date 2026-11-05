#!/usr/bin/env python3
# --------------------------------------------------------------------------
# Smoke probe of a configured interactive-AI runtime, WITHOUT InVesalius:
# starts the worker exactly as the plugin would (runtime_command from the
# config file), sends HELLO + PROBE, prints the answers, shuts it down.
# Standard library only - run it with ANY Python (e.g. InVesalius's own):
#
#   python tools/interactive_ai_runtime/probe_runtime.py <config.json>
#
# Exit code 0 = the provider reports available, 1 = not available,
# 2 = the runtime could not be started / did not answer.
# --------------------------------------------------------------------------
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol  # noqa: E402


def main(argv):
    if len(argv) != 2:
        print(__doc__ or "usage: probe_runtime.py <config.json>")
        return 2
    config = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    command = config.get("runtime_command") or []
    print("runtime_command:", command)
    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                                bufsize=0)
    except OSError as e:
        print("could not start the runtime:", e)
        return 2

    def call(command_name, rid, timeout, **payload):
        proc.stdin.write(protocol.encode(protocol.request(command_name, rid, **payload)).encode("utf-8"))
        proc.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"runtime exited (code {proc.poll()})")
            message = protocol.check_response(protocol.decode(line))
            if message["request_id"] == rid and message["status"] != protocol.STATUS_PROGRESS:
                return message
        raise RuntimeError("timeout")

    try:
        hello = call(protocol.HELLO, 1, float(config.get("start_timeout_s", 120)),
                     provider=config.get("provider", "medsam2"), provider_config=config.get("provider_config") or {})
        print(f"HELLO ({time.perf_counter() - t0:.1f} s):", json.dumps(hello, indent=1))
        t1 = time.perf_counter()
        probe = call(protocol.PROBE, 2, float(config.get("probe_timeout_s", 300)))
        print(f"PROBE ({time.perf_counter() - t1:.1f} s):", json.dumps(probe, indent=1))
        call(protocol.SHUTDOWN, 3, 30)
    except Exception as e:
        print("runtime failure:", e)
        proc.kill()
        return 2
    proc.wait(30)
    return 0 if (probe.get("provider_info") or {}).get("available") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
