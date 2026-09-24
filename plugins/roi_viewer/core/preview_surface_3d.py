# --------------------------------------------------------------------------
# Fast Live 3D Preview Module (E4, Advanced Segmentation Enhancement Track)
# Description: A fast, non-authoritative preview mesh + the single VTK
#              actor that displays it in the real Volume renderer. Mirrors
#              core/marker_3d.CrosshairMarker3D's attach()/detach()
#              lifecycle pattern exactly (same reason: the real 3D
#              renderer is a singleton that outlives any single
#              ROIViewerFrame).
#
# CORE INVARIANT this module exists to protect: a fast preview mesh is
# NEVER the final surface. Nothing here ever touches Project().
# surface_dict, never sends "Create surface from index", never replaces
# or reads the real final-surface actor/polydata. See
# docs/CT3D_ADVANCED_E4_LIVE_3D_PREVIEW_REPORT.md for the full source
# audit and benchmark evidence behind these choices.
# --------------------------------------------------------------------------
from typing import Optional, Tuple


def build_preview_mesh(binary_array, spacing: Tuple[float, float, float]):
    """
    Builds a fast preview vtkPolyData from a real logical (unpadded)
    binary mask region (foreground = any nonzero value, matching
    core/segmentation_cleanup.py's contract) - or returns None if there
    is no foreground at all (Section 26: never contour an empty mask).

    Geometric alignment with the REAL final surface (Section 5/24's
    audit requirement) is achieved by construction, not independently
    re-derived: this reuses the EXACT real conversion function
    (invesalius.data.converters.to_vtk) and the EXACT real
    pre-contour vtkImageFlip step (FilteredAxis=1, FlipAboutOriginOn)
    that invesalius/data/surface_process.py.create_surface_piece()'s
    from_binary=True branch already uses for the authoritative final
    surface - re-read directly from that file for this audit, not
    assumed from memory. Same isovalue (127 - the real "from_binary"
    convention that file uses) on a 0/255-valued array.

    Algorithm: vtkFlyingEdges3D, not vtkContourFilter/vtkMarchingCubes.
    Measured (see the E4 report's benchmark section) to produce
    IDENTICAL output geometry (same point count, cell count, bounds) to
    vtkMarchingCubes on a representative dataset-0051-shaped array, at
    ~2.2x the speed (0.068s vs 0.150s) - a safe, same-algorithm-family
    substitution for speed, not a different technique that could
    diverge from the real pipeline's geometry. vtkSurfaceNets3D/
    vtkDiscreteMarchingCubes/vtkDiscreteFlyingEdges3D were also
    benchmarked and found unsuitable for this isovalue-127-on-a-
    continuous-scalar-field usage (they expect discrete integer LABEL
    values, produced empty output with SetValue(0, 127) - a different,
    real usage contract, not a drop-in substitute here).

    No downsampling: full resolution already measured comfortably fast
    (see report) - "If full-resolution raw preview is fast enough:
    prefer it" (Section 7). Downsampling code was deliberately NOT
    added this milestone given the evidence did not justify its added
    complexity/alignment risk.
    """
    import numpy as np
    from vtkmodules.vtkCommonDataModel import vtkPolyData
    from vtkmodules.vtkFiltersCore import vtkFlyingEdges3D
    from vtkmodules.vtkImagingCore import vtkImageFlip
    from invesalius.data import converters

    arr = np.asarray(binary_array)
    if not (arr != 0).any():
        return None

    # Normalize to a clean 0/255 uint8 field regardless of the caller's
    # own foreground convention (0/1 vs 0/255 - E2/E3 both happen to
    # produce 0/255 today, but this function's documented contract is
    # "any nonzero", so it must not silently depend on that coincidence
    # - a 0/1 array contoured at isovalue 127 below would find no
    # isosurface at all otherwise, a real bug caught by this module's
    # own test_accepts_nonzero_foreground_not_only_255).
    normalized = (arr != 0).astype(np.uint8) * 255
    image = converters.to_vtk(normalized, spacing, 0, "AXIAL")

    flip = vtkImageFlip()
    flip.SetInputData(image)
    flip.SetFilteredAxis(1)
    flip.FlipAboutOriginOn()
    flip.Update()

    contour = vtkFlyingEdges3D()
    contour.SetInputData(flip.GetOutput())
    contour.SetValue(0, 127)
    # Speed hygiene for a non-authoritative preview mesh - the final
    # surface pipeline doesn't need these either (see its own commented-
    # out ComputeScalarsOn()/ComputeGradientsOn()/ComputeNormalsOn()
    # calls in surface_process.py, left off there too).
    contour.ComputeNormalsOff()
    contour.ComputeGradientsOff()
    contour.ComputeScalarsOff()
    contour.Update()

    polydata = vtkPolyData()
    polydata.DeepCopy(contour.GetOutput())
    return polydata


class PreviewSurfaceManager3D:
    """
    Owns exactly one vtkActor (fast preview mesh) in a given renderer.
    Mirrors core/marker_3d.CrosshairMarker3D's attach()/detach() pattern:
    attach() creates the actor once and is safe to call repeatedly
    (moving to a new renderer first detaches from the old one, so reopen
    never leaves a duplicate/orphaned actor); set_polydata() updates the
    SAME actor's mapper input in place - never adds a second actor.

    generation_id (Section 20, reusing E2's proven concept): bumped by
    new_generation() before starting a (possibly async) mesh build;
    set_polydata_if_current(generation_id, ...) discards a stale result
    whose generation no longer matches - the same async-race guard
    core/segmentation_preview.SegmentationPreviewManager already
    established for E2, reused here for the same real reason (a
    background mesh-build worker can finish after a newer one started).
    """

    def __init__(self, colour: Tuple[float, float, float] = (0.2, 0.7, 1.0), opacity: float = 0.45):
        self.colour = colour
        self.opacity = opacity
        self.renderer = None
        self.actor = None
        self.mapper = None
        self.visible = False
        self.generation_id = 0
        # "current_roi" | "otsu_preview" | "region_growing_preview" -
        # which real source the currently-displayed mesh (if any) came
        # from - set by set_polydata_if_current(), read by the GUI
        # layer for the status label (Section 17).
        self.source_kind: Optional[str] = None

    def attach(self, renderer) -> bool:
        try:
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

            if self.actor is not None and self.renderer is not None and self.renderer is not renderer:
                self.detach()

            if self.actor is None:
                self.mapper = vtkPolyDataMapper()
                self.actor = vtkActor()
                self.actor.SetMapper(self.mapper)
                self.actor.GetProperty().SetColor(*self.colour)
                self.actor.GetProperty().SetOpacity(self.opacity)
                # Section 10 (3D pick safety): never obstructs the real
                # picker (Pick Point in 3D / Region Growing seed pick /
                # 3D distance measurement / C8) - a real VTK mechanism,
                # not a convention this plugin has to separately enforce
                # in the picker code.
                self.actor.SetPickable(False)
                self.actor.VisibilityOff()

            if self.renderer is not renderer:
                renderer.AddActor(self.actor)
                self.renderer = renderer

            return True
        except Exception as e:
            print(f"ROI Viewer: preview surface attach failed - {e}")
            return False

    def is_attached(self) -> bool:
        return self.actor is not None and self.renderer is not None

    @property
    def actor_count(self) -> int:
        return 1 if self.actor is not None else 0

    def new_generation(self) -> int:
        self.generation_id += 1
        return self.generation_id

    def is_stale(self, generation_id: int) -> bool:
        return generation_id != self.generation_id

    def set_polydata_if_current(self, generation_id: int, polydata, source_kind: Optional[str] = None) -> bool:
        """
        Updates the SAME actor's mapper input (never a new actor) if
        `generation_id` is still current - returns False (no-op) for a
        stale result. `polydata=None` (Section 26 - empty mask) hides
        the actor without erroring.
        """
        if self.is_stale(generation_id):
            return False
        if self.mapper is None:
            return False
        if polydata is None:
            self.set_visible(False)
            self.source_kind = None
            return True
        self.mapper.SetInputData(polydata)
        self.mapper.Modified()
        self.source_kind = source_kind
        self.set_visible(True)
        return True

    def set_visible(self, visible: bool):
        if self.actor is None:
            return
        self.actor.SetVisibility(bool(visible))
        self.visible = bool(visible)

    def clear(self):
        """Hide and forget the current source, WITHOUT detaching (actor/
        mapper stay attached and ready for the next update) - and bumps
        generation_id so any in-flight build's result is automatically
        treated as stale when it completes."""
        self.generation_id += 1
        self.set_visible(False)
        self.source_kind = None

    def detach(self):
        """Remove the actor from its renderer entirely. Idempotent -
        same real semantics as CrosshairMarker3D.detach()."""
        if self.actor is not None and self.renderer is not None:
            try:
                self.renderer.RemoveActor(self.actor)
            except Exception:
                pass
        self.renderer = None
        self.actor = None
        self.mapper = None
        self.visible = False
        self.source_kind = None
        self.generation_id += 1
