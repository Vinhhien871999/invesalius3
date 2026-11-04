# --------------------------------------------------------------------------
# Transient 3D preview of HU classes: one non-pickable VTK actor per
# visible class, in the given renderer. Never touches Project().
# surface_dict, the final surfaces or the camera; detach() removes every
# actor it added (deterministic, idempotent). Meshes come from
# core/preview_surface_3d.build_preview_mesh() - the same alignment with
# the final surface as the E4 live preview.
# --------------------------------------------------------------------------
from typing import Dict, Optional, Sequence

import numpy as np


def build_class_meshes(labels, classes: Sequence, spacing_xyz) -> Dict[int, object]:
    """{class_id: vtkPolyData or None} for the visible classes (worker
    thread safe: no renderer, no wx)."""
    from ..preview_surface_3d import build_preview_mesh

    lab = np.asarray(labels)
    meshes = {}
    for c in classes:
        if c.visible:
            meshes[c.class_id] = build_preview_mesh((lab == c.class_id).astype(np.uint8) * 255, spacing_xyz)
    return meshes


class AnalysisPreview3DManager:
    def __init__(self):
        self.renderer = None
        self.actors: Dict[int, object] = {}
        self.generation_id = 0

    @property
    def actor_count(self) -> int:
        return len(self.actors)

    def new_generation(self) -> int:
        self.generation_id += 1
        return self.generation_id

    def show(self, renderer, meshes: Dict[int, object], classes: Sequence, generation_id: Optional[int] = None) -> bool:
        """Replace the shown actors by one per non-empty mesh. A result for
        an older generation is ignored (returns False)."""
        if generation_id is not None and generation_id != self.generation_id:
            return False
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        self.detach()
        by_id = {c.class_id: c for c in classes}
        for cid, polydata in meshes.items():
            c = by_id.get(cid)
            if polydata is None or c is None or not c.visible:
                continue
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(polydata)
            mapper.ScalarVisibilityOff()
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*(float(v) for v in c.display_color))
            actor.GetProperty().SetOpacity(float(c.opacity))
            actor.SetPickable(False)
            renderer.AddActor(actor)
            self.actors[cid] = actor
        self.renderer = renderer if self.actors else None
        return True

    def set_opacity(self, class_id: int, opacity: float):
        actor = self.actors.get(class_id)
        if actor is not None:
            actor.GetProperty().SetOpacity(float(opacity))

    def set_visible(self, class_id: int, visible: bool):
        actor = self.actors.get(class_id)
        if actor is not None:
            actor.SetVisibility(bool(visible))

    def detach(self):
        """Remove every actor this manager added. Bumps the generation so a
        mesh build still running is discarded when it finishes."""
        self.generation_id += 1
        if self.renderer is not None:
            for actor in self.actors.values():
                try:
                    self.renderer.RemoveActor(actor)
                except Exception as e:
                    print(f"ROI Viewer: analysis 3D actor removal failed - {e}")
        self.actors = {}
        self.renderer = None
