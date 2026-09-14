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
