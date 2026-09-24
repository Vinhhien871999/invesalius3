# --------------------------------------------------------------------------
# Persistent tests for the E1 (Advanced ROI Manager) additions to
# plugins/roi_viewer/core/roi_manager.py: lock/unlock, solo, show-all/
# hide-all, and the "locked ROI refuses deletion" invariant.
#
# Pure ROIManager/ROI logic - no wx, no invesalius.project singleton
# needed (rebuild_from_project_masks() itself is already covered,
# integration-marked, in test_roi_manager.py). Marked unit.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.roi_manager import ROIManager

pytestmark = pytest.mark.unit


def _mgr_with_three_rois():
    mgr = ROIManager()
    id_a = mgr.create_roi("A", mask_index=0, color=(255, 0, 0), visible=True)
    id_b = mgr.create_roi("B", mask_index=1, color=(0, 255, 0), visible=True)
    id_c = mgr.create_roi("C", mask_index=2, color=(0, 0, 255), visible=True)
    return mgr, id_a, id_b, id_c


def test_active_roi_selection():
    mgr, id_a, id_b, _ = _mgr_with_three_rois()
    # create_roi() itself already sets current_roi_id to the newest ROI.
    assert mgr.get_current_roi().name == "C"

    mgr.set_current_roi(id_a)
    assert mgr.get_current_roi() is mgr.get_roi(id_a)

    mgr.set_current_roi(id_b)
    assert mgr.get_current_roi() is mgr.get_roi(id_b)

    mgr.set_current_roi(9999)  # unknown id - no-op, active selection unchanged
    assert mgr.get_current_roi() is mgr.get_roi(id_b)


def test_visibility_toggle():
    mgr, id_a, id_b, id_c = _mgr_with_three_rois()
    assert all(roi.visible for roi in mgr.get_all_rois())

    changes = mgr.hide_all()
    assert changes == {id_a: False, id_b: False, id_c: False}
    assert not any(roi.visible for roi in mgr.get_all_rois())

    changes = mgr.show_all()
    assert changes == {id_a: True, id_b: True, id_c: True}
    assert all(roi.visible for roi in mgr.get_all_rois())

    # A second show_all() with nothing to change reports no changes -
    # callers (GUI layer) rely on this to avoid firing redundant real
    # "Show mask" pubsub messages.
    assert mgr.show_all() == {}


def test_lock_prevents_edit():
    mgr, id_a, _, _ = _mgr_with_three_rois()
    assert mgr.is_locked(id_a) is False
    assert mgr.is_locked_for_mask_index(0) is False

    assert mgr.set_locked(id_a, True) is True
    assert mgr.is_locked(id_a) is True
    assert mgr.is_locked_for_mask_index(0) is True  # what the GUI edit guards actually check

    # Unknown roi_id: set_locked reports failure, never raises.
    assert mgr.set_locked(9999, True) is False
    # Unknown mask_index: treated as "not locked" (see the method's own docstring).
    assert mgr.is_locked_for_mask_index(9999) is False


def test_unlock_restores_edit():
    mgr, id_a, _, _ = _mgr_with_three_rois()
    mgr.set_locked(id_a, True)
    assert mgr.is_locked_for_mask_index(0) is True

    assert mgr.set_locked(id_a, False) is True
    assert mgr.is_locked(id_a) is False
    assert mgr.is_locked_for_mask_index(0) is False


def test_solo_visibility():
    mgr, id_a, id_b, id_c = _mgr_with_three_rois()
    mgr.get_roi(id_b).visible = False  # B was already hidden before solo

    changes = mgr.enter_solo(id_a)
    assert mgr.solo_roi_id == id_a
    assert mgr.get_roi(id_a).visible is True
    assert mgr.get_roi(id_b).visible is False
    assert mgr.get_roi(id_c).visible is False
    # Only C's visibility actually flipped (A was already visible, B was
    # already hidden) - enter_solo() only reports real changes.
    assert changes == {id_c: False}

    restore_changes = mgr.exit_solo()
    assert mgr.solo_roi_id is None
    # Exactly B's pre-solo hidden state and C's pre-solo visible state
    # are restored - not a blanket "show everything".
    assert mgr.get_roi(id_a).visible is True
    assert mgr.get_roi(id_b).visible is False
    assert mgr.get_roi(id_c).visible is True
    assert restore_changes == {id_c: True}


def test_solo_unknown_roi_is_a_noop():
    mgr, _, _, _ = _mgr_with_three_rois()
    assert mgr.enter_solo(9999) == {}
    assert mgr.solo_roi_id is None


def test_exit_solo_without_active_solo_is_a_noop():
    mgr, _, _, _ = _mgr_with_three_rois()
    assert mgr.exit_solo() == {}


def test_show_all():
    mgr, id_a, id_b, id_c = _mgr_with_three_rois()
    mgr.enter_solo(id_a)  # engage solo first
    assert mgr.solo_roi_id == id_a

    changes = mgr.show_all()
    assert set(changes.keys()) == {id_b, id_c}  # A was already visible under solo
    assert all(roi.visible for roi in mgr.get_all_rois())
    # show_all() also cancels solo bookkeeping (see the method's docstring).
    assert mgr.solo_roi_id is None


def test_hide_all():
    mgr, id_a, id_b, id_c = _mgr_with_three_rois()
    mgr.enter_solo(id_a)
    assert mgr.solo_roi_id == id_a

    changes = mgr.hide_all()
    assert changes == {id_a: False}  # B/C were already hidden under solo
    assert not any(roi.visible for roi in mgr.get_all_rois())
    assert mgr.solo_roi_id is None


def test_delete_locked_behavior():
    mgr, id_a, id_b, _ = _mgr_with_three_rois()
    mgr.set_locked(id_a, True)

    # Default call refuses to delete a locked ROI - no mutation at all.
    assert mgr.delete_roi(id_a) is False
    assert mgr.get_roi(id_a) is not None
    assert len(mgr.get_all_rois()) == 3

    # An unlocked ROI deletes normally.
    assert mgr.delete_roi(id_b) is True
    assert mgr.get_roi(id_b) is None
    assert len(mgr.get_all_rois()) == 2

    # force=True overrides the lock (used internally by
    # rebuild_from_project_masks() when the real mask is already gone).
    assert mgr.delete_roi(id_a, force=True) is True
    assert mgr.get_roi(id_a) is None
    assert len(mgr.get_all_rois()) == 1


def test_delete_locked_solo_target_is_also_refused_and_solo_survives():
    mgr, id_a, _, _ = _mgr_with_three_rois()
    mgr.set_locked(id_a, True)
    mgr.enter_solo(id_a)
    assert mgr.solo_roi_id == id_a

    assert mgr.delete_roi(id_a) is False
    assert mgr.solo_roi_id == id_a  # refused deletion must not touch solo bookkeeping


def test_delete_unknown_roi_returns_false():
    mgr, _, _, _ = _mgr_with_three_rois()
    assert mgr.delete_roi(9999) is False
