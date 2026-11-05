# --------------------------------------------------------------------------
# Interactive AI geometry: prompt coordinates (2D cursor, 3D pick) on the
# real 0543 / 0051 grids, 2D prompt markers, and the REAL MedSAM2 worker
# provider's numpy-only parts (window, slice preprocessing, prompt mapping,
# row flip, slice range, largest component) - no torch, no model.
# --------------------------------------------------------------------------
import pathlib
import sys
import types

import numpy as np
import pytest

from plugins.roi_viewer.core.ai.prompts import AIPromptSet, PromptOutOfVolume
from plugins.roi_viewer.core.coordinates import (
    slice_to_view,
    view_to_slice,
    voxel_zyx_to_world_xyz,
    world_xyz_to_voxel_zyx,
)
from plugins.roi_viewer.gui import ai_prompt_overlay as overlay_mod

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "interactive_ai_runtime"))
from providers import medsam2_provider as m2w  # noqa: E402  (worker-side module, numpy parts only)

# Slice().matrix.shape (z, y, x) and Slice().spacing (x, y, z)
GEOMETRIES = {
    "0543": ((300, 512, 512), (0.5859375, 0.5859375, 1.0)),
    "0051": ((108, 512, 512), (0.4785, 0.4785, 1.5)),
}
VOXEL = (57, 301, 123)  # deliberately asymmetric (z, y, x)


@pytest.mark.parametrize("name", GEOMETRIES)
def test_2d_cursor_points_from_each_view(name):
    """The 2D cross focal point is slice-frame world (x, y, z) whichever
    view was clicked; the clicked view fixes its own axis at the slice."""
    shape, spacing = GEOMETRIES[name]
    world = voxel_zyx_to_world_xyz(VOXEL, spacing)
    # clicks a fraction of a voxel off-centre still select the voxel
    jitter = {"axial": (0.3 * spacing[0], -0.4 * spacing[1], 0.0),
              "coronal": (-0.2 * spacing[0], 0.0, 0.45 * spacing[2]),
              "sagittal": (0.0, 0.49 * spacing[1], -0.3 * spacing[2])}
    for view, d in jitter.items():
        prompts = AIPromptSet()
        p = prompts.add_point(tuple(w + e for w, e in zip(world, d)), spacing, shape, positive=view != "coronal")
        assert p.voxel_zyx == VOXEL, view
        assert world_xyz_to_voxel_zyx(voxel_zyx_to_world_xyz(p.voxel_zyx, spacing), spacing, shape) == VOXEL


@pytest.mark.parametrize("name", GEOMETRIES)
def test_3d_pick_goes_through_view_to_slice(name):
    shape, spacing = GEOMETRIES[name]
    world = voxel_zyx_to_world_xyz(VOXEL, spacing)
    picked_view_frame = slice_to_view(world)  # what the 3D picker reports (y negated)
    assert picked_view_frame[1] == -world[1]
    p = AIPromptSet().add_point(view_to_slice(picked_view_frame), spacing, shape, positive=True)
    assert p.voxel_zyx == VOXEL  # no y-flip regression
    with pytest.raises(PromptOutOfVolume):  # the raw view-frame point is outside the volume, never clamped
        AIPromptSet().add_point(picked_view_frame, spacing, shape, positive=True)


@pytest.mark.parametrize("name", GEOMETRIES)
def test_box_corners_order_and_bounds(name):
    shape, spacing = GEOMETRIES[name]
    a = voxel_zyx_to_world_xyz((60, 300, 100), spacing)
    b = voxel_zyx_to_world_xyz((40, 250, 140), spacing)
    s = AIPromptSet()
    assert s.set_corner(2, a, spacing, shape) is None and s.box is None  # one corner only
    box = s.set_corner(1, b, spacing, shape)
    assert box.voxel_min_zyx == (40, 250, 100) and box.voxel_max_zyx == (60, 300, 140)
    with pytest.raises(PromptOutOfVolume):
        s.set_corner(1, voxel_zyx_to_world_xyz((shape[0], 0, 0), spacing), spacing, shape)
    s.clear_box()
    assert s.box is None and s.corner1 is None and s.corner2 is None


def test_undo_last_and_clear():
    shape, spacing = GEOMETRIES["0051"]
    s = AIPromptSet()
    p1 = s.add_point(voxel_zyx_to_world_xyz((10, 10, 10), spacing), spacing, shape, True)
    s.add_point(voxel_zyx_to_world_xyz((20, 20, 20), spacing), spacing, shape, False)
    before = s.snapshot()
    s.add_point(voxel_zyx_to_world_xyz((30, 30, 30), spacing), spacing, shape, True)
    assert s.undo_last_point().voxel_zyx == (30, 30, 30)
    assert s.snapshot() == before and (s.positive_count, s.negative_count) == (1, 1)
    s.undo_last_point()
    assert s.points == [p1]
    s.clear()
    assert s.count == 0 and s.undo_last_point() is None


# ------------------------------------------------------------------ 2D markers
def test_markers_only_on_their_slice_in_each_orientation():
    spacing = GEOMETRIES["0543"][1]
    points = [((57, 301, 123), True), ((58, 10, 20), False)]
    world = voxel_zyx_to_world_xyz((57, 301, 123), spacing)
    assert overlay_mod.markers_for_slice(points, None, [], "AXIAL", 57, spacing) == [("point", world, True)]
    assert overlay_mod.markers_for_slice(points, None, [], "CORONAL", 301, spacing) == [("point", world, True)]
    assert overlay_mod.markers_for_slice(points, None, [], "SAGITAL", 123, spacing) == [("point", world, True)]
    assert overlay_mod.markers_for_slice(points, None, [], "AXIAL", 56, spacing) == []
    neg = overlay_mod.markers_for_slice(points, None, [], "AXIAL", 58, spacing)
    assert neg == [("point", voxel_zyx_to_world_xyz((58, 10, 20), spacing), False)]


def test_box_outline_in_each_orientation():
    spacing = GEOMETRIES["0051"][1]
    box = ((40, 250, 100), (60, 300, 140))
    (kind, quad), = overlay_mod.markers_for_slice([], box, [], "AXIAL", 50, spacing)
    assert kind == "box" and quad == [voxel_zyx_to_world_xyz(v, spacing) for v in
                                      ((50, 250, 100), (50, 300, 100), (50, 300, 140), (50, 250, 140))]
    assert overlay_mod.markers_for_slice([], box, [], "AXIAL", 61, spacing) == []
    (_, quad), = overlay_mod.markers_for_slice([], box, [], "CORONAL", 260, spacing)
    assert {q[1] for q in quad} == {260 * spacing[1]}
    (_, quad), = overlay_mod.markers_for_slice([], box, [], "SAGITAL", 100, spacing)
    assert {q[0] for q in quad} == {100 * spacing[0]}
    assert overlay_mod.markers_for_slice([], None, [(5, 6, 7)], "AXIAL", 5, spacing) == [
        ("corner", voxel_zyx_to_world_xyz((5, 6, 7), spacing))]


def test_overlay_attach_draw_detach(wx_app):
    shape, spacing = GEOMETRIES["0051"]
    calls = []

    class Canvas:
        def __init__(self, viewer):
            self.draw_list, self.viewer, self.evt_renderer, self.modified = [], viewer, None, False

        def draw_circle(self, center, radius, width=2, line_colour=None, fill_colour=None):
            calls.append(("circle", center, fill_colour))

        def draw_line(self, a, b, colour=None, width=1):
            calls.append(("line", a, b))

    def viewer(orientation, number):
        v = types.SimpleNamespace(orientation=orientation, slice_data=types.SimpleNamespace(number=number),
                                  renders=0)
        v.canvas = Canvas(v)
        v.UpdateRender = lambda: setattr(v, "renders", v.renders + 1)
        return v

    viewers = [viewer("AXIAL", 10), viewer("CORONAL", 20), viewer("SAGITAL", 30)]
    ov = overlay_mod.AIPromptOverlay2D(lambda: viewers)
    s = AIPromptSet()
    s.add_point(voxel_zyx_to_world_xyz((10, 20, 30), spacing), spacing, shape, True)
    ov.update(s, spacing, shape)
    assert ov.attached == 3 and all(len(v.canvas.draw_list) == 1 for v in viewers)
    handler = viewers[0].canvas.draw_list[0]
    assert handler.is_over(0, 0) is None  # never takes the mouse
    handler._3d_to_2d = lambda renderer, w: (w[0], w[1])  # display projection is InVesalius's own
    handler.draw_to_canvas(None, viewers[0].canvas)
    assert calls == [("circle", (30 * spacing[0], 20 * spacing[1]), overlay_mod.POSITIVE_COLOUR)]
    ov.update(s, spacing, shape)  # again: no duplicate objects
    assert all(len(v.canvas.draw_list) == 1 for v in viewers)
    s.clear()
    ov.update(s, spacing, shape)
    assert ov.attached == 0 and all(v.canvas.draw_list == [] for v in viewers)
    assert all(v.renders >= 2 for v in viewers)


# ------------------------------------------------------------------ MedSAM2 worker provider (numpy parts)
def test_window_and_uint8_match_the_official_formula():
    vol = np.array([[[-2000, -160, 40, 240, 3000]]], dtype=np.int16)
    out = m2w.window_to_uint8(vol, -160, 240)
    clipped = np.clip(vol.astype(np.float32), -160, 240)
    expected = ((clipped - clipped.min()) / (clipped.max() - clipped.min()) * 255.0).astype(np.uint8)
    assert out.dtype == np.uint8 and np.array_equal(out, expected) and out.tolist() == [[[0, 0, 127, 255, 255]]]
    assert m2w.window_to_uint8(np.full((1, 2, 2), 500), -160, 240).sum() == 0  # flat after clipping
    assert m2w.resolve_window(None) == (-160.0, 240.0) == m2w.resolve_window("soft_tissue")
    assert m2w.resolve_window("lung") == (-1350.0, 150.0) and m2w.resolve_window([-100, 100]) == (-100.0, 100.0)
    with pytest.raises(ValueError):
        m2w.resolve_window("brain")
    with pytest.raises(ValueError):
        m2w.resolve_window([10, 5])


def test_slice_preprocessing_shape_and_normalisation():
    vol = np.zeros((2, 37, 53), dtype=np.uint8)
    vol[1] = 255
    out = m2w.preprocess_slices(vol)
    assert out.shape == (2, 3, 512, 512) and out.dtype == np.float32
    mean, std = np.array(m2w.IMAGENET_MEAN), np.array(m2w.IMAGENET_STD)
    assert np.allclose(out[0].reshape(3, -1).mean(1), (0 - mean) / std, atol=1e-5)
    assert np.allclose(out[1].reshape(3, -1).mean(1), (1 - mean) / std, atol=1e-5)
    # the worker keeps uint8 and normalises on the device: same numbers
    u8 = m2w.resize_slices_uint8(vol)
    assert u8.shape == (2, 3, 512, 512) and u8.dtype == np.uint8
    renorm = (u8.astype(np.float32) / 255.0 - mean[:, None, None].astype(np.float32)) / std[:, None, None].astype(
        np.float32)
    assert np.allclose(renorm, out, atol=1e-6)


@pytest.mark.parametrize("name", GEOMETRIES)
def test_prompt_mapping_and_row_flip_roundtrip(name):
    shape, _spacing = GEOMETRIES[name]
    nz, ny, nx = shape
    prompts = {"points": [{"zyx": [57, 301, 123], "label": 1}, {"zyx": [57, 10, 20], "label": 0},
                          {"zyx": [80, 5, 6], "label": 1}],
               "box": {"min_zyx": [50, 250, 100], "max_zyx": [64, 320, 140]}}
    frames, z_range = m2w.map_prompts(prompts, shape, flip_rows=True)
    assert sorted(frames) == [57, 80] and z_range == (50, 64)  # box key slice (50+64)//2 = 57
    assert frames[57]["points"] == [[123.0, float(ny - 1 - 301)], [20.0, float(ny - 1 - 10)]]
    assert frames[57]["labels"] == [1, 0] and frames[80]["box"] is None
    assert frames[57]["box"] == [100.0, float(ny - 1 - 320), 140.0, float(ny - 1 - 250)]  # x0 y0 x1 y1, ordered
    plain, _ = m2w.map_prompts(prompts, shape, flip_rows=False)
    assert plain[57]["points"][0] == [123.0, 301.0]
    # a model-frame mask at the mapped prompt maps back exactly onto the prompt voxel
    model = np.zeros(shape, dtype=bool)
    x, y = (int(v) for v in frames[57]["points"][0])
    model[57, y, x] = True
    back = m2w.to_model_rows(model, True)
    assert back.shape == shape and list(zip(*np.nonzero(back))) == [(57, 301, 123)]
    vol = np.random.default_rng(0).integers(0, 9, (3, 4, 5))
    assert np.array_equal(m2w.to_model_rows(m2w.to_model_rows(vol, True), True), vol)


def test_single_slice_box_propagates_through_the_volume():
    frames, z_range = m2w.map_prompts({"points": [], "box": {"min_zyx": [9, 1, 2], "max_zyx": [9, 5, 6]}},
                                      (20, 10, 10), flip_rows=False)
    assert sorted(frames) == [9] and z_range is None


def test_largest_component_full_connectivity():
    m = np.zeros((5, 5, 5), dtype=bool)
    m[0:2, 0:2, 0:2] = True  # 8 voxels
    m[4, 4, 4] = True
    m[3, 3, 3] = True  # diagonal neighbour of (4,4,4): same component with full connectivity
    out = m2w.largest_component(m)
    assert out.sum() == 8 and out[0, 0, 0] and not out[4, 4, 4]
    assert m2w.largest_component(np.zeros((2, 2, 2), dtype=bool)).sum() == 0


def test_capabilities_are_declared_from_evidence():
    p = m2w.MedSAM2Provider({"checkpoint": "", "repo_path": ""})
    caps = p.capabilities(cuda=False)
    assert caps["box"] and caps["positive_point"] and caps["propagation_3d"]
    assert caps["negative_point"] is False  # no official MedSAM2 path uses label-0 clicks
    assert m2w.MedSAM2Provider({"allow_negative_points": True}).capabilities(False)["negative_point"] is True
    info = p.probe()  # this environment has no sam2 / checkpoint: reported, not raised
    assert info["available"] is False and info["reason"] in ("dependency_missing", "checkpoint_missing")
