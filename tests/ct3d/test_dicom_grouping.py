# --------------------------------------------------------------------------
# Persistent unit test for the DICOM series/study grouping LOGIC
# (invesalius.reader.dicom_grouper.DicomPatientGrouper), using synthetic
# duck-typed Dicom-like objects. CT3D_P12_QUANTITATIVE_VALIDATION,
# Section IX.
#
# IMPORTANT: this is a unit test of the grouping ALGORITHM only - it does
# NOT stand in for real multi-series runtime evidence (A4). No local
# DICOM dataset with >1 series per study exists (confirmed by real scan,
# see docs/CT3D_DATASET_REGISTRY.md) - A4 stays NEEDS_RUNTIME_TEST /
# BLOCKED_EXTERNAL_DATA regardless of this test passing. This only
# proves the grouping code itself correctly separates series when fed
# synthetic multi-series input - a real, different, narrower claim.
# --------------------------------------------------------------------------
import types

import pytest

from invesalius.reader import dicom_grouper

pytestmark = pytest.mark.unit


def _fake_dicom(patient_name, patient_id, id_study, serie_number, orientation_label,
                slice_position, image_number=0, image_type="ORIGINAL"):
    return types.SimpleNamespace(
        patient=types.SimpleNamespace(name=patient_name, id=patient_id),
        acquisition=types.SimpleNamespace(
            id_study=id_study, serie_number=serie_number, series_description=f"series-{serie_number}",
        ),
        image=types.SimpleNamespace(
            position=slice_position, orientation_label=orientation_label,
            type=image_type, number_of_frames=1, number=image_number,
        ),
    )


def test_single_series_single_study_groups_as_one():
    grouper = dicom_grouper.DicomPatientGrouper()
    for z in range(5):
        grouper.AddFile(_fake_dicom("P", "id1", "study1", "1", "AXIAL", (0, 0, float(z))))
    patients = grouper.GetPatientsGroups()
    assert len(patients) == 1
    groups = patients[0].GetGroups()
    assert len(groups) == 1
    assert len(list(groups[0].GetList())) == 5


def test_two_series_same_study_group_separately():
    """The real-world case A4 targets: one study containing 2 distinct
    series (different serie_number) - the grouper must split them, not
    merge them into one group."""
    grouper = dicom_grouper.DicomPatientGrouper()
    for z in range(5):
        grouper.AddFile(_fake_dicom("P", "id1", "study1", "1", "AXIAL", (0, 0, float(z))))
    for z in range(8):
        grouper.AddFile(_fake_dicom("P", "id1", "study1", "2", "AXIAL", (0, 0, float(z))))

    patients = grouper.GetPatientsGroups()
    assert len(patients) == 1  # same patient
    groups = patients[0].GetGroups()
    assert len(groups) == 2  # 2 distinct series correctly separated
    sizes = sorted(len(list(g.GetList())) for g in groups)
    assert sizes == [5, 8]


def test_two_different_patients_group_separately():
    grouper = dicom_grouper.DicomPatientGrouper()
    grouper.AddFile(_fake_dicom("P1", "id1", "study1", "1", "AXIAL", (0, 0, 0.0)))
    grouper.AddFile(_fake_dicom("P2", "id2", "study1", "1", "AXIAL", (0, 0, 0.0)))
    patients = grouper.GetPatientsGroups()
    assert len(patients) == 2


def test_two_studies_same_patient_group_separately():
    grouper = dicom_grouper.DicomPatientGrouper()
    grouper.AddFile(_fake_dicom("P", "id1", "study1", "1", "AXIAL", (0, 0, 0.0)))
    grouper.AddFile(_fake_dicom("P", "id1", "study2", "1", "AXIAL", (0, 0, 1.0)))
    patients = grouper.GetPatientsGroups()
    assert len(patients) == 1
    groups = patients[0].GetGroups()
    assert len(groups) == 2  # different studies -> different groups
