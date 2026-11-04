# CT3D ROI analysis — final validation worklog (04/11/2026)

Times are the machine clock (+07:00) from command output; "≈" marks a time read from the nearest logged command.

| Time | Action / finding | Decision | Files | Test / result | Commit |
|---|---|---|---|---|---|
| 21:56 | Git preflight: branch `enhancement/advanced-segmentation`, HEAD = origin = `1bd9e2ff`, clean (only untracked `.claude/`), diff-check clean, stable `aa1b3ad3` | proceed | `evidence/01_git_preflight.txt` | - | - |
| 21:56 | Environment recorded; user `config.json` hashed (no `state.json` present) | isolate every run with a temporary `XDG_CONFIG_HOME` | `evidence/00_environment.txt` | - | - |
| 21:57 | Baseline regression | baseline clean → continue | `evidence/02`, `03` | ct3d 706 passed / 2 skipped; upstream 94; pyflakes/compile/diff clean | - |
| ≈21:58 | Previous 0543 scratch data gone (scratchpad changed) | re-run the lung segmentation with the plugin's provider in the background | scratchpad `a0543/step1.py` | left 3,408,753, right 6,178,307 voxels; first lobe 158.5 s, others 1.0–1.4 s | - |
| ≈22:00 | Finding: comparison "Tổng" = arithmetic A + B; overlapping voxels counted twice | keep the arithmetic value, rename it `a_plus_b` (alias `total`), add union / intersection / only A / only B / Dice / IoU / union HU / per-class union | `core/analysis/analysis_session.py` | `test_roi_comparison.py` | `221047f3` |
| ≈22:00 | Finding: operator's bone ROI + lung classes = 100 % unclassified, correct but unexplained | non-blocking warning at 100 % and > 95 %; ranges never changed | `core/analysis/hu_classes.py`, panel | `test_coverage_warning_levels` | `221047f3`, `c5abf505` |
| ≈22:03 | Finding: class editor can differ from the class list without indication | explicit dirty state, block Compute/Compare/2D/3D/convert/CSV/PDF until Apply, no auto-apply | `gui/analysis_panel.py` | `test_unapplied_class_edit_blocks_every_class_action` | `c5abf505` |
| ≈22:03 | Gap: plugin-side edits do not mark the analysis stale until the next action; convert button not guarded | `_refresh_after_edit` calls `check_source`; button disabled while committing | `gui/segmentation_panel.py`, panel | `test_cleanup_through_the_segmentation_panel_makes_analysis_stale`, `test_convert_button_is_guarded_while_committing` | `c5abf505` |
| ≈22:05 | Report rewrite: sections 1–8, tables, overlap note, ROI contour; CSV with exact repr numbers, BOM, comparison file | - | `core/analysis/analysis_report.py` | report tests updated for the new number format (intended) | `e4b36f72` |
| ≈22:06 | Orientation audit: matrix row 0 = most posterior DICOM row, VTK draws it at the bottom → old PDF axial picture had posterior at the top | flip axial rows for top-down drawing | `analysis_report.py` | `test_axial_picture_has_anterior_at_the_top` | `e4b36f72` |
| ≈22:08 | Focused suites | - | - | 76 passed (3 old CSV/table expectations updated) | - |
| ≈22:10 | Full ct3d after changes | - | - | 730 passed / 2 skipped | - |
| ≈22:12 | No PDF rasterizer installed (no PyMuPDF/pdfium/poppler) | do not install anything; render the PDF's own Figure objects with Agg for visual QA | scratchpad `a0543/validate.py` | - | - |
| ≈22:15 | 0543 validation: statistics, positive/negative control, lung density, overlap/disjoint comparisons, CSV round trip, 4 PDFs | all exact (see evidence 04–06) | scratchpad | - | - |
| ≈22:16 | Visual QA finding: comparison tables past the right margin; pictures leave large blank areas | narrower columns + an assertion that tables fit; smaller pictures; re-render | `analysis_report.py` | re-render clean | `e4b36f72` |
| 22:20 | `git diff --check` blocked the first commit (blank line at EOF in `hu_classes.py`) | fix, redo commits | - | diff-check clean | `221047f3`, `c5abf505`, `e4b36f72` |
| ≈22:21 | Final regression ×3 + upstream + lint + focused suites | - | `evidence/07`–`12b` | see files | - |
| ≈22:30 | Documentation and manual-QA reconciliation; operator observations from the task brief recorded as PARTIAL (screenshots not attached here) | - | docs | - | docs commit |
