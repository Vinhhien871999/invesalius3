# --------------------------------------------------------------------------
# Persistent unit tests for plugins/roi_viewer/core/annotation.py
# (F1-F4 annotation logic/persistence). CT3D_P11_TEST_AUTOMATION,
# Section XII. Pure Python (json/os/datetime) - no wx/InVesalius
# dependency for AnnotationManager itself.
# --------------------------------------------------------------------------
import pytest

from plugins.roi_viewer.core.annotation import AnnotationManager

pytestmark = pytest.mark.unit


@pytest.fixture
def mgr():
    return AnnotationManager()


def _add(mgr, text="note", pos=(1.0, 2.0, 3.0)):
    return mgr.add_annotation(
        text=text, position=pos, voxel_position=(1, 2, 3), slice_index=5, plane="AXIAL"
    )


def test_add_annotation_returns_incrementing_ids(mgr):
    id0 = _add(mgr, "first")
    id1 = _add(mgr, "second")
    assert id0 == 0
    assert id1 == 1
    assert mgr.get_annotation_count() == 2


def test_add_sets_current_annotation(mgr):
    aid = _add(mgr)
    assert mgr.current_annotation_id == aid
    assert mgr.get_current_annotation().text == "note"


def test_edit_updates_text_and_modified_at(mgr):
    aid = _add(mgr, "original")
    original_modified = mgr.get_annotation(aid).modified_at
    mgr.update_annotation(aid, text="edited")
    assert mgr.get_annotation(aid).text == "edited"
    assert mgr.get_annotation(aid).modified_at >= original_modified


def test_edit_nonexistent_annotation_is_a_noop(mgr):
    mgr.update_annotation(999, text="x")  # must not raise


def test_delete_removes_and_reindexes_current(mgr):
    id0 = _add(mgr, "a")
    id1 = _add(mgr, "b")
    id2 = _add(mgr, "c")
    mgr.set_current_annotation(id2)
    mgr.delete_annotation(id0)  # deletes index 0; id2's list position shifts to 1
    assert mgr.get_annotation_count() == 2
    assert mgr.current_annotation_id == id2 - 1  # shifted down by one


def test_delete_current_annotation_clears_selection(mgr):
    aid = _add(mgr)
    mgr.set_current_annotation(aid)
    mgr.delete_annotation(aid)
    assert mgr.current_annotation_id is None


def test_prev_next_via_annotations_on_slice(mgr):
    """No explicit prev/next API exists on AnnotationManager itself (the
    GUI panel drives selection) - the underlying data this needs
    (ordered list, filterable by slice/plane) is get_annotations_on_slice()."""
    _add(mgr, "on-slice-a", pos=(0, 0, 0))
    id_b = mgr.add_annotation(
        text="on-slice-b", position=(0, 0, 0), voxel_position=(0, 0, 0),
        slice_index=5, plane="AXIAL",
    )
    mgr.add_annotation(
        text="other-slice", position=(0, 0, 0), voxel_position=(0, 0, 0),
        slice_index=6, plane="AXIAL",
    )
    on_slice_5 = mgr.get_annotations_on_slice(5, "AXIAL")
    assert len(on_slice_5) == 2
    assert on_slice_5[1].text == "on-slice-b"


def test_visibility_hide_all_show_all(mgr):
    _add(mgr, "a")
    _add(mgr, "b")
    mgr.hide_all()
    assert mgr.get_visible_count() == 0
    mgr.show_all()
    assert mgr.get_visible_count() == 2


def test_clear_resets_everything(mgr):
    _add(mgr, "a")
    _add(mgr, "b")
    mgr.clear()
    assert mgr.get_annotation_count() == 0
    assert mgr.current_annotation_id is None
    assert mgr.next_id == 0


def test_serialize_deserialize_sidecar_round_trip(mgr, tmp_path):
    """add -> save_sidecar -> clear -> load_sidecar -> same content."""
    _add(mgr, "note-1", pos=(1.0, 2.0, 3.0))
    _add(mgr, "note-2", pos=(4.0, 5.0, 6.0))

    ok = mgr.save_sidecar(str(tmp_path), "myproject.inv3")
    assert ok is True

    sidecar_path = AnnotationManager.sidecar_path_for(str(tmp_path), "myproject.inv3")
    import os

    assert os.path.exists(sidecar_path)

    mgr2 = AnnotationManager()
    loaded = mgr2.load_sidecar(str(tmp_path), "myproject.inv3")
    assert loaded is True
    assert mgr2.get_annotation_count() == 2
    assert mgr2.get_annotation(0).text == "note-1"
    assert mgr2.get_annotation(0).position == (1.0, 2.0, 3.0)
    assert mgr2.get_annotation(1).text == "note-2"


def test_load_sidecar_missing_file_returns_false_not_error(mgr, tmp_path):
    loaded = mgr.load_sidecar(str(tmp_path), "no_such_project.inv3")
    assert loaded is False
    assert mgr.get_annotation_count() == 0


def test_sidecar_path_uses_the_documented_suffix(tmp_path):
    path = AnnotationManager.sidecar_path_for(str(tmp_path), "case.inv3")
    assert path.endswith("case.inv3.roi_annotations.json")


def test_get_annotations_near_point_respects_tolerance(mgr):
    _add(mgr, "close", pos=(0.0, 0.0, 0.0))
    _add(mgr, "far", pos=(100.0, 100.0, 100.0))
    nearby = mgr.get_annotations_near_point((1.0, 1.0, 1.0), tolerance=5.0)
    assert len(nearby) == 1
    assert nearby[0].text == "close"


def test_get_annotations_near_point_excludes_hidden(mgr):
    aid = _add(mgr, "hidden-but-close", pos=(0.0, 0.0, 0.0))
    mgr.update_annotation(aid, visible=False)
    nearby = mgr.get_annotations_near_point((0.0, 0.0, 0.0), tolerance=5.0)
    assert len(nearby) == 0
