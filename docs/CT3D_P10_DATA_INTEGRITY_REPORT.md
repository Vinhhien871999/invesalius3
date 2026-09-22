# CT3D Phase 10 — Data Integrity, Save/Open Forensics & Undo/Redo Memory

> **⚠ Phase 11 correction/clarification (14/09/2026, added without editing the
> original text below)**: Section 12/13's worst-case Undo/Redo memory
> numbers (`~1.07 GB` old default, `~547 MB` new default) were based on
> the assumption that `undo_stack` and `redo_stack` could independently
> reach `max_history` **simultaneously** (a combined total of
> `2 × max_history` snapshots). Phase 11 built a real, code-verified
> invariant test (`tests/ct3d/test_undo_redo.py` -
> `test_undo_redo_memory_invariant_*`, 6 deterministic sequences + 300
> randomized public-API-only sequences, fixed seed) and proved this
> assumption is **wrong**: `save_state()` always clears `redo_stack` in
> the same call it adds to `undo_stack`, so the real, reachable maximum
> of `len(undo_stack) + len(redo_stack)` is `max_history`, not
> `2 × max_history`. **The correct worst-case number at the current
> default (`max_history=10`) is `10 × 27.36 MB ≈ 273.6 MB`, not
> `~547 MB`** - Phase 10 overestimated by exactly 2×. The **code decision
> itself (lowering `max_history` from 20 to 10) is unchanged** - it
> remains a valid, conservative, now-correctly-justified choice; only the
> number attached to it in this report, `CT3D_MASTER_PROGRESS.md`,
> `CT3D_FEATURE_AUDIT.md`, and `HUONG_DAN_SU_DUNG_ROI_VIEWER.md` was
> wrong and has been corrected in those other 3 files (this report's
> original Sections 12/13/16 text below is left as-written, as the
> historical record of Phase 10's own reasoning at the time - see
> `docs/CT3D_P11_TEST_AUTOMATION_REPORT.md` Sections 11-12 for the full
> investigation). Save/Open (Sections 4-10, CASE A) is **unaffected** by
> this correction and remains fully valid.

## 1. Metadata

| Field | Value |
|---|---|
| Phase | CT3D_P10_DATA_INTEGRITY |
| Repository | Vinhhien871999/invesalius3 |
| Branch | `thesis-ct-roi-tools` |
| Commit before Phase 10 | `b5d304fb` (last commit of Phase 09) |
| Commit after Phase 10 (code) | `0e51bcf9` |
| Date | 2026-09-14 |
| Scope | (1) Save/Open voxel-data-integrity forensics for the P2 item "checksum voxel mask lệch sau Save/Open" in `CT3D_REMAINING_WORK.md` item 2a; (2) Undo/Redo memory audit + benchmark + (if justified) minimal optimization. Explicitly **not** Phase 08 (D9/C7) or Phase 09 (Sync 2D→3D, F3) — those are closed and untouched. |
| Test machine RAM at time of testing | `RAM_TOTAL≈16.4 GB`, `RAM_FREE` observed as low as **~540–880 MB** during these very test runs (see raw runtime evidence, Section 8) — i.e. the memory-pressure environment that motivated Section II (Undo/Redo memory) is not hypothetical on this machine. |

## 2. Pre-flight (Section I of the spec)

- Branch: `thesis-ct-roi-tools` ✓
- HEAD before starting: `b5d304fb` ✓ (unchanged since end of Phase 09)
- `git status` before starting: clean except pre-existing, **unrelated** uncommitted changes (3 root-level `.md` files — `Ke_hoach_de_tai_InVesalius_CT3D.md`, `Lộ trình phát triển.md`, `Đề cương NCKH.md` — appear as deleted at root and untracked under `docs/`, i.e. already moved before this phase began). This predates Phase 10, is not part of its scope, and was **not touched or committed** by this phase — only the specific files listed in Section 21/24 below were staged and committed.
- Commit chain verified linear: `40c2c38b` → `7fed0156` → `d3683079` → `d366a635` → `b5d304fb` (all confirmed via `git log --oneline -5` and, for the two Phase-08 commits, `git merge-base --is-ancestor` — see Section 4).

## 3. Không làm lại (explicitly NOT touched this phase)

- Phase 08 (D9/C7 surface-update root cause + fix): zero code changes. `git diff --stat` for this phase touches exactly one file, `plugins/roi_viewer/core/mask_editor.py`.
- Phase 09 (Sync 2D→3D, F3 annotation position, `project_loaded` fix): zero code changes.
- No new UI features added.
- The 7 Phase-09 manual-QA items (P08.5, B4, C3, D4, D5, E2, E3) are **left exactly as `NEEDS_MANUAL_QA`** — not touched, not upgraded (see Section 20).

## 4. Git-consistency audit (the `40c2c38b` vs `7fed0156` question)

Ran directly (not from memory):

```
git show 40c2c38b --stat   -> 1 file: plugins/roi_viewer/gui/segmentation_panel.py
git show 7fed0156 --stat   -> 5 files, all docs (CT3D_P08_ROI3D_CLOSURE_REPORT.md, CT3D_MASTER_PROGRESS.md,
                               CT3D_FEATURE_AUDIT.md, CT3D_REMAINING_WORK.md, CT3D_CHANGELOG.md)
git merge-base --is-ancestor 40c2c38b 7fed0156   -> exit 0 (YES, 40c2c38b is an ancestor of 7fed0156)
git merge-base --is-ancestor 7fed0156 HEAD       -> exit 0 (YES, 7fed0156 is an ancestor of HEAD)
```

**Conclusion**: these are two different, real, correctly-ordered commits, not an inconsistency.
`40c2c38b` = the Phase 08 **code** fix (correctly cited by `CT3D_MASTER_PROGRESS.md` and
`CT3D_P08_ROI3D_CLOSURE_REPORT.md` as "the Phase 08 fix"). `7fed0156` = the Phase 08 **docs**
commit that landed immediately after it (correctly cited by `CT3D_P09_INTERACTION_QA_REPORT.md`
as "repo state right before Phase 09 began" — which is literally true, since it is the last
Phase-08-related commit before Phase 09's own work started). **No git history rewrite performed
or needed.**

## 5. Save/Open call-chain trace (read from source, Section V of the spec — "không suy đoán")

Traced end-to-end, both directions:

**Save**: `Controller.ShowDialogSaveProject()` / `SaveProject()` → `Project.SavePlistProject(dir_, filename, compress)`
(`invesalius/project.py:219`) → for each mask in `self.mask_dict`: `Mask.SavePlist(dir_temp, filelist, save_temp_files)`
(`invesalius/data/mask.py`) registers `filelist[mask.temp_file] = "<n>_mask.dat"` (a **path registration**, not a byte
copy) → `Compress(dir_temp, path, filelist, compress)` (`invesalius/project.py:652`) does the actual byte I/O: for
every `(source_path, archive_name)` pair in `filelist`, `tarfile.add(source_path, arcname=...)` — a raw, lossless
byte copy into a `tarfile` (`"w"` or `"w:gz"`). No transform, no dtype/endianness/transpose step anywhere in this path.

**Open**: `Controller.OpenProject(filepath)` → `Project.OpenPlistProject(path, progress_callback)`
(`invesalius/project.py:345`) → `Extract(filename, tempdir)` (`invesalius/project.py:708`) — `tarfile.extract()`,
again a raw, lossless byte copy back to disk — → `load_from_folder(dirpath, ...)` (`invesalius/project.py:378`):
for each mask entry, `m = Mask(); m.OpenPList(filepath)`, which (per `invesalius/data/mask.py`, re-read fresh this
phase) does `self.matrix = np.memmap(filename, shape=shape, dtype=dtype, mode="r+")` **directly on the extracted
file** — again no transform. `Controller.LoadProject()` (`invesalius/control.py:853`, read fresh this phase) then
does `Publisher.sendMessage("Load slice to viewer", mask_dict=proj.mask_dict)` and, per mask,
`Publisher.sendMessage("Add mask", mask=m)` — both traced to their real subscribers
(`invesalius/data/viewer_slice.py.Viewer.LoadImagedata` → `self.SetInput(mask_dict)`, and
`invesalius/gui/data_notebook.py`/`task_slice.py`/`task_navigator.py`'s `AddMask` handlers) and confirmed to be
**pure GUI/display wiring** (populate widget lists, set up renderers) — none of them read or rewrite `mask.matrix`.

**One real, source-confirmed subtlety** (not a data-corruption bug, but relevant to Section 9's forensics):
`load_from_folder()` reassigns `m.index = len(self.mask_dict)` in **insertion order**, where insertion order follows
`sorted(masks, key=lambda x: int(x))` over the **original** string keys saved in `main.plist`. This means a mask's
in-memory `index` after Open is **not guaranteed to equal** its `index` before Save whenever there is a gap in the
original indices (e.g. a mask was deleted before saving). This is by design (indices are meant to be a dense,
re-derived ordering, not a stable identity) — see Section 9 (RT-E) for why this matters to interpreting the
previously-reported checksum discrepancy.

**Conclusion of the source trace**: there is no code path, anywhere in the real Save→Close→Open pipeline
(`SavePlist`/`Compress`/`Extract`/`OpenPList`/`_open_mask`/`LoadProject`'s display-wiring messages), that transforms,
re-encodes, or otherwise mutates mask voxel bytes. The theoretical prediction, established purely from source
before any test was run, is: **a Save→Close→Open round trip should be byte-identical.**

## 6. Full-matrix vs logical-payload boundary (Section VI)

Re-confirmed from source (not assumed from prior reports): `Mask.create_mask()` allocates
`self.matrix` with shape `(shape[0]+1, shape[1]+1, shape[2]+1)` — one voxel of padding per axis.
The real image/segmentation data occupies `matrix[1:, 1:, 1:]`. The per-axial-slice lazy-threshold
sentinel used by `Slice.do_threshold_to_all_slices()` (and, since Phase 08, explicitly set by the
Region-Growing path) lives at `matrix[n, 0, 0]` for slice `n` — i.e. inside the padding column,
already excluded by `matrix[1:, 1:, 1:]`. This phase's test script (`p10_saveopen_forensics.py`)
computes and compares **both** a full-matrix hash (`matrix`, includes padding/sentinels) and a
logical-payload hash (`matrix[1:, 1:, 1:]`) for every scenario, so a difference confined to the
padding/sentinel region (which would be functionally harmless) would be distinguishable from a
difference inside real voxel data (which would not be).

## 7. Test design (Section VII)

Real DICOM import (sample series `0051`, for a fully valid `Project()`/`Slice()`/widget-tree state —
same bootstrap pattern as Phase 08/09), then the same small-synthetic-image swap used in Phase 08/09
((30,128,128) memmap image, background −1000, a distinct foreground block at 500) so the round trip
itself stays fast and low-RAM while exercising 100% real production save/open code.

Five real scenarios, in one continuous run against the same real `Project()`:

| ID | Description | Purpose |
|---|---|---|
| RT-A | Hand-written binary mask, precise known geometry, never thresholded (`was_edited=False`) | Baseline: simplest possible real mask object |
| RT-B | Real threshold-derived mask (`do_threshold_to_all_slices()` actually run against the synthetic image, thresh 400–600) | Realistic "created via Threshold tool" mask |
| RT-C | RT-B's threshold result **plus** a real hand-edit in a disjoint region, `was_edited=True` flushed | Realistic "edited via brush/checkpoint" mask — the Phase-08-relevant `was_edited` case |
| RT-D | Same 3 masks, second full Save→Close→Open cycle with `compress=True` (gzip tar) | Rules out gzip (de)compression as a source of the previously-reported discrepancy |
| RT-E | Delete the middle mask (creates a non-contiguous index gap: keys `{0, 2}` → 2 masks), Save→Close→Open, compare **by name** (robust) vs demonstrate what a **naive by-original-index** comparison would have found | Tests the "index remapping looks like a checksum bug" hypothesis (see Section 9) |

RT-D was skipped as noted in the spec's optional item (Region-Growing-derived mask) is **not** included
separately — RT-C already exercises a `was_edited=True` hand-edited mask, and Region Growing's own
mask-writing code path was already closed and proven in Phase 08 (D9/C7); re-deriving it here would
duplicate that work rather than test Save/Open. (Letter "RT-D" is used for the gzip scenario in this
report/test script, not for a Region-Growing scenario — naming is internal to this phase's test script.)

## 8. Runtime evidence (real execution, `D:\PyTools\invx-venv\Scripts\python.exe`, `XDG_CONFIG_HOME`-isolated)

Full captured snapshot data (shape/dtype/min/max/unique values/nonzero counts/hashes/threshold_range/was_edited)
for every mask, before and after, for every scenario:

```
RT-A BEFORE: shape=(31,129,129) dtype=uint8 min=0 max=255 unique=[0,1,255]
             nonzero_full=630 nonzero_payload=600 threshold_range=(1,1) was_edited=False
             full_hash=3adb3b8e03a66e3b... payload_hash=2129da65b2a648ba...
RT-A AFTER:  IDENTICAL (full_hash and payload_hash byte-for-byte equal)

RT-B BEFORE: shape=(31,129,129) dtype=uint8 min=0 max=255 unique=[0,1,255]
             nonzero_full=32288 nonzero_payload=32256 threshold_range=(400,600) was_edited=False
             full_hash=9ea2679306ec4b60... payload_hash=40eb653615d7fd44...
RT-B AFTER:  IDENTICAL

RT-C BEFORE: shape=(31,129,129) dtype=uint8 min=0 max=255 unique=[0,1,255]
             nonzero_full=32688 nonzero_payload=32656 threshold_range=(400,600) was_edited=True
             full_hash=90097bb6dd9ad9ba... payload_hash=fdcc7132085229d1...
RT-C AFTER:  IDENTICAL

RT-D (gzip, all 3 masks): all 3 full_hash/payload_hash IDENTICAL to their pre-gzip-cycle values.

RT-E (index gap): mask_dict keys before delete = {0:"RT-A synthetic", 1:"RT-B threshold" (deleted),
  2:"RT-C edited"}. After delete: {0, 2} (a genuine gap). After Save->Close->Open: reloaded keys = {0, 1}
  (re-densified, as predicted in Section 5). Matched by NAME (robust): both remaining masks
  full-matrix-hash IDENTICAL. "RT-A synthetic": original key 0 -> reloaded key 0 (unchanged).
  "RT-C edited": original key 2 -> reloaded key 1 (REMAPPED). A naive lookup of the reloaded
  dict using the STALE original key 2 finds nothing at that key (the dict only has keys {0,1}) -
  concretely demonstrating that an index-keyed (rather than name/identity-keyed) before/after
  comparison can silently compare the wrong pair of masks, or find "no mask", after any Save/Open
  cycle that follows a mask deletion - see Section 9 for why this is the most likely explanation
  for the previously-reported "checksum mismatch".
```

**Result: 30/30 checks PASS** (script: `p10_saveopen_forensics.py`, run 3 times across iterative
fixes to the test script itself — final run 30/30, zero failures, zero exceptions).

## 9. Interpreting the earlier "checksum mismatch" report (`CT3D_REMAINING_WORK.md` item 2a)

Round 2/3 reported, via now-deleted scratchpad scripts `test_project_roundtrip.py` /
`test_guide_saveopen.py`: "mọi thuộc tính khác khớp 100%, chỉ riêng checksum SHA-256 của voxel data
không khớp" (every other attribute matches; only the voxel-data SHA-256 checksum doesn't), and had
already ruled out a missing `flush()` before save.

This phase's source trace (Section 5) proves no transformation code exists anywhere in the real
Save/Open pipeline that could alter voxel bytes. This phase's runtime tests (Section 8) reproduce
byte-identical round trips across every realistic mask scenario this project has exercised
(hand-written, real-threshold, hand-edited-with-`was_edited`, gzip-compressed, and even under an
index-gap condition) — **30/30, zero discrepancies**.

The exact original test scripts no longer exist (scratchpad is ephemeral by this project's own
established convention — see prior phases' methodology notes) so an exact byte-for-byte
reproduction of their internal comparison logic is not possible. However, RT-E (Section 8)
demonstrates a concrete, real mechanism — index reassignment on Open whenever the saved index set
has a gap — that would produce exactly the reported symptom ("every other attribute matches, only
the voxel checksum looks wrong") if the original test compared masks by their pre-save `index`
rather than by name/object identity: comparing `before[2]` against whatever object happens to sit
at `after[2]` (or against nothing) after a deletion-caused remap would either compare two
genuinely different masks (a real checksum "mismatch" that is not a data-corruption bug) or fail
to find the mask at all.

**Classification: CASE A — no real data-integrity bug found.** The Save/Open pipeline is
byte-identical for actual mask voxel data in every tested condition. The most likely explanation
for the earlier report is a test-methodology artifact (index-based rather than identity-based
mask matching across a round trip that legitimately reassigns indices), not a defect in
`invesalius/data/mask.py`, `invesalius/project.py`, or the plugin. **No code fix applied** (per
the spec's own CASE A/B rule: no fix needed). `CT3D_REMAINING_WORK.md` item 2a is removed (see
Section 24), not left stale.

## 10. Section XI — geometry impact assessment

Not applicable: Section 9 found no voxel data difference in the CASE A round trip, so there is no
resulting surface-geometry difference to assess. (D9/C7's own surface-rebuild-after-edit path is
unrelated and untouched this phase — see Section 19 regression.)

## 11. Undo/Redo architecture (read from source, Section XII)

`plugins/roi_viewer/core/mask_editor.py`'s `UndoRedoManager` is real and wired to real UI:
`segmentation_panel.py._on_checkpoint()` (a "Checkpoint" button, explicit user action — not
triggered automatically per brush stroke) does `editor.mask = mask.matrix; editor.save_state()`;
`_on_undo()`/`_on_redo()` call `editor.undo_manager.undo(mask.matrix)` /
`.redo(mask.matrix)` and write the result straight back with `mask.matrix[:] = previous`. Confirmed
via grep across the whole plugin: `UndoRedoManager` has exactly one construction site
(`MaskEditor.__init__`) and `undo_manager` is referenced only from `segmentation_panel.py`'s three
checkpoint/undo/redo handlers — this is real, live, user-facing functionality, not dead code.
(`MaskEditor`'s own `draw_point_2d`/`draw_point_3d`/`interpolate_slices` drawing methods are a
separate matter — real brush editing goes through InVesalius's native `SLICE_STATE_EDITOR` remote
control, not these methods; that is a dead-code observation out of Phase 10's scope, not touched
here.)

`save_state(mask)` does `self.undo_stack.append(copy.deepcopy(mask))`, where in real usage `mask`
is `mask.matrix` — a `numpy.memmap`. `copy.deepcopy()` on a memmap materializes a genuine full
in-RAM `ndarray` (not another memmap), so every checkpoint fully reads the entire padded mask
matrix into RAM. Both `undo_stack` and `redo_stack` are `deque(maxlen=max_history)`, `max_history`
previously defaulted to **20** for each stack independently (so up to 40 full snapshots
simultaneously resident in the worst case: undo_stack full + redo_stack full).

## 12. Undo/Redo memory benchmark (Section XIII, real measurements)

Script: `p10b_undoredo_benchmark.py`, using the **real** `UndoRedoManager` class (not a
reimplementation), real `np.memmap`-backed masks (matching production, where `mask.matrix` is
always a memmap), real `psutil.Process().memory_info().rss` before/after N real `save_state()`
calls.

| Dataset | Shape (padded) | Voxels | Theoretical MB/checkpoint (uint8) | Measured MB/checkpoint | N pushed → RSS delta |
|---|---|---|---|---|---|
| SMALL (matches P08/09/10A synthetic tests) | (31,129,129) | 515,871 | 0.49 MB | 0.48–0.49 MB | 1→0.48MB, 5→1.97MB, 10→4.92MB, 20→9.85MB |
| REAL-CT-SIZE (matches sample series 0051 used throughout this project) | (109,513,513) | 28,685,421 | 27.36 MB | 27.36 MB (exact) | 1→27.36MB, 5→136.80MB, 10→273.59MB |

Measured values track the theoretical `voxels × 1 byte` prediction exactly (uint8, no per-checkpoint
overhead observed beyond the raw array). **Worst-case projection (both stacks simultaneously full
at the OLD default, maxlen=20)**:

- SMALL: `0.49 MB × 40 ≈ 19.7 MB` — negligible.
- **REAL-CT-SIZE: `27.36 MB × 40 ≈ 1,094 MB (≈1.07 GB)`** — significant, and not hypothetical: this
  very test session repeatedly observed `RAM_FREE` as low as **540–880 MB** on this machine while
  running these tests (see Section 1). A ~1 GB undo/redo history on top of that is a real,
  demonstrable risk of contributing to an OOM condition during a genuine editing session on a
  full-size CT series, not a theoretical concern.

Did not benchmark beyond real-single-series-CT scale (per the spec's own `BLOCKED_BY_MEMORY`
allowance — a larger multi-series or higher-resolution volume was not attempted given the already
low free RAM observed). The linear, exactly-`bytes-per-voxel` relationship measured at both tested
scales makes further empirical points unnecessary to justify the decision in Section 13 — the
relationship is `O(voxels)` with a measured constant of exactly 1 byte/voxel (matches `uint8`
exactly, no hidden overhead), so it extrapolates linearly and reliably to any larger real dataset.

## 13. Optimization decision (Section XIV–XVIII)

**Decision: lower `UndoRedoManager`'s default `max_history` from 20 to 10** (one-line change,
`plugins/roi_viewer/core/mask_editor.py`).

**Options considered**:
- *Bit-pack checkpoints (store `np.packbits` of a `>0` boolean mask, 8× smaller)* — **rejected**:
  real mask matrices are not guaranteed strictly binary. The padding column carries a real
  semantic sentinel value (`matrix[n,0,0] == 1`, distinct from the foreground value `255`, used by
  `Slice`'s lazy per-slice threshold logic and, since Phase 08, by Region Growing's
  `was_edited`-adjacent bookkeeping). Packing to 1 bit/voxel and unpacking back to `0`/`255` would
  either lose or corrupt that sentinel distinction on every undo/redo round trip — trading a
  performance win for a new, real data-integrity regression, which directly contradicts this
  phase's own purpose. Not implemented.
- *Delta/diff-based history instead of full snapshots* — **rejected as out of scope**: a materially
  larger, riskier refactor of the undo/redo storage model; not a "minimal fix," and not clearly
  justified when a much smaller, zero-risk change (below) already halves the worst case.
- *Keep `max_history=20` as-is, only document the limit* — considered, but the measured worst case
  (~1.07 GB) combined with this machine's directly observed low free RAM made "document only"
  insufficiently responsive to real, current evidence.
- ***Lower `max_history` to 10* — chosen.** Zero change to snapshot representation or undo/redo
  semantics (still exact full-fidelity snapshots, still FIFO eviction via the same
  `deque(maxlen=...)` mechanism already in place); halves the worst case to **~547 MB**; a single
  parameter change with no new correctness surface. 10 undo steps is still a reasonable real-world
  editing depth for a "Checkpoint" button workflow (an explicit, deliberate user action, not
  per-stroke auto-save).

## 14. Undo/Redo functional + memory verification (UR-T1–UR-T9)

Script: `p10c_undoredo_functional_tests.py`, using the real (post-fix) `UndoRedoManager` class.

| ID | Check | Result |
|---|---|---|
| UR-T1 | Default `max_history == 10` | PASS |
| UR-T2 | `save_state()` stores an independent deep copy (mutating the source afterward doesn't affect the stored checkpoint) | PASS |
| UR-T3/T3b/T3c | `undo()` returns the checkpoint, pushes the pre-undo state onto `redo_stack`, empties `undo_stack` when it was the only entry | PASS (3/3) |
| UR-T4/T4b/T4c | `redo()` returns the pre-undo state, pushes it back onto `undo_stack`, empties `redo_stack` | PASS (3/3) |
| UR-T5 | New `save_state()` after an `undo()` clears `redo_stack` (no "redo branching", standard semantics) | PASS |
| UR-T6a/b/c | `can_undo()`/`can_redo()` correctness (empty vs non-empty) | PASS (3/3) |
| UR-T7a/b/c | Eviction at the new `maxlen=10`: 15 pushes → exactly 10 retained, oldest 5 evicted (FIFO), newest entry correct | PASS (3/3) |
| UR-T8/T8b | `clear()` empties both stacks | PASS (2/2) |
| UR-T9/T9b | Real-CT-size (109×513×513) steady-state RSS at the new default (10 checkpoints) measured **273.59 MB**, well under the old worst case (1,094 MB); `undo_stack` length capped at 10 (not 20) | PASS (2/2) |

**20/20 PASS.**

## 15. Mandatory regression (Section XIX)

Phase 10 changed exactly one line in one file (`mask_editor.py`'s `max_history` default). The
regression surface is therefore narrow by construction; each item below states what was actually
re-verified this phase vs. reasoned from an unchanged code path:

| ID | Feature | This-phase status |
|---|---|---|
| D1 | Threshold segmentation | Re-exercised for real in RT-B (Section 7/8): `"Create new mask"` + `do_threshold_to_all_slices()` produced a real 32,256-voxel mask, correctly round-tripped. PASS (no code touched). |
| D7 | Undo/Redo | Directly changed this phase; full functional+memory re-verification, 20/20 PASS (Section 14). |
| D8 | ROI List (multi-mask management) | Not touched this phase (`core/roi_manager.py` untouched); RT-A/B/C/E (Section 7/8) exercised real multi-mask `mask_dict` management (create/select/delete-with-gap) incidentally as part of the Save/Open tests, all correct. No regression. |
| D9/C7 | Mask edit → surface update | `segmentation_panel.py` and `surface_process.py` untouched this phase (confirmed via `git diff --stat`, see Section 3) — Phase 08's fix and its 36/36 evidence stand unmodified. No regression possible from this phase's single-line change in an unrelated file. |
| D10 (core logic) | Region Growing | `core/segmentation.py` untouched this phase. Not re-run (RAM-costly, per spec's own allowance to skip when unrelated to this phase's change) — Phase 08/prior-round evidence stands. |
| E4 | Volume measurement | `core/measurement.py` untouched this phase. Not re-run — Round 3 evidence stands. |
| F4 | Annotation save-with-project | `core/annotation.py` untouched this phase. Not re-run — Round 2 evidence stands. |
| G1/G2 | Save/Open project, mask/surface serialization | Directly re-verified this phase, more thoroughly than any prior round: 30/30 PASS across 5 scenarios (RT-A/B/C/D/E), including the gzip and index-gap conditions no prior round tested (Section 7/8). |
| G3 | ROI List rebuild after load | `core/roi_manager.py` untouched this phase; RT-E's Open-side mask_dict rebuild (Section 8) exercises the same underlying `Project().mask_dict` reload path G3 depends on — count and identity (by name) correct. No regression. |
| C8 | Sync 2D→3D | `roi_panel.py`/`marker_3d.py`/`main.py` untouched this phase (Phase 09 code, confirmed via `git diff --stat`). No regression possible. |
| F3 | Annotation position | `annotation_panel.py`/`roi_panel.py.get_current_reference_position` untouched this phase. No regression possible. |

No regressions found or expected, consistent with the change's narrow, single-file, single-line
footprint.

## 16. Before/After status matrix

| ID | Before Phase 10 | After Phase 10 |
|---|---|---|
| G1 (Save/Open) | WORKING, with 1 unresolved narrow finding ("checksum voxel mask lệch") | **WORKING**, finding investigated and resolved: CASE A, no real bug, likely test-methodology artifact (Section 9) |
| D7 (Undo/Redo) | WORKING, unbounded-by-measurement memory footprint | **WORKING**, memory footprint measured and reduced (max_history 20→10, worst case ~1.07GB → ~547MB) |
| `CT3D_REMAINING_WORK.md` item 2a | Open (P2) | **Closed and removed** (Section 24) |

## 17. Bugs found and fixed this phase

None found in Save/Open (CASE A — no bug). One real, quantified memory-efficiency issue found and
fixed in Undo/Redo (Section 13): unbounded-in-practice worst-case memory footprint (~1.07 GB at
real CT scale) reduced to ~547 MB via a minimal, zero-correctness-risk default change.

## 18. Remaining issues / out of scope

- The exact original `test_project_roundtrip.py`/`test_guide_saveopen.py` scripts that reported
  the original checksum discrepancy no longer exist (ephemeral scratchpad), so their precise
  comparison logic could not be directly inspected — Section 9's explanation is the most plausible
  evidence-backed account, not a certainty. If the discrepancy is ever observed again through the
  real UI (not a test script), it should be re-investigated with the actual reproduction steps.
- `MaskEditor`'s own drawing methods (`draw_point_2d`/`draw_point_3d`/`interpolate_slices`) remain
  unused dead code (observed, not touched — out of this phase's scope; candidate for a future
  dead-code cleanup phase).
- The 7 Phase-09 manual-QA items remain `NEEDS_MANUAL_QA` (Section 3/20), untouched.

## 19. Test scripts (ephemeral, scratchpad — per this project's established convention)

- `p10_saveopen_forensics.py` — RT-A/B/C/D/E, 30/30 PASS.
- `p10b_undoredo_benchmark.py` — real-memory benchmark, SMALL + REAL-CT-SIZE.
- `p10c_undoredo_functional_tests.py` — UR-T1–UR-T9, 20/20 PASS.

## 20. Manual-QA items (unchanged, not touched this phase)

P08.5, B4, C3, D4, D5, E2, E3 — all remain `NEEDS_MANUAL_QA` exactly as Phase 09 left them. Not
re-classified, not auto-upgraded.

## 21. Files changed this phase

| File | Change |
|---|---|
| `plugins/roi_viewer/core/mask_editor.py` | `UndoRedoManager.__init__`'s `max_history` default 20 → 10, with an inline comment explaining the measured rationale |
| `docs/CT3D_P10_DATA_INTEGRITY_REPORT.md` | New (this file) |
| `docs/CT3D_MASTER_PROGRESS.md` | Phase 10 row added, baseline updated |
| `docs/CT3D_FEATURE_AUDIT.md` | G1 row updated (checksum finding resolved) |
| `docs/CT3D_REMAINING_WORK.md` | Item 2a removed; summary table updated |
| `docs/CT3D_CHANGELOG.md` | Phase 10 entry appended (Goal/Added/Changed/Fixed/Tests/Performance/Documentation/Known-Issues/Phase-Gate template) |
| `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` | Stale `(0,0,0)` fallback reference in "Giới hạn đã biết" fixed; header updated to reflect Phase 10 |

## 22. Phase gate

`PHASE_GATE: PASS`

## 23. Phase 11 recommendation

Not started this turn per explicit instruction. Candidate next steps (for the user to prioritize,
not started): (a) the 7 accumulated manual-QA items (single ~30–45 minute real-mouse session per
`CT3D_P09_INTERACTION_QA_REPORT.md` §9); (b) the `MaskEditor` dead-code cleanup noted in Section
18; (c) multi-vendor CT dataset testing (item 3 in `CT3D_REMAINING_WORK.md`, needs external data).
