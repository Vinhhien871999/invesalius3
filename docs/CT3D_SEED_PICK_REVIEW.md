# CT3D / ROI Viewer — "Chọn điểm hạt giống (3D)" review (05/11/2026)

Trigger: operator screenshots (0543, two sessions) — after pressing "Chọn điểm hạt giống (3D)" (and "Chọn điểm trong 3D" on tab Hiển thị) the status stayed "Nhấp chọn điểm hạt giống trong khung 3D…" / "X: -, Y: -, Z: -"; nothing visible happened.

## How it works

1. The button arms the shared 3D picker (`core/picker_3d.PointPicker3D`, a `vtkCellPicker` observer on InVesalius's real 3D interactor, `LeftButtonPressEvent`).
2. A left click in the Volume view picks the **first visible, pickable geometry under the cursor** — a 3D surface (e.g. made with "Cập nhật bề mặt 3D"), not the CT volume itself. The pick returns a point **on that surface** (3D view frame, y negated).
3. The point is converted to the slice frame and to a voxel `(z, y, x)`; the seed's HU is read.
4. Without "Bật chế độ xem trước": region growing runs at once (worker thread) and creates a real mask "Region Growing N". With preview mode: the seed is only recorded ("Hạt giống tại voxel (z, y, x) (HU h). Bấm Xem trước."), and **Xem trước** becomes available.

## Real-application test

A separate InVesalius process (isolated `XDG_CONFIG_HOME`), driven by script: 0543 imported with InVesalius's own importer, a bone surface (≥ 400 HU) given to InVesalius's `SurfaceManager`, ROI Viewer opened through InVesalius's plugin loader, the button pressed, and **real wx mouse events** sent to the 3D view widget (canvas → `wxVTKRenderWindowInteractor` → VTK → plugin observer).

| Case | Before the fix | After the fix |
|---|---|---|
| Click on the surface, preview off | picked, "Region Growing 2" created (2,181 voxels) | same |
| Click on empty background | reported as a point on the camera focal plane → meaningless seed | "Cú nhấp không trúng bề mặt 3D nào…", button stays armed |
| Click on the surface, preview on | seed recorded | seed (149, 407, 256), HU −16, Xem trước enabled, 3D marker moved to the seed |
| Seed at 2D cursor (new) | – | seed exactly at the cross position (140, 260, 150) |

The pick mechanism itself worked in the real application whenever the click landed on a visible surface. In the operator's case, likely explanations: the click missed the surfaces, or it hit the yellow marker sphere (see defect 4); a missed click now produces a visible message. The exact click of the operator could not be replayed. Note the 0543 bone-surface seed above has HU −16: a 3D pick lands **on the boundary** of the surface, often just outside the object.

## Defects found and fixed

1. **Miss reported as a point**: `vtkCellPicker.Pick()` returns 0 for a miss, but the old code always used `GetPickPosition()` (the focal plane). Now only hits are reported; misses go to `miss_callbacks`.
2. **Callbacks skipped**: a one-shot callback (seed, distance, AI point) removed itself while the list was being iterated, so the next callback did not run; one failing callback stopped the rest. Now a snapshot is iterated and each callback is isolated.
3. **"Chọn điểm trong 3D" stopped after a project reload**: re-attaching the picker cleared every callback, while the Display tab still believed its callback was registered. Re-attaching now keeps the callbacks (they are cleared only on plugin close).
4. **Marker in the way**: the yellow 3D marker sphere was pickable; a click near it picked the marker instead of the anatomy. Now non-pickable like the other plugin actors.
5. **No feedback / no inside seed**: the status now shows the seed voxel and HU, the 3D marker moves to the seed, and a new button **"Hạt giống tại con trỏ 2D"** uses the 2D cross position (a point inside the organ). Pressing the 3D button twice no longer registers twice.

Not changed: on Windows the plugin uses VTK's event position as InVesalius does for its own 3D picking; in this run the content scale was 1.0, so a HiDPI offset could not be tested.

## Tests

`tests/ct3d/test_seed_pick.py` (12, real off-screen VTK interactor with an InVesalius-like style and real `LeftButtonPressEvent`s, plus the real `ROIViewerPanel`): hit, miss, self-removing callback, failing callback, re-attach keeps callbacks, marker not pickable, 3D seed on a surface → voxel (8, 10, 15), miss stays armed, double press, untoggle, seed at 2D cursor with HU, Display-tab pick after a project reload. Six of them fail on the old code (miss, self-removal, failing callback, re-attach, Display tab after reload, marker). `tests/ct3d` 742 passed / 2 skipped ×3, upstream 94, pyflakes / compileall / diff-check clean.

Manual items: Manual QA "Seed pick" RG-A..RG-D (`NOT_RUN`).
