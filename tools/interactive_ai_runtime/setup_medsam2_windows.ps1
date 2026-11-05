# --------------------------------------------------------------------------
# Separate MedSAM2 environment on NATIVE Windows - EXPERIMENTAL.
# MedSAM2's README documents Linux only and SAM2's INSTALL.md recommends
# WSL on Windows; use setup_medsam2_linux.sh inside WSL2 when WSL works.
# This path skips the optional CUDA extension (SAM2_BUILD_CUDA=0; per
# SAM2's INSTALL.md it "shouldn't affect the results in most cases").
#
# These are the steps that were really run on 05/11/2026 (RTX 4060 Laptop,
# driver 560.92 / CUDA 12.6, Python 3.11.7 - the py launcher's 3.12 entry
# was broken on that machine; MedSAM2's setup.py requires >= 3.10).
#
# RUN BY THE OPERATOR, BY HAND, in NEW folders. Never touches InVesalius's
# environment (invx-venv) or the base Python's packages; no pip cache is
# written (--no-cache-dir). Never downloads the model checkpoint.
#
#   powershell -ExecutionPolicy Bypass -File setup_medsam2_windows.ps1 `
#       -EnvDir D:\PyTools\medsam2-venv -RepoDir D:\PyTools\MedSAM2 [-PythonVersion 3.11]
#
# Rollback: delete EnvDir and RepoDir (and the plugin's
# roi_viewer_interactive_ai.json if it was written). Nothing else changes.
# --------------------------------------------------------------------------
param(
    [Parameter(Mandatory = $true)][string]$EnvDir,
    [Parameter(Mandatory = $true)][string]$RepoDir,
    [string]$PythonVersion = "3.11"
)
$ErrorActionPreference = "Stop"
$Commit = "332f30d420f1d1b08e2a79b3ae6a602458808383"

if (Test-Path $EnvDir) { throw "refusing: $EnvDir already exists" }
& py "-$PythonVersion" -m venv $EnvDir
$Py = Join-Path $EnvDir "Scripts\python.exe"
& $Py -m pip install --no-cache-dir --upgrade pip
& $Py -m pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
# build tools for the editable install without build isolation (otherwise
# pip would download a second, CPU-only torch just to build MedSAM2)
& $Py -m pip install --no-cache-dir --upgrade "setuptools>=61" wheel

if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
    git clone https://github.com/bowang-lab/MedSAM2.git $RepoDir
}
git -C $RepoDir checkout --quiet $Commit
$env:SAM2_BUILD_CUDA = "0"
Push-Location $RepoDir
try { & $Py -m pip install --no-cache-dir --no-build-isolation -e . } finally { Pop-Location }
# used by the worker provider (largest connected component)
& $Py -m pip install --no-cache-dir scipy

& $Py -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); import sam2.build_sam as b; assert hasattr(b, 'build_sam2_video_predictor_npz'); print('sam2 (MedSAM2) import OK')"

$Ckpt = Join-Path $RepoDir "checkpoints\MedSAM2_latest.pt"
if (-not (Test-Path $Ckpt)) {
    Write-Host ""
    Write-Host "Checkpoint NOT found: $Ckpt"
    Write-Host "Download it yourself (after reading the licence) from https://huggingface.co/wanglab/MedSAM2"
    Write-Host "MedSAM2_latest.pt: 156040129 bytes, sha256 c92743b99f00d078bf32a3afcc38aaa9faf1c1692dffe3eaa7a90938c1991060"
    Write-Host "This script does not download model weights."
}
Write-Host ""
Write-Host "Next: write roi_viewer_interactive_ai.json (see interactive_ai.example.json) with"
Write-Host "  runtime_command = [`"$Py`", `"<repo>\tools\interactive_ai_runtime\worker.py`"]"
Write-Host "then:  python tools\interactive_ai_runtime\probe_runtime.py <config.json>"
