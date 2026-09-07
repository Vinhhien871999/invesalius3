# --------------------------------------------------------------------------
# Annotation Panel Module
# Description: Panel for annotation tools
# --------------------------------------------------------------------------

import wx
import wx.lib.colourselect as csel
import datetime

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s


class AnnotationPanel(wx.Panel):
    """
    Panel for annotation tools.
    """
    
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.annotations = []
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the annotation panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("Annotation Tools"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # Add annotation section
        box_add = wx.StaticBox(self, wx.ID_ANY, _("Add Annotation"))
        add_sizer = wx.StaticBoxSizer(box_add, wx.VERTICAL)
        
        # Text input
        add_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Text:")), 0, wx.ALL, 3)
        
        self.txt_annotation = wx.TextCtrl(
            self, wx.ID_ANY, "",
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP,
            size=(-1, 60)
        )
        add_sizer.Add(self.txt_annotation, 0, wx.ALL | wx.EXPAND, 3)
        
        # Color selection
        color_row = wx.BoxSizer(wx.HORIZONTAL)
        color_row.Add(wx.StaticText(self, wx.ID_ANY, _("Color:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.color_picker = csel.ColourSelect(
            self, wx.ID_ANY, 
            colour=wx.Colour(255, 0, 0),
            size=(30, -1)
        )
        color_row.Add(self.color_picker, 0, wx.ALL, 3)
        
        # Preset colors
        preset_colors = [
            (255, 0, 0),      # Red
            (0, 128, 0),      # Green
            (0, 0, 255),      # Blue
            (255, 165, 0),    # Orange
            (128, 0, 128),    # Purple
        ]
        
        for i, color in enumerate(preset_colors):
            btn = wx.Button(self, wx.ID_ANY, str(i+1), size=(25, -1))
            btn.SetBackgroundColour(wx.Colour(*color))
            btn.Bind(wx.EVT_BUTTON, lambda e, c=color: self._on_color_preset(c))
            color_row.Add(btn, 0, wx.ALL, 1)
        
        add_sizer.Add(color_row, 0, wx.EXPAND, 3)
        
        # Add button
        self.btn_add = wx.Button(self, wx.ID_ANY, _("Add at Current Position"))
        self.btn_add.Bind(wx.EVT_BUTTON, self._on_add_annotation)
        add_sizer.Add(self.btn_add, 0, wx.ALL | wx.EXPAND, 3)
        
        sizer.Add(add_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Annotation list section
        box_list = wx.StaticBox(self, wx.ID_ANY, _("Annotations"))
        list_sizer = wx.StaticBoxSizer(box_list, wx.VERTICAL)
        
        self.annotation_list = wx.ListBox(self, wx.ID_ANY, size=(-1, 120))
        self.annotation_list.Bind(wx.EVT_LISTBOX, self._on_select_annotation)
        list_sizer.Add(self.annotation_list, 1, wx.ALL | wx.EXPAND, 5)
        
        # List buttons row
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_goto = wx.Button(self, wx.ID_ANY, _("Go to"))
        self.btn_goto.Bind(wx.EVT_BUTTON, self._on_goto_annotation)
        btn_row.Add(self.btn_goto, 1, wx.ALL, 2)
        
        self.btn_edit = wx.Button(self, wx.ID_ANY, _("Edit"))
        self.btn_edit.Bind(wx.EVT_BUTTON, self._on_edit_annotation)
        btn_row.Add(self.btn_edit, 1, wx.ALL, 2)
        
        self.btn_delete = wx.Button(self, wx.ID_ANY, _("Delete"))
        self.btn_delete.Bind(wx.EVT_BUTTON, self._on_delete_annotation)
        btn_row.Add(self.btn_delete, 1, wx.ALL, 2)
        
        list_sizer.Add(btn_row, 0, wx.EXPAND, 3)
        
        sizer.Add(list_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        # Quick navigation
        box_nav = wx.StaticBox(self, wx.ID_ANY, _("Quick Navigation"))
        nav_sizer = wx.StaticBoxSizer(box_nav, wx.HORIZONTAL)
        
        self.btn_prev = wx.Button(self, wx.ID_ANY, _("Prev"))
        self.btn_prev.Bind(wx.EVT_BUTTON, self._on_prev_annotation)
        nav_sizer.Add(self.btn_prev, 1, wx.ALL, 2)
        
        self.btn_next = wx.Button(self, wx.ID_ANY, _("Next"))
        self.btn_next.Bind(wx.EVT_BUTTON, self._on_next_annotation)
        nav_sizer.Add(self.btn_next, 1, wx.ALL, 2)
        
        sizer.Add(nav_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)
        
    def _on_color_preset(self, color):
        """Handle color preset button click."""
        self.color_picker.SetColour(wx.Colour(*color))
        
    def _on_add_annotation(self, event):
        """Handle add annotation button click."""
        text = self.txt_annotation.GetValue().strip()
        if not text:
            wx.MessageBox(_("Please enter annotation text."), _("Warning"), wx.OK | wx.ICON_WARNING)
            return
            
        color = self.color_picker.GetColour()
        
        # Create annotation object
        annotation = {
            'text': text,
            'color': (color.Red(), color.Green(), color.Blue()),
            'timestamp': datetime.datetime.now(),
            'position': (0, 0, 0),  # Will be updated by actual position
            'slice_index': 0
        }
        
        self.annotations.append(annotation)
        
        # Update list
        display_text = f"{len(self.annotations)}. {text[:30]}{'...' if len(text) > 30 else ''}"
        self.annotation_list.Append(display_text)
        
        # Clear input
        self.txt_annotation.Clear()
        
        # Notify
        self._notify_annotation_added(annotation)
        
    def _on_select_annotation(self, event):
        """Handle annotation selection."""
        index = event.GetInt()
        if 0 <= index < len(self.annotations):
            self.current_annotation = self.annotations[index]
            
    def _on_goto_annotation(self, event):
        """Handle go to annotation button click."""
        index = self.annotation_list.GetSelection()
        if index >= 0:
            self._notify_goto_annotation(self.annotations[index])
            
    def _on_edit_annotation(self, event):
        """Handle edit annotation button click."""
        index = self.annotation_list.GetSelection()
        if index >= 0:
            # Show edit dialog
            annotation = self.annotations[index]
            dlg = wx.TextEntryDialog(
                self, 
                _("Edit annotation:"), 
                _("Edit Annotation"),
                annotation['text']
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_text = dlg.GetValue()
                annotation['text'] = new_text
                display_text = f"{index+1}. {new_text[:30]}{'...' if len(new_text) > 30 else ''}"
                self.annotation_list.SetString(index, display_text)
            dlg.Destroy()
            
    def _on_delete_annotation(self, event):
        """Handle delete annotation button click."""
        index = self.annotation_list.GetSelection()
        if index >= 0:
            del self.annotations[index]
            self.annotation_list.Delete(index)
            self._notify_annotation_deleted(index)
            
    def _on_prev_annotation(self, event):
        """Handle previous annotation button click."""
        current = self.annotation_list.GetSelection()
        if current > 0:
            self.annotation_list.SetSelection(current - 1)
            self._on_select_annotation(wx.CommandEvent())
            
    def _on_next_annotation(self, event):
        """Handle next annotation button click."""
        current = self.annotation_list.GetSelection()
        if current < self.annotation_list.GetCount() - 1:
            self.annotation_list.SetSelection(current + 1)
            self._on_select_annotation(wx.CommandEvent())
            
    def _notify_annotation_added(self, annotation):
        """Notify that an annotation was added."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("ROI Viewer: Annotation added", annotation=annotation)
        except ImportError:
            pass
            
    def _notify_goto_annotation(self, annotation):
        """Notify that we should go to an annotation."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("ROI Viewer: Go to annotation", position=annotation['position'])
        except ImportError:
            pass
            
    def _notify_annotation_deleted(self, index):
        """Notify that an annotation was deleted."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("ROI Viewer: Annotation deleted", index=index)
        except ImportError:
            pass
            
    def set_current_position(self, x, y, z, slice_index):
        """Update the current position for new annotations."""
        self.current_position = (x, y, z)
        self.current_slice = slice_index
