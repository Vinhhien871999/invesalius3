# CT3D — Advanced Segmentation Enhancement Track: Manual QA

> Same discipline as `docs/CT3D_MANUAL_QA_CHECKLIST.md`: Claude Code does **not** perform mouse/keyboard interaction and does **not** fabricate PASS results. Every item below is `NOT_RUN` until a real operator performs it on the real GUI and reports the actual result. Screenshot fields (if ever supplied) follow the same rule as the stable-release checklist: *"Evidence visually supplied by operator during manual QA session; image file not stored in repository."* — no invented image paths.

**Branch**: `enhancement/advanced-segmentation`. **Preconditions (common to all items below)**: real CT project imported (e.g. dataset `0051`, see `CT3D_DATASET_REGISTRY.md`), plugin open on the **Segmentation** tab, at least 2-3 masks created via Threshold/Region Growing so the "Segmentation Set" list has multiple real ROIs to exercise.

## E1 — Advanced ROI Manager

### TEST E1-A — Active ROI indicator
Click different rows in the Segmentation Set list.
**Expected**: "Active ROI:" label updates to the selected ROI's name; matches which mask becomes InVesalius's real current mask (e.g. visible in the native Masks tab selection).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-B — Colour indicator
Select ROIs with different colours.
**Expected**: the small swatch next to "Active ROI:" updates to match that ROI's real mask colour (compare against the native Masks tab's colour for the same mask).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-C — Visibility checkbox (unchanged behavior)
Toggle a ROI's checkbox in the list.
**Expected**: same behavior as the stable release - mask shows/hides in 2D and 3D views immediately.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-D — Lock prevents Brush
Select a ROI, click **Lock**, verify `[LOCKED]` prefix appears in the list. Try to enable the Brush Tool while this ROI is the current mask.
**Expected**: a warning dialog appears ("This ROI is locked...") and the brush does NOT enable.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-E — Lock prevents Undo/Redo
With the same locked ROI as current mask, click **Undo** (and **Redo**).
**Expected**: status text reads "ROI is locked - unlock to undo/redo"; mask content does not change.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-F — Lock prevents Delete
With the ROI still locked, select it and click **Delete**.
**Expected**: a warning dialog appears ("...is locked. Unlock it before deleting.") and no delete confirmation dialog appears; the mask is NOT removed.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-G — Unlock restores editing
Click **Unlock** on the same ROI (verify `[LOCKED]` prefix disappears). Retry Brush/Undo/Redo/Delete-cancel-before-confirming.
**Expected**: brush enables normally; undo/redo work normally; delete now proceeds to the normal confirmation dialog.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-H — Solo
With 3+ ROIs visible, select one and click **Solo** (toggle ON).
**Expected**: `[SOLO]` prefix appears on that row; only that ROI's mask remains visible in 2D/3D; the other ROIs' checkboxes become unchecked in the list.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-I — Exit Solo restores prior visibility
Before soloing, hide one ROI manually, then Solo a different ROI, then click **Solo** again (toggle OFF).
**Expected**: the previously-hidden ROI comes back hidden (not shown), and all others return to exactly their pre-solo visibility - not just "everything shown."
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-J — Show All / Hide All
Click **Hide All**, then **Show All**.
**Expected**: all ROIs hide, then all show; if Solo was active, it turns off (Solo toggle button un-presses).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-K — Manual visibility click cancels Solo
Engage Solo on a ROI, then manually click a DIFFERENT ROI's visibility checkbox.
**Expected**: Solo toggle button un-presses, `[SOLO]` prefix disappears from the list; no crash, no stuck state.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-L — Project close/reopen resets lock (documented, not a bug)
Lock a ROI, save the project, close it, reopen the same project file.
**Expected**: the ROI reappears UNLOCKED (this is documented, deliberate behavior - see `CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`'s persistence decision - not a defect to report).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-M — Reopen plugin, no duplicate/leak
Close the ROI Viewer window, reopen it from Plugins menu, repeat TEST E1-A through E1-C.
**Expected**: no duplicate list entries, no crash, Segmentation Set list correctly reflects current project masks.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E1-N — Classic workflow unaffected
With no ROI locked and Solo off, run through the classic workflow exactly as in the stable release: Threshold → Create Mask, Brush/Eraser, Undo/Redo, Update 3D Surface, Rename, Delete (unlocked ROI).
**Expected**: identical behavior to the frozen `ct3d-rc1` release - no new prompts, no new required steps.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

---

## Summary

| # | Test | PASS/FAIL |
|---|---|---|
| E1-A | Active ROI indicator | `NOT_RUN` |
| E1-B | Colour indicator | `NOT_RUN` |
| E1-C | Visibility checkbox | `NOT_RUN` |
| E1-D | Lock prevents Brush | `NOT_RUN` |
| E1-E | Lock prevents Undo/Redo | `NOT_RUN` |
| E1-F | Lock prevents Delete | `NOT_RUN` |
| E1-G | Unlock restores editing | `NOT_RUN` |
| E1-H | Solo | `NOT_RUN` |
| E1-I | Exit Solo restores prior visibility | `NOT_RUN` |
| E1-J | Show All / Hide All | `NOT_RUN` |
| E1-K | Manual visibility click cancels Solo | `NOT_RUN` |
| E1-L | Project close/reopen resets lock | `NOT_RUN` |
| E1-M | Reopen plugin, no duplicate/leak | `NOT_RUN` |
| E1-N | Classic workflow unaffected | `NOT_RUN` |

**E1_MANUAL_QA_COMPLETE: NOT_RUN** (0/14) — awaiting a real operator session. This does not block E1's automated `PASS` gate (see `CT3D_ADVANCED_SEGMENTATION_PROGRESS.md`), consistent with how the stable release separated automated evidence from manual GUI confirmation throughout Phase 08-14.
