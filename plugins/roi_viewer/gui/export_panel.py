# --------------------------------------------------------------------------
# Export Panel Module
# Description: Panel for export options
# --------------------------------------------------------------------------

import wx
import os

try:
    from invesalius.i18n import tr as _
except ImportError:
    def _(s):
        return s


class ExportPanel(wx.Panel):
    """
    Panel for export tools.

    `controller` is the owning ROIViewerFrame, giving access to the
    shared core/exporters.ExporterManager (controller.exporter) used for
    the VTK PolyData surface format and current-slice image export
    (mask/STL/PLY/OBJ export instead delegate to InVesalius's own real
    export dialogs/pipeline - see _export_mask_to_file() and
    _export_surface_to_file() below).
    """

    def __init__(self, parent, controller):
        wx.Panel.__init__(self, parent)
        self.controller = controller
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the export panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, wx.ID_ANY, _("Export Options"))
        title_font = wx.Font(wx.FontInfo(10).Bold())
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Export Mask Section
        # =================
        box_mask = wx.StaticBox(self, wx.ID_ANY, _("Export Mask"))
        mask_sizer = wx.StaticBoxSizer(box_mask, wx.VERTICAL)
        
        # Format selection
        format_row = wx.BoxSizer(wx.HORIZONTAL)
        format_row.Add(wx.StaticText(self, wx.ID_ANY, _("Format:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.choice_mask_format = wx.Choice(
            self, wx.ID_ANY,
            choices=[
                "NIfTI (.nii.gz)",
                "NRRD (.nrrd)",
                "MetaImage (.mhd)",
                "NumPy (.npy)"
            ]
        )
        self.choice_mask_format.SetSelection(0)
        format_row.Add(self.choice_mask_format, 1, wx.ALL, 3)
        
        mask_sizer.Add(format_row, 0, wx.EXPAND, 5)
        
        # Export button
        self.btn_export_mask = wx.Button(self, wx.ID_ANY, _("Export Mask"))
        self.btn_export_mask.Bind(wx.EVT_BUTTON, self._on_export_mask)
        mask_sizer.Add(self.btn_export_mask, 0, wx.ALL | wx.EXPAND, 3)
        
        sizer.Add(mask_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Export Surface Section
        # =================
        box_surf = wx.StaticBox(self, wx.ID_ANY, _("Export Surface"))
        surf_sizer = wx.StaticBoxSizer(box_surf, wx.VERTICAL)
        
        # Format selection
        surf_format_row = wx.BoxSizer(wx.HORIZONTAL)
        surf_format_row.Add(wx.StaticText(self, wx.ID_ANY, _("Format:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.choice_surf_format = wx.Choice(
            self, wx.ID_ANY,
            choices=[
                "STL Binary (.stl)",
                "STL ASCII (.stl)",
                "PLY (.ply)",
                "OBJ (.obj)",
                "VTK PolyData (.vtk)"
            ]
        )
        self.choice_surf_format.SetSelection(0)
        surf_format_row.Add(self.choice_surf_format, 1, wx.ALL, 3)
        
        surf_sizer.Add(surf_format_row, 0, wx.EXPAND, 5)
        
        # Export button
        self.btn_export_surf = wx.Button(self, wx.ID_ANY, _("Export Surface"))
        self.btn_export_surf.Bind(wx.EVT_BUTTON, self._on_export_surface)
        surf_sizer.Add(self.btn_export_surf, 0, wx.ALL | wx.EXPAND, 3)
        
        sizer.Add(surf_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Export Image Section
        # =================
        box_img = wx.StaticBox(self, wx.ID_ANY, _("Export Image"))
        img_sizer = wx.StaticBoxSizer(box_img, wx.VERTICAL)
        
        # Format selection
        img_format_row = wx.BoxSizer(wx.HORIZONTAL)
        img_format_row.Add(wx.StaticText(self, wx.ID_ANY, _("Format:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.choice_img_format = wx.Choice(
            self, wx.ID_ANY,
            choices=[
                "PNG (.png)",
                "JPEG (.jpg)",
                "TIFF (.tif)",
                "BMP (.bmp)"
            ]
        )
        self.choice_img_format.SetSelection(0)
        img_format_row.Add(self.choice_img_format, 1, wx.ALL, 3)
        
        img_sizer.Add(img_format_row, 0, wx.EXPAND, 5)
        
        # Resolution options
        res_row = wx.BoxSizer(wx.HORIZONTAL)
        res_row.Add(wx.StaticText(self, wx.ID_ANY, _("Scale:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        self.spin_scale = wx.SpinCtrl(self, wx.ID_ANY, "1", min=1, max=4)
        res_row.Add(self.spin_scale, 0, wx.ALL, 3)
        
        # NOTE: a misplaced ")" here used to close res_row.Add(...) right
        # after the widget argument, leaving ", 0, wx.ALL | ..., 3" as a
        # dangling no-op tuple statement - the "x" label was silently
        # added with default (no padding/centering) flags instead.
        res_row.Add(wx.StaticText(self, wx.ID_ANY, "x"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        
        img_sizer.Add(res_row, 0, wx.EXPAND, 5)
        
        # Export button
        self.btn_export_img = wx.Button(self, wx.ID_ANY, _("Export Current View"))
        self.btn_export_img.Bind(wx.EVT_BUTTON, self._on_export_image)
        img_sizer.Add(self.btn_export_img, 0, wx.ALL | wx.EXPAND, 3)
        
        sizer.Add(img_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # =================
        # Save Project Section
        # =================
        box_proj = wx.StaticBox(self, wx.ID_ANY, _("Project"))
        proj_sizer = wx.StaticBoxSizer(box_proj, wx.VERTICAL)
        
        self.cb_compress = wx.CheckBox(self, wx.ID_ANY, _("Compress project"))
        self.cb_compress.SetValue(True)
        proj_sizer.Add(self.cb_compress, 0, wx.ALL, 3)
        
        # Button row
        btn_proj_row = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_save_proj = wx.Button(self, wx.ID_ANY, _("Save"))
        self.btn_save_proj.Bind(wx.EVT_BUTTON, self._on_save_project)
        btn_proj_row.Add(self.btn_save_proj, 1, wx.ALL, 2)
        
        self.btn_save_as = wx.Button(self, wx.ID_ANY, _("Save As..."))
        self.btn_save_as.Bind(wx.EVT_BUTTON, self._on_save_as_project)
        btn_proj_row.Add(self.btn_save_as, 1, wx.ALL, 2)
        
        proj_sizer.Add(btn_proj_row, 0, wx.EXPAND, 3)
        
        sizer.Add(proj_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(sizer)
        
    def _get_mask_format_ext(self):
        """Get file extension for selected mask format."""
        formats = {
            0: ".nii.gz",  # NIfTI
            1: ".nrrd",    # NRRD
            2: ".mhd",     # MetaImage
            3: ".npy"      # NumPy
        }
        return formats.get(self.choice_mask_format.GetSelection(), ".nii.gz")
        
    def _get_surface_format_ext(self):
        """Get file extension for selected surface format."""
        formats = {
            0: ".stl",     # STL Binary
            1: ".stl",     # STL ASCII
            2: ".ply",     # PLY
            3: ".obj",     # OBJ
            4: ".vtk"      # VTK
        }
        return formats.get(self.choice_surf_format.GetSelection(), ".stl")
        
    def _get_image_format_ext(self):
        """Get file extension for selected image format."""
        formats = {
            0: ".png",     # PNG
            1: ".jpg",     # JPEG
            2: ".tif",     # TIFF
            3: ".bmp"      # BMP
        }
        return formats.get(self.choice_img_format.GetSelection(), ".png")
        
    def _on_export_mask(self, event):
        """Handle export mask button click."""
        # NOTE: this used to open its own wx.FileDialog first and then
        # discard the path the user picked, immediately firing InVesalius's
        # own "Show export mask dialog" (which opens a second, real save
        # dialog) right after - the user saw two save dialogs in a row and
        # the first choice was silently thrown away. That dialog is the one
        # that actually writes the file, so just fire it directly.
        self._export_mask_to_file()
        
    def _on_export_surface(self, event):
        """Handle export surface button click."""
        wildcard = f"{_('Surface files')} (*{self._get_surface_format_ext()})|*{self._get_surface_format_ext()}"
        
        dlg = wx.FileDialog(
            self,
            message=_("Export Surface"),
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            self._export_surface_to_file(filepath)
            
        dlg.Destroy()
        
    def _on_export_image(self, event):
        """Handle export image button click."""
        wildcard = f"{_('Image files')} (*{self._get_image_format_ext()})|*{self._get_image_format_ext()}"
        
        dlg = wx.FileDialog(
            self,
            message=_("Export Image"),
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            self._export_image_to_file(filepath)
            
        dlg.Destroy()
        
    def _on_save_project(self, event):
        """Handle save project button click."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show save dialog")
        except ImportError:
            pass
            
    def _on_save_as_project(self, event):
        """Handle save as project button click."""
        try:
            from invesalius.pubsub import pub as Publisher
            Publisher.sendMessage("Show save dialog", save_as=True)
        except ImportError:
            pass
            
    def _export_mask_to_file(self):
        """Open InVesalius's own export-mask dialog for the current mask."""
        try:
            from invesalius.pubsub import pub as Publisher
            import invesalius.data.slice_ as sl

            # NOTE: this used to hardcode mask_indexes=[0], so "export mask"
            # always exported the very first mask ever created regardless
            # of which one was actually selected. Use the real current
            # mask's index (Mask.index - see invesalius/data/mask.py).
            current_mask = sl.Slice().current_mask
            if current_mask is None:
                wx.MessageBox(
                    _("No mask selected."), _("Error"), wx.OK | wx.ICON_ERROR
                )
                return

            Publisher.sendMessage(
                "Show export mask dialog", mask_indexes=[current_mask.index]
            )
        except ImportError:
            wx.MessageBox(_("Export not available."), _("Error"), wx.OK | wx.ICON_ERROR)
            
    def _get_current_surface(self):
        """
        Find the "current" surface (there's no InVesalius singleton for
        this reachable from a plugin the way Slice().current_mask is for
        masks - SurfaceManager.last_surface_index lives on
        Controller().surface_manager, which isn't exposed anywhere
        public). Falls back to the highest-indexed surface in
        Project().surface_dict, i.e. the most recently created one.
        """
        try:
            from ..interface.project_interface import ProjectInterface

            surfaces = ProjectInterface().get_surface_dict()
            if not surfaces:
                return None
            return surfaces[max(surfaces.keys())]
        except Exception:
            return None

    def _export_surface_to_file(self, filepath):
        """Export surface to file."""
        surface = self._get_current_surface()
        if surface is None:
            wx.MessageBox(_("No surface available. Create one first."), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        selection = self.choice_surf_format.GetSelection()

        if selection in (0, 1, 2, 3):  # STL Binary/ASCII, PLY, OBJ
            try:
                from invesalius.pubsub import pub as Publisher
                import invesalius.constants as const

                filetype = {
                    0: const.FILETYPE_STL,
                    1: const.FILETYPE_STL_ASCII,
                    2: const.FILETYPE_PLY,
                    3: const.FILETYPE_OBJ,
                }[selection]

                # NOTE: this is the same topic InVesalius's own File menu
                # uses (see app.py's export() helper and
                # invesalius/data/surface.py's OnExportSurface) - it
                # exports the *current* surface directly from real VTK
                # polydata, so it's used here instead of duplicating
                # that logic through core/exporters.py.
                Publisher.sendMessage(
                    "Export surface to file", filename=filepath, filetype=filetype
                )
                self.controller.exporter.last_export_path = filepath
            except ImportError as e:
                wx.MessageBox(_("Export not available."), _("Error"), wx.OK | wx.ICON_ERROR)
                print(f"ROI Viewer: surface export failed - {e}")
        else:  # VTK PolyData (.vtk) - no InVesalius pubsub path for this
            try:
                from vtkmodules.util.numpy_support import vtk_to_numpy

                polydata = surface.polydata
                vertices = vtk_to_numpy(polydata.GetPoints().GetData())
                conn = vtk_to_numpy(polydata.GetPolys().GetData())
                # VTK's flat cell-connectivity array is
                # [n0, id0_0, id0_1, ..., n1, id1_0, ...]; InVesalius
                # surfaces are always triangulated (n == 3 everywhere),
                # so every 4th value is a count column we can drop.
                faces = conn.reshape(-1, 4)[:, 1:4]
                ok = self.controller.exporter.export_surface_vtk(vertices, faces, filepath)
                if not ok:
                    wx.MessageBox(_("VTK export failed."), _("Error"), wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(_("VTK export failed."), _("Error"), wx.OK | wx.ICON_ERROR)
                print(f"ROI Viewer: VTK surface export failed - {e}")

    def _export_image_to_file(self, filepath):
        """
        Export the current 2D slice (windowed to the real current
        window/level, like what's actually shown on screen) to an image
        file. "Current view" here means the current 2D slice raster, not
        a full 3D viewport screenshot.
        """
        try:
            from ..interface.project_interface import ProjectInterface
            from ..interface.view_interface import ViewInterface

            pi = ProjectInterface()
            plane, index = ViewInterface().get_slice_position()
            slice_2d = pi.get_slice(plane, index)
            if slice_2d is None:
                wx.MessageBox(_("No slice available."), _("Error"), wx.OK | wx.ICON_ERROR)
                return

            window, level = pi.get_window_level()
            window = window if window else 1
            lower = level - window / 2.0
            import numpy as np

            windowed = np.clip(slice_2d, lower, lower + window)
            image_8bit = ((windowed - lower) / window * 255.0).astype(np.uint8)

            scale = self.spin_scale.GetValue()
            ok = self.controller.exporter.export_image_png(image_8bit, filepath, scale=scale)
            if not ok:
                wx.MessageBox(_("Image export failed."), _("Error"), wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(_("Image export failed."), _("Error"), wx.OK | wx.ICON_ERROR)
            print(f"ROI Viewer: image export failed - {e}")
