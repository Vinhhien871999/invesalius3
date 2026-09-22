# --------------------------------------------------------------------------
# Persistent regression test for the D9/C7 surface-rebuild algorithm
# policy (Phase 08 root-cause fix). CT3D_P11_TEST_AUTOMATION, Section
# XVI: the decision logic was extracted (Phase 11, behavior-preserving,
# a one-line change) from _on_update_surface()'s inline expression into
# plugins/roi_viewer/gui/segmentation_panel.choose_surface_algorithm(mask)
# specifically so it is testable here without constructing a wx.Frame/
# GUI event.
# --------------------------------------------------------------------------
import types

import pytest

from plugins.roi_viewer.gui.segmentation_panel import choose_surface_algorithm

pytestmark = pytest.mark.unit


def test_sp_t1_unedited_mask_uses_default():
    mask = types.SimpleNamespace(was_edited=False)
    assert choose_surface_algorithm(mask) == "Default"


def test_sp_t2_edited_mask_uses_binary():
    mask = types.SimpleNamespace(was_edited=True)
    assert choose_surface_algorithm(mask) == "Binary"


def test_sp_missing_was_edited_attribute_defaults_to_default():
    """A mask object that (for whatever reason) has no was_edited
    attribute at all must be treated as unedited (matches
    getattr(mask, "was_edited", False))."""
    mask = types.SimpleNamespace()
    assert choose_surface_algorithm(mask) == "Default"
