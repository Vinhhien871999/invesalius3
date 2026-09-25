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

## E2 — Preview / Confirm Segmentation Workflow

**Additional precondition for this section**: at least 1 mask already exists and is the real current mask (any mask - Preview's 2D overlay only renders once `Slice().current_mask` is set, a real, pre-existing native constraint shared with InVesalius's own Watershed tool - see `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`'s "E2 Preview Architecture" section).

### TEST E2-A — Enable/disable Preview Workflow
Tick **"Enable Preview Workflow"** in the new "Preview Segmentation (E2, enhancement branch)" box.
**Expected**: "Preview Otsu" button becomes enabled; "Preview Region Growing" stays disabled until a seed is picked. Untick it again.
**Expected**: both buttons disable again; any active preview/overlay clears; status returns to "Idle".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-B — Otsu preview visible in all 3 views
With Preview Workflow ON, click **"Preview Otsu"**.
**Expected**: an orange, translucent overlay appears on the Axial, Coronal, AND Sagital 2D views, showing the candidate Otsu segmentation - visually distinct from any real (final) mask's own colour. Preview status shows the threshold and voxel count.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-C — Otsu Cancel
With the Otsu preview showing, click **"Cancel Preview"**.
**Expected**: the orange overlay disappears from all 3 views; status returns to "Idle"; NO new mask appears in the Segmentation Set list or the native Masks tab.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-D — Otsu Accept
Click **"Preview Otsu"** again, then click **"Accept Preview"**.
**Expected**: the overlay disappears; a new real mask (visible in the Segmentation Set list AND the native Masks tab) is created, using the SAME threshold the preview showed; status shows "Idle (accepted '...')"".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-E — Region Growing preview
With Preview Workflow ON, click **"Pick Seed Point (3D)"**, click a point in the 3D view.
**Expected**: status shows "Seed picked..." and does NOT immediately grow a region (unlike classic mode). Click **"Preview Region Growing"**.
**Expected**: after a short compute, an orange overlay appears showing the grown region in all 3 views; status shows voxel count/percentage (and a warning if it exceeds the safety threshold).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-F — Region Growing Cancel
With the region growing preview showing, click **"Cancel Preview"**.
**Expected**: overlay disappears; no new mask created.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-G — Region Growing Accept
Repeat the preview, then click **"Accept Preview"**.
**Expected**: overlay disappears; a new real "Region Growing ..." mask appears in the Segmentation Set list; if the region was oversized, a confirmation dialog appeared before the mask was actually created (same as classic mode's own oversized-region dialog).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-H — Second preview replaces first
With an Otsu preview showing, click **"Preview Otsu"** again (or switch to Region Growing preview).
**Expected**: the first overlay is replaced by the second - never both shown at once, never a stacked/accumulated appearance.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-I — Project close while preview visible
With a preview showing, close the project (File → Close, or open a different project).
**Expected**: no crash; the overlay does not appear in the newly-loaded (or absent) project; preview status resets to "Idle".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-J — Plugin close/reopen with preview active
With a preview showing, close the ROI Viewer window, reopen it.
**Expected**: no crash; no leftover overlay; Preview Workflow checkbox is back to unticked (fresh panel instance).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-K — Classic workflow with Preview mode OFF
With "Enable Preview Workflow" unticked, use Threshold/Otsu-checkbox/"Create Mask from Threshold" and Region Growing (seed-pick) exactly as in the stable release.
**Expected**: identical behavior to `ct3d-rc1`/E1 - masks are created immediately on click/seed-pick, no preview step, no behavior difference at all.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E2-L — E1 Lock/Solo interaction with preview
Lock the current ROI, then try Preview Otsu/Region Growing (should still work - preview never touches the locked mask, it only reads the volume). Enable Solo on some other ROI, then run a preview.
**Expected**: preview overlay still renders normally regardless of Solo state on other ROIs (they are independent real mechanisms - see architecture doc); Accept still creates a normal new (unlocked) mask.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

---

## E3 — Segmentation Cleanup (Current ROI)

**Additional precondition**: a real mask with some real "mess" to clean up (e.g. Threshold on a noisy region so the result has scattered small components, or an enclosed cavity) - ideally created via classic Threshold/Region Growing first.

### TEST E3-A — Keep Largest Component on noisy ROI
Select a ROI with multiple disconnected pieces (e.g. main structure + scattered noise voxels), click **"Keep Largest Component"**.
**Expected**: only the largest connected piece remains visible in 2D/3D (after a manual "Update 3D Surface" refresh); status shows before/after voxel counts and how many components were removed.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-B — Undo Keep Largest Component
Click **"Undo"** (in the existing Undo/Redo box) right after E3-A.
**Expected**: the mask returns to EXACTLY its pre-cleanup state (all the noise pieces are back).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-C — Redo Keep Largest Component
Click **"Redo"** right after E3-B.
**Expected**: the mask returns to EXACTLY the cleaned (largest-component-only) state.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-D — Remove Small Islands
Set **"Min component size (voxels)"** to a value that should remove some but not all noise, click **"Remove Small Islands"**.
**Expected**: only components smaller than the threshold disappear; status shows count/voxels removed.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-E — Remove Small Islands threshold boundary
Create (or identify) a component whose size exactly equals the "Min component size" value, run Remove Small Islands.
**Expected**: that exact-size component is KEPT (documented behavior: `size < min_voxels` removed, `size == min_voxels` kept).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-F — Fill Holes
On a ROI with a visible internal cavity (e.g. after Eraser carved a hole inside a solid region), click **"Fill Holes"**.
**Expected**: the enclosed cavity is filled; background touching the outside of the mask is NOT affected; status shows voxels added.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-G — Smooth Mask, one iteration
Set **"Smooth iterations"** to 1, click **"Smooth Mask"** on a jagged-boundary ROI.
**Expected**: boundary visibly smoother in the 2D views; status shows a small, bounded voxel-count change (not a drastic volume loss).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-H — Lock prevents cleanup
Lock the current ROI (E1), try any of the 4 cleanup buttons.
**Expected**: a warning dialog appears ("...is locked. Unlock it before running cleanup.") and nothing changes.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-I — Unlock permits cleanup
Unlock the same ROI, retry.
**Expected**: cleanup now runs normally.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-J — No-op operation
Run **"Keep Largest Component"** on a ROI that already has only one connected component.
**Expected**: status reads "No changes were necessary."; no Undo checkpoint is added (Undo button state/behavior unaffected by this click).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-K — Update 3D Surface after cleanup
After any real cleanup operation (E3-A/D/F/G), observe the 3D view BEFORE clicking "Update 3D Surface from Selected ROI".
**Expected**: the 3D surface does NOT change automatically; status message explicitly says the surface hasn't been rebuilt. Click "Update 3D Surface from Selected ROI" - the 3D view now reflects the cleaned mask.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-L — Plugin close/reopen
Close the ROI Viewer window, reopen it, verify the cleaned mask persisted (session-independent, since it's a real mask edit) and the Cleanup box behaves normally again.
**Expected**: no crash; cleaned mask state is exactly as left; cleanup buttons work normally on the reopened panel.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E3-M — Classic workflow unchanged
With no cleanup operations run, verify the rest of the classic workflow (Threshold, Otsu, Region Growing, Brush, Eraser, Undo/Redo, Update Surface, E1 Lock/Solo, E2 Preview) all behave exactly as in prior milestones.
**Expected**: identical behavior - E3 only adds new, opt-in buttons, changes nothing else.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

---

## E4 - Fast live 3D preview

### TEST E4-A — Enable live 3D preview shows Current ROI mesh
With a real mask already segmented (Current ROI), check "Enable Live 3D Preview". Wait for the debounce window.
**Expected**: a preview mesh appears in the 3D view tracking the Current ROI's shape; status label shows source "Current ROI".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-B — Preview follows Otsu preview (E2 source priority)
With live 3D preview enabled, run an Otsu preview (E2). Wait for the debounce window.
**Expected**: the preview mesh rebuilds to match the Otsu preview array, not the old Current ROI; status label shows source "Otsu preview".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-C — Preview follows Region Growing preview
With live 3D preview enabled, run a Region Growing preview (E2).
**Expected**: the preview mesh rebuilds to match the Region Growing preview array; status label shows source "Region Growing preview".
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-D — Preview reverts to Current ROI after E2 Cancel
From TEST E4-B or E4-C's state, click E2's Cancel.
**Expected**: the preview mesh rebuilds back to the Current ROI (or hides if there is none); no stale preview-sourced mesh remains.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-E — Preview follows E2 Accept
From TEST E4-B or E4-C's state, click E2's Accept.
**Expected**: the preview mesh rebuilds from the newly-committed Current ROI mask; no crash; no duplicate actor.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-F — Preview auto-refreshes after Brush edit
With live 3D preview enabled and a Current ROI selected, use the native Brush tool to paint on the mask, then release the mouse button.
**Expected**: within the debounce window, the preview mesh rebuilds to reflect the brushed region, with no manual Refresh click needed.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-G — Preview auto-refreshes after Eraser edit
Same as E4-F but using the native Eraser tool.
**Expected**: preview mesh rebuilds automatically to reflect the erased region.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-H — Debounce coalesces rapid edits
With live 3D preview enabled, perform several rapid Brush strokes in quick succession (faster than the debounce window).
**Expected**: no visible flicker/freeze/stutter during the strokes; exactly one rebuild happens shortly after the last stroke, not one per stroke.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-I — Manual Refresh button forces a rebuild
With live 3D preview enabled, click "Refresh 3D Preview" directly.
**Expected**: an immediate rebuild using the current source, independent of the debounce timer.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-J — Preview updates after E3 cleanup
With live 3D preview enabled, run an E3 cleanup operation (e.g. Keep Largest Component) on the Current ROI.
**Expected**: the preview mesh rebuilds to reflect the cleaned mask.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-K — Preview geometry aligns with the real final surface
Build the real final surface (Update 3D Surface) for the same mask the live preview is tracking, and visually compare.
**Expected**: the two meshes occupy the same position/orientation/scale in the 3D scene (no mirroring, no offset), consistent with the automated bounds-matching test.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-L — Camera not disturbed by preview rebuilds
Rotate/zoom/pan the 3D view to a specific framing, then trigger several preview rebuilds (edits, Refresh button).
**Expected**: the camera framing never changes on its own during any rebuild.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-M — Preview mesh is not pickable
With live 3D preview enabled and visible, use the plugin's point picker / Region Growing seed pick / measurement tools by clicking on the preview mesh's surface.
**Expected**: clicks pass through to whatever is behind the preview mesh (or hit nothing) - the preview mesh itself is never selected/picked.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-N — Disabling live 3D preview hides the mesh and stops updates
Uncheck "Enable Live 3D Preview", then perform a Brush edit.
**Expected**: the preview mesh disappears immediately on uncheck, and does not reappear/rebuild from the subsequent edit.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-O — Project close while preview enabled
With live 3D preview enabled and visible, close the project.
**Expected**: no crash; the preview actor is detached/removed; no leftover mesh from the closed project is visible.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-P — Plugin close/reopen, no duplicate actor
With live 3D preview enabled, close the ROI Viewer window and reopen it, then re-enable live 3D preview.
**Expected**: no crash; exactly one preview mesh is ever visible at a time, no duplicate/ghost actor from the previous session.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-Q — Save/Open unaffected by live preview
With live 3D preview enabled, save the project, close it, and reopen it.
**Expected**: the real mask data saved/loaded is identical to a session without live preview enabled; live 3D preview defaults back to OFF on reopen; no extra `surface_dict` entry was created by the preview.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E4-R — Classic workflow unaffected with live preview OFF
With live 3D preview left at its default (OFF), verify the rest of the classic workflow (Threshold, Otsu, Region Growing, Brush, Eraser, Undo/Redo, Update 3D Surface / D9-C7 policy, E1 Lock/Solo, E2 Preview, E3 Cleanup) all behave exactly as in prior milestones.
**Expected**: identical behavior - E4 only adds new, opt-in UI, changes nothing else.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

---

## E5 - Advanced 3D visualization (textured slice planes + clipping/cutaway)

### TEST E5-A — Enable textured planes
With a real project loaded and Sync 2D->3D active, tick "Show CT texture on slice planes" in the Interaction tab's "3D Visualization" box.
**Expected**: the 3 geometric coloured planes (C8) disappear and are replaced by 3 planes showing real CT image content (grey/colour, matching the 2D views' current Window/Level).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-B — Axial texture orientation
With texture mode on, compare the Axial textured plane's real anatomy (e.g. left/right, anterior/posterior landmarks) against the native Axial 2D view for the same slice.
**Expected**: no mirroring, no 90-degree rotation - the textured plane's content matches the 2D view's own orientation.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-C — Coronal texture orientation
Same comparison as E5-B for the Coronal plane.
**Expected**: no mirroring, no rotation, matches the native Coronal 2D view.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-D — Sagittal texture orientation
Same comparison as E5-B for the Sagittal plane.
**Expected**: no mirroring, no rotation, matches the native Sagittal 2D view.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-E — Move crosshair, textures follow
With texture mode on, use the native "Slices' cross intersection" tool to move the crosshair on a 2D view.
**Expected**: all 3 textured planes update to the new slice position and new content, with no stale old-slice content left showing at the new geometric position.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-F — Window/Level texture refresh
With texture mode on, change Window/Level via InVesalius's native control, then move the crosshair (or trigger any other real update).
**Expected**: the textured planes reflect the new Window/Level on their next update - no stale intensity mapping.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-G — Texture toggle OFF restores geometric planes
Untick "Show CT texture on slice planes".
**Expected**: the textured planes disappear and C8's original geometric coloured planes reappear (if "Show slice planes in 3D" is checked), at the correct current crosshair position.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-H — 3D picker works through textured planes
With texture mode on, use "Pick Point in 3D" or the Region Growing seed pick, clicking through/near a textured plane.
**Expected**: the pick behaves exactly as without texture mode - the textured plane never intercepts the click.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-I — Enable Axial clipping
Build a final surface for a real ROI (Update 3D Surface from Selected ROI), then tick "Enable Clipping" with Plane=Axial.
**Expected**: the 3D surface is visibly cut away on one side of the current Axial crosshair position.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-J — Move Axial crosshair changes cut
With Axial clipping enabled, move the crosshair up/down through the volume.
**Expected**: the cutaway plane moves with the crosshair in real time (via the same C8 event path), with no surface rebuild/flicker.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-K — Coronal clipping
Switch Plane to Coronal.
**Expected**: the cutaway plane reorients to a Coronal cut, tracking the Coronal crosshair position.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-L — Sagittal clipping
Switch Plane to Sagittal.
**Expected**: the cutaway plane reorients to a Sagittal cut, tracking the Sagittal crosshair position.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-M — Invert clipping
With any plane active, tick "Invert".
**Expected**: the cutaway flips to show the OPPOSITE half of the surface.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-N — Final polydata unchanged
With clipping enabled and a visible cutaway, disable clipping.
**Expected**: the surface returns to its exact original, uncut appearance (proving the underlying geometry was never modified, only the display).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-O — ROI switch while clipping
With clipping enabled on one ROI's final surface, select a different ROI in the Segmentation Set list.
**Expected**: clipping re-targets the new ROI's own final surface if one exists (or reports "No final surface for selected ROI." if not) - the OLD ROI's surface is no longer clipped.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-P — Rebuild final surface while clipping
With clipping enabled on the current ROI's final surface, click "Update 3D Surface from Selected ROI" again.
**Expected**: after the rebuild completes, clipping is still active and correctly applied to the NEWLY rebuilt surface (no dangling reference to the old, discarded one).
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-Q — E4 preview coexistence
Enable E4's Live 3D Preview alongside E5A texture mode and/or E5B clipping.
**Expected**: no crash; all features render correctly at once; switching the clipping Target to "Live Preview (E4)" clips the preview mesh instead of the final surface.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-R — Camera unchanged
Rotate/zoom/pan to a specific framing, then toggle texture mode and clipping on/off several times, and move the crosshair repeatedly.
**Expected**: the camera framing never changes on its own.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-S — Project close
With texture mode and/or clipping enabled, close the project.
**Expected**: no crash; no leftover textured planes or clipping plane visible; state is safely torn down.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-T — Plugin close/reopen
With texture mode and/or clipping enabled, close the ROI Viewer window and reopen it.
**Expected**: no crash; no duplicate/ghost textured-plane actors; clipping starts fresh (disabled) with no leftover plane on any mapper.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-U — Save/Open unaffected
With texture mode and/or clipping enabled, save the project, close it, and reopen it.
**Expected**: real mask/surface data saved/loaded identically to a session without E5 enabled; both E5 features default back to OFF on reopen.
**Actual Result**: `NOT_RUN` | **PASS/FAIL**: `NOT_RUN`

### TEST E5-V — Classic mode with E5 OFF
With both "Show CT texture on slice planes" and "Enable Clipping" left at their defaults (OFF), verify the rest of the classic workflow (C8 geometric planes, Threshold/Otsu/Region Growing, Brush/Eraser, Undo/Redo, Update 3D Surface, E1/E2/E3/E4) all behave exactly as in prior milestones.
**Expected**: identical behavior - E5 only adds new, opt-in UI, changes nothing else.
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
| E2-A | Enable/disable Preview Workflow | `NOT_RUN` |
| E2-B | Otsu preview visible in all 3 views | `NOT_RUN` |
| E2-C | Otsu Cancel | `NOT_RUN` |
| E2-D | Otsu Accept | `NOT_RUN` |
| E2-E | Region Growing preview | `NOT_RUN` |
| E2-F | Region Growing Cancel | `NOT_RUN` |
| E2-G | Region Growing Accept | `NOT_RUN` |
| E2-H | Second preview replaces first | `NOT_RUN` |
| E2-I | Project close while preview visible | `NOT_RUN` |
| E2-J | Plugin close/reopen with preview active | `NOT_RUN` |
| E2-K | Classic workflow with Preview mode OFF | `NOT_RUN` |
| E2-L | E1 Lock/Solo interaction with preview | `NOT_RUN` |
| E3-A | Keep Largest Component on noisy ROI | `NOT_RUN` |
| E3-B | Undo Keep Largest Component | `NOT_RUN` |
| E3-C | Redo Keep Largest Component | `NOT_RUN` |
| E3-D | Remove Small Islands | `NOT_RUN` |
| E3-E | Remove Small Islands threshold boundary | `NOT_RUN` |
| E3-F | Fill Holes | `NOT_RUN` |
| E3-G | Smooth Mask, one iteration | `NOT_RUN` |
| E3-H | Lock prevents cleanup | `NOT_RUN` |
| E3-I | Unlock permits cleanup | `NOT_RUN` |
| E3-J | No-op operation | `NOT_RUN` |
| E3-K | Update 3D Surface after cleanup | `NOT_RUN` |
| E3-L | Plugin close/reopen | `NOT_RUN` |
| E3-M | Classic workflow unchanged | `NOT_RUN` |
| E4-A | Enable live 3D preview shows Current ROI mesh | `NOT_RUN` |
| E4-B | Preview follows Otsu preview | `NOT_RUN` |
| E4-C | Preview follows Region Growing preview | `NOT_RUN` |
| E4-D | Preview reverts to Current ROI after E2 Cancel | `NOT_RUN` |
| E4-E | Preview follows E2 Accept | `NOT_RUN` |
| E4-F | Preview auto-refreshes after Brush edit | `NOT_RUN` |
| E4-G | Preview auto-refreshes after Eraser edit | `NOT_RUN` |
| E4-H | Debounce coalesces rapid edits | `NOT_RUN` |
| E4-I | Manual Refresh button forces rebuild | `NOT_RUN` |
| E4-J | Preview updates after E3 cleanup | `NOT_RUN` |
| E4-K | Preview geometry aligns with real final surface | `NOT_RUN` |
| E4-L | Camera not disturbed by preview rebuilds | `NOT_RUN` |
| E4-M | Preview mesh is not pickable | `NOT_RUN` |
| E4-N | Disabling preview hides mesh and stops updates | `NOT_RUN` |
| E4-O | Project close while preview enabled | `NOT_RUN` |
| E4-P | Plugin close/reopen, no duplicate actor | `NOT_RUN` |
| E4-Q | Save/Open unaffected by live preview | `NOT_RUN` |
| E4-R | Classic workflow unaffected with preview OFF | `NOT_RUN` |
| E5-A | Enable textured planes | `NOT_RUN` |
| E5-B | Axial texture orientation | `NOT_RUN` |
| E5-C | Coronal texture orientation | `NOT_RUN` |
| E5-D | Sagittal texture orientation | `NOT_RUN` |
| E5-E | Move crosshair, textures follow | `NOT_RUN` |
| E5-F | Window/Level texture refresh | `NOT_RUN` |
| E5-G | Texture toggle OFF restores geometric planes | `NOT_RUN` |
| E5-H | 3D picker works through textured planes | `NOT_RUN` |
| E5-I | Enable Axial clipping | `NOT_RUN` |
| E5-J | Move Axial crosshair changes cut | `NOT_RUN` |
| E5-K | Coronal clipping | `NOT_RUN` |
| E5-L | Sagittal clipping | `NOT_RUN` |
| E5-M | Invert clipping | `NOT_RUN` |
| E5-N | Final polydata unchanged | `NOT_RUN` |
| E5-O | ROI switch while clipping | `NOT_RUN` |
| E5-P | Rebuild final surface while clipping | `NOT_RUN` |
| E5-Q | E4 preview coexistence | `NOT_RUN` |
| E5-R | Camera unchanged | `NOT_RUN` |
| E5-S | Project close | `NOT_RUN` |
| E5-T | Plugin close/reopen | `NOT_RUN` |
| E5-U | Save/Open unaffected | `NOT_RUN` |
| E5-V | Classic mode with E5 OFF | `NOT_RUN` |

**E1_MANUAL_QA_COMPLETE: NOT_RUN** (0/14) — awaiting a real operator session. This does not block E1's automated `PASS` gate (see `CT3D_ADVANCED_SEGMENTATION_PROGRESS.md`), consistent with how the stable release separated automated evidence from manual GUI confirmation throughout Phase 08-14.

**E2_MANUAL_QA_COMPLETE: NOT_RUN** (0/12) — same discipline, same reasoning. Does not block E2's automated `PASS` gate.

**E3_MANUAL_QA_COMPLETE: NOT_RUN** (0/13) — same discipline, same reasoning. Does not block E3's automated `PASS` gate (Current ROI target).

**E4_MANUAL_QA_COMPLETE: NOT_RUN** (0/18) — same discipline, same reasoning. Does not block E4's automated `PASS` gate.

**E5_MANUAL_QA_COMPLETE: NOT_RUN** (0/22) — same discipline, same reasoning. Does not block E5's automated gate. Real operator confirmation of E5-B/C/D (texture orientation) is the authoritative verification for the one claim this milestone's own automated evidence could not additionally prove via live rendering (see `CT3D_ADVANCED_E5_VISUALIZATION_REPORT.md`'s "Texture orientation proof" section).
