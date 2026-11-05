# --------------------------------------------------------------------------
# Interactive-AI runtime configuration. READ ONLY - the plugin never writes,
# creates or edits it, and never touches InVesalius's config.json/state.json.
#
# Location (first that exists):
#   1. the file named by the environment variable ENV_CONFIG_PATH
#   2. <InVesalius user dir>/roi_viewer_interactive_ai.json
#      (invesalius.inv_paths.USER_INV_DIR - honours XDG_CONFIG_HOME)
# No file, "enabled": false, or a missing runtime_command -> the feature is
# off and the UI says "MedSAM2 chưa được cấu hình". Source defaults contain
# no machine-specific path; see tools/interactive_ai_runtime/
# interactive_ai.example.json.
#
# Keys
#   enabled            bool  (default false)
#   provider           "medsam2"
#   runtime_command    list of strings: the worker's command line, e.g.
#                      [".../envs/medsam2/python", ".../worker.py"] or
#                      ["wsl.exe", "-d", "Ubuntu", "--", "/home/u/m2/bin/python",
#                       "/mnt/d/.../tools/interactive_ai_runtime/worker.py"]
#   path_style         "native" | "wsl" (how the worker sees host temp paths)
#   provider_config    object passed to the worker's provider as-is
#                      (checkpoint path, model config, ... in WORKER paths)
#   start_timeout_s    worker start + HELLO (default 120)
#   probe_timeout_s    PROBE incl. imports (default 300)
#   load_timeout_s     LOAD_VOLUME (default 300)
#   predict_timeout_s  PREDICT (default 900)
# --------------------------------------------------------------------------
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

ENV_CONFIG_PATH = "ROI_VIEWER_INTERACTIVE_AI_CONFIG"
CONFIG_FILE_NAME = "roi_viewer_interactive_ai.json"

NOT_CONFIGURED_NO_FILE = "no_file"
NOT_CONFIGURED_DISABLED = "disabled"
NOT_CONFIGURED_INVALID = "invalid"


@dataclass(frozen=True)
class InteractiveAIConfig:
    enabled: bool = False
    provider: str = "medsam2"
    runtime_command: Tuple[str, ...] = ()
    path_style: str = "native"
    provider_config: dict = field(default_factory=dict)
    start_timeout_s: float = 120.0
    probe_timeout_s: float = 300.0
    load_timeout_s: float = 300.0
    predict_timeout_s: float = 900.0
    source: str = ""  # file it was read from
    problem: str = ""  # NOT_CONFIGURED_* code when unusable
    problem_detail: str = ""

    @property
    def usable(self) -> bool:
        return not self.problem


def default_config_path() -> Optional[Path]:
    try:
        import invesalius.inv_paths as inv_paths

        return Path(inv_paths.USER_INV_DIR) / CONFIG_FILE_NAME
    except Exception:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(base) / "invesalius" / CONFIG_FILE_NAME


def load_config(path=None) -> InteractiveAIConfig:
    if path is None:
        env = os.environ.get(ENV_CONFIG_PATH)
        path = Path(env) if env else default_config_path()
    path = Path(path) if path else None
    if path is None or not path.is_file():
        return InteractiveAIConfig(problem=NOT_CONFIGURED_NO_FILE, problem_detail=f"no file {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        command = data.get("runtime_command") or []
        if not isinstance(command, list) or not all(isinstance(c, str) and c for c in command):
            raise ValueError("runtime_command must be a list of non-empty strings")
        provider_config = data.get("provider_config") or {}
        if not isinstance(provider_config, dict):
            raise ValueError("provider_config must be an object")
        path_style = str(data.get("path_style", "native"))
        if path_style not in ("native", "wsl"):
            raise ValueError("path_style must be 'native' or 'wsl'")

        def seconds(key, default):
            value = float(data.get(key, default))
            if not value > 0:
                raise ValueError(f"{key} must be > 0")
            return value

        config = InteractiveAIConfig(
            enabled=data.get("enabled") is True,
            provider=str(data.get("provider", "medsam2")),
            runtime_command=tuple(command),
            path_style=path_style,
            provider_config=dict(provider_config),
            start_timeout_s=seconds("start_timeout_s", 120),
            probe_timeout_s=seconds("probe_timeout_s", 300),
            load_timeout_s=seconds("load_timeout_s", 300),
            predict_timeout_s=seconds("predict_timeout_s", 900),
            source=str(path),
        )
    except (OSError, ValueError, TypeError) as e:
        return InteractiveAIConfig(source=str(path), problem=NOT_CONFIGURED_INVALID, problem_detail=str(e))
    if not config.enabled:
        return InteractiveAIConfig(source=str(path), problem=NOT_CONFIGURED_DISABLED,
                                   problem_detail='"enabled" is not true')
    if not config.runtime_command:
        return InteractiveAIConfig(source=str(path), problem=NOT_CONFIGURED_INVALID,
                                   problem_detail="runtime_command is empty")
    return config
