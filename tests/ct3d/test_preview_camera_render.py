# --------------------------------------------------------------------------
# The plugin's 3D drawings must be visible before any surface exists
# (30/09/2026, real application: live 3D preview built, Volume view black).
# Rendered off-screen in a subprocess (see render_preview_camera_probe.py);
# a native graphics failure there is a skip, a Python error a FAIL.
# --------------------------------------------------------------------------
import json
import pathlib
import subprocess
import sys

import pytest

_PROBE = pathlib.Path(__file__).with_name("render_preview_camera_probe.py")


@pytest.fixture(scope="module")
def result():
    proc = subprocess.run([sys.executable, str(_PROBE)], capture_output=True, text=True, timeout=180)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if proc.returncode != 0 and not lines and "Traceback" not in proc.stderr:
        pytest.skip(f"VTK off-screen render/read-back unavailable here (exit {proc.returncode})")
    assert proc.returncode == 0 and lines, proc.stderr[-2000:]
    return json.loads(lines[-1])


def test_preview_is_invisible_with_the_default_camera(result):
    """The operator's symptom: mesh built, nothing drawn."""
    assert result["mesh_points"] > 0
    assert result["default_camera_position"] == [0.0, 0.0, 1.0]
    assert result["lit_before"] == 0


def test_placing_the_camera_shows_the_preview(result):
    assert result["placed"] is True
    assert result["lit_after"] > 500


def test_camera_placed_once_and_never_over_an_existing_one(result):
    assert result["placed_again"] is False and result["unchanged_on_second_call"] is True
    assert result["placed_when_set"] is False and result["user_camera_kept"] is True
    assert result["placed_without_attribute"] is False
