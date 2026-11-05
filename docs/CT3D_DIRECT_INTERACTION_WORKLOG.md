# CT3D ROI Viewer: Direct interaction worklog

All entries are from 05/11/2026, one session, in the real order. Times come from the evidence files; no other times are claimed.

| # | Action | Finding | Files | Result / decision |
|---|---|---|---|---|
| 1 | Preflight (15:59) | clean worktree on `feature/interactive-ai-medsam2` @ 02c15f9e; target branch absent | `00` | branch created |
| 2 | Baseline | ct3d 824/2, upstream 94, pyflakes / compileall / diff-check exit 0 | `01` | start |
| 3 | Source audit of the installed predictor | `add_new_points_or_box` returns the current frame without propagation; `_get_image_feature` keeps one frame; `reset_state` keeps images; single click = multimask | `02` | fast 2D and state reuse possible with the real API |
| 4 | Machine state | the operator's InVesalius and a MedSAM2 worker were running (~8.4 GB commit, 0.7–2.8 GB RAM free); the first TotalSegmentator reference attempts failed with MemoryError / "paging file too small" | – | no real-model run while the operator's session was open; asked the operator, who closed InVesalius |
| 5 | Worker provider: session, feature cache, slice scope, smart init | – | `providers/medsam2_provider.py`, `smart_prompt.py` | – |
| 6 | Host: options pass-through, scheduler, input capture, overlay drag, panel simple/advanced, provisional preview, restart, window guard, suggestion | – | `direct_scheduler.py`, `direct_ai_input.py`, `ai_prompt_overlay.py`, `segmentation_panel.py`, `semantic_suggestion.py`, `locale_vi.py` | existing suites: one intended update (the direct layout is the default) |
| 7 | **Defects found by the new tests** | (a) stage status overwritten by the job controller's synchronous state message; (b) **an edited config file was ignored by "Kiểm tra môi trường"** (an old client was reused); (c) a cross-tool drag would have produced an AI point on release | panel, `medsam2_external_provider.py`, `direct_ai_input.py` | all fixed; (b) has its own regression test |
| 8 | TotalSegmentator reference for 0543 (test data only, scratchpad) | full task run in 149.8 s; 88 labels present; liver, spleen, kidneys, T12, lung lobes among them | – | reference for measurement only |
| 9 | **Real benchmark 1** | the spec's fast-2D bbox was worse than the plain point (spleen 0.695 vs 0.953); the point fails only on the lung; click box 64 rescues the lung (0.44) and the vertebra (0.83) | `03` | default changed to `point_first` (measured) |
| 10 | **Real benchmark 2** (shipped policy) | 6/6 non-empty, click inside 6/6, mean Dice 0.818; refinement clicks unreliable; cache A/B identical candidates, repeats 10.9–13.3 s vs 17.4–18.6 s, VRAM 5.3 vs 1.3 GB | `04` | cache on by default with the free-memory guard; limitation documented |
| 11 | Latency | click → marker 39.7 ms headless; quick view 0.75–3.5 s; click → 3D 7–21 s | `05`, `04` | – |
| 12 | Regression | runs 1–2 clean (870/2). Run 3 took 2 h 24 min (the same unattended-slowdown pattern seen on the previous track) and reported 1 error, without the test name (the summary filter dropped it). A diagnostic rerun was clean; 3 more consecutive runs with `-rEf` were clean (870/2 each). Suspected, not proven: a 60 s wait in a fixture (e.g. the environment check) timed out during the slowdown | `11`–`13`, `13b` | reported as is; not hidden |
| 13 | Commits, push | see `git log` | – | not merged |
