# --------------------------------------------------------------------------
# MedSAM2ExternalProvider (host side) against the deterministic
# FakeInteractiveAIWorker through the REAL runtime client/process: probe
# levels, capabilities from the worker, candidate geometry, volume reuse,
# cancellation, crash/restart, timeout, invalid output, close/cleanup.
# The fake worker's masks are a protocol fixture, not model results.
# --------------------------------------------------------------------------
import pathlib
import sys
import threading
import time

import numpy as np
import pytest

from plugins.roi_viewer.core.ai.external import protocol as P
from plugins.roi_viewer.core.ai.external.config import InteractiveAIConfig, load_config
from plugins.roi_viewer.core.ai.external.runtime_client import InteractiveAIRuntimeClient
from plugins.roi_viewer.core.ai.provider import (
    OPTION_GENERATION,
    OPTION_HU_WINDOW,
    REASON_NOT_CHECKED,
    REASON_NOT_CONFIGURED,
    REASON_RUNTIME,
)
from plugins.roi_viewer.core.ai.providers import medsam2_external_provider as m2
from plugins.roi_viewer.core.ai.types import AIInferenceRequest, AIPrompts, Capability, PromptType, read_only_volume
from plugins.roi_viewer.core.ai.prompts import make_box_prompt, make_point_prompt

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAKE_WORKER = str(ROOT / "tests" / "ct3d" / "helpers" / "fake_interactive_ai_worker.py")
SHAPE = (20, 30, 40)
SPACING = (0.5, 0.5, 1.0)  # (x, y, z) mm, anisotropic


def make_provider(tmp_path, **provider_config):
    timeout = provider_config.pop("predict_timeout_s", 120)
    config = InteractiveAIConfig(enabled=True, provider="fake", runtime_command=(sys.executable, FAKE_WORKER),
                                 provider_config=provider_config, predict_timeout_s=timeout)
    clients = []

    def factory(c):
        client = InteractiveAIRuntimeClient(c, temp_root=str(tmp_path))
        client.cancel_grace_s = 1.0
        clients.append(client)
        return client

    provider = m2.MedSAM2ExternalProvider(config_loader=lambda: config, client_factory=factory)
    provider.clients = clients
    return provider


@pytest.fixture
def volume():
    rng = np.random.default_rng(1)
    return rng.integers(-1000, 1500, SHAPE).astype(np.int16)


def point(voxel_zyx, positive=True):
    z, y, x = voxel_zyx
    world = (x * SPACING[0], y * SPACING[1], z * SPACING[2])
    return make_point_prompt(world, SPACING, SHAPE, positive)


def request(vol, points=(), box=None, generation=1, **options):
    options[OPTION_GENERATION] = generation
    return AIInferenceRequest(volume=read_only_volume(vol, SPACING), prompts=AIPrompts(points=tuple(points), box=box),
                              options=options)


def run(provider, req, cancel_event=None):
    stages = []
    result = provider.infer(req, lambda f, s="": stages.append(s), cancel_event or threading.Event())
    return result, stages


def ball(center, radius=3):
    zz, yy, xx = np.ogrid[:SHAPE[0], :SHAPE[1], :SHAPE[2]]
    return (zz - center[0]) ** 2 + (yy - center[1]) ** 2 + (xx - center[2]) ** 2 <= radius ** 2


def owned_dirs(tmp_path):
    return [p for p in tmp_path.iterdir() if p.name.startswith("roiviewer-iai-")]


# ------------------------------------------------------------------ probe levels
def test_unconfigured_probe_starts_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ROI_VIEWER_INTERACTIVE_AI_CONFIG", str(tmp_path / "absent.json"))
    provider = m2.MedSAM2ExternalProvider()
    info = provider.probe()
    assert not info.available and info.unavailable_reason.startswith(REASON_NOT_CONFIGURED)
    assert info.show_when_unavailable and info.checkable and info.display_name == "MedSAM2"
    assert provider._client is None and owned_dirs(tmp_path) == []
    assert load_config().problem  # the default loader honours the env path


def test_configured_probe_is_cheap_and_check_reports_worker_capabilities(tmp_path):
    provider = make_provider(tmp_path)
    info = provider.probe()
    assert not info.available and info.unavailable_reason.startswith(REASON_NOT_CHECKED)
    assert provider._client is None  # no process before the explicit check
    checked = provider.check_environment()
    assert checked.available and checked.version == "test-1"
    assert set(checked.supported_prompt_types) == {PromptType.POSITIVE_POINT, PromptType.NEGATIVE_POINT,
                                                   PromptType.BOX}
    assert Capability.INTERRUPTIBLE in checked.capabilities and checked.supported_devices == ("cpu",)
    assert checked.parameter_choices[OPTION_HU_WINDOW] == ("soft_tissue", "lung", "bone")
    assert checked.details["worker_start_s"] is not None and provider.probe() is checked
    provider.close()


def test_check_failure_is_reported_not_raised(tmp_path):
    provider = make_provider(tmp_path, fail_probe=True)
    info = provider.check_environment()
    assert not info.available and info.unavailable_reason.startswith(f"{REASON_RUNTIME}: checkpoint_missing")
    bad = m2.MedSAM2ExternalProvider(
        config_loader=lambda: InteractiveAIConfig(enabled=True, runtime_command=(str(tmp_path / "nope.exe"),)),
        client_factory=lambda c: InteractiveAIRuntimeClient(c, temp_root=str(tmp_path)))
    info = bad.check_environment()
    assert info.unavailable_reason.startswith(f"{REASON_RUNTIME}: {P.E_WORKER_START}")
    provider.close()
    bad.close()


def test_infer_refused_before_check(tmp_path, volume):
    provider = make_provider(tmp_path)
    with pytest.raises(m2.InferenceFailed) as e:
        run(provider, request(volume, [point((10, 15, 20))]))
    assert e.value.code == P.E_NOT_CONFIGURED


# ------------------------------------------------------------------ geometry
def test_candidate_is_on_the_native_grid_at_the_prompt(tmp_path, volume):
    provider = make_provider(tmp_path, radius=3)
    provider.check_environment()
    before = volume.copy()
    result, stages = run(provider, request(volume, [point((10, 15, 20))]))
    mask = np.asarray(result.mask)
    assert mask.shape == SHAPE and mask.dtype == np.uint8 and set(np.unique(mask)) <= {0, 1}
    assert np.array_equal(mask.astype(bool), ball((10, 15, 20)))  # no mirror, no axis swap
    assert result.extra["candidate_bounds_zyx"] == [[7, 13], [12, 18], [17, 23]]
    assert result.extra["candidate_sha256"] == m2.candidate_sha256(mask)
    assert result.extra["positive_points"] == 1 and result.extra["box"] is False
    assert result.extra["mask_name_prefix"] == "AI - MedSAM2" and result.model_name == "MedSAM2"
    assert np.array_equal(volume, before)  # the source volume is never modified
    provider.close()


def test_negative_point_excludes_and_box_restricts(tmp_path, volume):
    provider = make_provider(tmp_path, radius=4)
    provider.check_environment()
    pos = point((10, 15, 20))
    a, _ = run(provider, request(volume, [pos], generation=1))
    b, _ = run(provider, request(volume, [pos, point((10, 15, 23), positive=False)], generation=2))
    na, nb = int(np.sum(a.mask)), int(np.sum(b.mask))
    assert nb < na and not np.asarray(b.mask)[ball((10, 15, 23), 4)].any()
    box = make_box_prompt((18 * SPACING[0], 13 * SPACING[1], 9.0), (22 * SPACING[0], 17 * SPACING[1], 11.0),
                          SPACING, SHAPE)
    c, _ = run(provider, request(volume, [pos], box=box, generation=3))
    inside = np.zeros(SHAPE, dtype=bool)
    inside[9:12, 13:18, 18:23] = True
    assert np.asarray(c.mask).astype(bool)[~inside].sum() == 0 and np.asarray(c.mask).sum() > 0
    assert b.extra["generation_id"] == 2 and c.extra["generation_id"] == 3
    provider.close()


def test_volume_loaded_once_per_fingerprint(tmp_path, volume):
    provider = make_provider(tmp_path)
    provider.check_environment()
    r1, _ = run(provider, request(volume, [point((5, 5, 5))], generation=1))
    r2, _ = run(provider, request(volume, [point((6, 6, 6))], generation=2))
    client = provider.clients[0]
    assert client.starts == 1
    first_volume = client.volume_id
    other = volume.copy()
    other[0, 0, 0] += 1
    run(provider, request(other, [point((5, 5, 5))], generation=3))
    assert client.volume_id != first_volume and client.starts == 1
    assert r1.extra["volume_id"] == r2.extra["volume_id"] == first_volume
    provider.close()


# ------------------------------------------------------------------ failures
def test_cooperative_cancel(tmp_path, volume):
    provider = make_provider(tmp_path, delay_s=0.1, steps=200)
    provider.check_environment()
    cancel = threading.Event()
    threading.Timer(0.6, cancel.set).start()
    t0 = time.perf_counter()
    with pytest.raises(m2.InferenceFailed) as e:
        run(provider, request(volume, [point((5, 5, 5))]), cancel)
    assert e.value.code == P.E_CANCELLED and time.perf_counter() - t0 < 6
    assert provider.clients[0].worker_alive  # model stays loaded
    result, _ = run(provider, request(volume, [point((5, 5, 5))], generation=2))  # usable at once, same worker
    assert provider.clients[0].starts == 1
    assert np.array_equal(np.asarray(result.mask).astype(bool), ball((5, 5, 5)))
    provider.close()


def test_crash_then_restart(tmp_path, volume):
    provider = make_provider(tmp_path, crash_on_predict=True)
    provider.check_environment()
    with pytest.raises(m2.InferenceFailed) as e:
        run(provider, request(volume, [point((5, 5, 5))]))
    assert e.value.code == P.E_WORKER_EXITED and not provider.clients[0].worker_alive
    with pytest.raises(m2.InferenceFailed):
        run(provider, request(volume, [point((5, 5, 5))], generation=2))  # restarted, crashes again
    assert provider.clients[0].starts == 2
    provider.close()


def test_timeout_kills_the_worker(tmp_path, volume):
    provider = make_provider(tmp_path, delay_s=1.0, steps=30, predict_timeout_s=1.5)
    provider.check_environment()
    with pytest.raises(m2.InferenceFailed) as e:
        run(provider, request(volume, [point((5, 5, 5))]))
    assert e.value.code == P.E_TIMEOUT and not provider.clients[0].worker_alive
    provider.close()


def test_invalid_output_is_rejected(tmp_path, volume):
    provider = make_provider(tmp_path, bad_output="shape")
    provider.check_environment()
    with pytest.raises(m2.InferenceFailed) as e:
        run(provider, request(volume, [point((5, 5, 5))]))
    assert e.value.code == P.E_INVALID_OUTPUT
    provider.close()


def test_close_removes_temp_data_and_worker(tmp_path, volume):
    provider = make_provider(tmp_path)
    provider.check_environment()
    run(provider, request(volume, [point((5, 5, 5))]))
    client = provider.clients[0]
    proc = client._process._proc
    assert len(owned_dirs(tmp_path)) == 1
    provider.close()
    assert owned_dirs(tmp_path) == [] and proc.poll() is not None
    provider.close()  # idempotent
    result, _ = run(provider, request(volume, [point((5, 5, 5))], generation=2))  # next project: starts again
    assert client.starts == 2 and np.asarray(result.mask).sum() > 0
    provider.close()


def test_close_during_inference(tmp_path, volume):
    provider = make_provider(tmp_path, delay_s=0.2, steps=100, ignore_cancel=True)
    provider.check_environment()
    errors = []

    def job():
        try:
            run(provider, request(volume, [point((5, 5, 5))]))
        except m2.InferenceFailed as e:
            errors.append(e.code)

    t = threading.Thread(target=job)
    t.start()
    time.sleep(1.0)
    provider.close()  # project closed while the model runs
    t.join(20)
    assert not t.is_alive() and errors and errors[0] in (P.E_WORKER_EXITED, P.E_CANCELLED, P.E_MALFORMED)
    assert owned_dirs(tmp_path) == []


def test_prompts_payload_uses_voxels():
    p = point((3, 4, 5), positive=False)
    box = make_box_prompt((2.0, 3.0, 4.0), (0.0, 0.0, 1.0), SPACING, SHAPE)
    payload = m2.prompts_payload(AIPrompts(points=(p,), box=box))
    assert payload["points"] == [{"zyx": [3, 4, 5], "label": 0}]
    assert payload["box"] == {"min_zyx": [1, 0, 0], "max_zyx": [4, 6, 4]}
    assert P.check_prompts(payload, SHAPE) == payload
