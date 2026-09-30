# --------------------------------------------------------------------------
# Sync Manager 2D-3D Module
# Description: Manages synchronization between 2D slices and 3D view
# --------------------------------------------------------------------------

from typing import Tuple, Callable, List, Dict
import time

from .coordinates import voxel_zyx_to_world_xyz, world_xyz_to_voxel_zyx


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
        
        # Volume info (set from the project). dimensions = Slice().matrix
        # .shape (z, y, x); spacing = Slice().spacing (x, y, z) - NOT
        # index-aligned with each other. See core/coordinates.py.
        self.spacing = (1.0, 1.0, 1.0)
        self.dimensions = (0, 0, 0)

    def set_volume_info(self, spacing: Tuple[float, float, float],
                        dimensions: Tuple[int, int, int]):
        """
        Set volume information for coordinate conversion.

        Args:
            spacing: Slice().spacing - (x, y, z) mm per voxel.
            dimensions: Slice().matrix.shape - (z, y, x) voxel counts,
                i.e. (axial, coronal, sagital).
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
        """World (x, y, z) mm -> clamped voxel (axial, coronal, sagital) =
        (z, y, x) index. Delegates to core/coordinates.py."""
        return world_xyz_to_voxel_zyx((x, y, z), self.spacing, self.dimensions)

    def voxel_to_world(self, axial: int, coronal: int, sagital: int) -> Tuple[float, float, float]:
        """Voxel (axial, coronal, sagital) = (z, y, x) -> world (x, y, z) mm.
        Delegates to core/coordinates.py."""
        return voxel_zyx_to_world_xyz((axial, coronal, sagital), self.spacing)
        
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
