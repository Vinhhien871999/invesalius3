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
#   * logits > 0 (the predictor resizes them back to H x W bilinearly), both
#     passes OR-ed into the volume;
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
#   * images are float32 on the device (official: float64) - the model runs
#     under bfloat16 autocast either way;
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


def window_to_uint8(volume_hu, lower, upper, chunk=16) -> np.ndarray:
    """Official: clip, then (x - min) / (max - min) * 255 of the CLIPPED
    volume, uint8 (truncation, as np.uint8 casting in the script).
    The clipped min/max equal the raw min/max clipped to the window, so the
    float conversion runs per chunk of slices - same numbers, without a
    full-volume float32 copy (host RAM: 0543 = 315 MB less)."""
    vol = np.asarray(volume_hu)
    lo = min(max(float(vol.min()), float(lower)), float(upper))
    hi = min(max(float(vol.max()), float(lower)), float(upper))
    out = np.zeros(vol.shape, dtype=np.uint8)
    if hi <= lo:
        return out
    flat = vol.reshape((vol.shape[0], -1)) if vol.ndim > 1 else vol.reshape((1, -1))
    view = out.reshape(flat.shape)
    for c0 in range(0, flat.shape[0], chunk):
        clipped = np.clip(flat[c0:c0 + chunk].astype(np.float32), lower, upper)
        view[c0:c0 + chunk] = ((clipped - lo) / (hi - lo) * 255.0).astype(np.uint8)
    return out


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


def resize_slices_uint8(volume_uint8, size=IMAGE_SIZE) -> np.ndarray:
    """(D, H, W) uint8 -> (D, 3, size, size) uint8: the official
    resize_grayscale_to_rgb_and_resize (PIL "RGB", resize default filter)."""
    from PIL import Image

    d = volume_uint8.shape[0]
    out = np.empty((d, 3, size, size), dtype=np.uint8)
    for i in range(d):
        rgb = Image.fromarray(np.ascontiguousarray(volume_uint8[i])).convert("RGB").resize((size, size))
        out[i] = np.asarray(rgb).transpose(2, 0, 1)
    return out


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
    connectivity in 3D). Memory-lean (05/11/2026, real 0543 run ran out of
    host RAM): labels only inside the mask's bounding box, uint16 labels
    when the component count fits, component sizes counted on the
    foreground voxels only (no full-volume int64 copy)."""
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return mask
    nz = [np.flatnonzero(mask.any(axis=tuple(a for a in range(mask.ndim) if a != ax))) for ax in range(mask.ndim)]
    box = tuple(slice(int(i[0]), int(i[-1]) + 1) for i in nz)
    sub = mask[box]
    try:
        from scipy import ndimage

        structure = np.ones((3,) * sub.ndim, dtype=bool)
        try:
            labels = np.zeros(sub.shape, dtype=np.uint16)
            n = ndimage.label(sub, structure=structure, output=labels)
        except RuntimeError:  # more than 65535 components
            labels, n = ndimage.label(sub, structure=structure)
    except ImportError:
        from skimage import measure

        labels = measure.label(sub)
        n = int(labels.max())
    if n <= 1:
        return mask
    counts = np.bincount(labels[sub])
    counts[0] = 0
    out = np.zeros(mask.shape, dtype=bool)
    out[box] = labels == int(np.argmax(counts))
    return out


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
        self._prepared = {}  # window -> (D, 3, 512, 512) uint8, for the loaded volume
        self._state = None  # reusable model state of the loaded volume (see _session)
        # OFF by default (real app, 05/11/2026): on Windows/WDDM the ~3.9 GB of
        # VRAM the 0543 feature cache holds was also charged to system commit
        # (worker 8.6 GB vs 4.8 GB without it) and the machine ran out of RAM.
        # "cache_features": true in provider_config turns it on (repeats ~30-40 %
        # faster, identical candidates) where RAM/VRAM allow.
        self.cache_features = self.config.get("cache_features", False) is True
        self.cache_min_free_mb = float(self.config.get("cache_min_free_mb", 1024))
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

    # ------------------------------------------------------------- volume / state
    def load_volume(self, array, meta, device):
        self.release_volume()
        self._volume = array
        return {"shape_zyx": list(array.shape)}

    def _prepared_images(self, window):
        if window not in self._prepared:
            t0 = time.perf_counter()
            volume_u8 = window_to_uint8(to_model_rows(self._volume, self.flip_rows), *window)
            # uint8 on the host (1/4 of float32); normalised once on the
            # device, as the official script does (/255, mean/std on GPU).
            self._prepared = {window: resize_slices_uint8(volume_u8)}  # only the current window is kept
            self.timings["preprocess_s"] = time.perf_counter() - t0
        return self._prepared[window]

    def _session(self, window, dev, predictor):
        """The reusable model state of the loaded volume for (window, device):
        the normalised image tensor on the device, ONE SAM2 inference_state
        (reset before every prediction - the prompts are always replayed in
        full from the canonical prompt set) and the per-slice image-feature
        cache. Built once; refinements reuse it."""
        import torch

        key = (window, dev)
        if self._state is not None and self._state["key"] == key:
            self.timings["state_reused"] = True
            return self._state
        self._drop_state()
        t0 = time.perf_counter()
        images = self._prepared_images(window)
        tensor = torch.empty(images.shape, dtype=torch.float32, device=dev)
        mean = torch.tensor(IMAGENET_MEAN, dtype=torch.float32, device=dev)[:, None, None]
        std = torch.tensor(IMAGENET_STD, dtype=torch.float32, device=dev)[:, None, None]
        for c0 in range(0, images.shape[0], 32):
            chunk = torch.from_numpy(images[c0:c0 + 32]).to(dev).float() / 255.0
            tensor[c0:c0 + 32] = (chunk - mean) / std
        init_kwargs = {}
        if self.offload_video and "offload_video_to_cpu" in inspect.signature(predictor.init_state).parameters:
            init_kwargs["offload_video_to_cpu"] = True
        nz, ny, nx = self._volume.shape
        state = predictor.init_state(tensor, ny, nx, **init_kwargs)
        self._state = {"key": key, "tensor": tensor, "state": state, "features": {}, "cache_full": False}
        self._install_feature_cache(predictor)
        self.timings["state_prep_s"] = time.perf_counter() - t0
        self.timings["state_reused"] = False
        return self._state

    def _install_feature_cache(self, predictor):
        """SAM2's _get_image_feature keeps ONE frame's features
        (sam2_video_predictor_npz.py: "we can use an LRU cache for more frames
        in the future"). The wrapper keeps every frame's backbone output for
        the current session and hands it to the ORIGINAL method through
        inference_state["cached_features"], so the model code is unchanged
        and the features are the same tensors it would compute."""
        if not self.cache_features or getattr(predictor, "_roi_viewer_original_get_image_feature", None):
            return
        original = predictor._get_image_feature
        provider = self

        def cached(inference_state, frame_idx, batch_size):
            session = provider._state
            if session is not None and session["state"] is inference_state:
                entry = session["features"].get(frame_idx)
                if entry is None:
                    result = original(inference_state, frame_idx, batch_size)
                    computed = inference_state["cached_features"].get(frame_idx)
                    if computed is not None and not session["cache_full"]:
                        session["features"][frame_idx] = computed
                        provider._check_cache_memory(session)
                    return result
                inference_state["cached_features"] = {frame_idx: entry}
            return original(inference_state, frame_idx, batch_size)

        predictor._roi_viewer_original_get_image_feature = original
        predictor._get_image_feature = cached

    def _check_cache_memory(self, session):
        """Stop caching more frames when free GPU memory gets low."""
        try:
            import torch

            if torch.cuda.is_available() and session["key"][1] == "cuda":
                free, _total = torch.cuda.mem_get_info()
                if free < self.cache_min_free_mb * 2 ** 20:
                    session["cache_full"] = True
        except Exception:
            session["cache_full"] = True

    def _drop_state(self):
        self._state = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def release_volume(self):
        self._drop_state()
        self._volume = None
        self._prepared = {}

    def close(self):
        self.release_volume()
        self._predictors = {}

    # ------------------------------------------------------------- predict
    def _add_frame_prompts(self, predictor, state, z, f):
        return predictor.add_new_points_or_box(
            state, frame_idx=z, obj_id=1,
            points=np.asarray(f["points"], dtype=np.float32) if f["points"] else None,
            labels=np.asarray(f["labels"], dtype=np.int32) if f["labels"] else None,
            box=np.asarray(f["box"], dtype=np.float32) if f["box"] is not None else None)

    def _fast_2d(self, predictor, state, prompts, z, shape):
        """Current-frame-only prediction (no propagation): the mask the model
        gives for slice z from the prompts on slice z. Returns the NATIVE
        (y, x) bool mask."""
        frames, _ = map_prompts(prompts, shape, self.flip_rows)  # the same per-slice inputs the 3D run uses
        predictor.reset_state(state)
        if z not in frames:
            return None
        _, _, masks = self._add_frame_prompts(predictor, state, z, frames[z])
        model_rows = (masks[0] > 0.0).cpu().numpy()[0]
        predictor.reset_state(state)
        return model_rows[::-1, :] if self.flip_rows else model_rows

    def predict(self, volume, meta, prompts, device, options, is_cancelled, progress):
        import torch

        from smart_prompt import POLICY_POINT_FIRST, STRATEGY_FAST_2D, box_prompt, initial_prompt

        if any(p["label"] == 0 for p in prompts.get("points") or []) and not self.allow_negative:
            raise _error("prompt_unsupported", "negative points are not enabled for MedSAM2")
        try:
            window = resolve_window(options.get("hu_window"))
        except (TypeError, ValueError) as e:
            raise _error("bad_request", str(e))
        scope = options.get("scope", "volume")
        if scope not in ("volume", "slice"):
            raise _error("bad_request", f"unknown scope {scope!r}")
        dev = self._device(device)
        nz, ny, nx = volume.shape
        t_start = time.perf_counter()
        progress("preparing")
        predictor = self._predictor(dev)
        if dev == "cuda":
            torch.cuda.reset_peak_memory_stats()
        details = {"window": list(window), "device": dev, "scope": scope, "flip_rows_to_dicom": self.flip_rows,
                   "checkpoint": Path(self.checkpoint).name, "model_config": self.model_config,
                   "model_version": repo_commit(self.repo_path) or ""}
        positives = [p for p in prompts.get("points") or [] if p["label"] == 1]
        autocast = (torch.autocast("cuda", dtype=torch.bfloat16) if dev == "cuda"
                    else torch.autocast("cpu", enabled=False))
        try:
            with torch.inference_mode(), autocast:
                session = self._session(window, dev, predictor)
                state = session["state"]
                details["state_reused"] = self.timings.get("state_reused")
                details["state_prep_s"] = None if details["state_reused"] else self.timings.get("state_prep_s")

                if scope == "slice":
                    # quick provisional feedback on one slice (never the final candidate)
                    z = int(options.get("target_z", positives[-1]["zyx"][0] if positives
                                        else (prompts.get("box") or {}).get("min_zyx", [0])[0]))
                    t0 = time.perf_counter()
                    m2d = self._fast_2d(predictor, state, prompts, z, volume.shape)
                    seg = np.zeros((nz, ny, nx), dtype=bool)
                    if m2d is not None:
                        seg[z] = m2d
                    details.update(slice_z=z, fast_2d_s=time.perf_counter() - t0, total_s=time.perf_counter() - t_start)
                    return seg.astype(np.uint8), details

                # one-click smart initial prompt (only without an operator box)
                if options.get("smart_init") and prompts.get("box") is None and positives:
                    anchor = positives[0]["zyx"]
                    t0 = time.perf_counter()
                    m2d = self._fast_2d(predictor, state, prompts, int(anchor[0]), volume.shape)
                    box, strategy, sd = initial_prompt(
                        m2d, (anchor[1], anchor[2]), (ny, nx),
                        policy=str(options.get("smart_policy", POLICY_POINT_FIRST)),
                        min_fast_2d_pixels=int(options.get("smart_min_fast_2d_pixels", 400)),
                        padding_fraction=float(options.get("smart_padding_fraction", 0.1)),
                        min_padding_px=int(options.get("smart_min_padding_px", 2)),
                        fallback_half_px=int(options.get("smart_fallback_half_px", 64)))
                    if box is not None:
                        prompts = dict(prompts, box=box_prompt(anchor[0], box))
                    details["auto_box"] = {"strategy": strategy, "z": int(anchor[0]),
                                           "box_yx": None if box is None else list(box),
                                           "fast_2d_s": time.perf_counter() - t0, **sd}
                    details["auto_box_is_fast_2d"] = strategy == STRATEGY_FAST_2D

                frames, z_range = map_prompts(prompts, volume.shape, self.flip_rows)
                first, last = min(frames), max(frames)
                seg = np.zeros((nz, ny, nx), dtype=bool)
                progress("running")
                t0 = time.perf_counter()
                predictor.reset_state(state)
                for z, f in sorted(frames.items()):
                    self._add_frame_prompts(predictor, state, z, f)
                done = 0
                # Both passes OR into the volume, as the official script
                # (segs_3D[idx, logits > 0] = 1).
                for frame_idx, _obj_ids, logits in predictor.propagate_in_video(state):
                    seg[frame_idx] |= (logits[0] > 0.0).cpu().numpy()[0]
                    done += 1
                    if is_cancelled():
                        raise _error("cancelled", "cancelled during forward propagation")
                    progress("running", done / nz)
                predictor.reset_state(state)
                for z, f in sorted(frames.items()):
                    self._add_frame_prompts(predictor, state, z, f)
                for frame_idx, _obj_ids, logits in predictor.propagate_in_video(state, reverse=True):
                    seg[frame_idx] |= (logits[0] > 0.0).cpu().numpy()[0]
                    done += 1
                    if is_cancelled():
                        raise _error("cancelled", "cancelled during reverse propagation")
                    progress("running", min(1.0, done / nz))
                predictor.reset_state(state)
                details["inference_s"] = time.perf_counter() - t0
                details["cached_frames"] = len(session["features"])
        except torch.cuda.OutOfMemoryError as e:
            self._drop_state()
            raise _error("cuda_oom", str(e))
        progress("mapping")
        t0 = time.perf_counter()
        if z_range is not None:
            seg[:z_range[0]] = False
            seg[z_range[1] + 1:] = False
        if self.keep_largest:
            seg = largest_component(seg)
        mask = to_model_rows(seg, self.flip_rows).astype(np.uint8)
        details.update(key_frames=sorted(frames), box_slice_range=z_range, largest_component=self.keep_largest,
                       first_last_frame=[first, last], mapping_s=time.perf_counter() - t0,
                       model_load_s=self.timings.get("model_load_s"), preprocess_s=self.timings.get("preprocess_s"),
                       total_s=time.perf_counter() - t_start)
        if dev == "cuda":
            details["peak_vram_mb"] = torch.cuda.max_memory_allocated() / 2 ** 20
        return np.ascontiguousarray(mask), details
