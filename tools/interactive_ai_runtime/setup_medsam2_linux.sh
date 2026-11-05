#!/usr/bin/env bash
# --------------------------------------------------------------------------
# Separate MedSAM2 environment for the ROI Viewer interactive-AI runtime -
# Linux or WSL2 Ubuntu (the platform MedSAM2's README and SAM2's INSTALL.md
# document). RUN BY THE OPERATOR, BY HAND. It never touches InVesalius's
# environment (invx-venv) and never downloads the model checkpoint.
#
#   bash setup_medsam2_linux.sh <env_dir> <medsam2_checkout_dir>
#
# Pins (audit 05/11/2026, docs/CT3D_INTERACTIVE_AI_ARCHITECTURE.md):
#   MedSAM2 main @ 332f30d420f1d1b08e2a79b3ae6a602458808383 (Apache-2.0)
#   Python 3.12 (README; setup.py: >= 3.10)
#   torch 2.5.1 / torchvision 0.20.1, CUDA 12.4 wheels (README)
# The checkpoint (wanglab/MedSAM2 on Hugging Face, MedSAM2_latest.pt,
# weights card: research/education use) must be downloaded by the operator
# after reading its licence, into <medsam2_checkout_dir>/checkpoints/.
# --------------------------------------------------------------------------
set -euo pipefail
ENV_DIR="${1:?usage: setup_medsam2_linux.sh <env_dir> <medsam2_checkout_dir>}"
REPO_DIR="${2:?usage: setup_medsam2_linux.sh <env_dir> <medsam2_checkout_dir>}"
COMMIT=332f30d420f1d1b08e2a79b3ae6a602458808383
PYTHON="${PYTHON:-python3.12}"

if [ -e "$ENV_DIR" ]; then echo "refusing: $ENV_DIR already exists"; exit 1; fi
"$PYTHON" -m venv "$ENV_DIR"
PY="$ENV_DIR/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone https://github.com/bowang-lab/MedSAM2.git "$REPO_DIR"
fi
git -C "$REPO_DIR" fetch --quiet origin "$COMMIT" || true
git -C "$REPO_DIR" checkout --quiet "$COMMIT"
# The optional CUDA post-processing extension may fail to build; MedSAM2's
# setup.py then continues (SAM2_BUILD_ALLOW_ERRORS=1).
"$PY" -m pip install --upgrade "setuptools>=61" wheel
(cd "$REPO_DIR" && SAM2_BUILD_ALLOW_ERRORS=1 "$PY" -m pip install --no-build-isolation -e .)
"$PY" -m pip install scipy  # used by the worker provider (largest connected component)

"$PY" - <<'EOF'
import torch
print("torch", torch.__version__, "cuda available", torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
import sam2.build_sam as b
assert hasattr(b, "build_sam2_video_predictor_npz"), "not the MedSAM2 fork of sam2"
print("sam2 (MedSAM2) import OK")
EOF

if [ ! -f "$REPO_DIR/checkpoints/MedSAM2_latest.pt" ]; then
  echo
  echo "Checkpoint NOT found: $REPO_DIR/checkpoints/MedSAM2_latest.pt"
  echo "Download it yourself (after reading the licence) from"
  echo "  https://huggingface.co/wanglab/MedSAM2"
  echo "This script does not download model weights."
fi
echo
echo "Next: write roi_viewer_interactive_ai.json (see interactive_ai.example.json) with"
echo "  runtime_command = [\"$PY\", \"<repo>/tools/interactive_ai_runtime/worker.py\"]"
echo "then run:  python tools/interactive_ai_runtime/probe_runtime.py <config.json>"
