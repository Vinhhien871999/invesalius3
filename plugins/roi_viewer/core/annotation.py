# --------------------------------------------------------------------------
# Annotation Module
# Description: Annotation management for ROI Viewer
# --------------------------------------------------------------------------

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
import datetime


@dataclass
class Annotation:
    """Represents an annotation in the ROI Viewer."""
    text: str
    position: Tuple[float, float, float]  # World coordinates (x, y, z)
    voxel_position: Tuple[int, int, int]  # Voxel coordinates (i, j, k)
    slice_index: int
    plane: str  # AXIAL, CORONAL, SAGITTAL
    color: Tuple[int, int, int] = (255, 0, 0)  # RGB
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    modified_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    visible: bool = True
    author: str = ""


class AnnotationManager:
    """
    Manages annotations in the ROI Viewer.
    """
    
    def __init__(self):
        self.annotations: List[Annotation] = []
        self.next_id = 0
        self.current_annotation_id = None
        self.observer_callbacks: List[callable] = []
        
    def add_annotation(self, text: str, 
                      position: Tuple[float, float, float],
                      voxel_position: Tuple[int, int, int],
                      slice_index: int,
                      plane: str,
                      color: Tuple[int, int, int] = (255, 0, 0),
                      author: str = "") -> int:
        """
        Add a new annotation.
        
        Args:
            text: Annotation text
            position: World coordinates (x, y, z) in mm
            voxel_position: Voxel coordinates (i, j, k)
            slice_index: Current slice index
            plane: Current plane name
            color: RGB color tuple
            author: Author name
            
        Returns:
            Annotation ID
        """
        annotation = Annotation(
            text=text,
            position=position,
            voxel_position=voxel_position,
            slice_index=slice_index,
            plane=plane,
            color=color,
            author=author
        )
        
        annotation_id = self.next_id
        self.annotations.append(annotation)
        self.next_id += 1
        self.current_annotation_id = annotation_id
        
        # Notify observers
        self._notify_observers("added", annotation_id, annotation)
        
        return annotation_id
        
    def get_annotation(self, annotation_id: int) -> Optional[Annotation]:
        """Get annotation by ID."""
        if 0 <= annotation_id < len(self.annotations):
            return self.annotations[annotation_id]
        return None
        
    def get_current_annotation(self) -> Optional[Annotation]:
        """Get the currently selected annotation."""
        if self.current_annotation_id is not None:
            return self.get_annotation(self.current_annotation_id)
        return None
        
    def set_current_annotation(self, annotation_id: int):
        """Set the currently selected annotation."""
        if 0 <= annotation_id < len(self.annotations):
            self.current_annotation_id = annotation_id
            
    def update_annotation(self, annotation_id: int, **kwargs):
        """
        Update annotation properties.
        
        Args:
            annotation_id: Annotation ID
            **kwargs: Properties to update (text, color, visible, etc.)
        """
        annotation = self.get_annotation(annotation_id)
        if annotation is None:
            return
            
        if 'text' in kwargs:
            annotation.text = kwargs['text']
        if 'color' in kwargs:
            annotation.color = kwargs['color']
        if 'visible' in kwargs:
            annotation.visible = kwargs['visible']
            
        annotation.modified_at = datetime.datetime.now()
        
        # Notify observers
        self._notify_observers("updated", annotation_id, annotation)
        
    def delete_annotation(self, annotation_id: int):
        """Delete an annotation."""
        if 0 <= annotation_id < len(self.annotations):
            annotation = self.annotations[annotation_id]
            del self.annotations[annotation_id]
            
            if self.current_annotation_id == annotation_id:
                self.current_annotation_id = None
            elif self.current_annotation_id is not None and self.current_annotation_id > annotation_id:
                self.current_annotation_id -= 1
                
            # Notify observers
            self._notify_observers("deleted", annotation_id, annotation)
            
    def get_annotations_on_slice(self, slice_index: int, plane: str) -> List[Annotation]:
        """
        Get all annotations on a specific slice.
        
        Args:
            slice_index: Slice index
            plane: Plane name
            
        Returns:
            List of annotations
        """
        return [
            ann for ann in self.annotations
            if ann.slice_index == slice_index and ann.plane == plane and ann.visible
        ]
        
    def get_annotations_near_point(self, position: Tuple[float, float, float],
                                   tolerance: float = 5.0) -> List[Annotation]:
        """
        Get annotations near a world position.
        
        Args:
            position: World position (x, y, z)
            tolerance: Search radius in mm
            
        Returns:
            List of nearby annotations
        """
        nearby = []
        for ann in self.annotations:
            if not ann.visible:
                continue
            distance = np.sqrt(
                (ann.position[0] - position[0])**2 +
                (ann.position[1] - position[1])**2 +
                (ann.position[2] - position[2])**2
            )
            if distance <= tolerance:
                nearby.append(ann)
                
        return nearby
        
    def get_annotation_count(self) -> int:
        """Get total number of annotations."""
        return len(self.annotations)
        
    def get_visible_count(self) -> int:
        """Get number of visible annotations."""
        return sum(1 for ann in self.annotations if ann.visible)
        
    def set_all_visible(self, visible: bool):
        """Set visibility for all annotations."""
        for ann in self.annotations:
            ann.visible = visible
        self._notify_observers("visibility_changed", None, None)
        
    def hide_all(self):
        """Hide all annotations."""
        self.set_all_visible(False)
        
    def show_all(self):
        """Show all annotations."""
        self.set_all_visible(True)
        
    def clear(self):
        """Clear all annotations."""
        self.annotations.clear()
        self.current_annotation_id = None
        self.next_id = 0
        self._notify_observers("cleared", None, None)
        
    def export_to_dict(self) -> List[Dict]:
        """
        Export annotations to a list of dictionaries.
        
        Returns:
            List of annotation dictionaries
        """
        return [
            {
                'id': i,
                'text': ann.text,
                'position': ann.position,
                'voxel_position': ann.voxel_position,
                'slice_index': ann.slice_index,
                'plane': ann.plane,
                'color': ann.color,
                'created_at': ann.created_at.isoformat(),
                'modified_at': ann.modified_at.isoformat(),
                'visible': ann.visible,
                'author': ann.author
            }
            for i, ann in enumerate(self.annotations)
        ]
        
    def import_from_dict(self, data: List[Dict]):
        """
        Import annotations from a list of dictionaries.
        
        Args:
            data: List of annotation dictionaries
        """
        self.clear()
        
        for item in data:
            annotation = Annotation(
                text=item.get('text', ''),
                position=tuple(item.get('position', (0, 0, 0))),
                voxel_position=tuple(item.get('voxel_position', (0, 0, 0))),
                slice_index=item.get('slice_index', 0),
                plane=item.get('plane', 'AXIAL'),
                color=tuple(item.get('color', (255, 0, 0))),
                visible=item.get('visible', True),
                author=item.get('author', '')
            )
            
            # Parse datetime strings
            if 'created_at' in item:
                annotation.created_at = datetime.datetime.fromisoformat(item['created_at'])
            if 'modified_at' in item:
                annotation.modified_at = datetime.datetime.fromisoformat(item['modified_at'])
                
            self.annotations.append(annotation)
            self.next_id += 1
            
        self._notify_observers("imported", None, None)
        
    def add_observer(self, callback: callable):
        """Add an observer callback."""
        if callback not in self.observer_callbacks:
            self.observer_callbacks.append(callback)
            
    def remove_observer(self, callback: callable):
        """Remove an observer callback."""
        if callback in self.observer_callbacks:
            self.observer_callbacks.remove(callback)
            
    def _notify_observers(self, event: str, annotation_id: Optional[int], 
                         annotation: Optional[Annotation]):
        """Notify all observers of a change."""
        for callback in self.observer_callbacks:
            try:
                callback(event, annotation_id, annotation)
            except Exception as e:
                print(f"Error in annotation observer: {e}")
