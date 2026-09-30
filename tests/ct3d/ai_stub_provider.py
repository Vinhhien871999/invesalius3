# --------------------------------------------------------------------------
# TEST-ONLY AI provider for the E6 orchestration tests. Deterministic, no
# model, no framework. It is never registered in production
# (plugins/roi_viewer/core/ai/registry.KNOWN_PROVIDER_MODULES is empty) and
# a PASS obtained with it says nothing about real AI inference.
#
# Output: the box prompt's voxels (inclusive), plus a 3x3x3 block around
# each positive point, minus each negative point's voxel.
# --------------------------------------------------------------------------
import threading

import numpy as np

from plugins.roi_viewer.core.ai.provider import AISegmentationProvider
from plugins.roi_viewer.core.ai.types import (
    AIInferenceResult,
    AIProviderInfo,
    Capability,
    DeviceKind,
    PromptType,
)


def stub_candidate(shape_zyx, prompts) -> np.ndarray:
    mask = np.zeros(shape_zyx, dtype=bool)
    if prompts.box is not None:
        (z0, y0, x0), (z1, y1, x1) = prompts.box.voxel_min_zyx, prompts.box.voxel_max_zyx
        mask[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1] = True
    for p in prompts.points:
        z, y, x = p.voxel_zyx
        if p.positive:
            mask[max(z - 1, 0):z + 2, max(y - 1, 0):y + 2, max(x - 1, 0):x + 2] = True
    for p in prompts.points:
        if not p.positive:
            mask[p.voxel_zyx] = False
    return mask


class StubAIProvider(AISegmentationProvider):
    def __init__(self, provider_id="stub", available=True, capabilities=(Capability.PROMPTS, Capability.INTERRUPTIBLE),
                 prompt_types=PromptType.SUPPORTED, devices=(DeviceKind.CPU,), requires_weights=False,
                 reason="", block=False, fail=False, output=None):
        self.provider_id = provider_id
        self._info = AIProviderInfo(
            provider_id=provider_id, display_name=f"Stub {provider_id}", version="0-test",
            available=available, unavailable_reason=reason, capabilities=tuple(capabilities),
            supported_prompt_types=tuple(prompt_types), supported_devices=tuple(devices),
            requires_weights=requires_weights,
        )
        self.release = threading.Event()
        if not block:
            self.release.set()
        self.fail = fail
        self.output = output  # callable(request) -> mask, overrides the default candidate
        self.calls = 0
        self.closed = 0
        self.seen_cancel = None
        self.requests = []

    def probe(self):
        return self._info

    def infer(self, request, progress, cancel_event):
        self.calls += 1
        self.requests.append(request)
        progress(0.25, "started")
        self.release.wait(10)
        self.seen_cancel = cancel_event.is_set()
        if self.fail:
            raise RuntimeError("stub provider failure")
        progress(1.0, "done")
        if self.output is not None:
            mask = self.output(request)
        else:
            mask = stub_candidate(request.volume.shape_zyx, request.prompts)
        return AIInferenceResult(mask=mask, model_name="stub-model", model_version="1",
                                 device_used=DeviceKind.CPU)

    def close(self):
        self.closed += 1


class QueueDispatch:
    """Stands in for wx.CallAfter: collects calls from the worker thread and
    runs them when the test calls pump() (on the test thread)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = []

    def __call__(self, fn, *args):
        with self._lock:
            self._calls.append((fn, args))

    def pump(self):
        ran = 0
        while True:
            with self._lock:
                if not self._calls:
                    return ran
                fn, args = self._calls.pop(0)
            fn(*args)
            ran += 1
