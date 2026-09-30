# --------------------------------------------------------------------------
# World <-> voxel regression (30/09/2026): runs the REAL frame/panel
# handlers (on_cross_focal_point_changed, update_textured_slice_planes,
# InteractionPanel._on_point_picked, SegmentationPanel._on_seed_picked)
# with dataset-0051-like ANISOTROPIC spacing - the kind of data that
# exposed both bugs:
#   * spacing order - Slice().spacing is (x, y, z), matrix is (z, y, x);
#   * frames - the 3D view is y-flipped relative to the 2D slice frame
#     (surfaces/volume use vtkImageFlip on Y; native converts with -y at
#     styles.py:555 and styles_3d.py:994).
# Expectations are derived from a KNOWN voxel and from the real
# converters.to_vtk() + vtkImageFlip ground truth, never from the code
# under test. Only the viewer lookup, the ProjectInterface singleton and
# Slice().GetSlices() are substituted.
# --------------------------------------------------------------------------
import types
from unittest.mock import patch

import numpy as np
import pytest

from plugins.roi_viewer.core import coordinates
from plugins.roi_viewer.core.marker_3d import CrosshairMarker3D
from plugins.roi_viewer.core.segmentation import SegmentationManager
from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D
from plugins.roi_viewer.core.surface_clipping_3d import (
    PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL, SurfaceClipping3D,
)
from plugins.roi_viewer.core.sync_2d3d import SyncManager2D3D
from plugins.roi_viewer.core.textured_slice_planes_3d import TexturedSlicePlanes3D
from plugins.roi_viewer.gui import roi_panel
from plugins.roi_viewer.gui.interaction_panel import InteractionPanel
from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel
from plugins.roi_viewer.interface.project_interface import ProjectInterface

pytestmark = pytest.mark.integration

SHAPE = (108, 512, 512)  # Slice().matrix.shape (z, y, x) - dataset 0051
SPACING = (0.4785, 0.4785, 1.5)  # Slice().spacing (x, y, z) - dataset 0051
VOXEL = (37, 301, 122)  # (z, y, x) - deliberately not the centre
SX, SY, SZ = SPACING
Z, Y, X = VOXEL
SLICE_POS = (X * SX, Y * SY, Z * SZ)  # where the 2D crosshair sits for VOXEL
VIEW_POS = (X * SX, -Y * SY, Z * SZ)  # the same point in the y-flipped 3D view


def _real_project_interface():
    # object.__new__, not ProjectInterface.__new__: the latter returns the
    # process-wide singleton, and the attributes set here (and the
    # get_volume_data stub below) then leaked into every later test
    # (found 30/09/2026 by the E6b TotalSegmentator tests).
    pi = object.__new__(ProjectInterface)
    pi._spacing, pi._shape = SPACING, SHAPE
    pi._slice = None
    return pi


@pytest.fixture
def env(monkeypatch):
    from vtkmodules.vtkRenderingCore import vtkRenderer

    from plugins.roi_viewer.interface import project_interface, view_interface

    renderer = vtkRenderer()
    monkeypatch.setattr(view_interface, "ViewInterface",
                        lambda: types.SimpleNamespace(get_volume_viewer=lambda: types.SimpleNamespace(ren=renderer)))
    pi = _real_project_interface()
    monkeypatch.setattr(project_interface, "ProjectInterface", lambda: pi)
    return renderer


def _frame(show_texture=False):
    f = types.SimpleNamespace(
        project_loaded=True,
        sync_mgr=types.SimpleNamespace(sync_2d_3d=True),
        marker_3d=CrosshairMarker3D(),
        slice_planes_3d=SlicePlanes3D(),
        textured_slice_planes_3d=TexturedSlicePlanes3D(),
        surface_clipping_3d=SurfaceClipping3D(),
        show_slice_planes=True,
        show_texture_planes=show_texture,
        _last_cross_focal_point=None,
        _texture_planes_position=None,
        request_render=lambda: None,
        place_3d_camera_if_unset=lambda: False,
    )
    for name in ("on_cross_focal_point_changed", "update_textured_slice_planes",
                 "apply_slice_plane_visibility", "_compute_volume_bounds"):
        setattr(f, name, getattr(roi_panel.ROIViewerPanel, name).__get__(f))
    return f


def _crosshair(frame, pos=SLICE_POS):
    with patch("invesalius.pubsub.pub.sendMessage"):
        frame.on_cross_focal_point_changed(pos)


def _view_frame_volume_bounds():
    """Ground truth: the real surface/volume frame - converters.to_vtk()
    of the whole volume, then the same vtkImageFlip the native surface
    (surface_process.py:156) and volume (volume.py:597) pipelines apply."""
    from vtkmodules.vtkImagingCore import vtkImageFlip

    from invesalius.data import converters

    image = converters.to_vtk(np.zeros(SHAPE, dtype=np.uint8), SPACING, 0, "AXIAL")
    flip = vtkImageFlip()
    flip.SetInputData(image)
    flip.SetFilteredAxis(1)
    flip.FlipAboutOriginOn()
    flip.Update()
    return flip.GetOutput().GetBounds()


# ------------------------------------------------------------------
# C8
# ------------------------------------------------------------------

def test_c8_marker_matches_native_3d_pointer(env):
    """Native puts its own 3D pointer at [x, -y, z] (styles.py:555)."""
    frame = _frame()
    _crosshair(frame)
    assert frame.marker_3d.get_position() == pytest.approx(VIEW_POS)


def test_c8_planes_bounds_match_real_3d_volume(env):
    frame = _frame()
    _crosshair(frame)
    assert frame.slice_planes_3d.bounds == pytest.approx(_view_frame_volume_bounds())
    # Before the fix: x up to 766.5 mm and z up to 51.2 mm on this data.
    xmin, xmax, ymin, ymax, zmin, zmax = frame.slice_planes_3d.bounds
    assert xmax == pytest.approx(511 * SX) and zmax == pytest.approx(107 * SZ)
    assert ymin == pytest.approx(-511 * SY) and ymax == pytest.approx(0.0)


def test_c8_axial_uses_z_spacing(env):
    frame = _frame()
    _crosshair(frame)
    assert frame.slice_planes_3d._planes["AXIAL"]["source"].GetOrigin()[2] == pytest.approx(Z * SZ)


def test_c8_coronal_uses_y_spacing(env):
    frame = _frame()
    _crosshair(frame)
    assert frame.slice_planes_3d._planes["CORONAL"]["source"].GetOrigin()[1] == pytest.approx(-Y * SY)


def test_c8_sagittal_uses_x_spacing(env):
    frame = _frame()
    _crosshair(frame)
    assert frame.slice_planes_3d._planes["SAGITAL"]["source"].GetOrigin()[0] == pytest.approx(X * SX)


def test_c8_axial_plane_reaches_top_of_volume(env):
    """Before the fix the axial plane was clamped to z <= 51.2 mm (the
    bottom third of 0051); the top slice must be reachable."""
    frame = _frame()
    _crosshair(frame, (0.0, 0.0, 107 * SZ))
    assert frame.slice_planes_3d._planes["AXIAL"]["source"].GetOrigin()[2] == pytest.approx(107 * SZ)


# ------------------------------------------------------------------
# 3D pick -> 2D, Region Growing seed
# ------------------------------------------------------------------

@pytest.mark.parametrize("plane,expected", [("AXIAL", Z), ("CORONAL", Y), ("SAGITAL", X)])
def test_3d_pick_maps_to_correct_slice_anisotropic(monkeypatch, plane, expected):
    """A 3D pick arrives in the view frame (Phase 09's real pick on real
    geometry returned y = -107.3); the slice selected must be VOXEL's."""
    from plugins.roi_viewer.gui import interaction_panel as ip_mod
    from plugins.roi_viewer.interface import project_interface, view_interface

    requested = []
    monkeypatch.setattr(project_interface, "ProjectInterface", _real_project_interface)
    monkeypatch.setattr(view_interface, "ViewInterface",
                        lambda: types.SimpleNamespace(set_slice_position=lambda p, i: requested.append((p, i))))
    monkeypatch.setattr(ip_mod.wx, "CallAfter", lambda fn, *a, **k: fn(*a, **k))

    sync = SyncManager2D3D()
    sync.current_plane = plane
    panel = types.SimpleNamespace(
        controller=types.SimpleNamespace(sync_mgr=sync),
        sync_3d_2d_enabled=True,
        update_coordinates=lambda *a: None,
    )
    InteractionPanel._on_point_picked.__get__(panel)(VIEW_POS)
    assert requested == [(plane, expected)]


def test_region_growing_seed_from_3d_pick_anisotropic(monkeypatch):
    """Before the fix every 3D-picked seed's coronal index clamped to 0."""
    from plugins.roi_viewer.gui import segmentation_panel as sp_mod
    from plugins.roi_viewer.interface import project_interface

    pi = _real_project_interface()
    pi.get_volume_data = lambda: types.SimpleNamespace(shape=SHAPE)
    monkeypatch.setattr(project_interface, "ProjectInterface", lambda: pi)
    monkeypatch.setattr(sp_mod.wx, "CallAfter", lambda fn, *a, **k: None)

    widget = lambda **methods: types.SimpleNamespace(**methods)
    panel = types.SimpleNamespace(
        controller=types.SimpleNamespace(
            sync_mgr=SyncManager2D3D(), seg_mgr=SegmentationManager(),
            picker=widget(remove_callback=lambda cb: None),
        ),
        btn_pick_seed=widget(SetValue=lambda v: None),
        rg_status=widget(SetLabel=lambda s: None),
        spin_rg_tolerance=widget(GetValue=lambda: 50),
        cb_enable_preview=widget(GetValue=lambda: True),  # records the seed, no growing
        btn_preview_region_growing=widget(Enable=lambda v: None),
        _preview_seed_world=None, _preview_seed_voxel=None,
    )
    panel._on_seed_picked = SegmentationPanel._on_seed_picked.__get__(panel)
    panel._on_seed_picked(VIEW_POS)
    assert panel._preview_seed_voxel == VOXEL
    assert panel._preview_seed_world == pytest.approx(SLICE_POS)


# ------------------------------------------------------------------
# E5A textured planes / E5B clipping
# ------------------------------------------------------------------

@pytest.fixture
def get_slices(monkeypatch, real_slice_and_project_singleton):
    from invesalius.data import converters

    s, proj, Project, Slice = real_slice_and_project_singleton
    Slice.instance, Project.instance = s, proj
    requested = {}

    def fake(orientation, index, *a):
        requested[orientation] = index
        h, w = {"AXIAL": (SHAPE[1], SHAPE[2]), "CORONAL": (SHAPE[0], SHAPE[2]),
                "SAGITAL": (SHAPE[0], SHAPE[1])}[orientation]
        return converters.to_vtk(np.zeros((h, w), dtype=np.uint8), SPACING, index, orientation)

    monkeypatch.setattr(s, "GetSlices", fake)
    return requested


@pytest.mark.parametrize("orientation,expected", [("AXIAL", Z), ("CORONAL", Y), ("SAGITAL", X)])
def test_texture_slice_selection_anisotropic(env, get_slices, orientation, expected):
    frame = _frame(show_texture=True)
    _crosshair(frame)
    assert get_slices[orientation] == expected


def test_texture_slice_selection_axial_anisotropic(env, get_slices):
    test_texture_slice_selection_anisotropic(env, get_slices, "AXIAL", Z)


def test_texture_slice_selection_coronal_anisotropic(env, get_slices):
    test_texture_slice_selection_anisotropic(env, get_slices, "CORONAL", Y)


def test_texture_slice_selection_sagittal_anisotropic(env, get_slices):
    test_texture_slice_selection_anisotropic(env, get_slices, "SAGITAL", X)


@pytest.mark.parametrize("orientation,axis", [("AXIAL", 2), ("CORONAL", 1), ("SAGITAL", 0)])
def test_textured_plane_coincides_with_c8_plane(env, get_slices, orientation, axis):
    frame = _frame(show_texture=True)
    _crosshair(frame)
    c8 = frame.slice_planes_3d._planes[orientation]["source"].GetOrigin()[axis]
    textured = frame.textured_slice_planes_3d._planes[orientation]["mapper"].GetInput().GetBounds()
    assert textured[2 * axis] == pytest.approx(c8)
    assert textured[2 * axis + 1] == pytest.approx(c8)


@pytest.mark.parametrize("orientation", [PLANE_AXIAL, PLANE_CORONAL, PLANE_SAGITAL])
def test_clipping_origin_matches_crosshair_anisotropic(env, orientation):
    """The clipping plane must pass through the same world point as the
    C8 slice plane of the same orientation."""
    frame = _frame()
    frame.surface_clipping_3d.set_orientation(orientation)
    _crosshair(frame)
    plane = frame.surface_clipping_3d.plane
    assert plane.GetOrigin() == pytest.approx(VIEW_POS)
    c8_origin = frame.slice_planes_3d._planes[orientation]["source"].GetOrigin()
    assert plane.EvaluateFunction(c8_origin) == pytest.approx(0.0, abs=1e-9)


# ------------------------------------------------------------------
# E4 / final surface share the 3D view frame with C8
# ------------------------------------------------------------------

def test_e4_preview_mesh_inside_c8_bounds(env):
    """E4 was already in the view frame (it reuses the surface pipeline's
    vtkImageFlip); after the fix C8 is too, so a mesh of the whole volume
    lies inside C8's plane bounds - before, their y ranges did not even
    overlap."""
    from plugins.roi_viewer.core.preview_surface_3d import build_preview_mesh

    shape, spacing = (20, 30, 40), (0.5, 0.8, 2.3)
    mask = np.zeros(shape, dtype=np.uint8)
    mask[2:-2, 2:-2, 2:-2] = 255
    mesh_bounds = build_preview_mesh(mask, spacing).GetBounds()
    c8 = coordinates.slice_bounds_to_view(coordinates.volume_bounds_world(shape, spacing))
    for axis in range(3):
        assert c8[2 * axis] <= mesh_bounds[2 * axis] and mesh_bounds[2 * axis + 1] <= c8[2 * axis + 1]
    assert mesh_bounds[3] <= 0.0
