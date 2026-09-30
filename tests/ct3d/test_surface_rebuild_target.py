# --------------------------------------------------------------------------
# "Update 3D surface from current ROI" must rebuild that ROI's own surface
# and never replace another one. 30/09/2026, real application (0801, after
# the first real TotalSegmentator run): rebuilding "AI - trachea" left only
# the trachea in 3D - the button always sent overwrite=True, and InVesalius
# overwrites its LAST surface (most recently created or selected, whatever
# mask it came from), e.g. the bone surface.
#
# Real SurfaceManager + real Project; only the host's multiprocessing
# contouring is skipped: "Create surface from index" goes straight to
# SurfaceManager._show_surface(), the step AddNewActor() ends with, on a
# prepared mesh.
# --------------------------------------------------------------------------
import gc
import types

import pytest

from plugins.roi_viewer.gui.segmentation_panel import SegmentationPanel, live_surface_index

BONE = "Bone (native Create Surface)"
AI = "AI - trachea"


def _write_mesh(path):
    from vtkmodules.vtkFiltersSources import vtkSphereSource
    from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter

    source = vtkSphereSource()
    source.Update()
    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(source.GetOutput())
    writer.Write()
    return str(path)


@pytest.fixture
def host(real_slice_and_project_singleton, tmp_path, monkeypatch):
    import wx

    import invesalius.data.surface as srf
    import invesalius.session as ses
    from invesalius.pubsub import pub as Publisher

    s, proj, Project, Slice = real_slice_and_project_singleton
    Project.instance, Slice.instance = proj, s
    saved = (proj.surface_dict, proj.mask_dict)
    proj.surface_dict = {}
    proj.mask_dict = {
        0: types.SimpleNamespace(index=0, name="Mask 1", was_edited=False),
        1: types.SimpleNamespace(index=1, name=AI, was_edited=True),
    }
    srf.Surface.general_index = -1
    manager = srf.SurfaceManager()
    mesh = _write_mesh(tmp_path / "mesh.vtp")
    env = types.SimpleNamespace(proj=proj, manager=manager, builds=[], errors=[], panel=None)
    real_send = Publisher.sendMessage

    def send(topic, **kwargs):
        if topic == "Create surface from index":
            options = kwargs["surface_parameters"]["options"]
            env.builds.append(dict(options))
            manager._show_surface(mesh, {"volume": 1.0, "area": 1.0}, options["overwrite"],
                                  options["name"], (1.0, 1.0, 0.0), "General", None)
        else:
            real_send(topic, **kwargs)

    def forward(surface):
        if env.panel is not None:
            env.panel._on_surface_info_updated(surface)

    def native_surface(name):
        """What InVesalius's own Create Surface ends with (overwrite off)."""
        manager._show_surface(mesh, {"volume": 1.0, "area": 1.0}, False, name, (1.0, 1.0, 1.0), "General", None)
        return proj.surface_dict[manager.last_surface_index]

    env.native_surface = native_surface
    env.mesh = mesh
    # The test session's config has no "surface_interpolation" (the real
    # application's default is 1); read-only stand-in, nothing is written.
    session = ses.Session()
    real_get = session.GetConfig
    monkeypatch.setattr(session, "GetConfig",
                        lambda key, default_value=None: 1 if key == "surface_interpolation"
                        else real_get(key, default_value))
    monkeypatch.setattr(Publisher, "sendMessage", send)
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: env.errors.append(a))
    Publisher.subscribe(forward, "Update surface info in GUI")
    try:
        yield env
    finally:
        Publisher.unsubscribe(forward, "Update surface info in GUI")
        proj.surface_dict, proj.mask_dict = saved
        srf.Surface.general_index = -1
        env.panel = None
        gc.collect()


def _panel(env):
    fake = types.SimpleNamespace(
        controller=types.SimpleNamespace(
            roi_mgr=types.SimpleNamespace(get_roi=lambda rid: types.SimpleNamespace(mask_index=rid))),
        roi_status=types.SimpleNamespace(label=None),
        _roi_surfaces={}, _pending_surface_build=None, selected=1,
    )
    fake.roi_status.SetLabel = lambda text: setattr(fake.roi_status, "label", text)
    fake._selected_roi_id = lambda: fake.selected
    for name in ("_on_update_surface", "_on_surface_info_updated", "get_surface_index_for_mask"):
        setattr(fake, name, getattr(SegmentationPanel, name).__get__(fake))
    env.panel = fake
    return fake


def _names(env):
    return [env.proj.surface_dict[i].name for i in sorted(env.proj.surface_dict)]


def test_host_overwrite_replaces_the_last_surface_whatever_its_mask(host):
    """The premise: InVesalius's overwrite is not per mask."""
    host.native_surface(BONE)
    host.manager._show_surface(host.mesh, {"volume": 1.0, "area": 1.0}, True, AI, (1.0, 1.0, 0.0), "General", None)
    assert _names(host) == [AI]


def test_rebuilding_an_roi_keeps_the_other_surfaces(host):
    """The operator's case: a bone surface exists and is InVesalius's last
    surface; rebuilding the AI ROI adds its own surface."""
    bone = host.native_surface(BONE)
    panel = _panel(host)
    panel._on_update_surface(None)
    assert host.errors == []
    assert host.builds[-1]["overwrite"] is False and host.builds[-1]["name"] == AI
    assert _names(host) == [BONE, AI] and host.proj.surface_dict[0] is bone
    assert panel.get_surface_index_for_mask(1) == 1
    assert AI in panel.roi_status.label and panel._pending_surface_build is None


def test_rebuilding_again_replaces_only_its_own_surface(host):
    bone = host.native_surface(BONE)
    panel = _panel(host)
    panel._on_update_surface(None)
    first = host.proj.surface_dict[1]
    panel._on_update_surface(None)
    assert host.builds[-1]["overwrite"] is True
    assert _names(host) == [BONE, AI] and host.proj.surface_dict[0] is bone
    assert host.proj.surface_dict[1] is not first  # rebuilt in place
    assert panel.get_surface_index_for_mask(1) == 1


def test_rebuild_after_the_user_selected_another_surface(host):
    """Selecting the bone makes it InVesalius's last surface; the rebuild
    must still replace the ROI's own surface."""
    from invesalius.pubsub import pub as Publisher

    bone = host.native_surface(BONE)
    panel = _panel(host)
    panel._on_update_surface(None)
    Publisher.sendMessage("Change surface selected", surface_index=0)
    assert host.manager.last_surface_index == 0
    panel._on_update_surface(None)
    assert _names(host) == [BONE, AI] and host.proj.surface_dict[0] is bone
    assert panel.get_surface_index_for_mask(1) == 1


def test_removed_or_renumbered_surfaces(host):
    from invesalius.pubsub import pub as Publisher

    host.native_surface(BONE)
    panel = _panel(host)
    panel._on_update_surface(None)
    Publisher.sendMessage("Remove surfaces", surface_indexes=[0])  # bone removed: AI renumbered 1 -> 0
    assert _names(host) == [AI] and panel.get_surface_index_for_mask(1) == 0
    panel._on_update_surface(None)
    assert host.builds[-1]["overwrite"] is True and _names(host) == [AI]
    Publisher.sendMessage("Remove surfaces", surface_indexes=[0])  # the ROI's surface removed
    assert panel.get_surface_index_for_mask(1) is None
    bone = host.native_surface(BONE)
    panel._on_update_surface(None)
    assert host.builds[-1]["overwrite"] is False and _names(host) == [BONE, AI]
    assert host.proj.surface_dict[0] is bone


def test_other_surface_events_are_not_attributed(host):
    """Selecting a surface fires the same event; only the surface the
    build asked for (its name) is recorded."""
    bone = host.native_surface(BONE)
    panel = _panel(host)
    panel._pending_surface_build = (1, AI)
    panel._on_surface_info_updated(bone)
    assert panel._pending_surface_build == (1, AI) and panel._roi_surfaces == {}


def test_live_surface_index():
    a, b = types.SimpleNamespace(index=0), types.SimpleNamespace(index=0)
    assert live_surface_index(a, {0: a}) == 0
    assert live_surface_index(a, {0: b}) is None  # replaced
    assert live_surface_index(a, {}) is None  # removed / other project
    assert live_surface_index(None, {0: a}) is None
