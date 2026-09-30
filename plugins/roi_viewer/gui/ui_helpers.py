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


def rewrap_hints(page, width):
    """Re-wrap every hint() under `page` to fit `width` px."""
    target = max(160, int(width) - 48)
    stack = list(page.GetChildren())
    while stack:
        window = stack.pop()
        stack.extend(window.GetChildren())
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
