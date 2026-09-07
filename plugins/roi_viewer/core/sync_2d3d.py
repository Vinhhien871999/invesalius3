# --------------------------------------------------------------------------
# Sync Manager 2D-3D Module
# Description: Manages synchronization between 2D slices and 3D view
# --------------------------------------------------------------------------

from typing import Tuple, Optional, Callable, List, Dict
import time


class SyncManager2D3D:
    """
    Manages synchronization between 2D slice views and 3D view.
    """
    
    def __init__(self):
        # State
        self.current_plane = "AXIAL"  # AXIAL, CORONAL, SAGITTAL
        self.current_slice_index = 0
        self.current_voxel_coords = (0, 0, 0)  # i, j, k
        self.current_world_coords = (0.0, 0.0, 0.0)  # x, y, z
        
        # Sync settings
        self.sync_3d_2d = True
        self.sync_2d_3d = True
        self.update_delay = 100  # ms
        self.last_update_time = 0
        
        # Callbacks
        self.slice_change_callbacks: List[Callable] = []
        self.mask_update_callbacks: List[Callable] = []
        self.world_coords_callbacks: List[Callable] = []
        
        # Volume info (will be set from project). Both are index-aligned
        # with Slice().matrix.shape: axis 0 = AXIAL, 1 = CORONAL,
        # 2 = SAGITAL - see world_to_voxel()'s docstring below.
        self.spacing = (1.0, 1.0, 1.0)
        self.dimensions = (0, 0, 0)

    def set_volume_info(self, spacing: Tuple[float, float, float],
                        dimensions: Tuple[int, int, int]):
        """
        Set volume information for coordinate conversion.

        Args:
            spacing: ProjectInterface().get_spacing() /
                Slice().spacing - (axial, coronal, sagital) mm per voxel.
            dimensions: ProjectInterface().get_shape() /
                Slice().matrix.shape - (axial, coronal, sagital) voxel
                counts. NOT a generic (width, height, depth).
        """
        self.spacing = spacing
        self.dimensions = dimensions
        
    def set_slice_position(self, plane: str, index: int):
        """
        Set the current slice position.
        
        Args:
            plane: Plane name (AXIAL, CORONAL, SAGITTAL)
            index: Slice index
        """
        self.current_plane = plane
        self.current_slice_index = index
        
        # Notify callbacks
        for callback in self.slice_change_callbacks:
            callback(plane, index)
            
    def set_world_coords(self, x: float, y: float, z: float):
        """
        Set the current world coordinates and update slice position.

        Args:
            x: World X coordinate in mm (VTK convention: fastest-varying
               axis, matches Slice().matrix's last axis / "SAGITAL")
            y: World Y coordinate in mm (matches matrix's middle axis /
               "CORONAL")
            z: World Z coordinate in mm (matches matrix's first axis /
               "AXIAL" slice stack)
        """
        self.current_world_coords = (x, y, z)

        # Convert to voxel coordinates
        voxel_coords = self.world_to_voxel(x, y, z)
        self.current_voxel_coords = voxel_coords

        # NOTE: voxel_coords is (axial_index, coronal_index, sagital_index)
        # - see world_to_voxel()'s docstring for why.
        if self.current_plane == "AXIAL":
            self.current_slice_index = voxel_coords[0]
        elif self.current_plane == "CORONAL":
            self.current_slice_index = voxel_coords[1]
        else:  # SAGITAL
            self.current_slice_index = voxel_coords[2]

        # Notify callbacks
        for callback in self.world_coords_callbacks:
            callback(x, y, z, self.current_plane, self.current_slice_index)

    def world_to_voxel(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """
        Convert a VTK world-space point (mm) to a
        Slice().matrix-style voxel index.

        NOTE on axis order: invesalius.data.slice_.Slice keeps
        `self.spacing` index-aligned with `self.matrix.shape` (see the
        axis-swap code in slice_.py, which permutes both together) -
        axis 0 is the AXIAL slice stack, axis 1 is CORONAL, axis 2 is
        SAGITAL. InVesalius builds its VTK volume/actors with the
        standard medical-imaging convention where VTK world X is the
        fastest-varying image axis (SAGITAL / matrix axis 2), Y is
        CORONAL (matrix axis 1), and Z is the slice stack (AXIAL /
        matrix axis 0). So the mapping is world (x, y, z) -> voxel
        (axis0, axis1, axis2) = (z/spacing[0], y/spacing[1], x/spacing[2]).
        `dimensions` must be set from Slice().matrix.shape directly
        (that axis order), not a generic "(width, height, depth)".

        Args:
            x, y, z: World coordinates in mm

        Returns:
            Tuple of (axial_index, coronal_index, sagital_index)
        """
        axial = int(z / self.spacing[0]) if self.spacing[0] != 0 else 0
        coronal = int(y / self.spacing[1]) if self.spacing[1] != 0 else 0
        sagital = int(x / self.spacing[2]) if self.spacing[2] != 0 else 0

        # Clamp to valid range
        axial = max(0, min(axial, self.dimensions[0] - 1))
        coronal = max(0, min(coronal, self.dimensions[1] - 1))
        sagital = max(0, min(sagital, self.dimensions[2] - 1))

        return (axial, coronal, sagital)

    def voxel_to_world(self, axial: int, coronal: int, sagital: int) -> Tuple[float, float, float]:
        """
        Convert a Slice().matrix-style voxel index (axial, coronal,
        sagital) back to a VTK world-space point (mm). Inverse of
        world_to_voxel() - see its docstring for the axis mapping.

        Returns:
            Tuple of (x, y, z) world coordinates in mm
        """
        x = sagital * self.spacing[2]
        y = coronal * self.spacing[1]
        z = axial * self.spacing[0]

        return (x, y, z)
        
    def request_3d_update(self):
        """Request a 3D view update (with throttling)."""
        current_time = time.time() * 1000  # ms
        if current_time - self.last_update_time > self.update_delay:
            self._do_3d_update()
            self.last_update_time = current_time
            
    def _do_3d_update(self):
        """Perform the actual 3D update."""
        for callback in self.mask_update_callbacks:
            callback()
            
    def add_slice_change_callback(self, callback: Callable):
        """Add a callback for slice position changes."""
        self.slice_change_callbacks.append(callback)
        
    def add_mask_update_callback(self, callback: Callable):
        """Add a callback for mask updates."""
        self.mask_update_callbacks.append(callback)
        
    def add_world_coords_callback(self, callback: Callable):
        """Add a callback for world coordinate changes."""
        self.world_coords_callbacks.append(callback)
        
    def remove_slice_change_callback(self, callback: Callable):
        """Remove a slice change callback."""
        if callback in self.slice_change_callbacks:
            self.slice_change_callbacks.remove(callback)
            
    def remove_mask_update_callback(self, callback: Callable):
        """Remove a mask update callback."""
        if callback in self.mask_update_callbacks:
            self.mask_update_callbacks.remove(callback)
            
    def enable_sync_3d_2d(self):
        """Enable 3D to 2D synchronization."""
        self.sync_3d_2d = True
        
    def disable_sync_3d_2d(self):
        """Disable 3D to 2D synchronization."""
        self.sync_3d_2d = False
        
    def enable_sync_2d_3d(self):
        """Enable 2D to 3D synchronization."""
        self.sync_2d_3d = True
        
    def disable_sync_2d_3d(self):
        """Disable 2D to 3D synchronization."""
        self.sync_2d_3d = False
        
    def set_update_delay(self, delay_ms: int):
        """Set the update delay in milliseconds."""
        self.update_delay = max(0, min(delay_ms, 1000))  # Clamp to 0-1000ms
        
    def get_current_info(self) -> Dict:
        """Get current state information."""
        return {
            'plane': self.current_plane,
            'slice_index': self.current_slice_index,
            'voxel_coords': self.current_voxel_coords,
            'world_coords': self.current_world_coords,
            'sync_enabled': self.sync_3d_2d and self.sync_2d_3d
        }
