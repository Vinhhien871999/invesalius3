# --------------------------------------------------------------------------
# ROI Viewer translation layer.
#
# InVesalius ships no Vietnamese catalog (locale/ has no "vi"), and the
# plugin's strings are not in the upstream "invesalius" gettext domain, so
# routing them through invesalius.i18n.tr can never produce Vietnamese.
# This module is the plugin's own msgid -> msgstr catalog lookup: source
# code keeps English msgids, locale_vi.CATALOG holds the translations.
# Upstream i18n is untouched.
#
# Rules (enforced by tests/ct3d/test_ui_localization.py):
#   * every _() argument is a string literal - no f-strings; put values in
#     with .format() AFTER translation, so the msgid stays constant;
#   * every msgid has a catalog entry;
#   * the empty string is never looked up - gettext("") returns the
#     catalog header, a real bug an operator once saw on screen.
# --------------------------------------------------------------------------
from .locale_vi import CATALOG

PLUGIN_LANGUAGE = "vi"


def _(message: str) -> str:
    if not message or PLUGIN_LANGUAGE != "vi":
        return message
    return CATALOG.get(message, message)


def fmt_int(value) -> str:
    """Vietnamese thousands separator: 152340 -> '152.340'."""
    return f"{int(value):,}".replace(",", ".")


def fmt_float(value, digits: int = 2) -> str:
    """Vietnamese decimal comma: 0.08 -> '0,08'; 1234.5 -> '1.234,50'."""
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
