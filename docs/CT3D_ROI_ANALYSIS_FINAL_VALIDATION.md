# CT3D / ROI Viewer — ROI analysis final validation (04/11/2026)

## Scope

Finish and validate the existing ROI analysis: statistics, HU histogram, HU classes, ROI comparison, CSV and PDF report. No new AI model, not Phase 15, not E7. Software correctness only - **not clinical accuracy**; 0543 is not ground truth. Branch `enhancement/advanced-segmentation`; stable `thesis-ct-roi-tools` / `ct3d-rc1` (`aa1b3ad3`) untouched.

## HEAD / environment

HEAD before `1bd9e2ff` (= origin). Python 3.11.7, numpy 1.26.4, scipy 1.14.0, VTK 9.3.0, wxPython 4.2.5, matplotlib 3.9.0, torch 2.7.1+cu118 (CUDA), TotalSegmentator 2.18.0, Windows 11 (26200), 15.3 GB RAM (1.4 GB free at start). Every test/helper process used a temporary `XDG_CONFIG_HOME`; the user's `config.json` was hashed before and after (`14_git_final.txt`). Evidence: `docs/evidence/roi_analysis_final_20261104/` (`00_environment.txt`, `01_git_preflight.txt`).

## Baseline

`tests/ct3d` 706 passed / 2 skipped, upstream 94 passed, pyflakes / compileall / diff-check clean (`02_baseline_ct3d_run1.txt`, `03_baseline_upstream.txt`).

## Source audit

| Contract | Where | Finding |
|---|---|---|
| Source ROI = current mask, read via `native_mask.logical_foreground()` (lazy threshold completed, `> 127`) | `gui/analysis_panel.py` | correct |
| Volume = voxels × sx·sy·sz (float64), same formula as Đo thể tích (`MeasurementManager.calculate_volume`) | `roi_statistics.py` | correct |
| Histogram of ROI voxels only, counts + below + above = ROI | `roi_statistics.py` | correct |
| Classes half-open `[min, max)`, overlap rejected, gaps → unclassified | `hu_classes.py` | correct; class count now capped at 254 |
| Comparison "Tổng" = arithmetic A + B (shared voxels twice) | `analysis_session.compare` | **defect (semantics)** - fixed |
| Class editor values could differ from the class list with no indication; actions used the list | `analysis_panel.py` | **defect (UX)** - fixed |
| 100 % unclassified (bone ROI with lung ranges) - correct but unexplained | panel / report | **gap** - warning added |
| Plugin-side edits (cleanup, undo/redo) fired no staleness until the next action | `segmentation_panel._refresh_after_edit` | **gap** - immediate check added |
| Convert class to ROI: no guard against a second click | panel | **gap** - guarded |
| PDF section letters skipped (A, B, C, E, G); text "tables"; axial picture posterior at the top | `analysis_report.py` | **defects** - fixed |
| CSV numbers rounded (not exact); no comparison output | `analysis_report.py` | fixed |

## Statistics validation

0543 (300 × 512 × 512, 0.5859 × 0.5859 × 1.0 mm), `04_analysis_validation.txt`:

| ROI | Voxels | Volume (ml) | HU min / max / mean / median / std | = NumPy | Đo thể tích diff |
|---|---:|---:|---|---|---|
| Mask 1 (226..3071 HU) | 3,814,341 | 1,309.550056 | 226 / 3070 / 405.3876 / 317 / 216.1059 | yes | 0.0 mm³ |
| AI - lung_left | 3,408,753 | 1,170.302467 | −1000 / 777 / −734.3865 / −792 / 174.3659 | yes | 0.0 mm³ |
| AI - lung_right | 6,178,307 | 2,121.153374 | −1000 / 590 / −762.5427 / −804 / 140.6054 | yes | 0.0 mm³ |

`volume_mm3 == voxels × 0.34332275390625` exactly for all three. Lungs were re-segmented in this run (the previous scratch data was gone): left lung has the same voxel count as on 15/10 (3,408,753); right lung 6,178,307 (15/10: 6,178,310 - GPU non-determinism). Tests: `test_roi_statistics.py` (10).

## HU classification validation

Half-open boundaries, overlap rejection, gaps, mask restriction, visibility/opacity independence, inputs unchanged, invalid edit keeps the last valid set: `test_hu_classes.py`, `test_invalid_edit_keeps_previous_valid_configuration`.

## Positive control

Mask 1 with [226,400) [400,700) [700,1200) [1200,2000) [2000,3071): 2,590,583 / 815,478 / 382,345 / 23,237 / 2,698 voxels, each equal to an independent NumPy count; unclassified 0 (no ROI voxel = 3071; ROI max 3070); accounting 3,814,341 = ROI. Note: Mask 1 is the "Bone" preset and also contains contrast-filled vessels/heart (class 226–400 = 67.9 %).

## Negative control

Mask 1 with five classes in −1000..−500: every class 0, unclassified 3,814,341 = **100 %**, `coverage_warning` = `none` → message "Không có voxel nào của ROI nằm trong các khoảng HU đã khai báo. Hãy kiểm tra lại các khoảng phân lớp." The earlier operator result (all classes 0) was mathematically correct, not a defect. Tests: `test_coverage_warning_levels`, `test_hundred_percent_unclassified_warning_in_ui`, `test_pdf_class_table_sum_and_coverage_warning`.

## Lung-density validation

Left lung, experimental preset: Emphysema 4,187 (0.123 %), Inflated 2,229,749 (65.412 %), Infiltrated 961,505 (28.207 %), Collapsed 183,377 (5.380 %), Vessels/dense 29,935 (0.878 %), unclassified 0, accounting exact. 15/10 reference (other segmentation run): 4,187 / 2,229,749 / 961,500 / 183,376 / 29,941 - differences of ≤ 6 voxels follow the re-segmentation, not the classifier. Reference/experimental only.

## ROI comparison semantics

A, B, **A + B** (arithmetic: voxels/volumes add, HU statistics over A's values then B's, shared voxels twice - labelled "Cộng A + B (có thể đếm trùng)") and **A ∪ B** (each voxel once). Spatial relation: intersection, union, only A, only B (voxels and ml). Class comparison: per class A, B, A + B, A ∪ B. Code: `analysis_session.compare`, `SpatialRelation`, `ClassComparisonRow`.

## Overlap test

A = Mask 1, B = constructed superset 100..3071 HU (**not** the operator's "ROI Viewer 2", which is not available here): A ⊂ B verified; intersection 3,814,341 = A; union 9,461,500 = B; only A 0; only B 5,647,159; A + B 13,275,841 > union; Dice 0.574629 = 2|A|/(|A|+|B|); IoU 0.403143 = |A|/|B|; HU mean A+B 296.90 vs A∪B 253.17. (`05_comparison_validation.txt`, `test_subset_catches_sum_as_union`.)

## Disjoint test

A = left lung, B = right lung: intersection 0, union 9,587,060 = A + B, Dice 0, IoU 0, equal to an independent NumPy computation. A∪B class shares: Inflated 72.910 %, Infiltrated 22.471 %. (`test_disjoint_sets`.)

## Dice / IoU

Dice = 2|A∩B| / (|A|+|B|), IoU = |A∩B| / |A∪B|. Policy: both empty → 1.0 and 1.0 (identical empty sets); one empty → 0.0 and 0.0. Tests: `test_dice_iou_empty_policy`, `test_both_empty_and_one_empty_through_compare`, `test_partial_overlap_set_identities`.

## Histogram

Automatic and manual range for Mask 1, left and right lung: counts + below + above = ROI voxels; manual [−500, 500] below/above equal NumPy (`04`). Tests: `test_histogram_counts_only_the_roi`.

## 2D preview

Label array and colour table on the overlay slot; own aux key, never takes the E2 preview's slot, off restores the view, no mask created (`test_2d_overlay_is_its_own_layer`, `test_segmentation_preview_keeps_the_overlay_slot`, `test_analysis_and_previews_never_change_the_roi`). Operator check AN-G not run.

## 3D preview

One non-pickable actor per visible non-empty class, not in `surface_dict`, camera untouched, hidden class removed, opacity display only, cleanup on project close / load / plugin close / source edit (`test_analysis_preview_3d.py`, `test_lifecycle_cleans_everything`). 0543 left lung: 5 meshes (7,722 – 1,260,350 points) in 2.8 s. Operator check AN-H not run.

## Convert class to ROI

Exactly one new ROI equal to the class, parent byte-identical, no surface, locked parent allowed, second click during commit ignored (`test_analysis_to_roi.py`, `test_convert_button_is_guarded_while_committing`).

## Staleness

Native brush (`Mask.modified` callback), cleanup through the real `SegmentationPanel._run_cleanup`, direct writes and deletion all mark the session stale; previews removed; convert, CSV, PDF and 2D/3D disabled (`test_native_modified_callback_marks_stale`, `test_cleanup_through_the_segmentation_panel_makes_analysis_stale`, `test_source_edit_makes_analysis_stale_and_clears_previews`).

## CSV

Statistics CSV `roi_name, class_name, min_hu, max_hu, voxel_count, volume_mm3, volume_ml, percent_roi, hu_mean, hu_median, hu_std, hu_min, hu_max`; comparison CSV `<name>_comparison.csv` keyed by `row_type` (A, B, A_PLUS_B, UNION, INTERSECTION, ONLY_A, ONLY_B, DICE, IOU, CLASS_A, CLASS_B, CLASS_A_PLUS_B, CLASS_UNION) + `class_name`. Comma delimiter, `.` decimal point, numbers written with Python `repr` (exact round trip), files UTF-8 with BOM (Excel shows Vietnamese). Round trip exact for all four 0543 reports and in `test_statistics_csv_round_trip_is_exact`, `test_comparison_csv_round_trip_is_exact`. Not opened in Excel in this run.

## PDF

Fixed sections 1. Thông tin dữ liệu, 2. Thông tin ROI, 3. Thống kê HU, 4. Phân lớp theo HU, 5. So sánh ROI, 6. Histogram, 7. Ảnh minh họa, 8. Ghi chú / giới hạn; an empty section prints "Chưa có dữ liệu." Tables for HU statistics, classes (with total row = ROI), comparison (Chỉ số | ROI A | ROI B | A+B (đếm trùng) | A∪B), spatial relation (Giao, Hợp, Chỉ A, Chỉ B, Dice, IoU), per-class comparison; overlap note; coverage warning. Pictures: axial/coronal/sagittal through the ROI centroid from the arrays (no screenshot), ROI contour red, class colours, axial anterior at the top and patient left on the image right (as InVesalius; `test_axial_picture_has_anterior_at_the_top`), mm aspect. **3D_REPORT_IMAGE = DEFERRED**: an off-screen OpenGL context inside the running application next to InVesalius's own was not judged safe.

Visual QA: four 0543 reports (positive control, lung density, left vs right, negative control + overlap) rendered page by page and inspected (`06_report_validation.txt`). No PDF rasterizer is installed; pages were rendered with matplotlib Agg from the same Figure objects written to the PDF, so the authoritative check of the PDF file itself in a PDF viewer is still an operator step (AN-O). First render found two defects (tables past the right margin, oversized pictures) - fixed and re-rendered clean.

## Performance

0543, this machine, single run (`04`–`06`): statistics 1.07–1.59 s, histogram 0.15–0.19 s, classification 0.59 s (Mask 1), full analysis with classes 3.17 s, comparison of the two lungs 5.92 s, 3D class meshes 2.80 s, PDF 0.91–1.28 s, CSV ≤ 0.03 s. In the panel, compute, comparison, 3D meshes and PDF run on worker threads.

## Manual QA status

See `CT3D_ADVANCED_SEGMENTATION_MANUAL_QA.md` "ROI analysis — manual QA". Operator observations described in the task brief of 04/11/2026 (screenshots/PDF not attached to this session, not reviewed here) are recorded as `PARTIAL`; nothing was marked PASS from automated tests. New items AN-Q..AN-T added.

## Defects found

1. Comparison "Tổng" was arithmetic A + B (double-counts overlap) but read as a total/union.
2. Unapplied class-editor values were invisible; actions used other values than shown.
3. 100 % unclassified result without explanation.
4. Plugin-side edits did not immediately mark the analysis stale.
5. Convert-class button could be clicked twice during a commit.
6. PDF: skipped section letters, text pseudo-tables, axial picture upside down relative to InVesalius, tables past the right margin, oversized pictures.
7. CSV numbers rounded; no comparison export.

## Fixes made

Commits `221047f3` (comparison sets, Dice/IoU, union HU, coverage warning), `c5abf505` (dirty state, warnings, labels, convert guard, edit hook), `e4b36f72` (PDF and CSV), plus this documentation commit. New tests: `test_roi_comparison.py` (17) and 7 panel tests.

## Remaining limitations

No 3D picture in the PDF; CSV not checked in Excel; PDF file not rasterized by an independent renderer; overlap control used a constructed superset, not the operator's "ROI Viewer 2"; one source ROI at a time; overlapping classes unsupported; no derived/formula metrics; analysis not saved with the project; manual AN items mostly open.

## Gate

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1–3 | voxel statistics, volume, histogram invariant exact | PASS | `04`, `test_roi_statistics.py` |
| 4–5 | class accounting exact, overlaps rejected | PASS | positive/negative control, `test_hu_classes.py` |
| 6 | unapplied edit safe | PASS | `test_unapplied_class_edit_blocks_every_class_action` |
| 7 | 100 % unclassified warning | PASS | negative control, `test_hundred_percent_unclassified_warning_in_ui` |
| 8–15 | A/B, A+B labelled, intersection, union, only A/B, Dice, IoU exact | PASS | `05`, `test_roi_comparison.py` |
| 16–17 | overlap and disjoint controls | PASS | `05` |
| 18–22 | 2D isolated, 3D transient, class-to-ROI exact, source unchanged, stale detection | PASS (automated) | tests above |
| 23–24 | CSV round trip, PDF data exact | PASS | `06`, CSV/report tests |
| 25–26 | PDF visually clean, Vietnamese | PASS (Agg render of the PDF's figures) | `06` |
| 27–28 | lifecycle safe, regression clean | PASS | `07`–`13` |
| 29–30 | docs synchronized, evidence/worklog | PASS | this file, `CT3D_ROI_ANALYSIS_WORKLOG.md` |

**ROI_ANALYSIS_FINAL_GATE = PARTIAL** - every automated criterion passes; the operator checks (AN-A..AN-T, PDF opened in a viewer, CSV in Excel) are not complete.
