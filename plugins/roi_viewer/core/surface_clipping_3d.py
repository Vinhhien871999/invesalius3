# --------------------------------------------------------------------------
# E5B - Surface Clipping / Cutaway Module (Advanced Segmentation
#       Enhancement Track, enhancement/advanced-segmentation branch ONLY)
# Description: a real, DISPLAY-ONLY VTK clipping plane attached to a
#              real final-surface actor's mapper via the standard real
#              VTK API vtkMapper.AddClippingPlane(vtkPlane) - never
#              vtkClipPolyData, never a change to any project surface
#              polydata.
#
# CORE INVARIANT this module exists to protect: clipping never modifies
# a mask, never modifies Project().surface_dict, never modifies a
# surface's own vtkPolyData - only what the mapper chooses to RASTERIZE
# changes. Removing the clipping plane restores the exact original
# rendered appearance, because the underlying geometry was never
# touched.
#
# Real source-first audit (see docs/CT3D_ADVANCED_E5_VISUALIZATION_
# REPORT.md's "Surface actor/mapper audit" section for the full
# citations): read invesalius/data/surface.py directly. Two real,
# load-bearing findings this module's design depends on:
#
#  1. `Surface` (the class backing Project().surface_dict entries) has
#     NO mask-index field anywhere - `mask_index == surface_index` is
#     NOT a safe assumption (it is, in fact, provably FALSE in
#     general): `SurfaceManager.AddNewActor()`'s real overwrite path
#     (data/surface.py ~line 1445-1448, the exact path this plugin's
#     own `_on_update_surface()` always exercises via
#     `surface_parameters["options"]["overwrite"]=True`) assigns the
#     newly-built Surface's `.index` from `self.last_surface_index` - a
#     single GLOBAL "most recently touched surface" counter shared
#     across ALL masks, not the mask index that was rebuilt. This
#     module therefore never guesses a surface index from a mask index;
#     see "Current-ROI surface resolution" below for the real,
#     evidence-based alternative.
#
#  2. `SurfaceManager.actors_dict` (index -> real vtkActor) is private
#     state on an object this plugin has no direct reference to
#     (SurfaceManager lives inside invesalius.control.Controller, never
#     exposed). The real, already-existing, already-used-elsewhere
#     (invesalius/gui/task_efield.py) way to fetch a real actor for a
#     known surface index without reaching into that private state is
#     the real pubsub request/reply pair `Publisher.sendMessage("Get
#     Actor", surface_index=...)` -> `SurfaceManager.GetActor()` (data/
#     surface.py) -> `Publisher.sendMessage("Send Actor",
#     e_field_actor=...)`, synchronous within the same call stack for a
#     single subscriber (pypubsub dispatches sendMessage() calls
#     synchronously). This module reuses that exact real mechanism.
# --------------------------------------------------------------------------
from typing import Optional, Tuple

PLANE_AXIAL = "AXIAL"
PLANE_CORONAL = "CORONAL"
PLANE_SAGITAL = "SAGITAL"

# Real, proven world-axis mapping (NOT assumed - see the module
# docstring's citation trail): world X = SAGITAL (fastest-varying image
# axis), Y = CORONAL, Z = AXIAL slice stack. Confirmed by TWO
# independent, already-tested real sources that had to agree with each
# other for either to be correct: interface/project_interface.py's
# ProjectInterface.voxel_to_world()/world_to_voxel() docstrings, and
# core/slice_planes_3d.py.SlicePlanes3D._update_geometry()'s own real,
# already-shipped geometry (Axial plane is constant in Z, Coronal
# constant in Y, Sagital constant in X). A clipping plane's normal for
# a given orientation is the SAME axis that orientation's geometric
# plane is constant along - both are "this orientation's slice normal
# direction".
_NORMALS = {
    PLANE_AXIAL: (0.0, 0.0, 1.0),
    PLANE_CORONAL: (0.0, 1.0, 0.0),
    PLANE_SAGITAL: (1.0, 0.0, 0.0),
}


def resolve_surface_actor(surface_index: int):
    """
    Real, source-proven mechanism (see module docstring finding #2) to
    fetch the real vtkActor for a known real surface_index, without any
    direct reference to the private SurfaceManager instance that owns
    it - reuses the exact same real "Get Actor"/"Send Actor" pubsub
    request/reply pair invesalius/gui/task_efield.py already uses for
    the identical real need. Returns None (never raises) if no project
    is loaded, pubsub is unavailable, or no actor exists for that index
    (a stale/deleted surface_index) - all real, expected "nothing to
    clip yet" outcomes, not error conditions.
    """
    try:
        from invesalius.pubsub import pub as Publisher
    except ImportError:
        return None

    result = {}

    def _capture(e_field_actor):
        result["actor"] = e_field_actor

    Publisher.subscribe(_capture, "Send Actor")
    try:
        Publisher.sendMessage("Get Actor", surface_index=surface_index)
    except Exception as e:
        print(f"ROI Viewer: resolve_surface_actor('Get Actor') failed - {e}")
    finally:
        Publisher.unsubscribe(_capture, "Send Actor")

    return result.get("actor")


class SurfaceClipping3D:
    """
    Owns exactly ONE real vtkPlane and tracks exactly ONE "owned"
    vtkMapper it has added that plane to (never more than one target at
    a time this milestone - Section 18's first-implementation-target
    scope: Current ROI Final Surface; optional E4 preview target tracked
    SEPARATELY per Section 25, not mixed into this same plane/mapper
    pair, to avoid any lifecycle ambiguity about which target "owns"
    the plane).

    Ownership discipline (Section 22 - "disable must fully remove...
    not merely move it away... do not remove clipping planes owned by
    something else"): this class NEVER calls RemoveAllClippingPlanes()
    on a mapper (that could remove a plane something else added) - it
    only ever calls mapper.RemoveClippingPlane(self.plane) with the
    exact vtkPlane instance IT added, and only on the exact mapper IT
    added it to (self.mapper), tracked explicitly rather than inferred.
    """

    def __init__(self):
        from vtkmodules.vtkCommonDataModel import vtkPlane

        self.plane = vtkPlane()
        self.enabled = False
        self.mapper = None
        self.orientation = PLANE_AXIAL
        self.inverted = False
        self.origin: Optional[Tuple[float, float, float]] = None
        self._apply_normal()

    # ------------------------------------------------------------------
    # Plane parameters
    # ------------------------------------------------------------------

    def set_orientation(self, orientation: str):
        if orientation not in _NORMALS:
            raise ValueError(f"orientation must be one of {list(_NORMALS)}, got {orientation!r}")
        self.orientation = orientation
        self._apply_normal()

    def set_inverted(self, inverted: bool):
        self.inverted = bool(inverted)
        self._apply_normal()

    def set_origin(self, world_position: Tuple[float, float, float]):
        """
        Section 19: real clipping-plane position comes from the SAME
        real C8 crosshair position SlicePlanes3D already uses - not a
        second, independent slider - so there is exactly one spatial
        source of truth (native 2D crosshair -> C8 planes -> E5
        clipping). Safe to call before enable()/set_target_mapper() -
        just records the position for when a plane function evaluation
        actually happens.
        """
        x, y, z = (float(c) for c in world_position)
        self.origin = (x, y, z)
        self.plane.SetOrigin(x, y, z)

    def _apply_normal(self):
        nx, ny, nz = _NORMALS[self.orientation]
        if self.inverted:
            nx, ny, nz = -nx, -ny, -nz
        self.plane.SetNormal(nx, ny, nz)

    # ------------------------------------------------------------------
    # Target / lifecycle
    # ------------------------------------------------------------------

    def set_target_mapper(self, mapper) -> None:
        """
        Section 23/24 (ROI-switch / surface-rebuild handling): detach
        from whatever mapper this instance previously owned (only if it
        actually added the plane there - Section 22's ownership
        discipline) before adopting a new one. Passing None detaches
        with no new target (Section 18/23 "no final surface for
        selected ROI" case) - the plane is not re-added anywhere until a
        real mapper is set again.
        """
        if self.mapper is not None and self.mapper is not mapper:
            self._remove_owned_plane_from(self.mapper)
        self.mapper = mapper
        if self.enabled and self.mapper is not None:
            self.mapper.AddClippingPlane(self.plane)

    def enable(self) -> None:
        """No-op if already enabled (Section 22 - "enable twice: no
        duplicate plane" - vtkMapper.AddClippingPlane() itself would
        happily add the same plane object twice, producing two entries
        in its vtkPlaneCollection; this class prevents that by never
        calling it a second time while already enabled)."""
        if self.enabled:
            return
        self.enabled = True
        if self.mapper is not None:
            self.mapper.AddClippingPlane(self.plane)

    def disable(self) -> None:
        """Fully removes the owned plane from the owned mapper (Section
        22) - not merely hidden/moved. Idempotent."""
        if not self.enabled:
            return
        self.enabled = False
        self._remove_owned_plane_from(self.mapper)

    def _remove_owned_plane_from(self, mapper):
        if mapper is None:
            return
        try:
            mapper.RemoveClippingPlane(self.plane)
        except Exception:
            pass

    def detach(self):
        """Full teardown (project close / plugin close, Section 28) -
        disables (removing the owned plane from its owned mapper) and
        forgets the mapper reference so no dangling reference survives
        into a new project."""
        self.disable()
        self.mapper = None

    @property
    def owned_plane_count_on(self) -> int:
        """Test helper: how many times THIS instance's plane object
        currently appears in its owned mapper's clipping-plane
        collection (must never exceed 1 - Section 22's duplicate-plane
        guard). Returns 0 if not enabled or no mapper."""
        if not self.enabled or self.mapper is None:
            return 0
        planes = self.mapper.GetClippingPlanes()
        if planes is None:
            return 0
        count = 0
        for i in range(planes.GetNumberOfItems()):
            if planes.GetItemAsObject(i) is self.plane:
                count += 1
        return count
