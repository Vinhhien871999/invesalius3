# --------------------------------------------------------------------------
# Persistent tests for E4 (Advanced Segmentation Enhancement Track):
# core/preview_surface_3d.PreviewSurfaceManager3D - actor lifecycle,
# generation guard. Real VTK renderer/actors, no wx/GUI needed -
# integration-marked, matching test_slice_planes_3d.py's/
# test_sync_2d3d.py's convention for core/marker_3d.py-style managers.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.preview_surface_3d import PreviewSurfaceManager3D

pytestmark = pytest.mark.integration


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


def _tiny_polydata():
    from vtkmodules.vtkFiltersSources import vtkCubeSource

    src = vtkCubeSource()
    src.Update()
    from vtkmodules.vtkCommonDataModel import vtkPolyData

    pd = vtkPolyData()
    pd.DeepCopy(src.GetOutput())
    return pd


def test_manager_initial_state():
    mgr = PreviewSurfaceManager3D()
    assert mgr.actor_count == 0
    assert mgr.is_attached() is False
    assert mgr.visible is False
    assert mgr.generation_id == 0


def test_attach_once(renderer):
    mgr = PreviewSurfaceManager3D()
    assert mgr.attach(renderer) is True
    assert mgr.actor_count == 1
    assert mgr.is_attached() is True
    assert renderer.GetActors().GetNumberOfItems() == 1


def test_attach_twice_no_duplicate(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    mgr.attach(renderer)  # repeated attach to the SAME renderer
    assert mgr.actor_count == 1
    assert renderer.GetActors().GetNumberOfItems() == 1


def test_attach_to_new_renderer_moves_not_duplicates():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    r1, r2 = vtkRenderer(), vtkRenderer()
    mgr = PreviewSurfaceManager3D()
    mgr.attach(r1)
    mgr.attach(r2)
    assert r1.GetActors().GetNumberOfItems() == 0
    assert r2.GetActors().GetNumberOfItems() == 1
    assert mgr.actor_count == 1


def test_actor_non_pickable(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    assert mgr.actor.GetPickable() == 0


def test_visibility(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    assert mgr.actor.GetVisibility() == 0  # starts hidden

    gen = mgr.new_generation()
    mgr.set_polydata_if_current(gen, _tiny_polydata(), source_kind="current_roi")
    assert mgr.visible is True
    assert mgr.actor.GetVisibility() == 1

    mgr.set_visible(False)
    assert mgr.visible is False
    assert mgr.actor.GetVisibility() == 0


def test_clear(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    gen = mgr.new_generation()
    mgr.set_polydata_if_current(gen, _tiny_polydata(), source_kind="current_roi")
    assert mgr.visible is True

    mgr.clear()
    assert mgr.visible is False
    assert mgr.source_kind is None
    assert mgr.is_attached() is True  # clear() does NOT detach


def test_detach(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    mgr.detach()
    assert mgr.actor_count == 0
    assert mgr.is_attached() is False
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_detach_idempotent(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    mgr.detach()
    mgr.detach()  # must not raise


def test_generation_increment():
    mgr = PreviewSurfaceManager3D()
    g1 = mgr.new_generation()
    g2 = mgr.new_generation()
    assert g2 != g1
    assert g2 == g1 + 1


def test_stale_generation_rejected(renderer):
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    g1 = mgr.new_generation()
    g2 = mgr.new_generation()  # a newer build started before g1's "worker" finished

    ok = mgr.set_polydata_if_current(g1, _tiny_polydata(), source_kind="current_roi")
    assert ok is False  # g1 is stale - discarded
    assert mgr.visible is False  # unaffected by the stale result

    ok2 = mgr.set_polydata_if_current(g2, _tiny_polydata(), source_kind="current_roi")
    assert ok2 is True
    assert mgr.visible is True


def test_disable_invalidates(renderer):
    """"Disable" (Enable Live 3D Preview unticked) is realized by the
    GUI layer calling clear() - verified here at the manager level:
    clear() bumps generation_id, so a subsequently-arriving stale build
    is rejected even after hiding."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    g1 = mgr.new_generation()
    mgr.clear()  # simulates "disable"
    ok = mgr.set_polydata_if_current(g1, _tiny_polydata(), source_kind="current_roi")
    assert ok is False


def test_project_close_invalidates(renderer):
    """Project close is realized by the GUI layer calling detach() (see
    gui/roi_panel.py's on_project_close(), same pattern as marker_3d/
    slice_planes_3d) - verified here: detach() bumps generation_id and
    removes the actor."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    g1 = mgr.new_generation()
    mgr.detach()
    assert mgr.is_attached() is False
    ok = mgr.set_polydata_if_current(g1, _tiny_polydata(), source_kind="current_roi")
    assert ok is False  # stale AND no mapper to update


def test_plugin_close_invalidates(renderer):
    """Same real mechanism as project close - plugin destroy also just
    calls detach()."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    mgr.detach()
    assert mgr.actor_count == 0


def test_source_change_invalidates(renderer):
    """Switching ROI/source (Section 27) is realized by the GUI layer
    calling clear() before scheduling a new build for the new source -
    verified at the manager level: a build for the OLD source, if still
    in flight, must be rejected once a new generation for the NEW
    source has started."""
    mgr = PreviewSurfaceManager3D()
    mgr.attach(renderer)
    g_old = mgr.new_generation()
    mgr.set_polydata_if_current(g_old, _tiny_polydata(), source_kind="current_roi")

    mgr.clear()  # switching source
    g_new = mgr.new_generation()

    # The old source's (slow) build finishes late - must be rejected.
    ok = mgr.set_polydata_if_current(g_old, _tiny_polydata(), source_kind="current_roi")
    assert ok is False

    ok2 = mgr.set_polydata_if_current(g_new, _tiny_polydata(), source_kind="otsu_preview")
    assert ok2 is True
    assert mgr.source_kind == "otsu_preview"
