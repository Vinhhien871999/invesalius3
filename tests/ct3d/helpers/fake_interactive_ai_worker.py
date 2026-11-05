# --------------------------------------------------------------------------
# FakeInteractiveAIWorker - TEST FIXTURE ONLY. Not MedSAM2, not a model:
# it runs the REAL tools/interactive_ai_runtime/worker.py protocol loop
# with a deterministic provider, so the host <-> worker protocol, temp
# files, cancellation, crash and lifecycle can be tested without a model.
# Its masks say NOTHING about segmentation quality.
#
#   positive point -> ball of `radius` voxels around it (union)
#   negative point -> ball removed
#   box            -> the result is restricted to the box (box alone: the
#                     whole box)
#
# provider_config (tests): radius, delay_s (per "slice" step, cancellable),
# steps, ignore_cancel, crash_on_predict, bad_output ("shape" | "values"),
# noise (print to stdout - must not corrupt the protocol), fail_probe.
#   python fake_interactive_ai_worker.py
# --------------------------------------------------------------------------
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "interactive_ai_runtime"))

import numpy as np  # noqa: E402

import worker  # noqa: E402


def ball(shape, center, radius):
    zz, yy, xx = np.ogrid[:shape[0], :shape[1], :shape[2]]
    z, y, x = center
    return (zz - z) ** 2 + (yy - y) ** 2 + (xx - x) ** 2 <= radius ** 2


def fake_candidate(shape, prompts, radius=3):
    mask = np.zeros(shape, dtype=bool)
    for p in prompts["points"]:
        if p["label"] == 1:
            mask |= ball(shape, p["zyx"], radius)
    for p in prompts["points"]:
        if p["label"] == 0:
            mask &= ~ball(shape, p["zyx"], radius)
    box = prompts.get("box")
    if box is not None:
        (z0, y0, x0), (z1, y1, x1) = box["min_zyx"], box["max_zyx"]
        inside = np.zeros(shape, dtype=bool)
        inside[z0:z1 + 1, y0:y1 + 1, x0:x1 + 1] = True
        mask = inside if not prompts["points"] else (mask & inside)
    return mask


class FakeInteractiveAIProvider:
    def __init__(self, config):
        self.config = dict(config)
        self.loaded = 0
        self.predictions = 0
        if self.config.get("noise"):
            print("fake provider: noisy library output on stdout")

    def probe(self):
        if self.config.get("fail_probe"):
            return {"name": "FakeInteractiveAIWorker", "available": False, "reason": "checkpoint_missing",
                    "detail": "fake: no checkpoint", "capabilities": {}, "devices": []}
        return {"name": "FakeInteractiveAIWorker", "version": "test-1", "available": True, "reason": "",
                "detail": "", "devices": ["cpu"], "checkpoint": "none (deterministic fixture)",
                "window_presets": ["soft_tissue", "lung", "bone"],
                "capabilities": {"positive_point": True, "negative_point": True, "box": True,
                                 "box_kind": "3d_voxel_box", "propagation_3d": True, "multi_object": False,
                                 "refinement": True, "cpu": True, "cuda": False}}

    def load_volume(self, array, meta, device):
        self.loaded += 1
        return {"loads": self.loaded, "pid": os.getpid()}

    def release_volume(self):
        pass

    def close(self):
        pass

    def predict(self, volume, meta, prompts, device, options, is_cancelled, progress):
        self.predictions += 1
        if self.config.get("crash_on_predict"):
            os._exit(3)
        steps = int(self.config.get("steps", 1))
        for i in range(steps):
            time.sleep(float(self.config.get("delay_s", 0)))
            if is_cancelled() and not self.config.get("ignore_cancel"):
                raise worker.WorkerError("cancelled", "fake cancelled")
            progress("running", (i + 1) / steps)
        if self.config.get("noise"):
            print("fake provider: more noise during predict")
            os.write(1, b"raw fd-1 noise\n")
        mask = fake_candidate(volume.shape, prompts, int(self.config.get("radius", 3)))
        bad = self.config.get("bad_output")
        if bad == "shape":
            mask = mask[:-1]
        elif bad == "values":
            mask = mask.astype(np.uint8) * 7
        return mask, {"predictions": self.predictions, "loads": self.loaded, "pid": os.getpid(),
                      "options": options}


if __name__ == "__main__":
    sys.exit(worker.main({"medsam2": FakeInteractiveAIProvider, "fake": FakeInteractiveAIProvider}))
