# --------------------------------------------------------------------------
# Interactive AI external runtime (feature/interactive-ai-medsam2).
#
# The model (MedSAM2 or a future provider) runs in a SEPARATE Python
# environment, as a persistent child process speaking protocol.py over
# stdin/stdout. Nothing in this package imports torch, sam2 or any model
# code, and nothing installs or downloads anything: InVesalius's own
# environment is never changed. See docs/CT3D_INTERACTIVE_AI_ARCHITECTURE.md.
# --------------------------------------------------------------------------
