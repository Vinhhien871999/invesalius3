# --------------------------------------------------------------------------
# Mask Editor Module
# Description: Undo/Redo history (UndoRedoManager) for the real current
#              mask's voxel data. (Phase 11: the standalone brush/eraser/
#              interpolation drawing API this module used to also define
#              was removed as confirmed dead code - see MaskEditor's
#              class docstring below. Real brush/eraser editing
#              remote-controls InVesalius's own native 2D editor style.)
# --------------------------------------------------------------------------

import numpy as np
from typing import Tuple, Optional, Deque
from collections import deque
import copy


class UndoRedoManager:
    """
    Manages undo/redo operations for mask editing.
    """
    
    def __init__(self, max_history: int = 10):
        # Phase 10 (CT3D_P10_DATA_INTEGRITY): each checkpoint is a full
        # copy.deepcopy() of the real mask.matrix (see save_state() below) -
        # for a single real CT series (measured: sample 0051, 108x512x512,
        # padded to 109x513x513) that is ~27.4 MB per checkpoint. With both
        # undo_stack and redo_stack at maxlen=20 (the old default), a real
        # editing session could hold up to (20+20)*27.4MB =~ 1.07 GB just
        # for undo/redo history. Benchmark: docs/CT3D_P10_DATA_INTEGRITY_REPORT.md
        # section "Undo/Redo Memory Benchmark". Lowering the default to 10
        # halves that worst case (~547 MB) with zero change to undo/redo
        # correctness or semantics - checkpoints beyond the limit are still
        # evicted the same way (deque(maxlen=...) FIFO eviction, unchanged).
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

    def save_state(self):
        """Save current state for undo."""
        self.undo_manager.save_state(self.mask)

    # NOTE (Phase 11, CT3D_P11_TEST_AUTOMATION - dead code audit, Section
    # XIX): this class used to also define undo()/redo()/clear_mask()/
    # set_brush_size()/set_brush_shape()/_get_brush_mask()/draw_point_2d()/
    # erase_point_2d()/draw_point_3d()/interpolate_slices()/get_mask()/
    # set_mask()/get_mask_slice() - a full standalone brush-drawing API.
    # Removed after confirming CONFIRMED_DEAD_CODE: a whole-repository
    # grep (direct calls, getattr/dynamic dispatch, event bindings,
    # callbacks, imports, subclass overrides, documentation references)
    # found ZERO real call-sites for any of them. The real brush/eraser
    # tools remote-control InVesalius's own native 2D editor style
    # (SLICE_STATE_EDITOR - see gui/segmentation_panel.py's
    # _on_toggle_brush()), never this class's drawing methods. The real
    # Undo/Redo feature (D7) goes through this class's `save_state()`
    # (kept above) plus `self.undo_manager` accessed DIRECTLY by
    # gui/segmentation_panel.py's _on_undo()/_on_redo()
    # (`editor.undo_manager.undo(mask.matrix)` /
    # `.redo(mask.matrix)`) - this class's own now-removed undo()/redo()
    # wrapper methods were bypassed entirely and were themselves dead.
    # `plugins/roi_viewer/core/mask_editor.py`'s git history has the
    # removed code if it is ever needed again. See
    # docs/CT3D_P11_TEST_AUTOMATION_REPORT.md Sections 13-14 for the full
    # investigation and the exact line count removed.


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
