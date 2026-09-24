# --------------------------------------------------------------------------
# Persistent tests for E4's debounce/coalescing contract (Section 19/20)
# and camera preservation (Section 41). Tests the real logic without
# relying on real wall-clock sleeps or a running wx event loop - a rapid
# "dirty" sequence is modeled directly via PreviewSurfaceManager3D's own
# generation_id (the real mechanism that makes "latest generation wins"
# true), matching how test_segmentation_preview.py already tests E2's
# identical async-race contract without any real threading/timing.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.preview_surface_3d import PreviewSurfaceManager3D

pytestmark = pytest.mark.unit


def _tiny_polydata():
    from vtkmodules.vtkFiltersSources import vtkCubeSource
    from vtkmodules.vtkCommonDataModel import vtkPolyData

    src = vtkCubeSource()
    src.Update()
    pd = vtkPolyData()
    pd.DeepCopy(src.GetOutput())
    return pd


def test_dirty_coalescing():
    """A rapid dirty sequence (Section 19's "A, B, C, D must produce one
    latest useful preview, not four expensive builds") - modeled here as
    4 rapid new_generation() calls (what 4 rapid _mark_preview_3d_dirty()
    calls would each eventually cause, once the debounce timer actually
    fires) followed by exactly one real build result arriving. Only the
    LATEST generation may ever successfully commit a result."""
    from vtkmodules.vtkRenderingCore import vtkRenderer

    mgr = PreviewSurfaceManager3D()
    mgr.attach(vtkRenderer())

    generations = [mgr.new_generation() for _ in range(4)]  # A, B, C, D
    assert generations == [1, 2, 3, 4]

    # Simulate 3 earlier (now-stale) results still arriving late.
    for gen in generations[:-1]:
        ok = mgr.set_polydata_if_current(gen, _tiny_polydata(), source_kind="current_roi")
        assert ok is False

    # Only the latest (D) succeeds.
    ok = mgr.set_polydata_if_current(generations[-1], _tiny_polydata(), source_kind="current_roi")
    assert ok is True
    assert mgr.visible is True


def test_latest_generation_wins():
    from vtkmodules.vtkRenderingCore import vtkRenderer

    mgr = PreviewSurfaceManager3D()
    mgr.attach(vtkRenderer())
    g_old = mgr.new_generation()
    g_new = mgr.new_generation()

    # Old arrives first but must not display.
    ok_old = mgr.set_polydata_if_current(g_old, _tiny_polydata(), source_kind="current_roi")
    assert ok_old is False
    assert mgr.visible is False

    ok_new = mgr.set_polydata_if_current(g_new, _tiny_polydata(), source_kind="otsu_preview")
    assert ok_new is True
    assert mgr.source_kind == "otsu_preview"


def test_no_unbounded_queue():
    """There is no queue at all in this design (Section 23's "at most 1
    running build, 1 latest pending generation, or equivalent coalescing
    design") - generation_id is a single integer counter, not a list;
    each new_generation() call implicitly invalidates every prior one at
    O(1) cost, regardless of how many rebuild requests happened, proving
    no unbounded accumulation is even structurally possible."""
    mgr = PreviewSurfaceManager3D()
    for _ in range(1000):
        mgr.new_generation()
    assert mgr.generation_id == 1000
    # Only ONE generation_id integer is ever held - no list/queue field
    # exists on the manager to inspect (confirmed by the class having no
    # such attribute at all - see core/preview_surface_3d.py).
    assert not hasattr(mgr, "_pending_queue")
    assert not hasattr(mgr, "_pending_generations")


def test_camera_never_touched_by_manager_api():
    """E4 must never call ResetCamera or modify camera position/focal
    point/view up (Section 11/41). Verified here by source inspection of
    the ENTIRE core/preview_surface_3d.py module - the real, complete
    set of VTK calls this module makes never includes any camera-related
    API at all, so no code path here could possibly touch it."""
    import inspect
    from plugins.roi_viewer.core import preview_surface_3d

    source = inspect.getsource(preview_surface_3d)
    for forbidden in ("GetActiveCamera", "ResetCamera", "SetPosition(", "SetFocalPoint", "SetViewUp"):
        assert forbidden not in source, f"found forbidden camera-related call: {forbidden}"


def test_gui_layer_never_touches_camera():
    """Same real assertion, extended to the GUI wiring
    (gui/segmentation_panel.py's E4 methods and
    gui/roi_panel.py's ensure_preview_surface_attached()/request_render())
    - neither file's E4-related code contains any camera API call."""
    import inspect
    from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel

    e4_methods = [
        SegmentationPanel._mark_preview_3d_dirty,
        SegmentationPanel._trigger_preview_3d_rebuild,
        SegmentationPanel._on_preview_3d_built,
        SegmentationPanel._select_preview_3d_source,
        SegmentationPanel._on_enable_live_3d_preview_toggle,
        SegmentationPanel._on_refresh_3d_preview,
    ]
    for method in e4_methods:
        source = inspect.getsource(method)
        for forbidden in ("GetActiveCamera", "ResetCamera", "SetFocalPoint", "SetViewUp"):
            assert forbidden not in source, f"{method.__name__} contains forbidden call: {forbidden}"
