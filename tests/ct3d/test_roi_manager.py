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


# --------------------------------------------------------------------------
# E1 (Advanced ROI Manager): interaction between the new lock/solo
# bookkeeping and rebuild_from_project_masks() - the one place lock/solo
# state has to survive (or correctly NOT survive) contact with the real
# Project().mask_dict.
# --------------------------------------------------------------------------
def test_roi_project_sync(project):
    """`.locked` (E1) has no real Mask counterpart, so a rebuild that
    resyncs name/color/visible from the real mask must leave an
    already-set `.locked` flag alone - it's a plugin-only field, not
    something a native-tab rename could ever change."""
    project.mask_dict = {0: _fake_mask("A")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    roi_id = list(mgr.rois.keys())[0]
    mgr.set_locked(roi_id, True)

    project.mask_dict[0].name = "A-renamed"  # real rename via native Masks tab
    mgr.rebuild_from_project_masks()

    roi = mgr.get_roi_by_mask_index(0)
    assert roi.name == "A-renamed"  # real data resynced
    assert roi.locked is True  # plugin-only field untouched by the resync


def test_rebuild_after_project_load(project):
    """Simulates opening a DIFFERENT project (a full mask_dict swap, not
    an incremental edit) while a ROI was solo'd - the solo target from
    the old project must not dangle onto whatever the new project's
    mask_dict happens to reuse as an index."""
    project.mask_dict = {0: _fake_mask("Old A"), 1: _fake_mask("Old B")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    old_mask0_roi = mgr.get_roi_by_mask_index(0)  # the "Old A" ROI object, for the identity check below
    mgr.enter_solo(mgr.current_roi_id if mgr.current_roi_id is not None else list(mgr.rois.keys())[0])
    assert mgr.solo_roi_id is not None

    # A different project loaded - entirely different masks (simulated
    # by wiping mask_dict as on_project_close()/ROIManager.clear() would
    # do, then rebuilding against the new project's masks, exactly as
    # ROIViewerFrame.on_project_load() -> on_roi_source_changed() does).
    mgr.clear()
    assert mgr.solo_roi_id is None
    project.mask_dict = {0: _fake_mask("New X")}
    mgr.rebuild_from_project_masks()

    assert len(mgr.get_all_rois()) == 1
    assert mgr.get_roi_by_mask_index(0).name == "New X"
    assert mgr.get_roi_by_mask_index(0).locked is False  # fresh ROI, never locked in this session
    assert mgr.solo_roi_id is None
    assert old_mask0_roi is not mgr.get_roi_by_mask_index(0)  # not the stale object from the old project


def test_no_orphan_roi_with_locked_and_solo_state(project):
    """Extends the base "no orphan ROI" invariant: a locked, solo'd ROI
    whose real mask is removed via the native Masks tab must still be
    dropped (delete_roi()'s force=True path in
    rebuild_from_project_masks() - see that method's own NOTE) and must
    not leave solo_roi_id dangling."""
    project.mask_dict = {0: _fake_mask("A"), 1: _fake_mask("B")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    roi_a_id = mgr.get_roi_by_mask_index(0)
    a_id = [rid for rid, roi in mgr.rois.items() if roi is roi_a_id][0]
    mgr.set_locked(a_id, True)
    mgr.enter_solo(a_id)
    assert mgr.solo_roi_id == a_id

    del project.mask_dict[0]  # real mask removed via native tab, even though "locked" in the plugin
    mgr.rebuild_from_project_masks()

    assert mgr.get_roi_by_mask_index(0) is None
    assert mgr.solo_roi_id is None  # no dangling reference to the now-deleted ROI
    assert all(r.mask_index in project.mask_dict for r in mgr.get_all_rois())
    assert len(mgr.get_all_rois()) == 1


def test_save_open_metadata_roundtrip_if_metadata_added(project):
    """E1's `.locked` field is a deliberate, documented exception to
    "everything here mirrors a real Mask attribute" (see the ROI class
    docstring and docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md): it
    is intentionally NEVER written to any real Mask field, so a project
    close+reopen cycle (simulated here the same way
    ROIViewerFrame.on_project_close()/on_project_load() drive it:
    ROIManager.clear() then rebuild_from_project_masks() again) must
    NOT preserve it. This test exists to make that deliberate
    non-persistence decision an explicit, checked contract rather than
    an unstated assumption - if a future change accidentally started
    persisting `.locked` through some other path, this test would need
    to be updated deliberately, not silently pass either way."""
    project.mask_dict = {0: _fake_mask("A")}
    mgr = ROIManager()
    mgr.rebuild_from_project_masks()
    roi_id = list(mgr.rois.keys())[0]
    mgr.set_locked(roi_id, True)
    assert mgr.is_locked_for_mask_index(0) is True

    # Simulate a real project close + reopen of the SAME underlying
    # project file (same mask, same index) - the only thing that could
    # possibly carry `.locked` across is a fresh ROIManager rebuilding
    # from the real (unchanged) mask_dict.
    mgr.clear()
    mgr.rebuild_from_project_masks()

    assert mgr.is_locked_for_mask_index(0) is False  # confirmed NOT persisted, as documented
