# --------------------------------------------------------------------------
# AnalysisPreview3DManager: transient, non-pickable actors only; no camera
# change; detach removes exactly its own actors; a stale build is ignored.
# The source-change / project-close / plugin-close paths through the real
# panel are in test_analysis_panel_integration.py.
# --------------------------------------------------------------------------
import inspect

import numpy as np
import pytest

from plugins.roi_viewer.core.analysis import analysis_preview_3d as ap
from plugins.roi_viewer.core.analysis.hu_classes import HUClass

CLASSES = (HUClass(1, "a", -1100, -500, (0.2, 0.6, 1.0), True, 0.4),
           HUClass(2, "b", -500, 0, (1.0, 0.5, 0.0), True, 0.6),
           HUClass(3, "empty", 500, 600))


@pytest.fixture
def renderer():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    return vtkRenderer()


def _labels():
    lab = np.zeros((12, 14, 16), dtype=np.uint8)
    lab[2:6, 3:9, 3:9] = 1
    lab[6:10, 3:9, 3:9] = 2
    return lab


def test_one_non_pickable_actor_per_non_empty_visible_class(renderer):
    meshes = ap.build_class_meshes(_labels(), CLASSES, (1.0, 1.0, 1.0))
    assert meshes[3] is None  # an empty class gets no mesh
    m = ap.AnalysisPreview3DManager()
    assert m.show(renderer, meshes, CLASSES, m.new_generation())
    assert m.actor_count == 2 == renderer.GetActors().GetNumberOfItems()
    for actor in m.actors.values():
        assert actor.GetPickable() == 0
    assert m.actors[1].GetProperty().GetOpacity() == pytest.approx(0.4)


def test_hidden_class_has_no_mesh_and_visibility_toggle(renderer):
    classes = (CLASSES[0], CLASSES[1].with_changes(visible=False))
    meshes = ap.build_class_meshes(_labels(), classes, (1.0, 1.0, 1.0))
    assert set(meshes) == {1}
    m = ap.AnalysisPreview3DManager()
    m.show(renderer, meshes, classes, m.new_generation())
    m.set_visible(1, False)
    assert m.actors[1].GetVisibility() == 0
    m.set_opacity(1, 0.9)
    assert m.actors[1].GetProperty().GetOpacity() == pytest.approx(0.9)


def test_detach_removes_only_its_actors_and_is_idempotent(renderer):
    from vtkmodules.vtkRenderingCore import vtkActor

    other = vtkActor()
    renderer.AddActor(other)
    m = ap.AnalysisPreview3DManager()
    m.show(renderer, ap.build_class_meshes(_labels(), CLASSES, (1, 1, 1)), CLASSES, m.new_generation())
    m.detach()
    m.detach()
    assert m.actor_count == 0 and renderer.GetActors().GetNumberOfItems() == 1


def test_repeated_show_never_duplicates(renderer):
    m = ap.AnalysisPreview3DManager()
    meshes = ap.build_class_meshes(_labels(), CLASSES, (1, 1, 1))
    for _ in range(4):
        m.show(renderer, meshes, CLASSES, m.new_generation())
    assert renderer.GetActors().GetNumberOfItems() == 2


def test_stale_build_ignored(renderer):
    m = ap.AnalysisPreview3DManager()
    old = m.new_generation()
    m.detach()  # e.g. project closed while the worker was building
    assert m.show(renderer, ap.build_class_meshes(_labels(), CLASSES, (1, 1, 1)), CLASSES, old) is False
    assert renderer.GetActors().GetNumberOfItems() == 0


def test_camera_untouched(renderer):
    cam = renderer.GetActiveCamera()
    cam.SetPosition(10, 20, 30)
    m = ap.AnalysisPreview3DManager()
    m.show(renderer, ap.build_class_meshes(_labels(), CLASSES, (1, 1, 1)), CLASSES, m.new_generation())
    m.detach()
    assert cam.GetPosition() == (10.0, 20.0, 30.0)
    code_lines = [line for line in inspect.getsource(ap).splitlines() if not line.lstrip().startswith("#")]
    source = "\n".join(code_lines)
    for forbidden in ("GetActiveCamera", "ResetCamera", "SetFocalPoint", "SetViewUp", "surface_dict"):
        assert forbidden not in source
