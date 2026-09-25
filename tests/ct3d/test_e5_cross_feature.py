# --------------------------------------------------------------------------
# E5 cross-feature integration tests (Section 33): prove E5A (textured
# slice planes) and E5B (clipping) coexist safely with C8 (marker +
# geometric slice planes) and E4 (fast live 3D preview), and that both
# stay strictly display-only / camera-safe / picker-safe / inert when
# off. Real VTK objects, no wx event loop needed (same style as the
# other E5 test files).
# --------------------------------------------------------------------------
import inspect

import pytest

from plugins.roi_viewer.core.marker_3d import CrosshairMarker3D
from plugins.roi_viewer.core.preview_surface_3d import PreviewSurfaceManager3D
from plugins.roi_viewer.core.slice_planes_3d import SlicePlanes3D
from plugins.roi_viewer.core.surface_clipping_3d import PLANE_AXIAL, SurfaceClipping3D
from plugins.roi_viewer.core.textured_slice_planes_3d import TexturedSlicePlanes3D


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


def _imported_module_names(module):
    import ast

    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_e5_preserves_c8_marker(renderer):
    """CrosshairMarker3D (C8) keeps working exactly as before - attached
    and positioned independently of whatever E5 objects also exist in
    the same renderer, and E5's own modules never IMPORT it at all
    (structural guarantee via real AST inspection - prose mentions of
    "marker_3d" in these modules' own comparison-explaining docstrings
    are expected and excluded, only real import statements count)."""
    import plugins.roi_viewer.core.surface_clipping_3d as clip_mod
    import plugins.roi_viewer.core.textured_slice_planes_3d as tex_mod

    for mod in (clip_mod, tex_mod):
        imported = _imported_module_names(mod)
        assert not any("marker_3d" in name for name in imported), imported

    marker = CrosshairMarker3D()
    textured = TexturedSlicePlanes3D()
    marker.attach(renderer)
    textured.attach(renderer)
    marker.update_position(1.0, 2.0, 3.0)

    assert marker.get_position() == pytest.approx((1.0, 2.0, 3.0))
    assert marker.actor.GetVisibility() == 1
    assert textured.actor_count == 3


def test_e5_preserves_c8_geometric_planes(renderer):
    """SlicePlanes3D (C8's geometric planes) is untouched by E5 - real
    functional smoke test proving its own real attach/bounds/position/
    visibility API still works exactly as before, in the presence of a
    co-attached TexturedSlicePlanes3D in the same renderer."""
    sp = SlicePlanes3D()
    textured = TexturedSlicePlanes3D()
    sp.attach(renderer)
    textured.attach(renderer)

    sp.set_bounds((0.0, 10.0, 0.0, 10.0, 0.0, 10.0))
    sp.update_position((5.0, 5.0, 5.0))
    sp.set_visible(True)

    assert sp.actor_count == 3
    assert sp.get_position() == pytest.approx((5.0, 5.0, 5.0))
    for entry in sp._planes.values():
        assert entry["actor"].GetVisibility() == 1
    # Both plane sets coexist in the same renderer without interfering.
    assert renderer.GetActors().GetNumberOfItems() == 6


def test_textured_planes_coexist_with_e4_preview(renderer):
    textured = TexturedSlicePlanes3D()
    preview = PreviewSurfaceManager3D()

    textured.attach(renderer)
    preview.attach(renderer)

    assert textured.actor_count == 3
    assert preview.actor_count == 1
    assert renderer.GetActors().GetNumberOfItems() == 4

    textured.set_visible(True)
    preview.set_visible(True)
    # Independent visibility - toggling one never toggles the other.
    textured.set_visible(False)
    assert preview.actor.GetVisibility() == 1


def test_clipping_does_not_rebuild_surface(real_slice_and_project_singleton):
    """Real dynamic proof (a pubsub spy), not just a source grep -
    matching E3/E4's own established pattern for this exact claim.

    Depends on the shared real_slice_and_project_singleton fixture (not
    used for its Slice()/Project() objects directly, only as a real
    dependency) purely to guarantee a real Slice() has already been
    constructed - and therefore "Create surface from index" already has
    its real pypubsub message-argument spec established by Slice.
    CreateSurfaceFromIndex(self, surface_parameters)'s own real
    signature - BEFORE this test's own bare `**kwargs` spy subscribes.
    Without this, if this test happened to run before any other test in
    the session had constructed a real Slice() yet, this spy would
    itself become the first-ever subscriber and incorrectly fix the
    topic's pypubsub spec from its own permissive signature, causing a
    real, deterministic ListenerMismatchError the NEXT time a real
    Slice() is constructed elsewhere in the session - a genuine
    regression this exact file caused and fixed within this same
    milestone's own regression pass (see docs/CT3D_ADVANCED_E5_
    VISUALIZATION_REPORT.md's "Regression" section)."""
    from invesalius.pubsub import pub as Publisher
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    calls = []

    def _spy(**kwargs):
        calls.append(kwargs)

    Publisher.subscribe(_spy, "Create surface from index")
    try:
        mapper = vtkPolyDataMapper()
        clip = SurfaceClipping3D()
        clip.set_target_mapper(mapper)
        clip.enable()
        clip.set_orientation(PLANE_AXIAL)
        clip.set_origin((1.0, 2.0, 3.0))
        clip.set_inverted(True)
        clip.disable()
        clip.detach()
    finally:
        Publisher.unsubscribe(_spy, "Create surface from index")

    assert calls == []


def test_clipping_does_not_modify_mask():
    """Structural guarantee: core/surface_clipping_3d.py never imports
    anything from invesalius.data.mask - it is impossible for it to
    write to a Mask's matrix, since it never obtains a reference to
    one."""
    import plugins.roi_viewer.core.surface_clipping_3d as clip_mod

    source = inspect.getsource(clip_mod)
    assert "invesalius.data.mask" not in source
    assert ".matrix[" not in source


def test_clipping_does_not_block_picker():
    """Clipping only ever calls AddClippingPlane/RemoveClippingPlane on
    the TARGET mapper - it never touches that surface's own actor's
    SetPickable() state (unlike E5A's/E4's/C8's OWN actors, which
    correctly set SetPickable(False) on THEMSELVES). A real final
    surface actor's pre-existing pickable state (whatever native code
    set it to) must survive enable()/disable() untouched."""
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

    mapper = vtkPolyDataMapper()
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.SetPickable(True)  # simulate whatever native code already set

    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    assert actor.GetPickable() == 1
    clip.disable()
    assert actor.GetPickable() == 1


def test_camera_unchanged():
    """Source-inspection guarantee (same real technique E4's own
    test_camera_never_touched_by_manager_api/test_gui_layer_never_
    touches_camera already established): neither E5 core module, nor
    InteractionPanel's/ROIViewerFrame's new E5 methods, contain any
    camera-related VTK call."""
    import plugins.roi_viewer.core.surface_clipping_3d as clip_mod
    import plugins.roi_viewer.core.textured_slice_planes_3d as tex_mod
    import plugins.roi_viewer.gui.interaction_panel as interaction_mod
    import plugins.roi_viewer.gui.roi_panel as roi_panel_mod

    camera_calls = ("GetActiveCamera", "ResetCamera", "SetPosition", "SetFocalPoint", "SetViewUp")

    for mod in (clip_mod, tex_mod):
        source = inspect.getsource(mod)
        for call in camera_calls:
            assert call not in source, f"{mod.__name__} unexpectedly references {call}"

    # The GUI-layer methods specifically (not the whole file, which also
    # contains pre-existing, unrelated camera-agnostic code) - matching
    # E4's own scoped-source-slice convention.
    e5_gui_sources = "".join(
        inspect.getsource(getattr(interaction_mod.InteractionPanel, name))
        for name in (
            "_on_texture_planes_toggle", "_on_clip_enabled_toggle",
            "_on_clip_plane_changed", "_on_clip_invert_toggle",
            "_on_clip_target_changed", "refresh_clipping_target",
        )
    )
    e5_gui_sources += inspect.getsource(roi_panel_mod.ROIViewerFrame.update_textured_slice_planes)
    for call in camera_calls:
        assert call not in e5_gui_sources, f"E5 GUI code unexpectedly references {call}"


def test_e5_off_matches_e4_behavior(renderer):
    """Section 8/39: with both E5 features left at their real default
    (never enabled), they must have ZERO footprint - no attached actor,
    no owned clipping plane - so E4 (and everything else) behaves
    exactly as if E5 did not exist."""
    textured = TexturedSlicePlanes3D()
    clip = SurfaceClipping3D()

    assert not textured.is_attached
    assert textured.actor_count == 0
    assert clip.enabled is False
    assert clip.owned_plane_count_on == 0

    # E4 itself is unaffected by E5 objects simply existing unattached.
    preview = PreviewSurfaceManager3D()
    preview.attach(renderer)
    assert preview.actor_count == 1
    assert renderer.GetActors().GetNumberOfItems() == 1
