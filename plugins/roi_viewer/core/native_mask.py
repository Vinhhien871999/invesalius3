# --------------------------------------------------------------------------
# Native mask contract - how ROI Viewer reads and writes a real InVesalius
# Mask (30/09/2026). Every plugin path that reads a whole mask (E3 cleanup,
# E4 "Current ROI", Measure Volume, NumPy/NRRD export) or writes one
# (Region Growing, E2 Accept, E3 cleanup, E6 AI Accept) goes through here.
#
# Source facts (invesalius/data/slice_.py, mask.py, styles.py):
#
# * Mask.matrix is (z+1, y+1, x+1) uint8. Index 0 of each axis is padding
#   whose cells are "slice already computed" sentinels: matrix[n, 0, 0]
#   for axial slice n-1, matrix[0, n, 0] coronal, matrix[0, 0, n]
#   sagittal.
# * Threshold masks are computed lazily. get_mask_slice() thresholds a
#   slice the first time a 2D view shows it (sentinel 0 -> compute, set 1);
#   do_threshold_to_all_slices() computes every unvisited axial slice and
#   is what native code calls before any whole-volume use (surface
#   creation, export, boolean ops, morphology, density, area).
# * do_threshold_to_a_slice() keeps only the edit values 1, 2, 253, 254;
#   a plain 255 on an unvisited slice is overwritten when that slice is
#   (re)computed.
# * Brush Draw writes 254, brush Erase writes 1. What the user sees as
#   the mask is "value > 127": the 2D mask colour table makes 0/1/2
#   transparent and colours 253-255, the binary surface is contoured at
#   127, and calc_image_density/calc_mask_area test > 127.
# * After writing a whole volume by hand, native code marks all three
#   sentinel planes (matrix[0], matrix[:, 0], matrix[:, :, 0] = 1 - see
#   Mask.modified(all_volume=True), Watershed's _create_new_mask) and
#   discards the 2D slice buffers so the views re-read the matrix.
#
# Before this module the plugin read matrix[1:, 1:, 1:] with "!= 0"
# (erased voxels counted as foreground, unvisited slices read as empty)
# and marked only the axial sentinels after a write, so showing a
# not-yet-visited coronal/sagittal slice later re-thresholded that plane
# and erased committed voxels.
# --------------------------------------------------------------------------
import numpy as np

FOREGROUND_ABOVE = 127


def compute_all_slices(slice_, mask) -> None:
    """Native lazy-threshold completion - call before reading a whole mask."""
    slice_.do_threshold_to_all_slices(mask)


def logical_foreground(slice_, mask) -> np.ndarray:
    """The mask's real foreground as a bool (z, y, x) array (a copy)."""
    compute_all_slices(slice_, mask)
    return np.asarray(mask.matrix[1:, 1:, 1:]) > FOREGROUND_ABOVE


def mark_all_slices_computed(mask) -> None:
    mask.matrix[0, :, :] = 1
    mask.matrix[:, 0, :] = 1
    mask.matrix[:, :, 0] = 1


def discard_slice_buffers(slice_) -> None:
    """Make the 2D views re-read the mask instead of a cached slice."""
    for buffer in getattr(slice_, "buffer_slices", {}).values():
        buffer.discard_mask()
        buffer.discard_vtk_mask()


def write_logical_region(slice_, mask, foreground) -> None:
    """Overwrite the whole logical region with exactly `foreground` (bool,
    unpadded (z, y, x) shape): 255 inside, 0 outside, every slice marked
    computed so no later lazy threshold can change it."""
    foreground = np.asarray(foreground, dtype=bool)
    region = mask.matrix[1:, 1:, 1:]
    if foreground.shape != region.shape:
        raise ValueError(f"shape {foreground.shape} does not match mask region {region.shape}")
    region[:] = np.where(foreground, 255, 0).astype(np.uint8)
    mark_all_slices_computed(mask)
    mask.matrix.flush()
    mask.was_edited = True
    discard_slice_buffers(slice_)


def commit_preview_array_to_new_mask(foreground, name, colour):
    """
    The one commit path for a computed candidate (Region Growing, E2
    Region Growing Accept, E6 AI Accept): creates a real mask through
    InVesalius's own "Create new mask" topic (Project().mask_dict entry,
    Masks tab, current-mask switch, ROI list refresh - all native), then
    writes `foreground` into it exactly. Returns the new Mask, or None if
    no mask was created. The logical region equals `foreground` bit for
    bit afterwards and stays so when any slice is shown later.
    """
    import invesalius.data.slice_ as sl
    from invesalius.pubsub import pub as Publisher

    foreground = np.asarray(foreground, dtype=bool)
    s = sl.Slice()
    if s.matrix is None or foreground.shape != tuple(s.matrix.shape):
        # Checked before creating anything: a wrong-shape candidate must
        # never leave an empty mask behind.
        raise ValueError(f"candidate shape {foreground.shape} does not match the volume")
    Publisher.sendMessage("Create new mask", mask_name=name, thresh=(1, 1), colour=colour)
    mask = s.current_mask
    if mask is None or mask.matrix is None or getattr(mask, "name", name) != name:
        return None
    write_logical_region(s, mask, foreground)
    return mask
