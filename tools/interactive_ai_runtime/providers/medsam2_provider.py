# --------------------------------------------------------------------------
# MedSAM2 provider for the ROI Viewer interactive-AI worker.
#
# Runs ONLY in the separate MedSAM2 environment. Source audited 05/11/2026
# (docs/CT3D_INTERACTIVE_AI_ARCHITECTURE.md, "Model audit"):
#   bowang-lab/MedSAM2 main @ 332f30d420f1d1b08e2a79b3ae6a602458808383
#   (2025-07-11), Apache-2.0; checkpoints wanglab/MedSAM2 on Hugging Face
#   (MedSAM2_latest.pt recommended; weights card: research/education use).
#
# What this provider reproduces from medsam2_infer_3D_CT.py:
#   * volume (z, y, x) HU, clipped to a CT window [lower, upper];
#   * scaled with the clipped volume's own min/max to 0..255, uint8;
#   * every slice -> PIL "RGB" -> resize((512, 512)) (PIL default filter),
#     /255, ImageNet mean (0.485, 0.456, 0.406) / std (0.229, 0.224, 0.225);
#   * build_sam2_video_predictor_npz(config, checkpoint), init_state(
#     images, H, W), add_new_points_or_box(frame_idx=key, obj_id=1, ...),
#     propagate_in_video forward, reset_state, the same prompts again,
#     propagate_in_video(reverse=True);
#   * logits > 0 (the predictor resizes them back to H x W bilinearly);
#   * largest connected component (getLargestCC, full connectivity).
# Deviations, all explicit (provider_config):
#   * the window is chosen by the operator (preset or [lower, upper]); the
#     official script reads a per-lesion DICOM window from its dataset CSV.
#     Presets are the paper's: soft tissue W400/L40, lung W1500/L-600,
#     bone W1800/L400;
#   * "flip_rows_to_dicom" (default true): InVesalius stores each axial
#     slice with its rows reversed relative to the DICOM pixel data
#     (imagedata_utils.dcm2memmap: [::-1]); the model sees the DICOM row
#     order, and the mask is flipped back - an exact index reversal;
#   * prompts on several slices (official: one key slice): every slice with
#     prompts is a conditioning frame; forward from the first, reverse from
#     the last;
#   * a 3D box (two corners on different slices) becomes the 2D box on its
#     middle slice, and the result is limited to the box's slice range.
#     A box set on a single slice propagates through the whole volume,
#     as in the official script.
# Prompt support declared (no guessing): box YES (the official CT path),
# positive points YES (the official RECIST script's labels = 1 points),
# negative points only when provider_config "allow_negative_points" is true
# - SAM2's API takes label 0, but no official MedSAM2 path uses it.
# --------------------------------------------------------------------------
import inspect
import sys
import time
from pathlib import Path

import numpy as np

IMAGE_SIZE = 512
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DEFAULT_MODEL_CONFIG = "configs/sam2.1_hiera_t512.yaml"
WINDOW_PRESETS = {
    "soft_tissue": (-160.0, 240.0),  # W400 / L40
    "lung": (-1350.0, 150.0),  # W1500 / L-600
    "bone": (-500.0, 1300.0),  # W1800 / L400
}
DEFAULT_WINDOW = "soft_tissue"
AUDITED_COMMIT = "332f30d420f1d1b08e2a79b3ae6a602458808383"


def _error(code, message):
    from worker import WorkerError

    return WorkerError(code, message)


# ---------------------------------------------------------------- numpy only
def resolve_window(value):
    if value is None:
        value = DEFAULT_WINDOW
    if isinstance(value, str):
        if value not in WINDOW_PRESETS:
            raise ValueError(f"unknown window preset {value!r}")
        return WINDOW_PRESETS[value]
    lower, upper = (float(v) for v in value)
    if not upper > lower:
        raise ValueError("window upper must be > lower")
    return lower, upper


def window_to_uint8(volume_hu, lower, upper) -> np.ndarray:
    """Official: clip, then (x - min) / (max - min) * 255 of the CLIPPED
    volume, uint8 (truncation, as np.uint8 casting in the script)."""
    clipped = np.clip(np.asarray(volume_hu, dtype=np.float32), lower, upper)
    lo, hi = float(clipped.min()), float(clipped.max())
    if hi <= lo:
        return np.zeros(clipped.shape, dtype=np.uint8)
    return ((clipped - lo) / (hi - lo) * 255.0).astype(np.uint8)


def to_model_rows(volume_zyx, flip_rows: bool):
    return volume_zyx[:, ::-1, :] if flip_rows else volume_zyx


def map_prompts(prompts, shape_zyx, flip_rows: bool):
    """Protocol prompts (voxel z, y, x) -> per-frame SAM2 inputs in the
    model's pixel frame: {z: {"points": [[x, y]], "labels": [..], "box":
    [x0, y0, x1, y1] | None}}, plus the box's slice range (or None)."""
    nz, ny, nx = shape_zyx

    def row(y):
        return (ny - 1 - y) if flip_rows else y

    frames = {}
    for p in prompts.get("points") or []:
        z, y, x = p["zyx"]
        f = frames.setdefault(int(z), {"points": [], "labels": [], "box": None})
        f["points"].append([float(x), float(row(y))])
        f["labels"].append(int(p["label"]))
    z_range = None
    box = prompts.get("box")
    if box is not None:
        (z0, y0, x0), (z1, y1, x1) = box["min_zyx"], box["max_zyx"]
        key = (int(z0) + int(z1)) // 2
        r0, r1 = sorted((row(y0), row(y1)))
        f = frames.setdefault(key, {"points": [], "labels": [], "box": None})
        f["box"] = [float(x0), float(r0), float(x1), float(r1)]
        if z1 > z0:
            z_range = (int(z0), int(z1))
    return frames, z_range


def preprocess_slices(volume_uint8, size=IMAGE_SIZE) -> np.ndarray:
    """(D, H, W) uint8 -> (D, 3, size, size) float32, as the official
    resize_grayscale_to_rgb_and_resize + /255 + ImageNet normalisation."""
    from PIL import Image

    d = volume_uint8.shape[0]
    out = np.empty((d, 3, size, size), dtype=np.float32)
    mean = np.asarray(IMAGENET_MEAN, dtype=np.float32)[:, None, None]
    std = np.asarray(IMAGENET_STD, dtype=np.float32)[:, None, None]
    for i in range(d):
        rgb = Image.fromarray(np.ascontiguousarray(volume_uint8[i])).convert("RGB").resize((size, size))
        arr = np.asarray(rgb, dtype=np.float32).transpose(2, 0, 1) / 255.0
        out[i] = (arr - mean) / std
    return out


def largest_component(mask) -> np.ndarray:
    """getLargestCC equivalent (skimage measure.label default = full
    connectivity in 3D)."""
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return mask
    try:
        from scipy import ndimage

        labels, n = ndimage.label(mask, structure=np.ones((3, 3, 3), dtype=bool))
    except ImportError:
        from skimage import measure

        labels = measure.label(mask)
        n = int(labels.max())
    if n <= 1:
        return mask
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    return labels == int(np.argmax(counts))


def repo_commit(repo_path):
    """HEAD commit of a MedSAM2 git checkout, read from .git (no git call)."""
    try:
        git = Path(repo_path) / ".git"
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            ref_file = git / ref
            if ref_file.is_file():
                return ref_file.read_text().strip()
            packed = git / "packed-refs"
            for line in packed.read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0]
            return ""
        return head
    except OSError:
        return ""


# ---------------------------------------------------------------- provider
class MedSAM2Provider:
    def __init__(self, config):
        self.config = dict(config)
        self.repo_path = self.config.get("repo_path") or ""
        self.checkpoint = self.config.get("checkpoint") or ""
        self.model_config = self.config.get("model_config") or DEFAULT_MODEL_CONFIG
        self.allow_negative = self.config.get("allow_negative_points") is True
        self.flip_rows = self.config.get("flip_rows_to_dicom", True) is not False
        self.keep_largest = self.config.get("largest_component", True) is not False
        self.offload_video = self.config.get("offload_video_to_cpu") is True
        self._predictors = {}  # device -> predictor (loaded once, kept)
        self._volume = None
        self._prepared = {}  # window -> (D, 3, 512, 512) float32, for the loaded volume
        self.timings = {}
        if self.repo_path and self.repo_path not in sys.path:
            sys.path.insert(0, self.repo_path)

    # ------------------------------------------------------------- probe
    def probe(self):
        info = {"name": "MedSAM2", "version": "", "available": False, "reason": "", "detail": "",
                "capabilities": self.capabilities(cuda=False), "devices": [],
                "checkpoint": Path(self.checkpoint).name if self.checkpoint else "",
                "model_config": self.model_config, "window_presets": list(WINDOW_PRESETS),
                "audited_commit": AUDITED_COMMIT}
        info["version"] = repo_commit(self.repo_path) if self.repo_path else ""
        try:
            import torch
        except Exception as e:
            info.update(reason="dependency_missing", detail=f"torch: {e}")
            return info
        try:
            import importlib

            build_sam = importlib.import_module("sam2.build_sam")
            if not hasattr(build_sam, "build_sam2_video_predictor_npz"):
                raise ImportError("sam2.build_sam has no build_sam2_video_predictor_npz (not the MedSAM2 fork?)")
        except Exception as e:
            info.update(reason="dependency_missing", detail=f"sam2 (MedSAM2): {e}")
            return info
        if not self.checkpoint or not Path(self.checkpoint).is_file():
            info.update(reason="checkpoint_missing", detail=f"checkpoint not found: {self.checkpoint!r}")
            return info
        cuda = bool(torch.cuda.is_available())
        devices = ["cpu"] + (["cuda"] if cuda else [])
        info.update(available=True, devices=devices, capabilities=self.capabilities(cuda),
                    torch=torch.__version__, cuda_device=torch.cuda.get_device_name(0) if cuda else "")
        return info

    def capabilities(self, cuda):
        return {"positive_point": True, "negative_point": self.allow_negative, "box": True,
                "box_kind": "2d_key_slice_with_slice_range", "propagation_3d": True, "multi_object": False,
                "refinement": True, "cpu": True, "cuda": bool(cuda)}

    # ------------------------------------------------------------- model
    def _device(self, requested):
        import torch

        if requested == "cuda":
            if not torch.cuda.is_available():
                raise _error("cuda_unavailable", "CUDA was selected but torch sees no CUDA device")
            return "cuda"
        if requested == "cpu":
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _predictor(self, device):
        if device in self._predictors:
            return self._predictors[device]
        if not self.checkpoint or not Path(self.checkpoint).is_file():
            raise _error("checkpoint_missing", f"checkpoint not found: {self.checkpoint!r}")
        try:
            from sam2.build_sam import build_sam2_video_predictor_npz

            t0 = time.perf_counter()
            kwargs = {}
            if "device" in inspect.signature(build_sam2_video_predictor_npz).parameters:
                kwargs["device"] = device
            predictor = build_sam2_video_predictor_npz(self.model_config, self.checkpoint, **kwargs)
            if not kwargs:
                predictor = predictor.to(device)
            self.timings["model_load_s"] = time.perf_counter() - t0
        except Exception as e:
            if "out of memory" in str(e).lower():
                raise _error("cuda_oom", f"model load: {e}")
            raise _error("model_load_failed", f"{type(e).__name__}: {e}")
        self._predictors = {device: predictor}  # one resident model
        return predictor

    # ------------------------------------------------------------- volume
    def load_volume(self, array, meta, device):
        self.release_volume()
        self._volume = array
        return {"shape_zyx": list(array.shape)}

    def _prepared_images(self, window):
        if window not in self._prepared:
            t0 = time.perf_counter()
            volume_u8 = window_to_uint8(to_model_rows(self._volume, self.flip_rows), *window)
            self._prepared = {window: preprocess_slices(volume_u8)}  # only the current window is kept
            self.timings["preprocess_s"] = time.perf_counter() - t0
        return self._prepared[window]

    def release_volume(self):
        self._volume = None
        self._prepared = {}
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def close(self):
        self.release_volume()
        self._predictors = {}

    # ------------------------------------------------------------- predict
    def predict(self, volume, meta, prompts, device, options, is_cancelled, progress):
        import torch

        if any(p["label"] == 0 for p in prompts.get("points") or []) and not self.allow_negative:
            raise _error("prompt_unsupported", "negative points are not enabled for MedSAM2")
        try:
            window = resolve_window(options.get("hu_window"))
        except (TypeError, ValueError) as e:
            raise _error("bad_request", str(e))
        dev = self._device(device)
        nz, ny, nx = volume.shape
        frames, z_range = map_prompts(prompts, volume.shape, self.flip_rows)
        progress("preparing")
        images = self._prepared_images(window)
        predictor = self._predictor(dev)
        if dev == "cuda":
            torch.cuda.reset_peak_memory_stats()
        seg = np.zeros((nz, ny, nx), dtype=bool)
        first, last = min(frames), max(frames)
        t0 = time.perf_counter()
        autocast = (torch.autocast("cuda", dtype=torch.bfloat16) if dev == "cuda"
                    else torch.autocast("cpu", enabled=False))
        try:
            with torch.inference_mode(), autocast:
                tensor = torch.from_numpy(images).to(dev)
                init_kwargs = {}
                if self.offload_video and "offload_video_to_cpu" in inspect.signature(predictor.init_state).parameters:
                    init_kwargs["offload_video_to_cpu"] = True
                state = predictor.init_state(tensor, ny, nx, **init_kwargs)

                def add_prompts():
                    for z, f in sorted(frames.items()):
                        predictor.add_new_points_or_box(
                            state, frame_idx=z, obj_id=1,
                            points=np.asarray(f["points"], dtype=np.float32) if f["points"] else None,
                            labels=np.asarray(f["labels"], dtype=np.int32) if f["labels"] else None,
                            box=np.asarray(f["box"], dtype=np.float32) if f["box"] is not None else None)

                progress("running")
                add_prompts()
                done = 0
                for frame_idx, _obj_ids, logits in predictor.propagate_in_video(state):
                    seg[frame_idx] = (logits[0] > 0.0).cpu().numpy()[0]
                    done += 1
                    if is_cancelled():
                        raise _error("cancelled", "cancelled during forward propagation")
                    progress("running", done / nz)
                predictor.reset_state(state)
                add_prompts()
                for frame_idx, _obj_ids, logits in predictor.propagate_in_video(state, reverse=True):
                    if frame_idx < first:
                        seg[frame_idx] = (logits[0] > 0.0).cpu().numpy()[0]
                    done += 1
                    if is_cancelled():
                        raise _error("cancelled", "cancelled during reverse propagation")
                    progress("running", min(1.0, done / nz))
                predictor.reset_state(state)
                del tensor
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            raise _error("cuda_oom", str(e))
        inference_s = time.perf_counter() - t0
        progress("mapping")
        if z_range is not None:
            seg[:z_range[0]] = False
            seg[z_range[1] + 1:] = False
        if self.keep_largest:
            seg = largest_component(seg)
        mask = to_model_rows(seg, self.flip_rows).astype(np.uint8)
        details = {"window": list(window), "device": dev, "key_frames": sorted(frames), "box_slice_range": z_range,
                   "flip_rows_to_dicom": self.flip_rows, "largest_component": self.keep_largest,
                   "inference_s": inference_s, "model_load_s": self.timings.get("model_load_s"),
                   "preprocess_s": self.timings.get("preprocess_s"), "checkpoint": Path(self.checkpoint).name,
                   "model_config": self.model_config, "model_version": repo_commit(self.repo_path) or "",
                   "first_last_frame": [first, last]}
        if dev == "cuda":
            details["peak_vram_mb"] = torch.cuda.max_memory_allocated() / 2 ** 20
        return np.ascontiguousarray(mask), details
