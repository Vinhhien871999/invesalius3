# --------------------------------------------------------------------------
# Small layout helpers shared by the ROI Viewer panels - native wx only.
# --------------------------------------------------------------------------
import wx

HINT_COLOUR = wx.Colour(90, 90, 90)


def collapsible(parent, label, on_toggle, expanded=False):
    """A native wx.CollapsiblePane; returns (pane, content_window). Widgets
    for the section must be created with content_window as their parent."""
    pane = wx.CollapsiblePane(parent, wx.ID_ANY, label,
                              style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)
    pane.Collapse(not expanded)
    pane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, on_toggle)
    return pane, pane.GetPane()


def relayout_scrolled(panel):
    """Re-fit a ScrolledPanel after a section expands/collapses, keeping the
    current scroll position and never adding a horizontal scrollbar."""
    panel.Layout()
    panel.SetupScrolling(scroll_x=False, scrollToTop=False)


def hint(parent, text, wrap=250):
    """Grey helper text. Wrapped at `wrap` px first; follow_width() re-wraps
    it to the page's real width (sidebar ~400 px, floating window, ...)."""
    label = wx.StaticText(parent, wx.ID_ANY, text)
    label.SetForegroundColour(HINT_COLOUR)
    label._hint_text = text
    label.Wrap(wrap)
    return label


class StatusText(wx.StaticText):
    """A status line that wraps to the page width (follow_width()) instead of
    being cut off at the sidebar edge - seen in the real application on
    15/10/2026 ("Đã tạo xem trước AI: 102.861 voxel (0,1% thể tích), 35.31"
    with the volume cut). GetLabel() returns the text as set, without the
    line breaks Wrap() inserts, so callers and tests see the plain text.
    `indent` is the width taken by a label before it on the same row."""

    def __init__(self, parent, text="", indent=0, style=0):
        self._status_text = text
        self._indent = indent
        self._wrap_width = 250 - indent
        self._wrapping = False
        super().__init__(parent, wx.ID_ANY, text, style=style)
        self._wrap()

    def _wrap(self):
        self._wrapping = True  # Wrap() may call SetLabel() back
        try:
            wx.StaticText.SetLabel(self, self._status_text)
            self.Wrap(self._wrap_width)
        finally:
            self._wrapping = False

    def SetLabel(self, text):
        if self._wrapping:
            wx.StaticText.SetLabel(self, text)
            return
        before = self.GetSize().height
        self._status_text = str(text)
        self._wrap()
        if self.GetBestSize().height != before:
            _relayout(self)

    def GetLabel(self):
        return self._status_text

    def set_wrap_width(self, width):
        width = max(120, int(width) - self._indent)
        if width != self._wrap_width:
            self._wrap_width = width
            self._wrap()


def _relayout(window):
    """Re-run the sizers from `window` up to its scrolled page (a wrapped
    status line can change height)."""
    parent = window.GetParent()
    while parent is not None:
        parent.Layout()
        if hasattr(parent, "SetupScrolling") or parent.IsTopLevel():
            if hasattr(parent, "FitInside"):
                parent.FitInside()
            break
        parent = parent.GetParent()


def rewrap_hints(page, width):
    """Re-wrap every hint() and StatusText under `page` to fit `width` px."""
    target = max(160, int(width) - 48)
    stack = list(page.GetChildren())
    while stack:
        window = stack.pop()
        stack.extend(window.GetChildren())
        if isinstance(window, StatusText):
            window.set_wrap_width(target)
            continue
        text = getattr(window, "_hint_text", None)
        if text is not None:
            window.SetLabel(text)
            window.Wrap(target)


def follow_width(page):
    """Keep the hints of a scrolled page wrapped to its current width."""
    def on_size(event):
        rewrap_hints(page, event.GetSize().width)
        event.Skip()

    page.Bind(wx.EVT_SIZE, on_size)


def button_row(*buttons, border=2):
    """Equal-width buttons side by side."""
    row = wx.BoxSizer(wx.HORIZONTAL)
    for button in buttons:
        row.Add(button, 1, wx.ALL, border)
    return row


def labelled_row(parent, label, control, unit=None, border=3):
    """'Label: [control] unit' on one line, label and unit vertically centred."""
    row = wx.BoxSizer(wx.HORIZONTAL)
    row.Add(wx.StaticText(parent, wx.ID_ANY, label), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, border)
    row.Add(control, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, border)
    if unit:
        row.Add(wx.StaticText(parent, wx.ID_ANY, unit), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, border)
    return row
