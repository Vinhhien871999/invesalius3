# --------------------------------------------------------------------------
# E6b - TotalSegmentator provider (automatic structure segmentation, CT).
#
# Optional and lazy: this module imports only numpy and the standard
# library. TotalSegmentator, torch, nnunetv2 and nibabel are imported inside
# probe()/infer(), i.e. only after the user switches AI on. Nothing is ever
# installed or downloaded by the plugin (see _guard() below).
#
# API used (TotalSegmentator's official Python API,
# totalsegmentator.python_api.totalsegmentator): input may be a
# nibabel Nifti1Image; with output=None it returns the segmentation as a
# Nifti1Image on the INPUT grid (it reorients to canonical, predicts,
# then undoes the reorientation/resampling back to the input shape and
# affine); label values are the ids of
# totalsegmentator.map_to_binary.class_map["total"]; roi_subset restricts
# prediction to a list of class names; device is "gpu", "cpu" or
# "gpu:N"; fast selects the lower-resolution model. probe() re-checks the
# installed version's real signature before anything is used.
#
# Grid contract (docs/CT3D_ADVANCED_E6B_TOTALSEGMENTATOR_REPORT.md, "NIfTI
# affine"): Slice().matrix is (z, y, x). For a single-frame axial DICOM
# series InVesalius sorts slices with gdcm.IPPSorter (ascending along the
# slice normal) and flips each slice's rows on import
# (imagedata_utils.dcm2memmap: read_dcm_slice_as_np2(f)[::-1]). With the
# stored ImageOrientationPatient (Project().patient_orientation, LPS) row
# cosine r and column cosine c, the matrix axes therefore point, in LPS:
#     x (column index) -> r,  y (flipped row index) -> -c,  z -> r x c.
# The NIfTI array is the matrix transposed to (x, y, z) and its affine has
# those directions (converted LPS -> RAS) times the (x, y, z) spacing. The
# translation is 0: the plugin's grid origin is 0, and TotalSegmentator's
# output is mapped back by exact array transposition after checking that
# the returned affine and shape equal the input ones. Volumes whose
# patient orientation cannot be established are refused, never guessed.
# --------------------------------------------------------------------------
import contextlib
import importlib
import inspect
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

from ..provider import (
    MODE_FAST,
    MODE_STANDARD,
    OPTION_ACQUISITION,
    OPTION_MODE,
    OPTION_PATIENT_ORIENTATION,
    OPTION_STRUCTURE,
    REASON_API,
    REASON_DEPENDENCY,
    REASON_PACKAGE_MISSING,
    REASON_WEIGHTS,
    REQUEST_MODE_UNSUPPORTED,
    REQUEST_ORIENTATION_UNKNOWN,
    REQUEST_STRUCTURE_UNKNOWN,
    STAGE_MAPPING,
    STAGE_PREPARING,
    STAGE_RUNNING,
    AISegmentationProvider,
    check_request,
)
from ..types import AIInferenceResult, AIProviderInfo, Capability, DeviceKind

PROVIDER_ID = "totalsegmentator"
TASK = "total"

# Shared codes/keys live in provider.py (generic E6 contract).
PARAM_STRUCTURE = OPTION_STRUCTURE
PARAM_MODE = OPTION_MODE
PARAM_PATIENT_ORIENTATION = OPTION_PATIENT_ORIENTATION
PARAM_ACQUISITION = OPTION_ACQUISITION

REQUIRED_API_PARAMETERS = ("input", "output", "task", "roi_subset", "device")


class OrientationUnknown(ValueError):
    pass


class OutputGridMismatch(ValueError):
    pass


class WeightsNotReady(RuntimeError):
    pass


# ------------------------------------------------------------------ geometry
_LPS_TO_RAS = np.diag([-1.0, -1.0, 1.0])


def matrix_axis_directions_ras(patient_orientation):
    """Unit RAS directions of the InVesalius matrix x, y, z axes for a
    single-frame axial DICOM import (see module header)."""
    iop = np.asarray(patient_orientation, dtype=float).reshape(-1)
    if iop.shape != (6,) or not np.all(np.isfinite(iop)):
        raise OrientationUnknown(f"ImageOrientationPatient must be 6 finite values, got {patient_orientation!r}")
    row, col = iop[:3], iop[3:]
    if abs(np.linalg.norm(row) - 1) > 1e-3 or abs(np.linalg.norm(col) - 1) > 1e-3 or abs(row @ col) > 1e-3:
        raise OrientationUnknown(f"ImageOrientationPatient is not two orthonormal vectors: {patient_orientation!r}")
    normal = np.cross(row, col)
    return _LPS_TO_RAS @ row, _LPS_TO_RAS @ (-col), _LPS_TO_RAS @ normal


def nifti_affine(spacing_xyz, patient_orientation) -> np.ndarray:
    """Affine (RAS mm) of the NIfTI array to_nifti_data(Slice().matrix)."""
    dx, dy, dz = matrix_axis_directions_ras(patient_orientation)
    sx, sy, sz = (float(s) for s in spacing_xyz)
    if min(sx, sy, sz) <= 0:
        raise ValueError(f"spacing must be positive, got {spacing_xyz}")
    affine = np.eye(4)
    affine[:3, 0] = dx * sx
    affine[:3, 1] = dy * sy
    affine[:3, 2] = dz * sz
    return affine


def to_nifti_data(volume_zyx):
    """(z, y, x) -> NIfTI array axes (x, y, z). A view, no copy."""
    return np.transpose(np.asarray(volume_zyx), (2, 1, 0))


def from_nifti_data(data_xyz):
    return np.transpose(np.asarray(data_xyz), (2, 1, 0))


def extract_structure(seg_img, label_id: int, shape_zyx, expected_affine) -> np.ndarray:
    """Binary (z, y, x) mask of one label from TotalSegmentator's output,
    after proving the output is on the input grid. Never resamples,
    reshapes or flips to make it fit."""
    data = np.asanyarray(seg_img.dataobj)
    expected_shape = tuple(int(n) for n in shape_zyx)[::-1]
    if tuple(data.shape) != expected_shape:
        raise OutputGridMismatch(f"output shape {data.shape} != input {expected_shape}")
    if not np.allclose(np.asarray(seg_img.affine, dtype=float), expected_affine, atol=1e-3):
        raise OutputGridMismatch(f"output affine differs from the input affine:\n{seg_img.affine}\n{expected_affine}")
    return np.ascontiguousarray(from_nifti_data(data == int(label_id)))


# ------------------------------------------------------------------ provider
class TotalSegmentatorProvider(AISegmentationProvider):
    provider_id = PROVIDER_ID

    def __init__(self, modules: Optional[dict] = None, version: Optional[str] = None):
        """`modules`/`version` replace real imports - for tests only."""
        self._modules = modules
        self._version = version

    # ---- imports
    def _module(self, name):
        if self._modules is not None:
            if name not in self._modules:
                raise ImportError(f"No module named '{name}'")
            return self._modules[name]
        return importlib.import_module(name)

    def _installed(self) -> bool:
        if self._modules is not None:
            return "totalsegmentator" in self._modules
        import importlib.util

        return importlib.util.find_spec("totalsegmentator") is not None  # does not import it

    def _package_version(self) -> str:
        if self._version is not None:
            return self._version
        try:
            from importlib.metadata import version

            return version("TotalSegmentator")
        except Exception:
            return ""

    # ---- probe
    def _unavailable(self, code, detail, version=""):
        return AIProviderInfo(
            provider_id=PROVIDER_ID, display_name="TotalSegmentator", version=version, available=False,
            unavailable_reason=f"{code}: {detail}", capabilities=(Capability.AUTOMATIC,),
            supported_prompt_types=(), supported_devices=(), requires_weights=True,
        )

    def _class_map(self):
        return dict(self._module("totalsegmentator.map_to_binary").class_map[TASK])

    def _weights_status(self):
        """TotalSegmentator's own weights directory (get_weights_dir():
        $TOTALSEG_WEIGHTS_PATH, else $TOTALSEG_HOME_DIR/nnunet/results, else
        ~/.totalsegmentator/nnunet/results). Ready if it holds at least one
        downloaded TotalSegmentator dataset folder. The run itself is
        additionally guarded against downloading (_guard)."""
        weights_dir = Path(self._module("totalsegmentator.config").get_weights_dir())
        if not weights_dir.is_dir():
            return False, f"no weights directory at {weights_dir}"
        found = [p.name for p in weights_dir.iterdir()
                 if p.is_dir() and p.name.startswith("Dataset") and "TotalSegmentator" in p.name]
        return bool(found), f"{len(found)} TotalSegmentator weight folder(s) in {weights_dir}"

    def _cuda_available(self) -> bool:
        torch = self._module("torch")
        try:
            return bool(torch.cuda.is_available()) and int(torch.cuda.device_count()) > 0
        except Exception:
            return False

    def probe(self) -> AIProviderInfo:
        if not self._installed():
            return self._unavailable(REASON_PACKAGE_MISSING, "the TotalSegmentator package is not installed")
        version = self._package_version()
        try:
            api = self._module("totalsegmentator.python_api")
            self._module("nibabel")
            self._module("torch")
        except Exception as e:  # typically torch / nnunetv2 missing or broken
            return self._unavailable(REASON_DEPENDENCY, f"{type(e).__name__}: {e}", version)
        try:
            params = inspect.signature(api.totalsegmentator).parameters
        except Exception as e:
            return self._unavailable(REASON_API, f"cannot inspect totalsegmentator(): {e}", version)
        missing = [p for p in REQUIRED_API_PARAMETERS if p not in params]
        if missing:
            return self._unavailable(REASON_API, f"totalsegmentator() lacks parameters {missing}", version)
        try:
            structures = tuple(self._class_map().values())
        except Exception as e:
            return self._unavailable(REASON_API, f"no class map for task '{TASK}': {e}", version)
        try:
            ready, detail = self._weights_status()
        except Exception as e:
            ready, detail = False, f"cannot locate weights: {e}"
        if not ready:
            return self._unavailable(REASON_WEIGHTS, detail, version)
        devices = (DeviceKind.CPU, DeviceKind.CUDA) if self._cuda_available() else (DeviceKind.CPU,)
        modes = (MODE_STANDARD, MODE_FAST) if "fast" in params else (MODE_STANDARD,)
        return AIProviderInfo(
            provider_id=PROVIDER_ID, display_name="TotalSegmentator", version=version, available=True,
            capabilities=(Capability.AUTOMATIC,),  # no prompts; not interruptible (see infer)
            supported_prompt_types=(), supported_devices=devices, requires_weights=True,
            parameter_choices={PARAM_STRUCTURE: structures, PARAM_MODE: modes},
        )

    # ---- request
    def validate_request(self, request) -> Optional[str]:
        info = self.probe()
        code = check_request(info, request)
        if code is not None:
            return code
        options = request.options
        if options.get(PARAM_STRUCTURE) not in info.parameter_choices.get(PARAM_STRUCTURE, ()):
            return REQUEST_STRUCTURE_UNKNOWN
        if options.get(PARAM_MODE, MODE_STANDARD) not in info.parameter_choices.get(PARAM_MODE, ()):
            return REQUEST_MODE_UNSUPPORTED
        if str(options.get(PARAM_ACQUISITION, "")).upper() != "AXIAL":
            return REQUEST_ORIENTATION_UNKNOWN
        try:
            matrix_axis_directions_ras(options.get(PARAM_PATIENT_ORIENTATION))
        except OrientationUnknown:
            return REQUEST_ORIENTATION_UNKNOWN
        return None

    @staticmethod
    def ts_device(device_kind: str, cuda_available: bool) -> str:
        """E6 DeviceKind -> TotalSegmentator device string. AUTO prefers a
        usable CUDA device; CUDA without one is refused by validate_request
        (supported_devices), never silently turned into CPU."""
        if device_kind == DeviceKind.CUDA:
            if not cuda_available:
                raise ValueError("CUDA requested but no CUDA device is available")
            return "gpu"
        if device_kind == DeviceKind.AUTO and cuda_available:
            return "gpu"
        return "cpu"

    @contextlib.contextmanager
    def _guard(self):
        """While TotalSegmentator runs: its weight download function raises
        instead of downloading (the plugin never starts a download), and
        its usage-statistics upload is a no-op (inference stays local)."""

        def refuse_download(*args, **kwargs):
            raise WeightsNotReady(f"TotalSegmentator weights missing (task id {args[0] if args else '?'})")

        def no_usage_stats(*args, **kwargs):
            return None

        if self._modules is not None:
            candidates = [m for n, m in self._modules.items() if n.startswith("totalsegmentator")]
        else:
            candidates = [m for n, m in list(sys.modules.items()) if n.startswith("totalsegmentator") and m]
        saved = []
        for module in candidates:
            for name, replacement in (("download_pretrained_weights", refuse_download),
                                      ("send_usage_stats", no_usage_stats)):
                if hasattr(module, name):
                    saved.append((module, name, getattr(module, name)))
                    setattr(module, name, replacement)
        try:
            yield
        finally:
            for module, name, original in reversed(saved):
                setattr(module, name, original)

    # ---- inference (worker thread, via AIInferenceJobController)
    def infer(self, request, progress, cancel_event) -> AIInferenceResult:
        t0 = time.perf_counter()
        progress(None, STAGE_PREPARING)
        api = self._module("totalsegmentator.python_api")
        nib = self._module("nibabel")
        params = inspect.signature(api.totalsegmentator).parameters
        options = request.options
        structure = options[PARAM_STRUCTURE]
        fast = options.get(PARAM_MODE, MODE_STANDARD) == MODE_FAST
        class_map = self._class_map()
        label_id = next(i for i, name in class_map.items() if name == structure)
        cuda = self._cuda_available()
        device = self.ts_device(request.device, cuda)

        affine = nifti_affine(request.volume.spacing_xyz, options[PARAM_PATIENT_ORIENTATION])
        data = np.ascontiguousarray(to_nifti_data(request.volume.array))
        image = nib.Nifti1Image(data, affine)
        image.set_qform(affine, code=1)
        image.set_sform(affine, code=1)
        t_prepared = time.perf_counter()
        if cancel_event.is_set():  # the only point before the model where stopping is real
            return AIInferenceResult(mask=np.zeros(request.volume.shape_zyx, dtype=bool))

        progress(None, STAGE_RUNNING)
        kwargs = {"input": image, "output": None, "task": TASK, "roi_subset": [structure], "device": device}
        for name, value in (("fast", fast), ("quiet", True), ("ml", True)):
            if name in params:
                kwargs[name] = value
        with self._guard():
            output = api.totalsegmentator(**kwargs)
        if isinstance(output, tuple):  # (seg_img, stats) when statistics are on
            output = output[0]
        t_inferred = time.perf_counter()

        progress(None, STAGE_MAPPING)
        mask = extract_structure(output, label_id, request.volume.shape_zyx, affine)
        t_mapped = time.perf_counter()
        return AIInferenceResult(
            mask=mask, model_name=f"TotalSegmentator ({TASK})", model_version=self._package_version(),
            device_used=DeviceKind.CUDA if device.startswith("gpu") else DeviceKind.CPU,
            extra={
                "structure": structure, "label_id": int(label_id), "mode": MODE_FAST if fast else MODE_STANDARD,
                "ts_device": device, "input_conversion_s": t_prepared - t0,
                "inference_s": t_inferred - t_prepared, "output_mapping_s": t_mapped - t_inferred,
                "foreground_voxels": int(mask.sum()), "output_affine": np.asarray(output.affine).tolist(),
            },
        )

    def close(self) -> None:
        torch = sys.modules.get("torch") if self._modules is None else self._modules.get("torch")
        try:
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"ROI Viewer: TotalSegmentator close - {e}")


def create_provider() -> TotalSegmentatorProvider:
    return TotalSegmentatorProvider()
