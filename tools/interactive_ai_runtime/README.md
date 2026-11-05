# ROI Viewer interactive-AI runtime (MedSAM2)

This is the separate Python process that runs MedSAM2 for ROI Viewer's experimental "Phân đoạn AI tương tác (MedSAM2)". InVesalius's own environment is never changed: the plugin only starts `worker.py` with the command you configure, and talks to it over stdin/stdout using JSON Lines (`protocol.py`).

| File | Role |
|---|---|
| `worker.py` | Persistent worker loop. Standard library and numpy only. |
| `protocol.py` | Byte-identical copy of `plugins/roi_viewer/core/ai/external/protocol.py`. A test checks that the two are identical. |
| `providers/medsam2_provider.py` | MedSAM2 inference, following the official `medsam2_infer_3D_CT.py`. Imports torch and sam2 lazily. |
| `probe_runtime.py` | Stand-alone smoke probe (HELLO + PROBE) that runs without InVesalius. |
| `setup_medsam2_linux.sh` | Builds the separate environment on Linux or WSL2. This is the documented platform. |
| `setup_medsam2_windows.ps1` | Builds the separate environment on native Windows. Experimental: skips the optional CUDA extension. |
| `interactive_ai.example.json` | Example of the configuration file the plugin reads. |

## Setup (operator, by hand)

1. Run one of the setup scripts with a new environment folder and a MedSAM2 checkout folder. The scripts:
   - pin MedSAM2 `332f30d4` (Apache-2.0)
   - pin torch 2.5.1 / torchvision 0.20.1 with CUDA 12.4
   - never touch `invx-venv`
2. Download a checkpoint yourself, after reading its licence, from https://huggingface.co/wanglab/MedSAM2. `MedSAM2_latest.pt` is the recommended one. The weights card says "research and education purposes" only, while the repository metadata says CC-BY-SA-4.0; check both before any other use. Neither the scripts nor the plugin download weights.
3. Copy `interactive_ai.example.json` to `<InVesalius user dir>/roi_viewer_interactive_ai.json`, and fill in the real paths:
   - `runtime_command` uses host paths.
   - `provider_config` uses worker paths.

   You can instead point the environment variable `ROI_VIEWER_INTERACTIVE_AI_CONFIG` at the file. For a worker inside WSL, use `"path_style": "wsl"` and a command such as `["wsl.exe", "-d", "Ubuntu", "--", "/home/<you>/medsam2-env/bin/python", "/mnt/d/.../worker.py"]`.
4. Check the runtime from the repository root with `python tools/interactive_ai_runtime/probe_runtime.py <config.json>`. Exit code 0 means the model is available.
5. In ROI Viewer, open Phân đoạn → AI and do the following:
   1. Tick "Bật phân đoạn AI".
   2. Choose "Phân đoạn AI tương tác (MedSAM2)".
   3. Click "Kiểm tra môi trường".

## What the provider really supports (official-source audit, 05/11/2026)

- **Box: yes.** You set it with two corners at the 2D cursor. It is used as a 2D box on its middle slice, and the result is limited to the box's slice range. A box drawn on a single slice propagates through the whole volume, as in the official script.
- **Positive points: yes.** This is the same SAM2 call the official RECIST script uses with label-1 points.
- **Negative points: off by default.** SAM2's API accepts label 0, but no official MedSAM2 path uses it. Set `"allow_negative_points": true` to try it experimentally.
- **3D:** forward and reverse propagation from the slices that carry prompts. The largest connected component is kept, as in the official script.
- **CPU:** the library falls back to CPU, but the official scripts use CUDA only. CPU is untested here.

Full details are in `docs/CT3D_INTERACTIVE_AI_ARCHITECTURE.md`.
