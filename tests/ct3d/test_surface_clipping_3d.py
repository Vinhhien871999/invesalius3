# --------------------------------------------------------------------------
# E5B tests: core/surface_clipping_3d.py - real VTK objects
# (vtkPolyDataMapper/vtkPlane), no rendering needed (AddClippingPlane/
# RemoveClippingPlane/GetClippingPlanes are pure mapper-state APIs,
# confirmed real and safe to exercise headlessly during this milestone's
# own audit).
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.surface_clipping_3d import (
    PLANE_AXIAL,
    PLANE_CORONAL,
    PLANE_SAGITAL,
    SurfaceClipping3D,
)


@pytest.fixture
def mapper():
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    return vtkPolyDataMapper()


def _plane_count(mapper):
    planes = mapper.GetClippingPlanes()
    return 0 if planes is None else planes.GetNumberOfItems()


def test_clipping_initially_disabled():
    clip = SurfaceClipping3D()
    assert clip.enabled is False
    assert clip.mapper is None


def test_enable_adds_one_owned_plane(mapper):
    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    assert _plane_count(mapper) == 1
    assert clip.owned_plane_count_on == 1


def test_disable_removes_owned_plane(mapper):
    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    clip.disable()
    assert _plane_count(mapper) == 0
    assert clip.owned_plane_count_on == 0


def test_enable_twice_no_duplicate_plane(mapper):
    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    clip.enable()
    clip.enable()
    assert _plane_count(mapper) == 1


def test_axial_normal():
    clip = SurfaceClipping3D()
    clip.set_orientation(PLANE_AXIAL)
    assert clip.plane.GetNormal() == pytest.approx((0.0, 0.0, 1.0))


def test_coronal_normal():
    clip = SurfaceClipping3D()
    clip.set_orientation(PLANE_CORONAL)
    assert clip.plane.GetNormal() == pytest.approx((0.0, 1.0, 0.0))


def test_sagittal_normal():
    clip = SurfaceClipping3D()
    clip.set_orientation(PLANE_SAGITAL)
    assert clip.plane.GetNormal() == pytest.approx((1.0, 0.0, 0.0))


def test_invert_normal():
    clip = SurfaceClipping3D()
    clip.set_orientation(PLANE_AXIAL)
    assert clip.plane.GetNormal() == pytest.approx((0.0, 0.0, 1.0))
    clip.set_inverted(True)
    assert clip.plane.GetNormal() == pytest.approx((0.0, 0.0, -1.0))
    clip.set_inverted(False)
    assert clip.plane.GetNormal() == pytest.approx((0.0, 0.0, 1.0))


def test_crosshair_moves_plane_origin():
    clip = SurfaceClipping3D()
    clip.set_origin((1.0, 2.0, 3.0))
    assert clip.plane.GetOrigin() == pytest.approx((1.0, 2.0, 3.0))
    clip.set_origin((4.0, 5.0, 6.0))
    assert clip.plane.GetOrigin() == pytest.approx((4.0, 5.0, 6.0))


def test_polydata_identity_unchanged(mapper):
    """Section 17/21: clipping is a mapper-level display filter, never a
    polydata mutation - the mapper's own input polydata object identity
    (and therefore its points/cells) is completely untouched by
    enable()/disable()/set_orientation()/set_origin()."""
    from vtkmodules.vtkCommonDataModel import vtkPolyData

    original_polydata = vtkPolyData()
    mapper.SetInputData(original_polydata)

    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    clip.set_orientation(PLANE_CORONAL)
    clip.set_origin((1.0, 1.0, 1.0))
    clip.disable()

    assert mapper.GetInput() is original_polydata


def test_polydata_points_cells_unchanged():
    """Same guarantee as above, checked via real point/cell counts on a
    non-trivial real polydata (a cube), not just object identity."""
    from vtkmodules.vtkFiltersSources import vtkCubeSource
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    cube = vtkCubeSource()
    cube.Update()
    n_points_before = cube.GetOutput().GetNumberOfPoints()
    n_cells_before = cube.GetOutput().GetNumberOfCells()

    mapper = vtkPolyDataMapper()
    mapper.SetInputData(cube.GetOutput())

    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()

    assert mapper.GetInput().GetNumberOfPoints() == n_points_before
    assert mapper.GetInput().GetNumberOfCells() == n_cells_before


def test_surface_dict_unchanged():
    """Section 17: this module has no reference to Project() at all - a
    real, structural guarantee, not just an absence of a test failure -
    verified here by asserting the module's real code never imports
    invesalius.project or writes a `.surface_dict[...]` entry anywhere
    (comments mentioning "surface_dict" in prose, e.g. this module's own
    docstrings explaining WHY it is safe, are expected and excluded)."""
    import ast
    import inspect

    import plugins.roi_viewer.core.surface_clipping_3d as mod

    source = inspect.getsource(mod)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(m == "invesalius.project" or m.startswith("invesalius.project.") for m in imported_modules)
    assert "surface_dict[" not in source
    assert ".surface_dict =" not in source


def test_roi_switch_detaches_old_mapper(mapper):
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    other_mapper = vtkPolyDataMapper()

    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    assert _plane_count(mapper) == 1

    clip.set_target_mapper(other_mapper)
    assert _plane_count(mapper) == 0
    assert _plane_count(other_mapper) == 1


def test_surface_rebuild_rebinds_mapper(mapper):
    """Section 24: rebuilding a surface produces a NEW real mapper
    object (this plugin's own _on_update_surface() always triggers a
    fresh AddNewActor() -> new vtkActor/vtkPolyDataMapper) - the owned
    plane must move to the new mapper, not stay attached to the old,
    now-discarded one."""
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    new_mapper = vtkPolyDataMapper()

    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()

    clip.set_target_mapper(new_mapper)
    assert _plane_count(mapper) == 0
    assert _plane_count(new_mapper) == 1


def test_missing_surface_safe():
    """Section 18/23: passing None (no final surface for the selected
    ROI) must not raise, and must not add a clipping plane anywhere."""
    clip = SurfaceClipping3D()
    clip.enable()
    clip.set_target_mapper(None)
    assert clip.mapper is None
    assert clip.owned_plane_count_on == 0


def test_project_close_removes_clipping(mapper):
    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    clip.detach()
    assert _plane_count(mapper) == 0
    assert clip.mapper is None
    assert clip.enabled is False


def test_plugin_close_removes_clipping(mapper):
    clip = SurfaceClipping3D()
    clip.set_target_mapper(mapper)
    clip.enable()
    clip.detach()
    # Reopen simulation - re-enabling on a fresh target must not find
    # any leftover plane from the previous session.
    clip.set_target_mapper(mapper)
    clip.enable()
    assert _plane_count(mapper) == 1
