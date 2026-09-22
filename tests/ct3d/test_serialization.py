# --------------------------------------------------------------------------
# Persistent regression suite for G1/G2 (Save/Open project serialization).
# Promotes Phase 10's ephemeral p10_saveopen_forensics.py (RT-A/B/C/E,
# 30/30 PASS) into a real, re-runnable pytest suite -
# CT3D_P11_TEST_AUTOMATION, Section XVII.
#
# Deliberately does NOT go through a full wx.Frame/Controller/DICOM-
# import bootstrap (Phase 08/09/10's standalone scripts needed that only
# to get a valid 3D-viewer widget tree for surface building - this suite
# tests Save/Open only, which invesalius.project.Project.SavePlistProject/
# OpenPlistProject/Close and invesalius.data.mask.Mask.SavePlist/OpenPList
# do not need). Masks are constructed directly (Mask() + create_mask()),
# matching Phase 10's approach but skipping the unnecessary GUI weight -
# real production save/open code is exercised end to end either way.
#
# Matches masks by NAME (stable identity across a round trip), never by
# the pre-save numeric index - see SER-T3 below, which is a direct,
# permanent regression test for the mechanism Phase 10 identified as the
# likely cause of the earlier (false-positive) checksum report.
# --------------------------------------------------------------------------
import hashlib
import os

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _full_hash(matrix):
    return hashlib.sha256(np.ascontiguousarray(matrix).tobytes()).hexdigest()


def _payload_hash(matrix):
    return hashlib.sha256(np.ascontiguousarray(matrix[1:, 1:, 1:]).tobytes()).hexdigest()


@pytest.fixture
def project_with_image(tmp_path):
    """A real Project() with a small synthetic image backing it - enough
    for Mask.create_mask()/SavePlist/OpenPList/SavePlistProject/
    OpenPlistProject to run for real, without a DICOM import or GUI."""
    import invesalius.project as prj

    shape = (6, 8, 8)
    img_path = str(tmp_path / "image.dat")
    image = np.memmap(img_path, mode="w+", dtype="int16", shape=shape)
    image[:] = 0
    image.flush()

    proj = prj.Project()
    proj.matrix_shape = shape
    proj.matrix_dtype = "int16"
    proj.matrix_filename = img_path
    proj.mask_dict = {}
    proj.surface_dict = {}
    proj.image_versions = []
    proj.spacing = (1.0, 1.0, 1.0)
    return proj, shape


def _make_mask(shape, name, fill_slice=slice(1, 3), was_edited=False, threshold_range=(1, 1)):
    from invesalius.data.mask import Mask

    m = Mask()
    m.create_mask(shape)
    m.name = name
    m.threshold_range = threshold_range
    m.matrix[fill_slice, 1:4, 1:4] = 255
    m.was_edited = was_edited
    m.matrix.flush()
    return m


def test_ser_t1_synthetic_mask_round_trip(project_with_image, tmp_path):
    proj, shape = project_with_image
    mask = _make_mask(shape, "RT-A synthetic")
    mask.index = 0
    proj.mask_dict[0] = mask

    before_full = _full_hash(mask.matrix)
    before_payload = _payload_hash(mask.matrix)
    before_nonzero = int((mask.matrix > 0).sum())

    save_dir = str(tmp_path / "save1")
    os.makedirs(save_dir, exist_ok=True)
    proj.SavePlistProject(save_dir, "p.inv3", compress=False)
    saved_path = os.path.join(save_dir, "p.inv3")
    assert os.path.exists(saved_path)

    proj.Close()
    assert len(proj.mask_dict) == 0

    ok = proj.OpenPlistProject(saved_path)
    assert ok is not False
    assert len(proj.mask_dict) == 1

    reloaded = list(proj.mask_dict.values())[0]
    assert reloaded.name == "RT-A synthetic"
    assert reloaded.matrix.shape == mask.matrix.shape
    assert reloaded.matrix.dtype == mask.matrix.dtype
    assert int((reloaded.matrix > 0).sum()) == before_nonzero
    assert _full_hash(reloaded.matrix) == before_full
    assert _payload_hash(reloaded.matrix) == before_payload


def test_ser_t2_edited_mask_was_edited_flag_round_trips(project_with_image, tmp_path):
    proj, shape = project_with_image
    mask = _make_mask(shape, "RT-C edited", fill_slice=slice(0, 2), was_edited=True, threshold_range=(400, 600))
    mask.index = 0
    proj.mask_dict[0] = mask
    before_hash = _full_hash(mask.matrix)

    save_dir = str(tmp_path / "save2")
    os.makedirs(save_dir, exist_ok=True)
    proj.SavePlistProject(save_dir, "p.inv3", compress=False)
    proj.Close()
    proj.OpenPlistProject(os.path.join(save_dir, "p.inv3"))

    reloaded = list(proj.mask_dict.values())[0]
    assert reloaded.was_edited is True  # the D9/C7 policy depends on this surviving a round trip
    # plistlib round-trips a tuple as a list (a real, benign serialization
    # quirk - content is what matters, not the container type).
    assert tuple(reloaded.threshold_range) == (400, 600)
    assert _full_hash(reloaded.matrix) == before_hash


def test_ser_t3_index_gap_scenario_must_match_by_name_not_stale_index(project_with_image, tmp_path):
    """
    Direct regression test for the mechanism identified in Phase 10
    (docs/CT3D_P10_DATA_INTEGRITY_REPORT.md Section 9, RT-E) as the
    likely explanation for the earlier (false-positive) checksum report:
    OpenPlistProject() reassigns mask.index by insertion order
    (`m.index = len(self.mask_dict)`), so after a mask is deleted before
    saving, the reloaded index for a REMAINING mask does not equal its
    pre-save index. A correct comparison must match by name/identity,
    never by the stale pre-save index.
    """
    proj, shape = project_with_image
    mask_a = _make_mask(shape, "keep-A")
    mask_b = _make_mask(shape, "delete-me")
    mask_c = _make_mask(shape, "keep-C", fill_slice=slice(3, 5))
    mask_a.index, mask_b.index, mask_c.index = 0, 1, 2
    proj.mask_dict[0] = mask_a
    proj.mask_dict[1] = mask_b
    proj.mask_dict[2] = mask_c

    before_hash_c = _full_hash(mask_c.matrix)
    del proj.mask_dict[1]  # create the index gap: {0, 2} remain
    assert list(proj.mask_dict.keys()) == [0, 2]

    save_dir = str(tmp_path / "save3")
    os.makedirs(save_dir, exist_ok=True)
    proj.SavePlistProject(save_dir, "p.inv3", compress=False)
    proj.Close()
    proj.OpenPlistProject(os.path.join(save_dir, "p.inv3"))

    assert len(proj.mask_dict) == 2
    reloaded_keys = list(proj.mask_dict.keys())
    assert reloaded_keys == [0, 1]  # re-densified - NOT {0, 2} anymore

    by_name = {m.name: m for m in proj.mask_dict.values()}
    reloaded_c = by_name["keep-C"]
    # The mask formerly at index 2 is now at index 1 - a naive lookup by
    # the STALE original index would find the WRONG mask (or nothing).
    stale_index_lookup = proj.mask_dict.get(2)
    assert stale_index_lookup is None or stale_index_lookup.name != "keep-C"
    # Matching by name (the correct, robust approach) finds the right
    # mask with byte-identical data.
    assert _full_hash(reloaded_c.matrix) == before_hash_c


def test_ser_t3b_gzip_compression_does_not_change_checksums(project_with_image, tmp_path):
    proj, shape = project_with_image
    mask = _make_mask(shape, "gz-mask")
    mask.index = 0
    proj.mask_dict[0] = mask
    before_hash = _full_hash(mask.matrix)

    save_dir = str(tmp_path / "save_gz")
    os.makedirs(save_dir, exist_ok=True)
    proj.SavePlistProject(save_dir, "p.inv3", compress=True)
    proj.Close()
    proj.OpenPlistProject(os.path.join(save_dir, "p.inv3"))

    reloaded = list(proj.mask_dict.values())[0]
    assert _full_hash(reloaded.matrix) == before_hash


def test_mask_metadata_survives_round_trip(project_with_image, tmp_path):
    proj, shape = project_with_image
    mask = _make_mask(shape, "meta-mask")
    mask.index = 0
    mask.colour = (0.2, 0.4, 0.6)
    mask.is_shown = False
    proj.mask_dict[0] = mask

    save_dir = str(tmp_path / "save_meta")
    os.makedirs(save_dir, exist_ok=True)
    proj.SavePlistProject(save_dir, "p.inv3", compress=False)
    proj.Close()
    proj.OpenPlistProject(os.path.join(save_dir, "p.inv3"))

    reloaded = list(proj.mask_dict.values())[0]
    assert reloaded.name == "meta-mask"
    assert tuple(reloaded.colour[:3]) == pytest.approx((0.2, 0.4, 0.6))
    assert reloaded.is_shown is False
