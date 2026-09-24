# CT3D — Advanced Segmentation Enhancement Track: Roadmap

> **Branch**: `enhancement/advanced-segmentation` (forked from the frozen `thesis-ct-roi-tools` release candidate, tag `ct3d-rc1`). **This is NOT Phase 15** and does not extend the CT3D Phase 08-14 software roadmap, which remains `COMPLETE` — see `docs/CT3D_P14_FINAL_AUDIT_REPORT.md`, `docs/CT3D_RELEASE_MANIFEST.md`. This is a separate, opt-in enhancement effort, tracked in its own set of `CT3D_ADVANCED_SEGMENTATION_*.md` documents so the stable release documentation never has to describe features that only exist here.
>
> Design inspiration is drawn from the **UX ideas** of modern segmentation tools (MITK's workflow concepts: multi-label management, preview/confirm segmentation, post-processing cleanup, live 3D preview) — **no MITK code or architecture is copied or reused**. Every feature here is a from-scratch design built on InVesalius's own real APIs (pubsub topics, `Mask`, `Slice`, `Project`), reusing the exact same "remote control, not reimplementation" principle the rest of the ROI Viewer plugin already follows.

## Milestones

| Stage | Name | Priority | Status |
|---|---|---|---|
| E1 | Advanced ROI Management / Segmentation Set | P1 | **WORKING** |
| E2 | Preview / Confirm segmentation workflow | P1 | **WORKING** (this run) |
| E3 | Segmentation cleanup tools | P1 | **WORKING** (Current ROI target; Active Preview target deferred — see below) |
| E4 | Fast live 3D preview | P1 | PLANNED |
| E5 | Advanced 3D visualization (textured planes, clipping) | P2 | PLANNED |
| E6 | AI segmentation architecture | P2/Experimental | PLANNED |
| E6b | TotalSegmentator integration | P3/Experimental | PLANNED |

Each milestone is audited against real source first, implemented, tested, documented, and committed **separately** — never squashed together. A milestone does not start until the previous one's gate is `PASS` (see `docs/CT3D_ADVANCED_SEGMENTATION_PROGRESS.md` for live per-feature status).

## Architecture principles (apply to every milestone)

- InVesalius stays the host application; ROI Viewer stays a plugin. No fork of native functionality that already works well (brush, threshold, native Masks tab, Save/Open).
- `Project().mask_dict` remains the single source of truth for segmentation data. No second, independently-serialized mask/ROI model.
- No automatic high-quality surface rebuild on every mouse move / mask edit (this is exactly the D9/C7 performance trap the Phase 08-14 roadmap already identified and designed around — see `CT3D_KNOWN_LIMITATIONS.md` item 9).
- Save/Open, `ROIManager`'s no-orphan invariant, and C8 (2D↔3D sync: marker + slice planes) must never regress.
- No plugin feature silently steals the native toolbar/tool state.
- Every new feature has a fallback, a clear lifecycle (attach/detach, create/destroy, enable/disable), and automated tests before being called `WORKING`.
- High-risk/incomplete features (E5's textured planes if infeasible, all of E6) get an explicit config/UI toggle, default OFF until proven.

## Classic workflow guarantee

If every `ENABLE_*` flag introduced by this track is left at its default, the plugin's behavior must be identical to the frozen `ct3d-rc1` release: Threshold, Otsu, Region Growing, Brush, Eraser, Undo/Redo, Update Surface, Measurements, Annotation, Save/Open, Export all keep working exactly as documented in `docs/HUONG_DAN_SU_DUNG_ROI_VIEWER.md`.

## Stop conditions

Development on this track stops immediately (not just the current milestone - reassess before continuing at all) if any of the following is observed:
wrong branch; a dirty worktree with unexplained user changes; a regression in the existing `tests/ct3d`/upstream suites; Save/Open data corruption; a VTK actor leak; a plugin close/reopen crash; the D9/C7 "Update 3D Surface" policy breaking; the C8 marker/slice-plane sync breaking; production code starting to depend on a hardcoded local path; or an AI feature (E6/E6b) that would require committing model weights/data without review.

## Commit & push discipline

- One commit per milestone (`Advanced segmentation E<N>: <summary>`), never auto-squashed.
- Push to `origin/enhancement/advanced-segmentation` after each milestone's gate is `PASS`.
- Never merge into `thesis-ct-roi-tools`, never force-push, never amend a historical release commit, never touch the `ct3d-rc1` tag.

## E1 scope note

E1 implemented the Advanced ROI Manager, per that run's explicit first-execution scope: audit → design → implement → test → regress → document → commit → push, then stop.

**Naming correction (E2 run)**: the milestone table above originally titled E1 "Multi-label / Advanced ROI Management." The source-first audit performed for E1 (and repeated again for E2) confirmed the real backend is independent InVesalius masks (`Project().mask_dict`), not a shared multi-label voxel volume - "multilabel" was never an accurate claim about the data model. Corrected to "Advanced ROI Management / Segmentation Set," matching the UI's own box title and `docs/CT3D_ADVANCED_SEGMENTATION_ARCHITECTURE.md`'s "Naming" section. No historical stable-release report is altered by this correction - it only fixes wording in this enhancement-track-only planning document.

## E2 scope note

E2 implemented Preview/Confirm for Otsu and Region Growing, per that run's explicit scope. See `docs/CT3D_ADVANCED_E2_PREVIEW_REPORT.md` for the full design/audit writeup.

## E3 scope note (this run)

This run implements **E3** (Segmentation cleanup tools: Keep Largest Component, Remove Small Islands, Fill Holes, Smooth Mask) for the **Current ROI** target only. **Active Preview cleanup is deferred**, not implemented this milestone - the source audit found that E2's Otsu Accept path recreates its mask from the recorded threshold (not from an array), so cleaning the preview array and then Accepting would silently discard the cleanup for Otsu specifically; rather than ship an inconsistent (works-for-Region-Growing-only) or unsafe feature, this was deferred wholesale, with the exact reasoning documented in `docs/CT3D_ADVANCED_E3_CLEANUP_REPORT.md`'s "Cleanup targets" section. E4-E6 remain planned only - no E4-E6 code exists yet. See `docs/CT3D_ADVANCED_SEGMENTATION_PROGRESS.md` for the live status table.
