# CT3D Phase 11 — Persistent Test & Regression Architecture

## 1. Metadata

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Repository | Vinhhien871999/invesalius3 |
| Branch | `thesis-ct-roi-tools` |
| HEAD before | `ffa08954` (last commit of Phase 10) |
| HEAD after | `36dc59ba` |
| Python | 3.11.7 (`D:\PyTools\invx-venv\Scripts\python.exe`) |
| pytest | 8.3.5 (already an InVesalius dependency, `pyproject.toml`) |
| NumPy | 1.26.4 |
| SciPy | 1.14.0 |
| VTK | 9.3.0 |
| wxPython | 4.2.5 |
| Other | psutil 6.0.0, nibabel 5.2.1; `pynrrd` NOT installed (optional, exercised via `pytest.importorskip`) |

## 2. Objectives

Per the phase spec: (1) promote important prior-round evidence from ephemeral scratchpad scripts into a persistent, repository-tracked `pytest` suite; (2) a one-command-runnable architecture with `unit`/`integration`/`gui`/`slow`/`dataset` markers; (3) re-verify the Phase 10 Undo/Redo memory invariant with real code/tests (not hand reasoning) and correct Phase 10's documentation if the estimate was wrong; (4) remove `MaskEditor`'s dead drawing methods only if proven to have zero call-sites and only after the new suite passes; (5) a light, evidence-based static-quality pass; (6) no new features, no auto-upgrading the 7 manual-QA items.

## 3. Baseline

`git log --oneline -3` at start:
```
ffa08954 Phase 10 docs: ...
0e51bcf9 Phase 10 (CT3D_P10_DATA_INTEGRITY): lower Undo/Redo default history from 20 to 10
b5d304fb Phase 09 docs: ...
```
`git status` at start: clean except a pre-existing, unrelated set of uncommitted root-level `.md` file moves (`Ke_hoach_de_tai_InVesalius_CT3D.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md` → `docs/`) that predate this phase and were not touched.

## 4. Existing Test Audit

| Test evidence | Persistent before P11? | Action |
|---|---|---|
| `tests/test_mask.py`, `test_dicom_loading.py`, `test_segmentation_tools.py`, `test_bone_thresholding.py`, `test_3mf.py`, `test_mesh_generation.py`, `test_ply_export.py`, `test_publisher.py`, `test_session.py`, `test_stl_export.py`, `test_tracker.py`, `test_vtp_export.py`, `test_math_utils.py` | **A - tracked in git** (upstream InVesalius suite, not CT3D-specific) | Left untouched - out of scope. Ran for real (`pytest tests/ --ignore=tests/ct3d`): **94 passed** in 188.7s, unaffected by this phase's changes (the only shared file touched, `pyproject.toml`, only adds a new `[tool.pytest.ini_options]` markers section, additive and non-breaking). |
| `plugins/roi_viewer/` test files | **None existed** | New `tests/ct3d/` suite created (this phase). |
| `test_project_roundtrip.py`, `test_guide_saveopen.py`, `test_coordinate_roundtrip.py`, `test_region_growing_limits.py`, all Phase 08/09 scripts, `p10_saveopen_forensics.py`, `p10b_undoredo_benchmark.py`, `p10c_undoredo_functional_tests.py` | **C - only referenced in docs, files no longer exist** (this project's established scratchpad-is-ephemeral convention - confirmed, not assumed: none of these paths exist under `tests/`, `plugins/`, or the repo root) | `EPHEMERAL_TEST_MISSING` for all of them. Not recovered verbatim - their important evidence was re-derived as real, independent persistent tests (see Sections 8-10 below), per the spec's explicit instruction that recovery of the exact old scripts was not the goal. |

## 5. Test Architecture

No existing repo convention fit a plugin-scoped suite cleanly (the upstream `tests/` directory is InVesalius-core-only, uses no markers, and `tests/__init__.py` makes it a package). Used the spec's suggested `tests/ct3d/`:

```
tests/ct3d/
├── conftest.py            # isolation fixtures (see Section 7)
├── test_segmentation.py   # D10 Region Growing, D2 threshold/Otsu (unit)
├── test_measurement.py    # E1/E3/E4 distance/area/volume (unit)
├── test_coordinates.py    # voxel<->world transform (unit)
├── test_undo_redo.py      # D7 Undo/Redo + memory invariant (unit)
├── test_annotation.py     # F1/F2/F4 add/edit/delete/sidecar (unit)
├── test_roi_manager.py    # D8 ROI List cache/view invariant (integration)
├── test_sync_2d3d.py      # C8 Sync 2D->3D + F3 position policy (integration)
├── test_serialization.py  # G1/G2 Save/Open round-trip (integration, slow)
├── test_exporters.py      # H1/H2-H5 mask/surface export (integration)
└── test_surface_policy.py # D9/C7 algorithm-choice policy (unit)
```
No file was created "just to have a name" - `test_surface_policy.py` exists because the underlying logic needed a small, behavior-preserving extraction (see Section 9) to be testable at all; every other file maps 1:1 onto a real `core/` module.

## 6. Pytest Markers

Added to `pyproject.toml`'s new `[tool.pytest.ini_options]` section (the repo had no `[tool.pytest...]` section before this phase):
```toml
markers = [
    "unit: pure deterministic tests - no DICOM/GUI/VTK-renderer/dataset required",
    "integration: tests that use real InVesalius singletons (Project/Slice), VTK objects, or pubsub wiring, but no mouse/keyboard interaction",
    "gui: requires real GUI mouse/keyboard interaction - not automatable, never faked",
    "slow: relatively expensive integration tests (real DICOM import, full-size builds)",
    "dataset: requires an external DICOM dataset on disk",
]
```
No `gui`- or `dataset`-marked tests exist yet in this suite (nothing in it needed real mouse/keyboard interaction or an external dataset to be tested meaningfully - see Section 18 for what genuinely still needs a human). `slow` is applied to `test_serialization.py` (real Save/Compress/Extract/Open cycles).

## 7. Fixtures & Isolation

`tests/ct3d/conftest.py`:
- **Config isolation**: `XDG_CONFIG_HOME` redirected to a fresh `tempfile.mkdtemp()` at conftest module-import time (before any `invesalius` import), matching `invesalius/inv_paths.py`'s module-level env-var read - the same technique Phase 08/09/10's standalone scripts used. The real user's `~/.config/invesalius/` (or `%APPDATA%` equivalent) is never touched.
- **Circular-import ordering**: `invesalius.project` imports `invesalius.gui.dialogs` at module level, which transitively imports `invesalius.data.slice_`, which does `from invesalius.project import Project` back - a real, pre-existing circular import in `invesalius/` itself (confirmed by reproducing it standalone; not introduced by this suite). Importing `invesalius.data.slice_` first avoids it - exactly what the existing upstream `tests/test_mask.py` already does. Done once in `conftest.py` so individual test files don't need to know about it.
- **Singleton reset**: `invesalius.project.Project` and `invesalius.data.slice_.Slice` use `invesalius.utils.Singleton` (a metaclass storing `cls.instance`). An `autouse=True` fixture sets `Project.instance = None` / `Slice.instance = None` before AND after every single test, so state from one test never leaks into the next.
- **`wx_app`**: a single session-scoped `wx.App(False)`, since some real invesalius code (e.g. `Slice.create_new_mask()`'s `wx.BeginBusyCursor()`) requires one to exist even when no window is ever shown.
- **`isolated_cwd_tmp`**: convenience `tmp_path`-based chdir fixture for tests that write files.

## 8. Unit Tests Added

75 unit tests, zero DICOM/GUI/VTK-renderer/dataset dependency, run in ~0.14s:
- `test_segmentation.py`: RG-U1..U8 (region growing: single component, disjoint same-intensity regions, tolerance 0, negative tolerance raises, out-of-bounds seed, NaN/Inf seed, boundary seed, 6-connectivity diagonal-vs-face-adjacent) + Otsu/threshold/region-stats tests.
- `test_measurement.py`: M-U1 (3-4-5 triangle), M-U2 (uneven-spacing distance, independent reference calc), M-U3 (uneven-spacing volume), **M-U4 (direct regression test for the real E4 padding/sentinel bug fixed in Round 3)** + area/delete/clear tests.
- `test_coordinates.py`: origin/center/near-end/non-integer/out-of-bounds/zero-spacing round trips, with independent reference formulas (not copied from `world_to_voxel`/`voxel_to_world`'s own code).
- `test_undo_redo.py`: UR11-T1..T9 plus the memory-invariant investigation (Section 11).
- `test_annotation.py`: add/edit/delete/visibility/clear/sidecar round-trip via real `tmp_path`.
- `test_surface_policy.py`: SP-T1/T2 against the newly-extracted `choose_surface_algorithm()`.

## 9. Integration Tests Added

34 tests (33 passed + 1 skipped), real `Project()`/VTK objects/pubsub, no mouse/keyboard, ~0.45s:
- `test_roi_manager.py`: rebuild/rename/visibility/remove against a real `Project().mask_dict`, "no orphan ROI" invariant after a chained sequence of operations.
- `test_sync_2d3d.py`: `CrosshairMarker3D` against a real `vtkRenderer()` (no duplicate actors across 20 updates, detach removes the actor, reattach to a new renderer leaves no orphan); `on_cross_focal_point_changed`/`get_current_reference_position` exercised via their real, unmodified bound-method code against a minimal stand-in `self` (documented in the file header - these methods only touch a small, fully-enumerated attribute set, verified by reading their full bodies first).
- `test_exporters.py`: NumPy/NIfTI/VTK/STL/PLY/OBJ round trips on a tiny synthetic mesh/mask; NRRD explicitly skips (not fails) when `pynrrd` is absent, and a second test confirms the real ImportError-handling branch returns `False` rather than raising.
- `test_serialization.py`: see Section 10.

`choose_surface_algorithm(mask)` (Section XVI's allowed extraction): pulled the one-line `algorithm = "Binary" if getattr(mask, "was_edited", False) else "Default"` decision out of `_on_update_surface()`'s inline body into a small top-level pure function in the same file, called from the same place - zero behavior change, confirmed by the existing Phase 08 evidence still being valid (the extraction is a pure rename/relocation of one expression).

## 10. Serialization Regression

`test_serialization.py` promotes Phase 10's RT-A/B/C/E scenarios (ephemeral `p10_saveopen_forensics.py`, 30/30 PASS, no longer present on disk) into 5 persistent tests, constructing `Mask()`/`Project()` directly rather than going through a full wx Frame/Controller/DICOM-import bootstrap (unnecessary for Save/Open-only testing - confirmed neither `Mask.SavePlist`/`OpenPList`/`_open_mask` nor `Project.SavePlistProject`/`OpenPlistProject`/`Close` import wx):
- SER-T1: synthetic mask, byte-identical full-matrix and logical-payload SHA-256 hashes after a real Save→Close→Open cycle.
- SER-T2: `was_edited=True` + a non-default `threshold_range` both survive the round trip (the D9/C7 policy depends on this).
- **SER-T3**: a direct, permanent regression test for the index-remapping mechanism Phase 10 identified (`CT3D_P10_DATA_INTEGRITY_REPORT.md` Section 9) as the likely explanation for the earlier false-positive checksum report - deletes a mask to create an index gap, saves, reopens, and asserts that a lookup by the STALE pre-save index finds the wrong mask (or nothing), while a lookup by name finds the correct one with an identical hash.
- A gzip-compression variant and a metadata (name/colour/visibility) round-trip test.

All 5 pass for real, confirming Phase 10's CASE A conclusion (no code fix needed) remains correct under this phase's fresh, independent test implementation.

## 11. Undo/Redo Invariant Investigation

**This is Phase 11's most consequential finding.** Answered with real code (`test_undo_redo.py`), not hand reasoning:

- **max undo reachable**: `max_history` (10, the current default) - a `deque(maxlen=max_history)`, confirmed via `test_ur_t7_eviction_at_max_history`.
- **max redo reachable**: `max_history` (10) - same structural cap on `redo_stack`.
- **max combined reachable**: **`max_history` (10), NOT `2 * max_history` (20)**. Proof (see `test_undo_redo_memory_invariant_q1_both_stacks_simultaneously_full_is_impossible` and the deterministic/randomized sequence tests): `redo_stack` can only gain entries via `undo()`, which takes them FROM `undo_stack` (a zero-sum transfer between the two stacks, or a net loss if the destination is already full and evicts). The only operation that adds brand-new content, `save_state()`, always clears `redo_stack` to empty in the same call. So the combined total can only be built up by repeated `save_state()` calls (which simultaneously zero the other stack) - it structurally cannot independently fill both stacks to `max_history` at once. Confirmed empirically across the 6 deterministic sequences from the spec (10 saves; +1 undo; +5 undo; +10 undo; +10 undo +5 redo; +5 undo + new save) and 300 randomized sequences (fixed seed `20260914`, public-API-only: save/undo/redo/clear) - `len(undo_stack) + len(redo_stack) <= max_history` held in **every single one of the thousands of intermediate states checked**, and the ceiling (`== max_history`) was empirically reached, not just theoretically possible.
- **bytes/checkpoint** (real CT scale, 109×513×513 uint8, matching Phase 10's measured shape): **28,685,421 bytes** (exactly reproduced from Phase 10's number).
- **actual reachable maximum memory**: `10 × 28,685,421 bytes = 286,854,210 bytes ≈ 273.6 MB` - confirmed two independent ways in the same test: (a) the Q1/Q2-derived formula, and (b) a real run of `UndoRedoManager` against real memmap-backed arrays (small shape, for test speed, but the identical uint8/1-byte-per-voxel relationship), summing each retained array's real `.nbytes`.

**Conclusion: Phase 10's report and the user guide both stated a worst case of ~1.07 GB (old default, `max_history=20`) reduced to ~547 MB (new default, `max_history=10`) - both numbers assumed `undo_stack` and `redo_stack` could independently reach `max_history` SIMULTANEOUSLY (`2 × max_history` combined). That assumption is wrong: the real, code-verified maximum is `max_history` combined snapshots, not `2 × max_history`. The correct real-CT-scale worst case at the CURRENT default (`max_history=10`) is ~273.6 MB, not ~547 MB - Phase 10 overestimated by exactly 2×.**

## 12. Phase 10 Memory Clarification

Per Section XI of the spec, this is a correction, not a silent rewrite of history - Phase 10's report, `CT3D_MASTER_PROGRESS.md`, `CT3D_FEATURE_AUDIT.md`, `CT3D_CHANGELOG.md`, and `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` are all updated (Section 19/23) with an explicit "Phase 11 correction" note stating: the old assumption (`2 × max_history` combined), the new invariant (`max_history` combined, proven by `test_undo_redo.py`), the corrected number (~273.6 MB, not ~547 MB), and that **the Phase 10 code decision itself (lower `max_history` from 20 to 10) is UNCHANGED** - kept as a deliberate, conservative, documented bounded-history limit (see Section below), not reverted, since 20 vs 10 was never actually the load-bearing part of that decision (halving `max_history` still halves the real worst case at either the old, wrong 2× formula or the new, correct 1× formula - the decision's direction and safety margin both remain valid; only the absolute number attached to it was wrong by a factor of 2).

## 13. Dead Code Audit

Per Section XIX, before removing anything: grepped the WHOLE repository (not just the plugin) for direct calls, `getattr`/dynamic dispatch, event bindings, callbacks, imports, subclass overrides, and documentation references, for every method Phase 10 flagged (`draw_point_2d`, `draw_point_3d`, `interpolate_slices`) plus everything else in the same class that turned out to share the same fate once the investigation started:

| Method (on `MaskEditor`) | Call sites found (whole repo) | Verdict |
|---|---|---|
| `draw_point_2d`, `erase_point_2d`, `draw_point_3d` | 0 (only self-references inside the dead cluster itself) | `CONFIRMED_DEAD_CODE` |
| `interpolate_slices` | 0 | `CONFIRMED_DEAD_CODE` |
| `_get_brush_mask` | 0 (only called by the dead `draw_point_2d`/`draw_point_3d`) | `CONFIRMED_DEAD_CODE` (transitively) |
| `set_brush_size`, `set_brush_shape` | 0 | `CONFIRMED_DEAD_CODE` |
| `get_mask`, `set_mask`, `get_mask_slice` (this class's own versions - distinct from `invesalius.data.slice_.Slice.get_mask_slice`, a real, actively-used, unrelated core method) | 0 | `CONFIRMED_DEAD_CODE` |
| **`undo()`, `redo()`, `clear_mask()`** (this class's OWN wrapper methods) | 0 - the real GUI (`segmentation_panel.py._on_undo`/`_on_redo`) calls `editor.undo_manager.undo(mask.matrix)` / `.redo(mask.matrix)` **directly**, bypassing these wrapper methods entirely | `CONFIRMED_DEAD_CODE` (a broader finding than Phase 10's original 3-method flag - documented explicitly, not silently expanded) |
| `save_state()` | Real: `segmentation_panel.py._on_checkpoint()` calls `editor.save_state()` | **KEPT** |
| `__init__`, `self.shape`/`self.mask`/`self.undo_manager` | Real: `editor.mask = mask.matrix` (direct attribute write), `.undo_manager` (accessed directly) | **KEPT** |
| `UndoRedoManager` (the whole class) | Real, heavily used (D7) | **KEPT**, per the explicit instruction not to touch it |

## 14. Dead Code Removed

`plugins/roi_viewer/core/mask_editor.py`: **175 lines removed, 29 lines added** (net **-146 lines**; whole-file: 294 → 150 lines with this phase's other doc-comment additions included). All persistent tests re-run after removal: **109 passed, 1 skipped** (same result as before removal - confirmed zero regression). A new permanent regression guard (`test_mask_editor_surviving_surface_after_dead_code_removal`) asserts the removed methods stay removed and the real surface (`shape`/`mask`/`undo_manager`/`save_state`) stays present.

Not removed (out of this phase's investigation trigger, flagged `NOT_PROVEN_DEAD` rather than assumed): `MaskEditorManager.set_current_mask()`, `.get_current_editor()`, `.delete_editor()` - a different class, not part of Phase 10's original flag, not investigated with the same rigor this phase; left as-is per "không refactor lớn".

## 15. Static Quality Audit

Manual grep audit (bare `except:`, `except Exception: pass`, leftover debug prints, TODO/FIXME, hardcoded absolute paths): **zero findings** - the plugin was already clean on all of these. Installed `pyflakes` (small, pure-Python, no risk) for a more rigorous unused-import/unused-variable pass across `plugins/roi_viewer/`:

Fixed (all evidence-based, plugin-only, one-line-per-file, zero behavior change, confirmed via `pyflakes` + `py_compile`):
- Unused imports removed: `main.py` (`os`; and 5 redundant top-level submodule imports - `interaction_panel`/`measurement_panel`/`annotation_panel`/`export_panel`/`project_interface`/`view_interface` - confirmed redundant since `roi_panel.py` itself imports the 4 GUI panels directly, and the 2 interface modules are imported locally where actually used elsewhere), `exporters.py` (`os`, `typing.List`, `tempfile`), `mask_editor.py` (`typing.List`, now unused after the dead-code removal), `measurement.py` (`time`), `sync_2d3d.py` (`typing.Optional`), `annotation_panel.py` (`datetime`), `export_panel.py` (`os`), `roi_panel.py` (`wx.lib.scrolledpanel as scrolled`), `picker_3d.py` (`vtkPointPicker`, `vtkInteractorStyleRubberBandPick`, `vtkCoordinate` - all confirmed unused inside their respective function bodies).
- Dead local variable removed: `segmentation.py`'s `auto_threshold_otsu()` computed `total_mean` and never used it (the between-class-variance formula actually used, `w0*w1*(m0-m1)^2`, is a standard equivalent that doesn't need it - not a correctness bug, just leftover computation from an earlier formulation).

Found but deliberately NOT fixed (documented, not silently ignored): `pyflakes` flags 10 occurrences of `global _roi_viewer_window` in `main.py` as "unused: name is never assigned in that scope" (each of those functions only READS the global, never assigns it - the `global` keyword there is technically redundant). Left as-is: a pure style nit with zero behavior impact, and fixing 10 call sites for style alone would violate the spec's own "không tạo diff khổng lồ chỉ vì style" instruction.

`py_compile` + a full plugin import check confirm every file still compiles and imports cleanly after all of the above.

## 16. Regression Results

| Suite | Collected | Passed | Failed | Skipped | Duration |
|---|---:|---:|---:|---:|---:|
| `tests/ct3d -m unit` | 75 | 75 | 0 | 0 | 0.14s |
| `tests/ct3d -m integration` | 34 | 33 | 0 | 1 (`pynrrd` not installed) | 0.45s |
| `tests/ct3d` (full, `-m "not gui and not dataset"` equivalent - no gui/dataset tests exist yet) | 109 | 108 | 0 | 1 | ~0.55s |
| `tests/` (upstream, excluding `tests/ct3d`) | 94 | 94 | 0 | 0 | 188.7s |

## 17. Three Consecutive Runs

Run 1: `108 passed, 1 skipped in 0.56s`
Run 2: `108 passed, 1 skipped in 0.54s`
Run 3: `108 passed, 1 skipped in 0.52s`
(Re-run once more after the dead-code removal + static-quality pass, final state: `109 passed, 1 skipped in 0.55-0.62s` across further repeated runs - the +1 test is the new dead-code regression guard added afterward.) No test order dependency observed; no leftover temp files (all file-writing tests use `tmp_path`); no writes to the real user config directory (isolated via `XDG_CONFIG_HOME`, verified by checking the isolated temp path, not `~/.config/invesalius/`, receives the session state file).

## 18. Manual QA Still Required

Unchanged from Phase 09/10 - **not touched, not auto-upgraded**: P08.5 (D9/C7 via the real GUI dialog, not `batch_mode`), B4 (Zoom/Pan 2D), C3 (Rotate/Pan/Zoom 3D), D4 (Brush), D5 (Eraser), E2 (Distance 2D), E3 (Area 2D). All remain `NEEDS_MANUAL_QA`. Checklist: `CT3D_P09_INTERACTION_QA_REPORT.md` Section 9.

## 19. Files Changed

Code: `plugins/roi_viewer/core/mask_editor.py` (dead-code removal), `plugins/roi_viewer/gui/segmentation_panel.py` (`choose_surface_algorithm()` extraction), `plugins/roi_viewer/core/{exporters,measurement,picker_3d,segmentation,sync_2d3d}.py` and `plugins/roi_viewer/gui/{annotation_panel,export_panel,roi_panel}.py` and `plugins/roi_viewer/main.py` (static-quality import/dead-variable cleanup), `pyproject.toml` (pytest markers).
New: `tests/ct3d/` (11 files, 109 tests), `docs/CT3D_P11_TEST_AUTOMATION_REPORT.md` (this file).
Docs updated: `docs/CT3D_MASTER_PROGRESS.md`, `docs/CT3D_FEATURE_AUDIT.md`, `docs/CT3D_REMAINING_WORK.md`, `docs/CT3D_CHANGELOG.md`, `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`, `docs/CT3D_P10_DATA_INTEGRITY_REPORT.md` (memory correction note).

## 20. Bugs Found

1. **Phase 10's Undo/Redo worst-case memory estimate was overestimated by exactly 2×** (~547 MB claimed vs ~273.6 MB real maximum reachable) - a documentation/reasoning bug, not a code bug (Section 11/12).
2. A larger-than-previously-documented dead-code surface inside `MaskEditor` (10 methods, not just the 3 Phase 10 flagged) - a code-cleanliness finding, not a functional bug (Section 13).
3. Minor static-quality findings (unused imports, one dead local variable) - no functional impact (Section 15).

## 21. Bugs Fixed

1. Documentation corrected (5 files) to state the real ~273.6 MB maximum instead of ~547 MB (Section 12/19). The `max_history=10` code decision itself is kept (still valid, conservative, and now correctly justified by real numbers).
2. 10 confirmed-dead methods removed from `MaskEditor`, 146 net lines (Section 14).
3. All static-quality findings listed as "fixed" in Section 15 were fixed.

## 22. Remaining Issues

- The 7 manual-QA items (Section 18) still need a real human mouse session - unchanged, not this phase's job.
- `MaskEditorManager`'s 3 possibly-unused methods (`set_current_mask`/`get_current_editor`/`delete_editor`) are `NOT_PROVEN_DEAD` - not investigated with full rigor this phase, left as-is.
- The `global _roi_viewer_window` style nit in `main.py` (10 occurrences) - deliberately left, documented in Section 15.
- No `gui`- or `dataset`-marked tests exist in the new suite - nothing added this phase needed real mouse/keyboard interaction or an external dataset to be meaningfully tested; this is expected, not a gap in the suite's design.

## 23. Status Matrix Changes

| ID | Before Phase 11 | After Phase 11 |
|---|---|---|
| D7 (Undo/Redo) | WORKING, memory estimate ~547 MB (Phase 10, later shown to be a 2x overestimate) | WORKING, memory estimate corrected to ~273.6 MB (real maximum, code-verified), `max_history=10` decision unchanged |
| D2/D9/D10/E1/E4/F1-F4/G1/G2/H1/H5/C8 (test-automation evidence only - no functional status change) | Evidence: ephemeral scratchpad scripts (Phase 08-10), no longer present on disk | Evidence: persistent, re-runnable `tests/ct3d/` suite (109 tests), re-verified this phase |
| Dead-code item ("`MaskEditor.draw_point_2d/draw_point_3d/interpolate_slices` là dead code... chưa dọn") | Open (`CT3D_REMAINING_WORK.md` item 8) | Closed - removed (10 methods, 146 lines), item 8 removed from `CT3D_REMAINING_WORK.md` |

## 24. Phase Gate

`PHASE_GATE: PASS`

Checklist against the spec's own 10 gate criteria: (1) persistent suite in repo - yes, `tests/ct3d/`; (2) documented one-command run - yes, Section 25 of the final response; (3) core tests PASS - yes, 108-109/109-110; (4) 3 consecutive runs PASS - yes (Section 17); (5) no FAIL skipped/ignored - yes, the 1 skip has a documented reason (`pynrrd` not installed); (6) optional-dependency skips only - yes, only the NRRD test; (7) Undo/Redo memory invariant determined by real code/test - yes (Section 11); (8) Phase 10 doc correction synced - yes (Section 12/19); (9) dead code removed only after proof - yes (Section 13/14); (10) 7 manual-QA items still correctly `NEEDS_MANUAL_QA` - yes (Section 18), not touched.

## 25. Phase 12 Recommendation

Not started this turn per explicit instruction. Candidates for Phase 12 (Dataset & Quantitative Validation, per the spec's own naming): multi-vendor CT dataset testing, Dice/Jaccard/Hausdorff quantitative segmentation validation, usability (SUS) - all explicitly out of Phase 11's scope and requiring external datasets/human subjects this environment does not have. Also worth considering for a future phase (not proposed as Phase 12 itself, just noted): investigating `MaskEditorManager`'s 3 `NOT_PROVEN_DEAD` methods with the same rigor as Section 13, and the `global` style nit in `main.py`, if a future cleanup phase is scheduled.
