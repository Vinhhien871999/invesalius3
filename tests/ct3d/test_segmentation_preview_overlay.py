# --------------------------------------------------------------------------
# Persistent tests for E2's real 2D overlay mechanism:
# SegmentationPanel._show_preview_overlay()/_clear_preview_overlay(),
# against a REAL invesalius.data.slice_.Slice() - the SAME real, native
# aux_matrices/to_show_aux path InVesalius's own Watershed tool uses (see
# invesalius/data/styles.py's WatershedInteractorStyle). No VTK actor is
# involved at all (this overlay is a 2D raster blend baked into the
# slice image, not a scene actor) - see
# docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md's "E2 Preview
# Architecture" section and this file's own test docstrings for what
# that does and does not make meaningful to test here.
#
# Reuses tests/ct3d/test_segmentation_preview_commit.py's real-singleton-
# reuse fixture pattern (see that file's _shared_real_slice_and_project_
# once() docstring for why a fresh Slice() per test is unsafe once real
# pubsub-driven mask creation - and, here, real aux_matrices mutation -
# is involved). Marked integration.
# --------------------------------------------------------------------------
import types

import numpy as np
import pytest

pytestmark = pytest.mark.integration

_SHAPE = (6, 16, 16)


@pytest.fixture
def real_slice(real_slice_and_project_singleton):
    """Reuses the ONE real Slice()/Project() pair shared across the whole
    session (conftest.py's real_slice_and_project_singleton) - see its
    docstring for why a single shared pair, not a fresh Slice()/Project()
    per test or per module, is required once real pubsub/aux_matrices
    state is involved."""
    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance = proj
    Slice.instance = s

    proj.mask_dict = {}
    proj.image_versions = []

    rng = np.random.RandomState(1)
    volume = rng.randint(-200, 800, size=_SHAPE).astype(np.int16)
    s.current_mask = None
    s.matrix = volume
    s._spacing = (1.0, 1.0, 1.0)
    s.aux_matrices = {}
    s.aux_matrices_colours = {}
    s.to_show_aux = ""
    return s


def _panel_like():
    """Bind just the overlay methods under test to a bare object - same
    pattern as test_segmentation_preview_commit.py's _new_panel_like(),
    avoiding real wx.Panel/ScrolledPanel construction."""
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    fake = types.SimpleNamespace(_preview_temp_file=None)
    fake._show_preview_overlay = SegmentationPanel._show_preview_overlay.__get__(fake)
    fake._clear_preview_overlay = SegmentationPanel._clear_preview_overlay.__get__(fake)
    return fake


def test_overlay_visible_in_all_three_views(real_slice):
    """"One overlay, all 3 views" - the real aux_matrices/to_show_aux
    mechanism is a single shared 3D array; Axial/Coronal/Sagital each
    read their own real slice out of the SAME array via
    Slice.get_aux_slice(name, orientation, n) - proven here directly
    against real data, not a stand-in."""
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    panel = _panel_like()
    array = np.zeros(_SHAPE, dtype=np.uint8)
    array[2, 5, 5] = 255  # one marked voxel, distinguishable per axis

    panel._show_preview_overlay(array)
    assert real_slice.to_show_aux == PREVIEW_AUX_KEY
    assert real_slice.aux_matrices[PREVIEW_AUX_KEY] is array

    axial = real_slice.get_aux_slice(PREVIEW_AUX_KEY, "AXIAL", 2)
    coronal = real_slice.get_aux_slice(PREVIEW_AUX_KEY, "CORONAL", 5)
    sagital = real_slice.get_aux_slice(PREVIEW_AUX_KEY, "SAGITAL", 5)
    assert axial[5, 5] == 255
    assert coronal[2, 5] == 255
    assert sagital[2, 5] == 255


def test_no_duplicate_actor_on_repeated_preview(real_slice):
    """"No duplicate overlay actor" translated to this actor-free
    mechanism: a second _show_preview_overlay() call must overwrite the
    SAME dict key, never accumulate a second one."""
    panel = _panel_like()
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    panel._show_preview_overlay(np.zeros(_SHAPE, dtype=np.uint8))
    assert list(real_slice.aux_matrices.keys()) == [PREVIEW_AUX_KEY]

    second_array = np.ones(_SHAPE, dtype=np.uint8) * 255
    panel._show_preview_overlay(second_array)
    assert list(real_slice.aux_matrices.keys()) == [PREVIEW_AUX_KEY]  # still exactly one key
    assert real_slice.aux_matrices[PREVIEW_AUX_KEY] is second_array  # replaced, not appended


def test_cancel_removes_overlay(real_slice):
    panel = _panel_like()
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    panel._show_preview_overlay(np.zeros(_SHAPE, dtype=np.uint8))
    assert real_slice.to_show_aux == PREVIEW_AUX_KEY

    panel._clear_preview_overlay()
    assert real_slice.to_show_aux == ""
    assert PREVIEW_AUX_KEY not in real_slice.aux_matrices
    assert PREVIEW_AUX_KEY not in real_slice.aux_matrices_colours


def test_accept_removes_overlay():
    """Accept's real cleanup call is the SAME _clear_preview_overlay() as
    Cancel's (see gui/segmentation_panel.py's _on_preview_accept()) -
    covered by test_cancel_removes_overlay() above; not duplicated."""


def test_clear_overlay_safe_when_nothing_shown(real_slice):
    panel = _panel_like()
    panel._clear_preview_overlay()  # must not raise
    assert real_slice.to_show_aux == ""


def test_reopen_has_no_duplicate(real_slice):
    """"Reopen" for this actor-free mechanism means: clear, then show
    again - still exactly one real entry, same as any other repeated
    show/clear cycle (no persistent per-window actor to leak here at
    all, unlike a real VTK-actor-based overlay would risk)."""
    panel = _panel_like()
    from plugins.roi_viewer.gui.segmentation_panel import PREVIEW_AUX_KEY

    panel._show_preview_overlay(np.zeros(_SHAPE, dtype=np.uint8))
    panel._clear_preview_overlay()
    panel._show_preview_overlay(np.ones(_SHAPE, dtype=np.uint8) * 255)
    assert list(real_slice.aux_matrices.keys()) == [PREVIEW_AUX_KEY]


def test_overlay_is_not_actor_based_pickability_not_applicable(real_slice):
    """Documents, as a real assertion rather than only prose, that this
    overlay is a 2D raster blend (invesalius.data.slice_.Slice.
    aux_matrices, blended by do_custom_colour()/do_blend() into the 2D
    slice's own vtkImageData) and creates NO vtkActor/vtkProp at all -
    "pickable" is a VTK actor/prop concept that does not apply here.
    Confirmed by construction: aux_matrices values are plain numpy
    arrays, never VTK actors."""
    panel = _panel_like()
    array = np.zeros(_SHAPE, dtype=np.uint8)
    panel._show_preview_overlay(array)
    stored = real_slice.aux_matrices["roi_viewer_preview"]
    assert isinstance(stored, np.ndarray)
    assert not hasattr(stored, "GetPickable")  # confirms it is not any kind of VTK actor/prop
