# CT3D — Pre-E6 Product Polish: ROI Viewer UI/UX + Vietnamese Localization

**Branch**: `enhancement/advanced-segmentation` · **Date**: 30/09/2026 · **Code commit**: `4d0ca6e5` "Polish ROI Viewer UI and Vietnamese localization" · **Preceded by** the coordinate fix `7b245865` / `c9f220bd` / `89ef7f19` (`docs/CT3D_COORDINATE_SPACING_FIX_REPORT.md`).

Not an E-milestone. No new feature, no backend change, no E6/AI work. Stable `thesis-ct-roi-tools` / tag `ct3d-rc1` (`aa1b3ad3`) untouched: the stable UI stays English with 5 tabs.

---

## 1. Goals and constraints

1. Reorganise the plugin UI by workflow (Phân đoạn → ROI & 3D → Tương tác & Hiển thị), advanced controls collapsible, basic workflow always visible.
2. 100% Vietnamese user-facing plugin UI using the project glossary; short statuses; Vietnamese number format.
3. Keep every behaviour: E1 lock/solo, E2 preview, E3 cleanup, E4 live preview, E5 textures/clipping, C8, pubsub topics, `Project().mask_dict`, final-surface policy.
4. Existing wxPython only (no framework rewrite); no screenshot-based "tests".

## 2. Audit before the change (`89ef7f19`)

**Layout** (measured on the real `ROIViewerFrame` built headlessly, window 400 px wide → 349 px notebook page, 623 px viewport):

- 5 tabs: Interaction / Segmentation / Measurements / Annotations / Export. 157 widgets.
- **Segmentation tab content 1396 px tall** in a 623 px viewport: Threshold, Region Growing, the ROI list with its E1 buttons, "Update 3D Surface", E2 preview, E3 cleanup, E4 live preview, brush and undo were all stacked open in one scrolling column - more than two screens, with the basic workflow split by advanced boxes.
- Interaction tab had two boxes with **no effect**: "Real-time Update" + "Update delay (ms)" slider (stored a value nothing read) and a "Brush Mode / Brush Size" copy (the real brush is in Segmentation). Their handlers and `get_brush_config()` had no caller.
- E-milestone boxes carried developer labels ("Preview Segmentation (E2, enhancement branch)", "3D Preview (E4, enhancement branch)", "3D Visualization (E5, enhancement branch)").

**Strings** (AST over `plugins/roi_viewer`, `_()` calls):

| | Before `89ef7f19` | After `4d0ca6e5` |
|---|---:|---:|
| `_()` calls | 302 | 319 |
| literal msgid | 271 | 319 |
| `_(f"...")` (untranslatable - msgid changes every call) | 29 | 0 |
| `_(variable)` | 2 | 0 |
| unique literal msgids | 199 | 237 |
| msgids with a Vietnamese translation | **0** | **237** |

Why 0 before: the plugin called `invesalius.i18n.tr`, but InVesalius ships no `vi` catalog (`locale/` has no `vi`) and the plugin's strings are not in the upstream `invesalius` domain - so even a Vietnamese UI language could never translate them. Every user-facing plugin string was English.

## 3. Decisions

| Decision | Reason |
|---|---|
| Plugin-local catalog `plugins/roi_viewer/locale_vi.py` (English msgid → Vietnamese) read by `plugins/roi_viewer/i18n.py` `_()` | Only way to get Vietnamese without editing upstream InVesalius i18n or shipping a compiled `.mo`; keeps English msgids in source; testable as plain data |
| Every `_()` argument a literal; values inserted with `.format()` after translation | An f-string msgid can never match a catalog entry |
| `_("")` returns `""` without lookup | gettext's `""` returns the catalog header - the metadata leak an operator saw earlier |
| Tabs in workflow order: Phân đoạn / ROI & 3D / Tương tác & Hiển thị / Đo lường / Ghi chú / Xuất dữ liệu | Creating masks is the first thing a user does; ROI management and the final surface are the second step; sync/display is support |
| ROI management + 3D surface moved to a new page, still owned by `SegmentationPanel` | Moves ~40% of the old Segmentation column without touching a single handler, attribute name or pubsub subscription (tests and other panels reach the same attributes) |
| 4 native `wx.CollapsiblePane`s, collapsed by default: Hậu xử lý (E3), Chỉnh sửa thủ công (brush), Xem trước 3D thời gian thực (E4), Hiển thị 3D nâng cao (E5) | Spec: advanced controls collapsed, basic workflow (Ngưỡng, Otsu, Phát triển vùng, Xem trước, Chấp nhận/Hủy) never hidden. The brush is classic, but it is a secondary editing tool and its 7 controls were the largest block; its section title stays visible |
| Workflow hint "1. Tạo / xem trước → 2. Chấp nhận → 3. Hậu xử lý → 4. Cập nhật bề mặt 3D" | **Deviates from the spec's suggested order** "Tạo/Xem trước → Kiểm tra → Hậu xử lý → Chấp nhận → Cập nhật 3D": post-processing cannot run on a preview (E3 "Cleanup targets": Otsu Accept rebuilds the mask from the threshold, so cleanup before Accept would be lost). The hint shows the order the software actually supports |
| "ROI hiện tại:" repeated at the top of Phân đoạn | Post-processing, brush and undo act on the current ROI while the list is on another tab |
| Region Growing buttons stacked, not side by side | An equal-width row is twice its longest label and overflowed a 360 px window |
| Dead Interaction controls removed (not translated) | They did nothing; translating them would present fake features |
| Pick-point readout in slice frame (`view_to_slice`) | Same millimetres as the 2D views; closes the last known limitation of the coordinate report |
| Long core error details → console; UI shows one short Vietnamese sentence | Spec §12: short statuses. Details stay available for debugging |
| Kept English (see §6) | Proper names, file formats, units, and names the user sees in English elsewhere in InVesalius |
| Auto-generated mask names "ROI Viewer N" / "Region Growing N" unchanged | They are project data saved in `.inv3`, not UI chrome; changing them would change saved projects vs `ct3d-rc1` |

## 4. Changes (`4d0ca6e5`, 11 files, +1105 / −652)

- New: `plugins/roi_viewer/i18n.py` (`_`, `fmt_int`, `fmt_float`), `plugins/roi_viewer/locale_vi.py` (237 entries), `plugins/roi_viewer/gui/ui_helpers.py` (`collapsible`, `relayout_scrolled`, `hint`, `button_row`, `labelled_row`), `tests/ct3d/test_ui_localization.py` (21 tests).
- `gui/segmentation_panel.py`: new `_init_ui` (Phân đoạn) and `_build_roi_3d_page()` (ROI & 3D); 64 message call sites rewritten as literal msgids + `.format()`; ROI/surface statuses go to a status line on the ROI & 3D page; helpers `_region_info()` and `_e4_source_label()`; all `Bind` calls unchanged.
- `gui/interaction_panel.py`: new `_init_ui` (Đồng bộ 2D – 3D, Chọn điểm 3D, collapsible Hiển thị 3D nâng cao); dead controls/handlers removed; `_update_status()`; slice-frame readout.
- `gui/roi_panel.py`: `ScrolledPanel` page `roi_3d_page`, new tab order, translated title.
- `gui/measurement_panel.py`, `annotation_panel.py`, `export_panel.py`: switched to the plugin `_()`; measurement results via `fmt_float`.
- `tests/ct3d/test_exporters.py`: the NRRD dropdown assertion compares against `_("NRRD (.nrrd) - library not installed")` instead of the English literal (behaviour under test unchanged).

## 5. Glossary applied (excerpt)

| English | Tiếng Việt |
|---|---|
| Segmentation / Preview / Accept / Cancel preview | Phân đoạn / Xem trước / Chấp nhận / Hủy xem trước |
| Threshold / Auto threshold (Otsu) / Create mask | Ngưỡng / Tự động xác định ngưỡng (Otsu) / Tạo mặt nạ |
| Region Growing / Tolerance / Pick seed point (3D) | Phát triển vùng / Độ dung sai / Chọn điểm hạt giống (3D) |
| Mask / Current ROI | Mặt nạ / ROI hiện tại |
| Post-processing / Keep largest connected component / Remove small islands / Fill holes / Smooth mask | Hậu xử lý / Giữ thành phần liên thông lớn nhất / Loại bỏ vùng nhỏ / Lấp lỗ / Làm mịn mặt nạ |
| Brush / Undo / Redo / Save restore point | Cọ vẽ / Hoàn tác / Làm lại / Lưu điểm khôi phục |
| Lock / Unlock / Show only this ROI / Show all / Hide all | Khóa / Mở khóa / Chỉ hiện ROI này / Hiện tất cả / Ẩn tất cả |
| 3D surface / Update 3D surface from current ROI | Bề mặt 3D / Cập nhật bề mặt 3D từ ROI hiện tại |
| Live 3D preview (experimental) | Xem trước 3D thời gian thực (thử nghiệm) |
| Show slice planes in 3D / Show slice image on 3D planes | Hiển thị mặt phẳng lát cắt trong 3D / Hiển thị ảnh lát cắt trên mặt phẳng 3D |
| Enable 3D clipping / Invert cut side / Target | Bật cắt hiển thị 3D / Đảo phía cắt / Đối tượng |
| Axial / Coronal / Sagittal | Axial (ngang) / Coronal (đứng ngang) / Sagittal (dọc) |

Full English → Vietnamese button mapping for users of older docs: `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md` §1.2.

## 6. String census after the change

**Source**: 319 `_()` calls, all literal; 237 unique msgids, **237/237 in the catalog**, 0 unused entries, placeholders identical in msgid and translation. 3 entries are intentionally identical to the msgid: "ROI & 3D", "2D", "3D".

**Runtime** (real `ROIViewerFrame`, every visible label, button, checkbox, radio, box title, collapsible title, drop-down entry, tab name, window title and tooltip at startup; pynrrd absent):

| Category | Distinct strings |
|---|---:|
| Vietnamese | 120 |
| Neutral (not language-specific): `-`, `voxel`, `x`, `2D`, `3D`, `ROI & 3D`, colour presets `1`-`5` | 11 |
| File-format names: NIfTI (.nii.gz), NumPy (.npy), STL Binary/ASCII (.stl), PLY (.ply), OBJ (.obj), VTK PolyData (.vtk), PNG (.png), JPEG (.jpg), TIFF (.tif), BMP (.bmp) | 11 |
| **Other (English)** | **0** |
| Tooltips (all Vietnamese) | 15 |

Statuses and dialogs are not visible at startup; they are covered by the source census (every message is a catalog msgid) and by `test_classic_controls_still_wired`, which fires real buttons and checks the Vietnamese status.

**English remaining, with reasons**:

| Kept | Reason |
|---|---|
| NIfTI, NRRD, NumPy, STL, PLY, OBJ, VTK PolyData, PNG, JPEG, TIFF, BMP | File-format proper names |
| mm, mm³, voxel, s | Units (voxel is the standard Vietnamese technical term too) |
| ROI | Glossary keeps it |
| Otsu | Algorithm name |
| Window/Level | Standard radiology term, and the name of InVesalius's own control |
| "Slices' cross intersection", tab "Measures" | Names of InVesalius's own tool/tab, which InVesalius shows in English (no `vi` catalog) - translating them would point the user to a label that does not exist |
| Axial / Coronal / Sagittal | Kept as the standard anatomical names **with Vietnamese in parentheses** ("Axial (ngang)") |
| ROI Viewer (product name, menu item, window title prefix) | Product name (`plugin.json`) |
| `pynrrd`, `pip install pynrrd` inside a Vietnamese sentence | Package name and command |
| Mask names "ROI Viewer N" / "Region Growing N" | Project data, see §3 |
| Console `print` output | Developer diagnostics, not UI |
| Yes / No / OK / Cancel on message boxes | Native Windows buttons; they follow the OS language, not the plugin |

## 7. Layout after the change

Measured on the real frame (window 400 px wide unless noted):

| Page | Height needed | Viewport | Scroll |
|---|---:|---:|---|
| Phân đoạn, sections collapsed | 603 px (was 1396) | 623 px | none |
| Phân đoạn, all sections expanded | 890 px | 623 px | vertical only |
| ROI & 3D, expanded | 521 px | 623 px | none |
| Tương tác & Hiển thị, expanded | 445 px | 623 px | none |

- No horizontal overflow and no clipped button/checkbox/radio at 400 px and 330 px, collapsed and expanded (automated); also checked at 360 px during development. Below ~330 px the 250 px hint wrap and the widest labels start to crowd - not a supported width.
- 159 widgets (157 before; +collapsible panes/hint/current-ROI row, −dead controls). No duplicate window IDs.

## 8. Behaviour preservation

- Handler logic unchanged; only their messages changed (literal msgid + `.format()`, ROI/surface statuses shown on the ROI & 3D page's status line, long core error details printed to the console instead of the UI). The set of `Bind(...)` calls in `SegmentationPanel` is identical before and after (diffed); widgets inside collapsible panes are bound directly, so reparenting does not change routing.
- Defaults unchanged and tested: preview mode OFF, live 3D preview OFF, texture planes OFF, clipping OFF, "Hiển thị mặt phẳng lát cắt trong 3D" ON, Sync ON; preview/accept/cancel/refresh buttons disabled until their mode is on.
- No pubsub topic, `Project().mask_dict` access, final-surface policy, C8/E5 geometry or coordinate code changed in this commit (the slice-frame readout only changes what the read-only text box shows).
- Full `tests/ct3d` passed unchanged apart from the one exporter assertion that compared English text.

## 9. Tests

`tests/ct3d/test_ui_localization.py` (21):

- Static: all msgids literal; every msgid translated; no unused catalog entries; placeholders preserved; empty string never translated; no upstream translator import; Vietnamese number format.
- Real frame: tab names/order and window title; every visible label Vietnamese or allow-listed neutral/format; every tooltip Vietnamese; the 4 collapsible sections collapsed on a fresh frame; feature defaults; preview buttons follow preview mode; classic buttons (Hoàn tác, Lưu điểm khôi phục) reach their real handlers and report in Vietnamese; dead Interaction controls gone; no duplicate window IDs; no clipped controls / horizontal overflow at 400 and 330 px, collapsed and expanded (4 cases); Phân đoạn fits one screen when collapsed.
- **Proven to detect a missing translation**: with `PLUGIN_LANGUAGE = "en"` (English msgids shown; set through a pytest plugin, no source edit) **6 of 21 fail**: tabs/title, visible labels, tooltips, collapsible titles, classic-control status text, and the 330 px expanded overflow case (some English labels are wider than their Vietnamese translations). The other 15 check language-independent rules and still pass. *(An earlier check during development, on a smaller version of this file, showed 4 failures; the number above is the final file.)*
- Existing guards still apply: `test_no_empty_string_gettext_calls`.

## 10. Regression

| Check | Result |
|---|---|
| `tests/ct3d` run 1 / 2 / 3 | 446 passed / 1 skipped / 0 failed each (447 collected; +21 vs 425/1 after the coordinate fix) |
| Upstream `tests --ignore=tests/ct3d` | 94 passed |
| `pyflakes plugins/roi_viewer` | clean |
| `compileall plugins/roi_viewer` | clean |
| `git diff --check` | clean |

The 1 skip is the optional `pynrrd` round-trip test (library not installed), as before.

## 11. Manual QA

New section "UI/UX Final Polish" in `docs/CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md`: **UI-A..UI-J all `NOT_RUN`** - readability, real font/DPI rendering and whether the workflow is understandable need a real operator. The operator's general statement that earlier feature groups passed in manual use is recorded as "Operator reports previous feature groups passed during manual use; item-level reconciliation pending." and did not change any item. E5-A stays `PASS`; E5-B/C/D/E/J/K/L stay `RETEST_REQUIRED` (coordinate-dependent).

## 12. Known limitations

- InVesalius's own UI (menus, toolbar, Masks/Measures tabs, native dialogs such as "Export Mask as NIfTI") keeps InVesalius's language; the plugin does not touch upstream i18n.
- The catalog is a Python dict, not a `.po`/`.mo` pair: fine for one language inside one plugin; a second language would need a second dict or a move to gettext files.
- Layout numbers are wx measurements on this Windows machine at default DPI; other DPI/fonts are for UI-D/UI-I.
- Minimum supported window width ≈ 330 px.

## 13. Git

`4d0ca6e5` Polish ROI Viewer UI and Vietnamese localization (code + tests) · docs commit "Update advanced segmentation documentation" (User Guide, Manual QA, Architecture, Progress, this report, coordinate report, known-limitations reference). Pushed to `origin/enhancement/advanced-segmentation`. Stable branch and tag unchanged at `aa1b3ad3`.

## 14. Next

E5 closure needs the operator retest of E5-B/C/D/E/J/K/L on this build (plus, optionally, UI-A..UI-J). E6 AI stays blocked until E5_GATE is `PASS`.
