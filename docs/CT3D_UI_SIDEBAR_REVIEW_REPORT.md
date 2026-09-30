# CT3D — Full UI/Flow Review and Sidebar Docking (30/09/2026)

**Branch**: `enhancement/advanced-segmentation` · after E6b (`29a891b6`). Stable `ct3d-rc1` not modified. No InVesalius file changed.

Requested by the user after E6b: review the whole flow, fix what is wrong or unreasonable, make the Vietnamese UI more sensible, and show the ROI Viewer in the sidebar.

## 1. Method

Earlier UI work was verified only by headless widget-tree tests. This review also **looked at the real rendered UI**: the plugin was built in its own process (isolated `XDG_CONFIG_HOME`, real 0051 volume from the sample `.inv3`) and screenshotted with DPI-correct capture (this display is 1920×1080 at 125 %), first as the old window, then docked in a stand-in for InVesalius's AUI main window, finally inside a real `wx` main loop. Findings below that the tests had not caught are marked *(seen only on screen)*.

## 2. Findings and fixes

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 1 | Tab labels lost "&": "ROI & 3D" rendered "ROI 3D", "Tương tác & Hiển thị" rendered without "&" — wx treats `&` in a tab label as a keyboard mnemonic | *seen only on screen* | `roi_panel.tab_label()` doubles `&` |
| 2 | Six tabs did not fit: at ~420 px the last tabs ("Ghi chú", "Xuất dữ liệu") were only reachable through tab-scroll arrows — worse in a sidebar | *seen only on screen* | **4 tabs**: Phân đoạn · ROI & 3D · Hiển thị · Công cụ (Đo lường / Ghi chú / Xuất dữ liệu stacked on one scrolling page, each with a bold section title) |
| 3 | **Current-ROI colour swatch always (near) black** — InVesalius mask colours are floats 0..1 (`constants.MASK_COLOUR`), the swatch did `int(c)` → 0/1 | *seen only on screen* (green mask shown black); E1-B manual item had never been run | `segmentation_panel.mask_colour_to_wx()` scales 0..1 → 0..255 (0..255 still accepted); tests |
| 4 | AI section cluttered: point/box, structure and mode rows shown even when the selected model cannot use them (or no model exists) | screenshot | rows shown only when used: prompts for prompt-driven models, structure/mode where the provider declares them; without a model an install hint is shown instead |
| 5 | Hint lines wrapped at a fixed 250 px ("3. Hậu / xử lý" broken mid-phrase in a 400 px sidebar) | screenshot | `ui_helpers.follow_width()` re-wraps hints to the page's real width |
| 6 | Annotation colour presets labelled "1…5" (meaningless) | screenshot | plain colour swatches with Vietnamese colour names as tooltips (Đỏ, Xanh lá, Xanh dương, Cam, Tím) |
| 7 | Tool panels repeated their own titles ("Công cụ đo lường", "Tùy chọn xuất") under a tab of the same meaning | screenshot | titles are now the section names (Đo lường / Ghi chú / Xuất dữ liệu); annotation list box renamed "Danh sách ghi chú" |
| 8 | Separate floating window hid the viewers / got lost behind the main window | user request | **docked sidebar pane** (§3) |

Not changed after review (reasoned): the workflow order inside "Phân đoạn" (create → AI → preview/accept → post-process → brush → history) matches the real constraints (post-processing only on accepted masks); the E2 preview still needs a current mask (native overlay constraint, clear message shown); console messages stay English (developer diagnostics).

## 3. Sidebar docking (`plugins/roi_viewer/gui/sidebar.py`)

- InVesalius's main window uses `wx.aui` (`Frame.__init_aui`: `self.aui_manager`; "Tasks" docked left at 385 px, viewers centre, import panes shown/hidden by name; it never reloads a saved perspective). The plugin adds one more pane: name `roi_viewer`, caption "ROI Viewer", **docked right**, best width 400, min 340, floatable/dockable, close button, `DestroyOnClose`.
- `ROIViewerFrame` (a `wx.Frame`) became **`ROIViewerPanel`** (a `wx.Panel`) with the same controller role; its cleanup moved to `shutdown()` (idempotent): picker observer, marker/C8 planes, E4 mesh, E5 textures/clipping, AI. The pane's close button (`EVT_AUI_PANE_CLOSE`) calls `shutdown()` before AUI destroys the pane; plugin unload calls `sidebar.close_viewer()`.
- Plugins menu again: an open pane is shown/raised (no second pane); after closing, a fresh pane opens.
- A host window without an AUI manager gets a plain frame (same panel).
- **Not possible without changing InVesalius**: showing the sidebar automatically at application start — `PluginManager.find_plugins()` only reads `plugin.json`; the plugin's code is first imported when its menu item is chosen (`enable-startup` only enables that menu item before a project is open). The project has never modified InVesalius itself, so this was left as a decision for the user (see §6).

## 4. Tests

- `tests/ct3d/test_sidebar.py` (9): docks right next to "Tasks"/"Data" with caption/close/float/destroy-on-close and min width; pane close runs `shutdown()`; show again; close detaches and destroys; plain-frame fallback; `main.load()` docks, reuses the open pane, opens a fresh one after close; colour-swatch scaling (InVesalius float colours and 0..255).
- `test_ui_localization.py`: 4 tabs with doubled `&`; tools page holds the three panels; clipping check now skips widgets that are not displayed (inside a collapsed section or hidden) — they cannot be clipped, and hiding AI rows lays them out at 0 width.
- `test_ai_ui_state.py` / `test_totalsegmentator_provider.py`: rows hidden/shown per model.
- All `ROIViewerFrame` references in tests renamed.

## 5. Regression

`tests/ct3d` **610 passed / 1 skipped / 0 failed** ×3; upstream 94; pyflakes / compileall / diff-check clean.

## 6. Open items / decisions for the user

1. **Auto-show at InVesalius start** needs a small change in InVesalius's `PluginManager` (e.g. a `"auto-load": true` key in `plugin.json` that calls `load_plugin` after `find_plugins`). Not done: it would be the first change to InVesalius itself.
2. **Real-application check**: the sidebar was verified in a stand-in AUI window and with the real panel, not in a running InVesalius (the user's own InVesalius session was open; a second instance shares `config.json`/`state.json`). Manual items UI-K..UI-N cover it.
3. **Incident during this review**: one screenshot script run without an isolated config directory rewrote the user's `%USERPROFILE%\.config\invesalius\config.json` with defaults (recent-projects list, surface defaults, random id lost). Restoring the file was blocked by the permission system. The running InVesalius session keeps the full configuration in memory and writes it back on its next configuration save (e.g. opening a project or a normal exit). All later scripts used an isolated `XDG_CONFIG_HOME`; the test suite always did.
