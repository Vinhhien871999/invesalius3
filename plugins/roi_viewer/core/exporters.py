# --------------------------------------------------------------------------
# Exporters Module
# Description: Export functions for masks, surfaces, and projects
# --------------------------------------------------------------------------

import os
import numpy as np
from typing import Optional, Tuple, List
import tempfile


class ExporterManager:
    """
    Manages all export operations.
    """
    
    def __init__(self):
        self.last_export_path = None
        self.default_compression = True
        
    def set_compression(self, enabled: bool):
        """Set default compression setting."""
        self.default_compression = enabled
        
    def export_mask_nifti(self, mask: np.ndarray, filepath: str,
                         spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                         compress: bool = True) -> bool:
        """
        Export mask to NIfTI format.
        
        Args:
            mask: 3D binary mask
            filepath: Output file path
            spacing: Voxel spacing (mm)
            compress: Use gzip compression
            
        Returns:
            True if successful
        """
        try:
            import nibabel as nib
            
            # Ensure proper dtype and format
            export_data = mask.astype(np.uint8)
            
            # Create NIfTI image with identity affine (RAS+)
            nifti_img = nib.Nifti1Image(export_data, np.eye(4))
            nifti_img.header.set_zooms(spacing)
            
            # Save
            nib.save(nifti_img, filepath)
            
            self.last_export_path = filepath
            return True
            
        except ImportError:
            print("NIfTI export requires nibabel: pip install nibabel")
            return False
        except Exception as e:
            print(f"NIfTI export error: {e}")
            return False
            
    def export_mask_nrrd(self, mask: np.ndarray, filepath: str,
                        spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bool:
        """
        Export mask to NRRD format.
        
        Args:
            mask: 3D binary mask
            filepath: Output file path
            spacing: Voxel spacing (mm)
            
        Returns:
            True if successful
        """
        try:
            import nrrd
            
            # Create NRRD header
            header = {
                'space directions': np.diag(spacing),
                'space origin': [0, 0, 0],
                'encoding': 'gzip'
            }
            
            # Save
            nrrd.write(filepath, mask.astype(np.uint8), header)
            
            self.last_export_path = filepath
            return True
            
        except ImportError:
            print("NRRD export requires pynrrd: pip install pynrrd")
            return False
        except Exception as e:
            print(f"NRRD export error: {e}")
            return False
            
    def export_mask_numpy(self, mask: np.ndarray, filepath: str) -> bool:
        """
        Export mask to NumPy format.
        
        Args:
            mask: 3D binary mask
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            np.save(filepath, mask.astype(np.uint8))
            self.last_export_path = filepath
            return True
        except Exception as e:
            print(f"NumPy export error: {e}")
            return False
            
    def export_surface_stl(self, vertices: np.ndarray, faces: np.ndarray,
                          filepath: str, binary: bool = True) -> bool:
        """
        Export surface to STL format.
        
        Args:
            vertices: Vertex coordinates (N, 3)
            faces: Face indices (M, 3)
            filepath: Output file path
            binary: Use binary STL (True) or ASCII (False)
            
        Returns:
            True if successful
        """
        try:
            from stl import mesh
            
            # Create mesh
            stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
            for i, face in enumerate(faces):
                stl_mesh.vectors[i] = vertices[face]
                
            # Save
            stl_mesh.save(filepath, mode=binary and 'binary' or 'ascii')
            
            self.last_export_path = filepath
            return True
            
        except ImportError:
            print("STL export requires numpy-stl: pip install numpy-stl")
            return False
        except Exception as e:
            print(f"STL export error: {e}")
            return False
            
    def export_surface_ply(self, vertices: np.ndarray, faces: np.ndarray,
                          filepath: str, color: Tuple[int, int, int] = (200, 200, 200)) -> bool:
        """
        Export surface to PLY format.
        
        Args:
            vertices: Vertex coordinates (N, 3)
            faces: Face indices (M, 3)
            filepath: Output file path
            color: RGB color tuple
            
        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w') as f:
                # Header
                f.write("ply\n")
                f.write("format ascii 1.0\n")
                f.write(f"element vertex {len(vertices)}\n")
                f.write("property float x\n")
                f.write("property float y\n")
                f.write("property float z\n")
                f.write(f"element face {len(faces)}\n")
                f.write("property list uchar int vertex_indices\n")
                f.write("end_header\n")
                
                # Vertices
                for v in vertices:
                    f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                    
                # Faces
                for face in faces:
                    f.write(f"3 {face[0]} {face[1]} {face[2]}\n")
                    
            self.last_export_path = filepath
            return True
            
        except Exception as e:
            print(f"PLY export error: {e}")
            return False
            
    def export_surface_obj(self, vertices: np.ndarray, faces: np.ndarray,
                          filepath: str, colors: Optional[np.ndarray] = None) -> bool:
        """
        Export surface to OBJ format.
        
        Args:
            vertices: Vertex coordinates (N, 3)
            faces: Face indices (M, 3)
            filepath: Output file path
            colors: Optional vertex colors (N, 3)
            
        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w') as f:
                f.write("# OBJ export from ROI Viewer\n")
                f.write(f"# Vertices: {len(vertices)}, Faces: {len(faces)}\n\n")
                
                # Vertices
                for v in vertices:
                    f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                    
                # Optional colors (as vertex colors)
                if colors is not None:
                    for c in colors:
                        f.write(f"# Colors: {c[0]:.0f} {c[1]:.0f} {c[2]:.0f}\n")
                        
                f.write("\n")
                
                # Faces (OBJ is 1-indexed)
                for face in faces:
                    f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
                    
            self.last_export_path = filepath
            return True
            
        except Exception as e:
            print(f"OBJ export error: {e}")
            return False
            
    def export_surface_vtk(self, vertices: np.ndarray, faces: np.ndarray,
                          filepath: str) -> bool:
        """
        Export surface to VTK PolyData format.
        
        Args:
            vertices: Vertex coordinates (N, 3)
            faces: Face indices (M, 3)
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            from vtkmodules.vtkCommonDataModel import (
                vtkPolyData, vtkPoints, vtkCellArray, vtkPolyLine
            )
            
            # Create VTK objects
            points = vtkPoints()
            for v in vertices:
                points.InsertNextPoint(v)
                
            polygons = vtkCellArray()
            for face in faces:
                polygon = vtkPolyLine()
                polygon.GetPointIds().SetNumberOfIds(3)
                for i, idx in enumerate(face):
                    polygon.GetPointIds().SetId(i, idx)
                polygons.InsertNextCell(polygon)
                
            polydata = vtkPolyData()
            polydata.SetPoints(points)
            polydata.SetPolys(polygons)
            
            # Save using VTK writer
            from vtkmodules.vtkIOCore import vtkPolyDataWriter
            writer = vtkPolyDataWriter()
            writer.SetFileName(filepath)
            writer.SetInputData(polydata)
            writer.Write()
            
            self.last_export_path = filepath
            return True
            
        except ImportError:
            print("VTK export requires VTK library")
            return False
        except Exception as e:
            print(f"VTK export error: {e}")
            return False
            
    def export_image_png(self, image: np.ndarray, filepath: str,
                        scale: int = 1) -> bool:
        """
        Export image to PNG format.
        
        Args:
            image: 2D image array
            filepath: Output file path
            scale: Upscale factor
            
        Returns:
            True if successful
        """
        try:
            from PIL import Image
            
            # Handle grayscale images
            if len(image.shape) == 2:
                img = Image.fromarray(image.astype(np.uint8))
            else:
                img = Image.fromarray(image.astype(np.uint8))
                
            # Resize if needed
            if scale > 1:
                new_size = (img.width * scale, img.height * scale)
                img = img.resize(new_size, Image.NEAREST)
                
            img.save(filepath)
            
            self.last_export_path = filepath
            return True
            
        except ImportError:
            print("PNG export requires Pillow: pip install pillow")
            return False
        except Exception as e:
            print(f"PNG export error: {e}")
            return False
            
    def get_supported_formats(self) -> dict:
        """Get dictionary of supported export formats."""
        return {
            'mask': ['.nii.gz', '.nrrd', '.mhd', '.npy'],
            'surface': ['.stl', '.ply', '.obj', '.vtk'],
            'image': ['.png', '.jpg', '.tif', '.bmp']
        }
