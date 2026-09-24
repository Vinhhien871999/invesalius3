# CT3D — Advanced Segmentation Enhancement Track: Roadmap

> **Branch**: `enhancement/advanced-segmentation` (forked from the frozen `thesis-ct-roi-tools` release candidate, tag `ct3d-rc1`). **This is NOT Phase 15** and does not extend the CT3D Phase 08-14 software roadmap, which remains `COMPLETE` — see `docs/CT3D_P14_FINAL_AUDIT_REPORT.md`, `docs/CT3D_RELEASE_MANIFEST.md`. This is a separate, opt-in enhancement effort, tracked in its own set of `CT3D_ADVANCED_SEGMENTATION_*.md` documents so the stable release documentation never has to describe features that only exist here.
>
> Design inspiration is drawn from the **UX ideas** of modern segmentation tools (MITK's workflow concepts: multi-label management, preview/confirm segmentation, post-processing cleanup, live 3D preview) — **no MITK code or architecture is copied or reused**. Every feature here is a from-scratch design built on InVesalius's own real APIs (pubsub topics, `Mask`, `Slice`, `Project`), reusing the exact same "remote control, not reimplementation" principle the rest of the ROI Viewer plugin already follows.

## Milestones

| Stage | Name | Priority | Status |
|---|---|---|---|
| E1 | Multi-label / Advanced ROI Management | P1 | **WORKING** (this run) |
| E2 | Preview / Confirm segmentation workflow | P1 | PLANNED |
| E3 | Segmentation cleanup tools | P1 | PLANNED |
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

## E1 scope note (this run)

This run implements **only E1** (Advanced ROI Manager), per the explicit first-execution scope: audit → design → implement → test → regress → document → commit → push, then stop. E2-E6 are documented here as planned milestones only - no E2-E6 code exists yet. See `docs/CT3D_ADVANCED_SEGMENTATION_PROGRESS.md` for the live status table.
