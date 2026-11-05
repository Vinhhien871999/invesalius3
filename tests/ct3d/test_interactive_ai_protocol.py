# --------------------------------------------------------------------------
# Interactive AI external runtime - protocol, worker loop, process wrapper,
# temp data and configuration (feature/interactive-ai-medsam2).
#
# The worker used here is tests/ct3d/helpers/fake_interactive_ai_worker.py:
# the REAL tools/interactive_ai_runtime/worker.py loop with a deterministic
# FakeInteractiveAIProvider. No model is involved; nothing here says
# anything about segmentation quality.
# --------------------------------------------------------------------------
import json
import os
import pathlib
import sys
import threading
import time

import numpy as np
import pytest

from plugins.roi_viewer.core.ai.external import config as cfg
from plugins.roi_viewer.core.ai.external import protocol as P
from plugins.roi_viewer.core.ai.external import volume_cache as vc
from plugins.roi_viewer.core.ai.external.errors import RequestCancelled, RuntimeFailure, WorkerExited, WorkerTimeout
from plugins.roi_viewer.core.ai.external.runtime_client import load_candidate
from plugins.roi_viewer.core.ai.external.runtime_process import RuntimeProcess

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAKE_WORKER = str(ROOT / "tests" / "ct3d" / "helpers" / "fake_interactive_ai_worker.py")


def fake_command():
    return [sys.executable, FAKE_WORKER]


@pytest.fixture
def proc():
    p = RuntimeProcess(fake_command())
    p.start()
    yield p
    p.terminate()


def hello(p, rid=1, **config):
    p.send(P.request(P.HELLO, rid, provider="fake", provider_config=config))
    return p.receive(rid, 60)


# ------------------------------------------------------------------ protocol
def test_protocol_copies_are_identical():
    host = ROOT / "plugins" / "roi_viewer" / "core" / "ai" / "external" / "protocol.py"
    worker = ROOT / "tools" / "interactive_ai_runtime" / "protocol.py"
    assert host.read_bytes() == worker.read_bytes()


def test_json_lines_roundtrip_and_envelope():
    req = P.request(P.PREDICT, 7, generation_id=3, volume_id="abc", prompts={"points": [], "box": None})
    line = P.encode(req)
    assert line.endswith("\n") and "\n" not in line[:-1]
    back = P.check_request(P.decode(line.encode("utf-8")))
    assert back == req and back["request_id"] == 7 and back["generation_id"] == 3 and back["volume_id"] == "abc"
    resp = P.response(back, P.STATUS_OK, voxels=5)
    assert P.check_response(P.decode(P.encode(resp)))["voxels"] == 5
    assert (resp["request_id"], resp["generation_id"], resp["volume_id"]) == (7, 3, "abc")


@pytest.mark.parametrize("bad", [b"", b"[1, 2]", b"not json", b"\xff\xfe", b'{"a": NaN}', b"x" * (P.MAX_LINE_BYTES + 1)],
                         ids=["empty", "array", "text", "not-utf8", "nan", "too-long"])
def test_decode_rejects_anything_but_one_json_object(bad):
    with pytest.raises(P.ProtocolError):
        P.decode(bad)


def test_encode_rejects_nan_and_objects_and_reserved_keys():
    with pytest.raises(P.ProtocolError):
        P.encode({"x": float("nan")})
    with pytest.raises(P.ProtocolError):
        P.encode({"x": object()})
    with pytest.raises(P.ProtocolError):
        P.request(P.HELLO, 1, protocol=2)  # envelope keys cannot be overridden by a payload
    with pytest.raises(P.ProtocolError):
        P.request("EVAL", 1)


@pytest.mark.parametrize("missing", ["request_id", "generation_id", "volume_id", "status", "error_code", "message"])
def test_malformed_response_envelope(missing):
    resp = P.response({"request_id": 1, "generation_id": 0, "volume_id": ""})
    del resp[missing]
    with pytest.raises(P.ProtocolError):
        P.check_response(resp)
    err = P.response({"request_id": 1}, P.STATUS_ERROR, "", "no code")
    with pytest.raises(P.ProtocolError):
        P.check_response(err)
    with pytest.raises(P.ProtocolError):
        P.check_response(dict(P.response({"request_id": 1}), request_id=True))  # bool is not an id


def test_prompt_payload_validation():
    shape = (10, 20, 30)
    ok = P.check_prompts({"points": [{"zyx": [1, 2, 3], "label": 1}, {"zyx": [9, 19, 29], "label": 0}],
                          "box": {"min_zyx": [5, 10, 20], "max_zyx": [2, 3, 4]}}, shape)
    assert ok["box"] == {"min_zyx": [2, 3, 4], "max_zyx": [5, 10, 20]}  # reversed corners ordered
    for bad in ({"points": [{"zyx": [10, 0, 0], "label": 1}]},  # outside
                {"points": [{"zyx": [1, 2], "label": 1}]},
                {"points": [{"zyx": [1.5, 2, 3], "label": 1}]},
                {"points": [{"zyx": [1, 2, 3], "label": 2}]},
                {"points": [{"zyx": [1, 2, 3], "label": True}]},
                {"box": {"min_zyx": [0, 0, 0], "max_zyx": [0, 0, 30]}},
                "points"):
        with pytest.raises(P.ProtocolError):
            P.check_prompts(bad, shape)


# ------------------------------------------------------------------ worker loop
def test_worker_hello_and_unknown_command(proc):
    reply = hello(proc)
    assert reply["status"] == P.STATUS_OK and reply["protocol_name"] == P.PROTOCOL_NAME
    assert reply["protocol"] == P.PROTOCOL_VERSION and reply["provider"] == "fake"
    msg = P.request(P.HELLO, 2, provider="fake")
    msg["command"] = "RUN_ARBITRARY_CODE"
    proc.send(msg)
    err = proc.receive(2, 30)
    assert err["status"] == P.STATUS_ERROR and err["error_code"] == P.E_UNKNOWN_COMMAND


def test_worker_reports_bad_envelope_and_unknown_provider(proc):
    proc.send({"command": P.HELLO, "request_id": 3, "generation_id": 0, "volume_id": "", "protocol": 999})
    with pytest.raises(WorkerTimeout):
        proc.receive(3, 3)  # answered with request_id -1 (envelope unreadable) -> never matches; counted stale
    assert proc.stale_responses == 1


def test_worker_unknown_provider_is_an_error():
    p = RuntimeProcess(fake_command())
    p.start()
    try:
        p.send(P.request(P.HELLO, 1, provider="nonexistent"))
        r = p.receive(1, 60)
        assert r["status"] == P.STATUS_ERROR and r["error_code"] == P.E_BAD_REQUEST
    finally:
        p.terminate()


def test_stale_response_is_discarded(proc, tmp_path):
    hello(proc)
    proc.send(P.request(P.PROBE, 10))  # given up on: its answer must not be taken for the next one
    proc.send(P.request(P.PROBE, 11))
    reply = proc.receive(11, 60)
    assert reply["request_id"] == 11 and proc.stale_responses == 1


def test_library_noise_on_stdout_does_not_corrupt_the_protocol(tmp_path):
    p = RuntimeProcess(fake_command())
    p.start()
    try:
        assert hello(p, noise=True)["status"] == P.STATUS_OK
        assert p.malformed_lines == 0
        deadline = time.time() + 10
        while not any("noisy library output" in line for line in p.stderr_tail) and time.time() < deadline:
            time.sleep(0.05)
        assert any("noisy library output" in line for line in p.stderr_tail)  # went to stderr
    finally:
        p.terminate()


def test_shutdown_is_clean(proc):
    hello(proc)
    assert proc.shutdown(99, timeout=20) is True
    assert not proc.is_alive()


def test_worker_exits_when_host_closes_stdin():
    p = RuntimeProcess(fake_command())
    p.start()
    hello(p)
    raw = p._proc
    raw.stdin.close()
    assert raw.wait(20) == 0
    p.terminate()


def test_timeout_kills_only_its_worker():
    p = RuntimeProcess([sys.executable, "-c", "import time; time.sleep(60)"])
    p.start()
    pid = p.pid
    with pytest.raises(WorkerTimeout):
        p.receive(1, 0.5)
    assert not p.is_alive() and p.pid is None and pid is not None


def test_malformed_worker_output_kills_the_worker():
    p = RuntimeProcess([sys.executable, "-c", "import sys,time; print('garbage'); sys.stdout.flush(); time.sleep(30)"])
    p.start()
    with pytest.raises(RuntimeFailure) as e:
        p.receive(1, 20)
    assert e.value.code == P.E_MALFORMED and not p.is_alive()


def test_worker_crash_is_reported():
    p = RuntimeProcess([sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(4)"])
    p.start()
    with pytest.raises(WorkerExited) as e:
        p.receive(1, 20)
    assert "exit code 4" in str(e.value)


def test_missing_executable_is_a_start_failure():
    p = RuntimeProcess([str(ROOT / "no_such_python.exe")])
    with pytest.raises(RuntimeFailure) as e:
        p.start()
    assert e.value.code == P.E_WORKER_START


def _load(p, tmp_path, vol, rid=20):
    session = vc.SessionDirectory(str(tmp_path))
    path, meta = vc.write_volume(session, vol, (1.0, 1.0, 1.0))
    p.send(P.request(P.LOAD_VOLUME, rid, volume_id=meta["volume_id"], volume_path=str(path), metadata=meta))
    assert p.receive(rid, 60)["status"] == P.STATUS_OK
    return session, meta


def test_cancelled_request_answers_cancelled(tmp_path):
    p = RuntimeProcess(fake_command())
    p.start()
    try:
        hello(p, delay_s=0.2, steps=50)
        vol = np.zeros((8, 8, 8), dtype=np.int16)
        session, meta = _load(p, tmp_path, vol)
        p.send(P.request(P.PREDICT, 30, 1, meta["volume_id"], prompts={"points": [{"zyx": [4, 4, 4], "label": 1}]},
                         output_path=str(session.file("c.npy"))))
        cancel = threading.Event()
        threading.Timer(0.5, cancel.set).start()
        t0 = time.perf_counter()
        with pytest.raises(RequestCancelled):
            p.receive(30, 60, cancel_event=cancel,
                      on_cancel=lambda: p.send(P.request(P.CANCEL, 31, target_request_id=30)))
        assert time.perf_counter() - t0 < 5  # cooperative: far before the 10 s of work
        assert p.is_alive()  # the worker survives a cooperative cancel
        assert not session.file("c.npy").exists()
    finally:
        p.terminate()


def test_cancel_ignored_by_the_model_kills_the_worker(tmp_path):
    p = RuntimeProcess(fake_command())
    p.start()
    try:
        hello(p, delay_s=0.2, steps=100, ignore_cancel=True)
        session, meta = _load(p, tmp_path, np.zeros((8, 8, 8), dtype=np.int16))
        p.send(P.request(P.PREDICT, 40, 1, meta["volume_id"], prompts={"points": [{"zyx": [4, 4, 4], "label": 1}]},
                         output_path=str(session.file("c.npy"))))
        cancel = threading.Event()
        cancel.set()
        with pytest.raises(RequestCancelled):
            p.receive(40, 60, cancel_event=cancel, cancel_grace=1.0,
                      on_cancel=lambda: p.send(P.request(P.CANCEL, 41, target_request_id=40)))
        assert not p.is_alive()
    finally:
        p.terminate()


def test_predict_without_volume_or_prompt(proc, tmp_path):
    hello(proc)
    proc.send(P.request(P.PREDICT, 50, 1, "x", prompts={"points": [{"zyx": [0, 0, 0], "label": 1}]}, output_path="o"))
    assert proc.receive(50, 30)["error_code"] == P.E_NO_VOLUME
    session, meta = _load(proc, tmp_path, np.zeros((4, 4, 4), dtype=np.int16), rid=51)
    proc.send(P.request(P.PREDICT, 52, 1, meta["volume_id"], prompts={"points": []}, output_path="o"))
    assert proc.receive(52, 30)["error_code"] == P.E_NEEDS_PROMPT
    proc.send(P.request(P.PREDICT, 53, 1, "other-volume", prompts={"points": []}, output_path="o"))
    assert proc.receive(53, 30)["error_code"] == P.E_VOLUME_MISMATCH


def test_worker_rejects_wrong_shape_output(tmp_path):
    p = RuntimeProcess(fake_command())
    p.start()
    try:
        hello(p, bad_output="shape")
        session, meta = _load(p, tmp_path, np.zeros((6, 6, 6), dtype=np.int16))
        p.send(P.request(P.PREDICT, 60, 1, meta["volume_id"], prompts={"points": [{"zyx": [3, 3, 3], "label": 1}]},
                         output_path=str(session.file("c.npy"))))
        assert p.receive(60, 30)["error_code"] == P.E_INVALID_OUTPUT
    finally:
        p.terminate()


# ------------------------------------------------------------------ candidate file
def test_load_candidate_validation(tmp_path):
    shape = (3, 4, 5)
    good = tmp_path / "good.npy"
    np.save(good, np.ones(shape, dtype=np.uint8))
    assert load_candidate(good, shape).dtype == np.uint8
    np.save(tmp_path / "bool.npy", np.zeros(shape, dtype=bool))
    assert load_candidate(tmp_path / "bool.npy", shape).sum() == 0
    cases = {"shape.npy": np.ones((3, 4, 4), dtype=np.uint8), "float.npy": np.ones(shape, dtype=np.float32),
             "values.npy": np.full(shape, 7, dtype=np.uint8)}
    for name, arr in cases.items():
        np.save(tmp_path / name, arr)
        with pytest.raises(RuntimeFailure) as e:
            load_candidate(tmp_path / name, shape)
        assert e.value.code == P.E_INVALID_OUTPUT
    np.save(tmp_path / "obj.npy", np.array([{"a": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(RuntimeFailure):
        load_candidate(tmp_path / "obj.npy", (1,))  # pickle is never loaded


# ------------------------------------------------------------------ temp data
def test_fingerprint_is_deterministic_and_sensitive():
    a = np.arange(60, dtype=np.int16).reshape(3, 4, 5)
    fp = vc.fingerprint(a, (1, 1, 2))
    assert fp == vc.fingerprint(a.copy(), (1.0, 1.0, 2.0))
    b = a.copy()
    b[0, 0, 0] += 1
    assert len({fp, vc.fingerprint(b, (1, 1, 2)), vc.fingerprint(a, (1, 1, 2.5)),
                vc.fingerprint(a, (1, 1, 2), orientation=(1, 0, 0, 0, 1, 0)),
                vc.fingerprint(a.astype(np.int32), (1, 1, 2))}) == 5


def test_session_directory_and_files_carry_no_patient_data(tmp_path):
    s = vc.SessionDirectory(str(tmp_path))
    vol = np.zeros((2, 3, 4), dtype=np.int16)
    path, meta = vc.write_volume(s, vol, (0.5, 0.5, 1.0), orientation=(1, 0, 0, 0, 1, 0))
    assert s.path.name.startswith(vc.DIR_PREFIX) and len(s.path.name) > len(vc.DIR_PREFIX) + 4
    assert sorted(p.name for p in s.path.iterdir()) == sorted([vc.MARKER_NAME, vc.VOLUME_FILE, vc.METADATA_FILE])
    assert np.array_equal(np.load(path, allow_pickle=False), vol)
    saved = json.loads((s.path / vc.METADATA_FILE).read_text(encoding="utf-8"))
    assert set(saved) == {"volume_id", "shape_zyx", "dtype", "spacing_xyz", "orientation", "index_order", "min",
                          "max", "values"}
    assert saved == meta
    with pytest.raises(ValueError):
        s.file("../escape.npy")
    s.cleanup()
    assert not any(tmp_path.iterdir())


def test_cleanup_abandoned_deletes_only_old_owned_directories(tmp_path):
    old = vc.SessionDirectory(str(tmp_path))
    old.create()
    young = vc.SessionDirectory(str(tmp_path))
    young.create()
    no_marker = tmp_path / (vc.DIR_PREFIX + "foreign")
    no_marker.mkdir()
    other = tmp_path / "someone-elses-dir"
    other.mkdir()
    (other / vc.MARKER_NAME).write_text("x")
    long_ago = time.time() - 2 * vc.ABANDONED_AGE_SECONDS
    os.utime(old.path / vc.MARKER_NAME, (long_ago, long_ago))
    removed = vc.cleanup_abandoned(str(tmp_path))
    assert removed == [str(old.path)]
    assert young.path.is_dir() and no_marker.is_dir() and other.is_dir()


def test_wsl_path_mapping():
    assert vc.to_worker_path(r"C:\Users\x\AppData\Local\Temp\roiviewer-iai-1\volume.npy", "wsl") == \
        "/mnt/c/Users/x/AppData/Local/Temp/roiviewer-iai-1/volume.npy"
    assert vc.to_worker_path("/tmp/a", "native") == "/tmp/a"
    with pytest.raises(ValueError):
        vc.to_worker_path("relative/path", "wsl")


# ------------------------------------------------------------------ config
def test_config_absent_disabled_invalid_valid(tmp_path, monkeypatch):
    monkeypatch.delenv(cfg.ENV_CONFIG_PATH, raising=False)
    missing = cfg.load_config(tmp_path / "none.json")
    assert not missing.usable and missing.problem == cfg.NOT_CONFIGURED_NO_FILE
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"enabled": False, "runtime_command": ["python", "worker.py"]}))
    assert cfg.load_config(f).problem == cfg.NOT_CONFIGURED_DISABLED
    for bad in ({"enabled": True, "runtime_command": "python worker.py"}, {"enabled": True, "runtime_command": []},
                {"enabled": True, "runtime_command": ["p"], "path_style": "smb"},
                {"enabled": True, "runtime_command": ["p"], "predict_timeout_s": 0}):
        f.write_text(json.dumps(bad))
        assert cfg.load_config(f).problem == cfg.NOT_CONFIGURED_INVALID
    f.write_text("{not json")
    assert cfg.load_config(f).problem == cfg.NOT_CONFIGURED_INVALID
    f.write_text(json.dumps({"enabled": True, "runtime_command": ["python", "worker.py"], "path_style": "wsl",
                             "provider_config": {"checkpoint": "/models/MedSAM2_latest.pt"}}))
    good = cfg.load_config(f)
    assert good.usable and good.runtime_command == ("python", "worker.py") and good.path_style == "wsl"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH, str(f))
    assert cfg.load_config() == good


def test_default_config_path_follows_xdg(monkeypatch):
    path = cfg.default_config_path()
    assert path.name == cfg.CONFIG_FILE_NAME and path.parent.name == "invesalius"


def test_plugin_never_writes_the_config():
    """Static: nothing in core/ai/external opens the config for writing."""
    src = (ROOT / "plugins" / "roi_viewer" / "core" / "ai" / "external" / "config.py").read_text(encoding="utf-8")
    assert "write_text" not in src and "open(" not in src and ".write(" not in src


def test_standalone_probe_script(tmp_path):
    """tools/interactive_ai_runtime/probe_runtime.py (operator smoke probe)."""
    import subprocess

    config = tmp_path / "c.json"
    config.write_text(json.dumps({"enabled": True, "provider": "fake", "runtime_command": fake_command()}))
    script = str(ROOT / "tools" / "interactive_ai_runtime" / "probe_runtime.py")
    out = subprocess.run([sys.executable, script, str(config)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert '"available": true' in out.stdout and "FakeInteractiveAIWorker" in out.stdout
    config.write_text(json.dumps({"enabled": True, "provider": "fake", "runtime_command": fake_command(),
                                  "provider_config": {"fail_probe": True}}))
    out = subprocess.run([sys.executable, script, str(config)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 1
