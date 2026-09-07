# --------------------------------------------------------------------------
# Mask Editor Module
# Description: Mask editing operations (brush, eraser, interpolation)
# --------------------------------------------------------------------------

import numpy as np
from typing import Tuple, List, Optional, Deque
from collections import deque
import copy


class UndoRedoManager:
    """
    Manages undo/redo operations for mask editing.
    """
    
    def __init__(self, max_history: int = 20):
        self.undo_stack: Deque[np.ndarray] = deque(maxlen=max_history)
        self.redo_stack: Deque[np.ndarray] = deque(maxlen=max_history)
        self.max_history = max_history
        
    def save_state(self, mask: np.ndarray):
        """Save current mask state for undo."""
        self.undo_stack.append(copy.deepcopy(mask))
        self.redo_stack.clear()  # Clear redo when new action is performed
        
    def undo(self, current_mask: np.ndarray) -> Optional[np.ndarray]:
        """Undo the last action."""
        if not self.undo_stack:
            return None
            
        self.redo_stack.append(copy.deepcopy(current_mask))
        return self.undo_stack.pop()
        
    def redo(self, current_mask: np.ndarray) -> Optional[np.ndarray]:
        """Redo the last undone action."""
        if not self.redo_stack:
            return None
            
        self.undo_stack.append(copy.deepcopy(current_mask))
        return self.redo_stack.pop()
        
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
        
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
        
    def clear(self):
        """Clear all history."""
        self.undo_stack.clear()
        self.redo_stack.clear()


class MaskEditor:
    """
    Handles mask editing operations.
    """
    
    def __init__(self, shape: Tuple[int, int, int]):
        self.shape = shape
        self.mask = np.zeros(shape, dtype=np.uint8)
        self.undo_manager = UndoRedoManager()
        self.brush_size = 5
        self.brush_shape = 'circle'  # 'circle' or 'square'
        self.current_value = 255  # Foreground value
        
    def save_state(self):
        """Save current state for undo."""
        self.undo_manager.save_state(self.mask)
        
    def undo(self) -> bool:
        """Undo the last operation."""
        previous = self.undo_manager.undo(self.mask)
        if previous is not None:
            self.mask = previous
            return True
        return False
        
    def redo(self) -> bool:
        """Redo the last undone operation."""
        next_state = self.undo_manager.redo(self.mask)
        if next_state is not None:
            self.mask = next_state
            return True
        return False
        
    def clear_mask(self):
        """Clear the entire mask."""
        self.save_state()
        self.mask.fill(0)
        
    def set_brush_size(self, size: int):
        """Set the brush size in pixels."""
        self.brush_size = max(1, min(size, 50))
        
    def set_brush_shape(self, shape: str):
        """Set the brush shape ('circle' or 'square')."""
        self.brush_shape = shape
        
    def _get_brush_mask(self) -> np.ndarray:
        """Generate a brush mask based on current settings."""
        size = self.brush_size
        if self.brush_shape == 'circle':
            y, x = np.ogrid[-size:size+1, -size:size+1]
            mask = x**2 + y**2 <= size**2
        else:  # square
            mask = np.ones((2*size+1, 2*size+1), dtype=bool)
        return mask
        
    def draw_point_2d(self, x: int, y: int, z: int, value: int = None):
        """
        Draw at a point on a 2D slice.
        
        Args:
            x: X coordinate
            y: Y coordinate
            z: Slice index (layer)
            value: Drawing value (default: current_value)
        """
        if value is None:
            value = self.current_value
            
        self.save_state()
        
        brush_mask = self._get_brush_mask()
        brush_half = self.brush_size
        
        # Calculate bounds
        x_min = max(0, x - brush_half)
        x_max = min(self.shape[2], x + brush_half + 1)
        y_min = max(0, y - brush_half)
        y_max = min(self.shape[1], y + brush_half + 1)
        
        # Calculate brush mask bounds
        mask_x_min = x_min - (x - brush_half)
        mask_x_max = mask_x_min + (x_max - x_min)
        mask_y_min = y_min - (y - brush_half)
        mask_y_max = mask_y_min + (y_max - y_min)
        
        # Apply brush
        self.mask[z, y_min:y_max, x_min:x_max] = np.where(
            brush_mask[mask_y_min:mask_y_max, mask_x_min:mask_x_max],
            value,
            self.mask[z, y_min:y_max, x_min:x_max]
        )
        
    def erase_point_2d(self, x: int, y: int, z: int):
        """Erase at a point (set to 0)."""
        self.draw_point_2d(x, y, z, 0)
        
    def draw_point_3d(self, x: int, y: int, z: int, value: int = None):
        """
        Draw at a point in 3D space (affects all slices in a small neighborhood).
        
        Args:
            x: X coordinate
            y: Y coordinate
            z: Z coordinate
            value: Drawing value
        """
        if value is None:
            value = self.current_value
            
        self.save_state()
        
        brush_mask = self._get_brush_mask()
        brush_half = self.brush_size
        
        # Calculate 3D bounds
        x_min = max(0, x - brush_half)
        x_max = min(self.shape[2], x + brush_half + 1)
        y_min = max(0, y - brush_half)
        y_max = min(self.shape[1], y + brush_half + 1)
        z_min = max(0, z - brush_half)
        z_max = min(self.shape[0], z + brush_half + 1)
        
        # Create a flat circular mask for 2D application
        y2d, x2d = np.ogrid[-brush_half:brush_half+1, -brush_half:brush_half+1]
        if self.brush_shape == 'circle':
            mask_2d = x2d**2 + y2d**2 <= brush_half**2
        else:
            mask_2d = np.ones((2*brush_half+1, 2*brush_half+1), dtype=bool)
            
        # Apply to all slices in the z neighborhood
        for zz in range(z_min, z_max):
            slice_mask = self.mask[zz, y_min:y_max, x_min:x_max]
            slice_brush = mask_2d[
                (brush_half-(y-y_min)):(brush_half+(y_max-y)),
                (brush_half-(x-x_min)):(brush_half+(x_max-x))
            ]
            
            if slice_brush.shape == slice_mask.shape:
                self.mask[zz, y_min:y_max, x_min:x_max] = np.where(
                    slice_brush,
                    value,
                    self.mask[zz, y_min:y_max, x_min:x_max]
                )
                
    def interpolate_slices(self, slice1: int, slice2: int, num_interp: int = 5):
        """
        Interpolate mask between two slices.
        
        Args:
            slice1: First slice index
            slice2: Second slice index
            num_interp: Number of intermediate slices
        """
        if not (0 <= slice1 < self.shape[0] and 0 <= slice2 < self.shape[0]):
            return
            
        self.save_state()
        
        mask1 = self.mask[slice1].astype(float)
        mask2 = self.mask[slice2].astype(float)
        
        for i in range(1, num_interp + 1):
            alpha = i / (num_interp + 1)
            interp_mask = mask1 * (1 - alpha) + mask2 * alpha
            interp_slice = slice1 + int((slice2 - slice1) * alpha)
            
            if 0 <= interp_slice < self.shape[0]:
                self.mask[interp_slice] = (interp_mask > 127).astype(np.uint8)
                
    def get_mask(self) -> np.ndarray:
        """Get the current mask."""
        return self.mask.copy()
        
    def set_mask(self, mask: np.ndarray):
        """Set the mask from external source."""
        if mask.shape == self.shape:
            self.save_state()
            self.mask = mask.copy()
            
    def get_mask_slice(self, z: int) -> np.ndarray:
        """Get a single slice of the mask."""
        if 0 <= z < self.shape[0]:
            return self.mask[z].copy()
        return np.zeros((self.shape[1], self.shape[2]), dtype=np.uint8)


class MaskEditorManager:
    """
    Manages multiple masks and editing operations.
    """
    
    def __init__(self):
        self.editors: dict = {}  # mask_index -> MaskEditor
        self.current_index: int = 0
        
    def create_editor(self, mask_index: int, shape: Tuple[int, int, int]) -> MaskEditor:
        """Create a new mask editor."""
        editor = MaskEditor(shape)
        self.editors[mask_index] = editor
        self.current_index = mask_index
        return editor
        
    def get_editor(self, mask_index: int) -> Optional[MaskEditor]:
        """Get editor for a specific mask."""
        return self.editors.get(mask_index)
        
    def get_current_editor(self) -> Optional[MaskEditor]:
        """Get the current mask editor."""
        return self.editors.get(self.current_index)
        
    def set_current_mask(self, mask_index: int):
        """Set the current active mask."""
        if mask_index in self.editors:
            self.current_index = mask_index
            
    def delete_editor(self, mask_index: int):
        """Delete a mask editor."""
        if mask_index in self.editors:
            del self.editors[mask_index]
            if self.current_index == mask_index:
                self.current_index = next(iter(self.editors.keys()), 0)
                
    def clear_all(self):
        """Clear all editors."""
        self.editors.clear()
        self.current_index = 0
