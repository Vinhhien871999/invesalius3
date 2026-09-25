# --------------------------------------------------------------------------
# E5 Section 4 reconciliation regression test: a real operator observed
# the Segmentation tab rendering raw gettext catalogue metadata
# (Project-Id-Version, Report-Msgid-Bugs-To, PO-Revision-Date,
# Language-Team, Plural-Forms, X-Poedit-...) displacing the Preview
# Workflow controls. Root cause, confirmed by directly reading
# invesalius/i18n.py: `tr` wraps a real `gettext.translation(...).
# gettext` function - and calling gettext("") on a REAL loaded .mo
# catalogue is documented, standard gettext behavior that returns the
# catalogue's own PO header block (msgid "" maps to it) instead of an
# empty string. This plugin's own `_(s): return s` fallback (used only
# when `invesalius.i18n` cannot be imported at all, e.g. some test
# contexts) does NOT exhibit this bug - it only manifests with the real
# InVesalius i18n system active, exactly the real-application case the
# operator hit.
#
# 7 real occurrences of `_("")` were found and fixed this milestone (all
# in gui/segmentation_panel.py, 3x wx.StaticText construction + 4x
# .SetLabel() call - see docs/CT3D_ADVANCED_E5_VISUALIZATION_REPORT.md's
# "Gettext UI bug reconciliation" section for the full list). This test
# is the real regression guard against reintroducing the pattern
# anywhere in the plugin.
# --------------------------------------------------------------------------
import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins" / "roi_viewer"
_EMPTY_GETTEXT_PATTERN = re.compile(r"""_\(\s*(["'])\1\s*\)""")


def test_no_empty_string_gettext_calls():
    offenders = []
    for path in _PLUGIN_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _EMPTY_GETTEXT_PATTERN.search(text):
            offenders.append(str(path.relative_to(_PLUGIN_ROOT)))
    assert not offenders, (
        f'Found _("")/_(\'\') gettext calls (real PO-header-leak bug) in: {offenders} - '
        f'use a plain "" literal for an intentionally blank translated label instead.'
    )
