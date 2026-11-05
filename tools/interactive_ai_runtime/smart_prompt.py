# --------------------------------------------------------------------------
# Smart initial prompt for one-click interactive segmentation (numpy only;
# used by the worker providers and tested in InVesalius's environment).
#
# Real 0543 evidence (05/11/2026): one positive point alone gives MedSAM2 an
# EMPTY 3D result, while a box (Dice 0.96 vs TotalSegmentator) or a box +
# point (0.965) work. So a click is turned into box + point:
#
#   1. fast 2D candidate on the clicked slice from the point(s) - the
#      model's own current-frame output (add_new_points_or_box returns the
#      mask of that frame without propagating; sam2_video_predictor_npz.py);
#   2. if that 2D mask is non-empty AND contains the click: its tight bbox,
#      padded by `padding_fraction` of its size (at least `min_padding_px`),
#      clamped to the image - strategy "fast_2d_mask";
#   3. otherwise an AUTOMATIC INITIAL BOX centred on the click (strategy
#      "click_centred_box", half size `fallback_half_px`). This is a
#      heuristic initial box, not anatomical recognition.
# All coordinates here are NATIVE voxel (y, x) of one axial slice; the
# provider converts to the model's row order itself.
# --------------------------------------------------------------------------
import numpy as np

STRATEGY_FAST_2D = "fast_2d_mask"
STRATEGY_CLICK_BOX = "click_centred_box"


def bbox_2d(mask2d):
    """(y0, x0, y1, x1) inclusive of the True pixels, or None."""
    m = np.asarray(mask2d, dtype=bool)
    if not m.any():
        return None
    ys = np.flatnonzero(m.any(axis=1))
    xs = np.flatnonzero(m.any(axis=0))
    return int(ys[0]), int(xs[0]), int(ys[-1]), int(xs[-1])


def pad_box(box, shape_yx, padding_fraction, min_padding_px=0):
    y0, x0, y1, x1 = box
    ny, nx = shape_yx
    py = max(int(round((y1 - y0 + 1) * float(padding_fraction))), int(min_padding_px))
    px = max(int(round((x1 - x0 + 1) * float(padding_fraction))), int(min_padding_px))
    return max(0, y0 - py), max(0, x0 - px), min(ny - 1, y1 + py), min(nx - 1, x1 + px)


def click_centred_box(click_yx, shape_yx, half_px):
    y, x = (int(v) for v in click_yx)
    ny, nx = shape_yx
    h = max(1, int(half_px))
    return max(0, y - h), max(0, x - h), min(ny - 1, y + h), min(nx - 1, x + h)


def box_contains(box, click_yx):
    y0, x0, y1, x1 = box
    y, x = click_yx
    return y0 <= y <= y1 and x0 <= x <= x1


def initial_box(mask2d, click_yx, shape_yx, padding_fraction=0.1, min_padding_px=2, fallback_half_px=32):
    """Returns (box (y0, x0, y1, x1), strategy, details). The click is always
    inside the returned box."""
    details = {"fast_2d_pixels": 0 if mask2d is None else int(np.count_nonzero(mask2d))}
    if mask2d is not None:
        m = np.asarray(mask2d, dtype=bool)
        y, x = (int(v) for v in click_yx)
        inside = 0 <= y < m.shape[0] and 0 <= x < m.shape[1] and bool(m[y, x])
        details["click_in_fast_2d"] = inside
        box = bbox_2d(m)
        if box is not None and inside:
            padded = pad_box(box, shape_yx, padding_fraction, min_padding_px)
            details.update(tight_box=list(box), padding_fraction=float(padding_fraction))
            return padded, STRATEGY_FAST_2D, details
    box = click_centred_box(click_yx, shape_yx, fallback_half_px)
    details["fallback_half_px"] = int(fallback_half_px)
    return box, STRATEGY_CLICK_BOX, details


POLICY_POINT_FIRST = "point_first"
POLICY_FAST_2D_BOX = "fast_2d_box"
STRATEGY_POINT_ONLY = "point_only"


def initial_prompt(mask2d, click_yx, shape_yx, policy=POLICY_POINT_FIRST, min_fast_2d_pixels=400,
                   padding_fraction=0.1, min_padding_px=2, fallback_half_px=64):
    """The one-click policy. Returns (box or None, strategy, details).

    point_first (default, measured on 0543 - see the architecture doc): when
    the model's quick 2D mask from the click is non-empty, contains the
    click and has at least `min_fast_2d_pixels` pixels, the point alone is
    used (no box: on solid organs a lone point matched or beat a box
    derived from that 2D mask); otherwise a click-centred automatic box of
    half size `fallback_half_px` is added (lung: point 0.0003 -> box 0.44).
    fast_2d_box: the padded bbox of the quick 2D mask (initial_box)."""
    if policy == POLICY_FAST_2D_BOX:
        return initial_box(mask2d, click_yx, shape_yx, padding_fraction, min_padding_px, fallback_half_px)
    if policy != POLICY_POINT_FIRST:
        raise ValueError(f"unknown smart policy {policy!r}")
    m = None if mask2d is None else np.asarray(mask2d, dtype=bool)
    pixels = 0 if m is None else int(np.count_nonzero(m))
    y, x = (int(v) for v in click_yx)
    inside = m is not None and 0 <= y < m.shape[0] and 0 <= x < m.shape[1] and bool(m[y, x])
    details = {"policy": policy, "fast_2d_pixels": pixels, "click_in_fast_2d": inside,
               "min_fast_2d_pixels": int(min_fast_2d_pixels)}
    if inside and pixels >= int(min_fast_2d_pixels):
        return None, STRATEGY_POINT_ONLY, details
    details["fallback_half_px"] = int(fallback_half_px)
    return click_centred_box(click_yx, shape_yx, fallback_half_px), STRATEGY_CLICK_BOX, details


def box_prompt(z, box):
    """Protocol box on one axial slice (inclusive voxel bounds)."""
    y0, x0, y1, x1 = box
    return {"min_zyx": [int(z), int(y0), int(x0)], "max_zyx": [int(z), int(y1), int(x1)]}
