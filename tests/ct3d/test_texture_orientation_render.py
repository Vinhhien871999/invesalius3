# --------------------------------------------------------------------------
# E5A texture orientation - real rendered proof (30/09/2026).
#
# Closes the gap recorded in docs/CT3D_ADVANCED_E5_VISUALIZATION_REPORT.md
# ("Texture orientation proof"): the geometry tests in
# test_textured_slice_planes_3d.py prove corner <-> voxel correspondence,
# but not how VTK samples the texture at render time. This test renders the
# production textured plane for all 3 orientations and reads the real
# framebuffer back - see render_texture_orientation_probe.py for the check.
#
# The render runs in a subprocess: a native graphics crash there is reported
# as a skip with its exit code instead of killing the whole pytest run. A
# Python error inside the probe (e.g. update_plane() failing) is a FAIL.
# --------------------------------------------------------------------------
import json
import pathlib
import subprocess
import sys

import pytest

_PROBE = pathlib.Path(__file__).with_name("render_texture_orientation_probe.py")
_ORIENTATIONS = ("AXIAL", "CORONAL", "SAGITAL")


@pytest.fixture(scope="module")
def render_result():
    proc = subprocess.run([sys.executable, str(_PROBE)], capture_output=True, text=True, timeout=180)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("{")]
    if proc.returncode != 0 and not lines and "Traceback" not in proc.stderr:
        pytest.skip(f"VTK off-screen render/read-back unavailable here (exit {proc.returncode})")
    assert proc.returncode == 0 and lines, proc.stderr[-2000:]
    return json.loads(lines[-1])


@pytest.mark.parametrize("orientation", _ORIENTATIONS)
def test_rendered_texture_matches_voxels(render_result, orientation):
    """Every pattern block's rendered colour, at the 3D view position of its
    own voxel, equals that voxel's value - no mirror, swap or rotation."""
    r = render_result[orientation]
    assert r["checked"] >= 12
    assert r["mismatches"] == 0, r["first_mismatches"]


@pytest.mark.parametrize("orientation", _ORIENTATIONS)
@pytest.mark.parametrize("axis", ("u", "v"))
def test_probe_detects_mirrored_texture(render_result, orientation, axis):
    """Control: the same check on a deliberately mirrored texture fails -
    the probe can see a wrong orientation."""
    r = render_result[f"{orientation}_mirror_{axis}_control"]
    assert r["mismatches"] >= r["checked"] // 2


def test_planes_rendered_in_view_frame(render_result):
    """The textured planes sit in the y-flipped 3D view frame (y <= 0), like
    the native surfaces, at the slice position given by (x, y, z) spacing."""
    sx, sy, sz = render_result["spacing_xyz"]
    assert render_result["AXIAL"]["actor_bounds"][4] == pytest.approx(7 * sz, abs=1e-3)
    assert render_result["CORONAL"]["actor_bounds"][2] == pytest.approx(-10 * sy, abs=1e-3)
    assert render_result["SAGITAL"]["actor_bounds"][0] == pytest.approx(13 * sx, abs=1e-3)
    for o in _ORIENTATIONS:
        assert render_result[o]["actor_bounds"][3] <= 1e-6
