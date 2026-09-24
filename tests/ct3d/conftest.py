# --------------------------------------------------------------------------
# Shared fixtures for plugins/roi_viewer's persistent test suite
# (CT3D_P11_TEST_AUTOMATION). See docs/CT3D_P11_TEST_AUTOMATION_REPORT.md.
#
# Isolation contract (Phase 11, Section XXIV of the spec):
#   - Never touch the real user's ~/.config/invesalius/ (or %APPDATA%
#     equivalent). XDG_CONFIG_HOME is redirected to a fresh temp directory
#     BEFORE any `invesalius` module is imported by this process, because
#     invesalius/inv_paths.py reads it at module-import time
#     (`CONF_DIR = ...os.environ.get("XDG_CONFIG_HOME", ...)`), not
#     lazily. This must happen at conftest.py's own module level (not
#     inside a fixture function), since pytest imports conftest.py before
#     collecting/importing any test module in this directory - the same
#     ordering guarantee the Phase 08/09/10 standalone test scripts relied
#     on by setting the env var before their own `import invesalius...`.
#   - invesalius.project.Project and invesalius.data.slice_.Slice are
#     process-wide singletons (invesalius.utils.Singleton metaclass sets
#     `cls.instance` once and reuses it forever). Without an explicit
#     reset, state written by one test (a mask created, a project "loaded")
#     leaks into every later test in the same pytest process. The
#     `reset_invesalius_singletons` fixture below forces a fresh instance
#     for every single test.
# --------------------------------------------------------------------------
import os
import tempfile

_CT3D_XDG_CONFIG_HOME = tempfile.mkdtemp(prefix="ct3d_pytest_xdg_")
os.environ["XDG_CONFIG_HOME"] = _CT3D_XDG_CONFIG_HOME

# invesalius.project imports invesalius.gui.dialogs at module level, which
# (transitively, via imagedata_utils) imports invesalius.data.slice_,
# which imports `from invesalius.project import Project` back - a real,
# pre-existing circular import in invesalius/ itself (not introduced by
# this plugin or this test suite). Importing invesalius.data.slice_ FIRST
# avoids it, exactly like the existing upstream tests/test_mask.py
# already does (`from invesalius.data.slice_ import Slice` before
# `from invesalius.project import Project`). Doing this once here, before
# any ct3d test module is collected, means individual test files don't
# each need to know about or repeat this ordering.
import invesalius.data.slice_ as _ensure_slice_imported_before_project  # noqa: F401

import pytest


@pytest.fixture(scope="session")
def wx_app():
    """
    A single real wx.App for the whole pytest session. Some real
    invesalius code (e.g. invesalius.data.slice_.Slice.create_new_mask
    calling wx.BeginBusyCursor()) requires one to exist, even for tests
    that never show a window or need mouse/keyboard interaction (those
    are `gui`-marked and skipped by default - see pyproject.toml).
    Session-scoped because constructing more than one wx.App in the same
    process is unsupported.
    """
    import wx

    app = wx.App(False)
    yield app


@pytest.fixture(autouse=True)
def reset_invesalius_singletons():
    """
    Force invesalius.project.Project() and invesalius.data.slice_.Slice()
    to construct fresh instances for every test, so state from one test
    (masks created, "current_mask" selected, a project "loaded") never
    leaks into the next. Runs for every test in this directory
    automatically (autouse=True) - individual tests do not need to
    request it explicitly.
    """
    try:
        from invesalius.project import Project

        Project.instance = None
    except ImportError:
        pass
    try:
        from invesalius.data.slice_ import Slice

        Slice.instance = None
    except ImportError:
        pass

    yield

    try:
        from invesalius.project import Project

        Project.instance = None
    except ImportError:
        pass
    try:
        from invesalius.data.slice_ import Slice

        Slice.instance = None
    except ImportError:
        pass


@pytest.fixture(scope="session")
def real_slice_and_project_singleton(wx_app):
    """
    A SINGLE real Slice()/Project() pair, constructed exactly once for
    the whole pytest session, shared by every test file that needs to
    exercise real pubsub-driven InVesalius behavior (e.g. actually
    sending the real "Create new mask" message and letting
    Slice.__add_mask_thresh handle it - not a fake/mocked stand-in).

    Why a SINGLE shared pair, not "construct a fresh Slice()/Project()
    per test or per module" (an earlier version of the CT3D E2/E3 test
    files each did this independently, once per module): the autouse
    reset_invesalius_singletons fixture above nulls Slice.instance/
    Project.instance before AND after every test, but that only
    un-points the singleton lookup - it does not unsubscribe the real
    pypubsub bindings a Slice() instance makes once, inside its own
    __init__ (e.g. to the real "Create new mask" topic). Those bindings
    stay alive and registered for as long as anything still holds a
    reference to that old instance. Constructing more than one "fresh"
    real Slice() across the session therefore accumulates several real,
    still-subscribed instances; when a real message is later sent,
    pypubsub invokes ALL of their handlers - not only whichever one
    `.instance` currently points to - and every handler beyond the
    intended one operates on stale/mismatched state. This was found for
    real (deterministic, not flaky - reproduced identically across
    repeated full-suite runs) once a second and third module-scoped
    "fresh Slice()" pattern coexisted in the same test session while
    building CT3D's E2/E3 tests. Reusing exactly one real pair for the
    whole session - resetting only ITS mutable data (mask_dict, matrix,
    current_mask, ...) between tests, never constructing new objects -
    avoids the accumulation entirely. Test files use this by
    re-pointing `.instance` back to the SAME shared objects at the start
    of each test (see e.g. tests/ct3d/test_segmentation_preview_commit.py's
    `real_slice_and_project` fixture), undoing the autouse reset above
    for just that one test.
    """
    import invesalius.data.slice_ as sl
    import invesalius.project as prj

    prj.Project.instance = None
    sl.Slice.instance = None
    proj = prj.Project()
    s = sl.Slice()
    return s, proj, prj.Project, sl.Slice


@pytest.fixture
def isolated_cwd_tmp(tmp_path, monkeypatch):
    """
    Convenience fixture for tests that write files (exports, sidecars,
    saved projects): chdir into a fresh pytest tmp_path for the duration
    of the test, so relative paths and any file the code under test
    writes land in an auto-cleaned temp directory rather than the repo
    or the real user's filesystem.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path
