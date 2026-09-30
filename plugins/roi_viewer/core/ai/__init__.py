# --------------------------------------------------------------------------
# E6 - AI segmentation architecture (Advanced Segmentation Enhancement
# Track, enhancement/advanced-segmentation branch only).
#
# AI is NOT a separate segmentation subsystem. The only path is:
#
#   real CT volume (Slice().matrix, read-only)
#     -> AISegmentationProvider.infer()          (worker thread)
#     -> candidate mask, validated on the native grid (preview_bridge)
#     -> E2 SegmentationPreviewManager, kind "ai" (2D overlay)
#     -> E4 live 3D preview picks it up like any E2 preview
#     -> Accept -> core/native_mask.commit_preview_array_to_new_mask()
#     -> real InVesalius Mask in Project().mask_dict (source of truth)
#
# Nothing here creates a Mask, touches Project, wx or VTK. No AI framework
# (torch, onnxruntime, monai, ...) is imported by this package; providers
# import their own dependencies lazily, and are only loaded when the user
# switches AI on. E6 ships NO production provider: registry.
# KNOWN_PROVIDER_MODULES is empty, so the UI says no compatible model is
# installed. Test doubles live in tests/ only.
# --------------------------------------------------------------------------

# Default of the "Bật phân đoạn AI (thử nghiệm)" checkbox. With it off the
# plugin creates no registry, loads no provider and starts no AI thread.
ENABLE_AI_SEGMENTATION = False
