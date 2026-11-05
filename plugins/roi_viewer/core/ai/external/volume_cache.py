# --------------------------------------------------------------------------
# Temporary data and volume identity for the interactive-AI runtime.
#
# * One private directory per runtime session, created with
#   tempfile.mkdtemp (random name, owner-only permissions on POSIX) and the
#   prefix DIR_PREFIX. A marker file MARKER_NAME inside it is what makes it
#   "ours": cleanup_abandoned() only ever deletes directories that have BOTH
#   the prefix and the marker, are directly inside the temp root and are
#   older than the given age - never anything else.
# * Files: volume.npy (the CT exactly as Slice().matrix, (z, y, x), plain
#   .npy so the worker can memory-map it), metadata.json (shape, dtype,
#   spacing, orientation, fingerprint - no patient name/ID/study text), and
#   candidate_<request>.npy written by the worker. No DICOM copy, no patient
#   data in any file name.
# * fingerprint(): deterministic id of (shape, dtype, spacing, orientation,
#   content). The worker caches its loaded volume / model state per
#   fingerprint, and a candidate is only accepted for the volume it was
#   computed on.
# --------------------------------------------------------------------------
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path, PureWindowsPath
from typing import Optional

import numpy as np

DIR_PREFIX = "roiviewer-iai-"
MARKER_NAME = ".roi_viewer_interactive_ai"
ABANDONED_AGE_SECONDS = 24 * 3600
VOLUME_FILE = "volume.npy"
METADATA_FILE = "metadata.json"

PATH_STYLE_NATIVE = "native"
PATH_STYLE_WSL = "wsl"


def fingerprint(array, spacing_xyz, orientation=None) -> str:
    """blake2b over the geometry header and the raw voxel bytes."""
    arr = np.ascontiguousarray(np.asarray(array))
    h = hashlib.blake2b(digest_size=16)
    header = {
        "shape": list(arr.shape),
        "dtype": arr.dtype.str,
        "spacing": [round(float(s), 9) for s in spacing_xyz],
        "orientation": None if orientation is None else [round(float(v), 9) for v in orientation],
    }
    h.update(json.dumps(header, sort_keys=True).encode("ascii"))
    h.update(memoryview(arr).cast("B"))
    return h.hexdigest()


def to_worker_path(path, style: str = PATH_STYLE_NATIVE) -> str:
    """Host path -> the path the worker must open. "wsl": a Windows drive
    path D:\\a\\b becomes /mnt/d/a/b (WSL's default automount)."""
    path = str(path)
    if style == PATH_STYLE_NATIVE:
        return path
    if style == PATH_STYLE_WSL:
        p = PureWindowsPath(path)
        if not p.drive or not p.drive.endswith(":"):
            raise ValueError(f"cannot map {path!r} to a WSL path")
        return "/mnt/" + p.drive[0].lower() + "/" + "/".join(p.parts[1:])
    raise ValueError(f"unknown path style {style!r}")


class SessionDirectory:
    """The private temp directory of one runtime session."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root) if root else Path(tempfile.gettempdir())
        self.path: Optional[Path] = None

    def create(self) -> Path:
        if self.path is None or not self.path.is_dir():
            self.path = Path(tempfile.mkdtemp(prefix=DIR_PREFIX, dir=str(self.root)))
            (self.path / MARKER_NAME).write_text(f"pid={os.getpid()} created={time.time():.0f}\n", encoding="ascii")
        return self.path

    def file(self, name: str) -> Path:
        if os.sep in name or "/" in name or name.startswith("."):
            raise ValueError(f"not a plain file name: {name!r}")
        return self.create() / name

    def remove_file(self, name: str) -> None:
        if self.path is None:
            return
        try:
            (self.path / name).unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"ROI Viewer: interactive AI could not remove {name} - {e}")

    def cleanup(self) -> None:
        """Delete this session's directory (only if it is ours)."""
        path, self.path = self.path, None
        if path is not None and is_owned_directory(path):
            shutil.rmtree(path, ignore_errors=True)


def is_owned_directory(path) -> bool:
    path = Path(path)
    return (path.is_dir() and not path.is_symlink() and path.name.startswith(DIR_PREFIX)
            and (path / MARKER_NAME).is_file())


def cleanup_abandoned(root: Optional[str] = None, max_age_seconds: float = ABANDONED_AGE_SECONDS, now=None) -> list:
    """Remove plugin-owned session directories older than max_age_seconds
    left by a crashed or killed session. Returns the removed paths."""
    root = Path(root) if root else Path(tempfile.gettempdir())
    now = time.time() if now is None else now
    removed = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return removed
    for entry in entries:
        try:
            if not is_owned_directory(entry) or entry.parent.resolve() != root.resolve():
                continue
            if now - (entry / MARKER_NAME).stat().st_mtime < max_age_seconds:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(str(entry))
        except OSError:
            continue
    return removed


def write_volume(session: SessionDirectory, array, spacing_xyz, orientation=None, volume_id: Optional[str] = None):
    """Write volume.npy + metadata.json. Returns (volume_path, metadata)."""
    arr = np.asarray(array)
    if arr.ndim != 3:
        raise ValueError(f"volume must be 3D, got shape {arr.shape}")
    volume_id = volume_id or fingerprint(arr, spacing_xyz, orientation)
    path = session.file(VOLUME_FILE)
    tmp = session.file("volume.partial.npy")
    np.save(tmp, np.ascontiguousarray(arr), allow_pickle=False)
    os.replace(tmp, path)
    finite = arr.size > 0
    metadata = {
        "volume_id": volume_id,
        "shape_zyx": [int(n) for n in arr.shape],
        "dtype": arr.dtype.str,
        "spacing_xyz": [float(s) for s in spacing_xyz],
        "orientation": None if orientation is None else [float(v) for v in orientation],
        "index_order": "zyx",
        "min": float(arr.min()) if finite else None,
        "max": float(arr.max()) if finite else None,
        "values": "HU (Slice().matrix, rescale applied on import)",
    }
    session.file(METADATA_FILE).write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    return path, metadata
