# --------------------------------------------------------------------------
# E6 result validation - the gate between a provider's output and the E2
# preview. A candidate must already be on the native (z, y, x) volume grid
# and binary; nothing is reshaped, resampled, cropped or thresholded here
# (that is the provider's job), so the preview shows exactly what the
# provider returned and Accept commits exactly that.
# --------------------------------------------------------------------------
import numpy as np

CANDIDATE_SHAPE = "shape"
CANDIDATE_DTYPE = "dtype"
CANDIDATE_NON_FINITE = "non_finite"
CANDIDATE_NOT_BINARY = "not_binary"


class CandidateError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def validate_candidate(mask, volume_shape_zyx) -> np.ndarray:
    """Returns the candidate as a bool (z, y, x) array, or raises
    CandidateError. Accepted encodings: bool; integer or float arrays whose
    values are all 0/1 or all 0/255."""
    arr = np.asarray(mask)
    expected = tuple(int(n) for n in volume_shape_zyx)
    if arr.shape != expected:
        raise CandidateError(CANDIDATE_SHAPE, f"got {arr.shape}, volume is {expected}")
    if arr.dtype == np.bool_:
        return arr.copy()
    if not (np.issubdtype(arr.dtype, np.integer) or np.issubdtype(arr.dtype, np.floating)):
        raise CandidateError(CANDIDATE_DTYPE, f"unsupported dtype {arr.dtype}")
    if np.issubdtype(arr.dtype, np.floating) and not np.isfinite(arr).all():
        raise CandidateError(CANDIDATE_NON_FINITE, "NaN or infinite values")
    zero = arr == 0
    if not (np.all(zero | (arr == 1)) or np.all(zero | (arr == 255))):
        raise CandidateError(CANDIDATE_NOT_BINARY, "values other than 0/1 or 0/255 (probabilities or labels?)")
    return ~zero


def preview_values(foreground) -> np.ndarray:
    """bool candidate -> the 0/255 uint8 values the E2 overlay displays."""
    return np.where(np.asarray(foreground, dtype=bool), 255, 0).astype(np.uint8)
