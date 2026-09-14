# --------------------------------------------------------------------------
# Persistent tests for plugins/roi_viewer/core/roi_manager.py (D8: ROI
# List is a cache/view of Project().mask_dict, never a second source of
# truth). CT3D_P11_TEST_AUTOMATION, Section XIV.
#
# rebuild_from_project_masks() only ever reads Project().mask_dict via
# duck-typed getattr("colour"/"is_shown"/"name") - real invesalius.data.
# mask.Mask objects are not needed, lightweight stand-ins are enough to
# exercise the real rebuild logic against the real Project() singleton.
# Marked integration (imports invesalius.project) even though it needs
# no wx widget tree.
# --------------------------------------------------------------------------
import types

import pytest

from plugins.roi_viewer.core.roi_manager import ROIManager

pytestmark = pytest.mark.integration


def _fake_mask(name, colour=(255, 0, 0), is_shown=True):
    return types.SimpleNamespace(name=name, colour=colour, is_shown=is_shown)


@pytest.fixture
def project():
    import invesalius.project as prj

    p = prj.Project()
    p.mask_dict = {}
    return p


def test_rebuild_creates_roi_for_each_real_mask(project):
    project.mask_dict = {0: _fake_mask("Mask A"), 1: _fake_mask("Mask B")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    assert len(mgr.get_all_rois()) == 2
    names = sorted(r.name for r in mgr.get_all_rois())
    assert names == ["Mask A", "Mask B"]


def test_rebuild_updates_existing_roi_in_place_on_rename(project):
    project.mask_dict = {0: _fake_mask("Old Name")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    roi = mgr.get_roi_by_mask_index(0)
    roi_id_before = mgr.current_roi_id if mgr.current_roi_id is not None else next(iter(mgr.rois))

    project.mask_dict[0].name = "New Name"  # simulate a rename via InVesalius's native Masks tab
    mgr.rebuild_from_project_masks()

    assert roi.name == "New Name"  # same object, updated in place
    assert mgr.get_roi(list(mgr.rois.keys())[0]) is roi  # identity preserved, not replaced


def test_rebuild_reflects_visibility_toggle(project):
    project.mask_dict = {0: _fake_mask("M", is_shown=True)}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(0).visible is True

    project.mask_dict[0].is_shown = False  # toggled via InVesalius's native tab
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(0).visible is False


def test_rebuild_drops_roi_when_mask_removed_no_orphan(project):
    project.mask_dict = {0: _fake_mask("A"), 1: _fake_mask("B")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    assert len(mgr.get_all_rois()) == 2

    del project.mask_dict[0]  # real mask removed (via plugin or native tab)
    mgr.rebuild_from_project_masks()

    rois = mgr.get_all_rois()
    assert len(rois) == 1
    assert rois[0].name == "B"
    # invariant: no ROI whose mask_index isn't in the real mask_dict
    assert all(r.mask_index in project.mask_dict for r in mgr.get_all_rois())


def test_rebuild_with_empty_mask_dict_is_a_noop_not_an_error(project):
    project.mask_dict = {}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()  # must not raise
    assert mgr.get_all_rois() == []


def test_rebuild_picks_up_masks_created_outside_the_plugin(project):
    """Covers the scenario the module docstring describes: a mask
    created via InVesalius's OWN native UI, never through this plugin's
    threshold/region-growing buttons, must still appear after rebuild."""
    project.mask_dict = {}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    assert mgr.get_all_rois() == []

    project.mask_dict[5] = _fake_mask("Native Mask")  # not created via mgr.create_roi()
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(5) is not None
    assert mgr.get_roi_by_mask_index(5).name == "Native Mask"


def test_no_orphan_roi_invariant_after_repeated_create_rename_hide_remove(project):
    """A denser scenario chaining several real operations, asserting the
    "no orphan ROI" invariant after each step."""
    project.mask_dict = {0: _fake_mask("A"), 1: _fake_mask("B"), 2: _fake_mask("C")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()

    project.mask_dict[1].name = "B-renamed"
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(1).name == "B-renamed"
    assert all(r.mask_index in project.mask_dict for r in mgr.get_all_rois())

    project.mask_dict[2].is_shown = False
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(2).visible is False
    assert all(r.mask_index in project.mask_dict for r in mgr.get_all_rois())

    del project.mask_dict[0]
    mgr.rebuild_from_project_masks()
    assert mgr.get_roi_by_mask_index(0) is None
    assert all(r.mask_index in project.mask_dict for r in mgr.get_all_rois())
    assert len(mgr.get_all_rois()) == 2
