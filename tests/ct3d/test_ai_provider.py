# --------------------------------------------------------------------------
# E6 provider abstraction + registry (core/ai/provider.py, registry.py), and
# the production policy: no provider shipped, no AI framework imported, no
# download/install code, a failing provider isolated.
# --------------------------------------------------------------------------
import ast
import pathlib
import subprocess
import sys

import numpy as np
import pytest

from ai_stub_provider import StubAIProvider
from plugins.roi_viewer.core.ai import ENABLE_AI_SEGMENTATION
from plugins.roi_viewer.core.ai import provider as ai_provider
from plugins.roi_viewer.core.ai import registry as ai_registry
from plugins.roi_viewer.core.ai.prompts import AIPromptSet
from plugins.roi_viewer.core.ai.types import (
    AIInferenceRequest,
    AIProviderInfo,
    Capability,
    DeviceKind,
    PromptType,
    read_only_volume,
)

_PLUGIN = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "roi_viewer"
_HEAVY = ("torch", "tensorflow", "onnxruntime", "monai", "totalsegmentator", "segment_anything")


def _request(prompts=None, device=DeviceKind.AUTO, shape=(4, 6, 8)):
    volume = read_only_volume(np.zeros(shape, dtype=np.int16), (1.0, 1.0, 1.0))
    return AIInferenceRequest(volume=volume, prompts=(prompts or AIPromptSet()).snapshot(), device=device)


def _prompts_with_point(shape=(4, 6, 8)):
    prompts = AIPromptSet()
    prompts.add_point((2.0, 2.0, 1.0), (1.0, 1.0, 1.0), shape, positive=True)
    return prompts


# ------------------------------------------------------------------ registry
def test_registry_empty():
    reg = ai_registry.AIProviderRegistry()
    assert reg.list_providers() == []
    assert reg.probe_all() == []
    assert reg.get("stub") is None


def test_register_probe_get():
    reg = ai_registry.AIProviderRegistry()
    stub = StubAIProvider()
    reg.register(stub)
    assert reg.get("stub") is stub
    assert reg.list_providers()[0].available is False  # not probed yet
    [info] = reg.probe_all()
    assert info.available is True and info.provider_id == "stub"
    assert reg.available_providers() == [info]


def test_duplicate_or_nameless_provider_rejected():
    reg = ai_registry.AIProviderRegistry()
    reg.register(StubAIProvider())
    with pytest.raises(ValueError):
        reg.register(StubAIProvider())
    with pytest.raises(ValueError):
        reg.register(StubAIProvider(provider_id=""))


def test_unregister_closes_provider():
    reg = ai_registry.AIProviderRegistry()
    stub = StubAIProvider()
    reg.register(stub)
    assert reg.unregister("stub") is True
    assert stub.closed == 1
    assert reg.get("stub") is None and reg.list_providers() == []
    assert reg.unregister("stub") is False


class _BrokenProbe(StubAIProvider):
    def probe(self):
        raise RuntimeError("driver exploded")


class _BrokenClose(StubAIProvider):
    def close(self):
        raise RuntimeError("cannot release")


class _WrongInfo(StubAIProvider):
    def probe(self):
        return AIProviderInfo(provider_id="someone-else", display_name="x", available=True)


def test_probe_exception_isolated():
    reg = ai_registry.AIProviderRegistry()
    good = StubAIProvider(provider_id="good")
    reg.register(_BrokenProbe(provider_id="broken"))
    reg.register(_WrongInfo(provider_id="wrong"))
    reg.register(good)
    infos = {i.provider_id: i for i in reg.probe_all()}
    assert infos["broken"].available is False and "probe failed" in infos["broken"].unavailable_reason
    assert infos["wrong"].available is False
    assert infos["good"].available is True
    assert [i.provider_id for i in reg.available_providers()] == ["good"]


def test_close_exception_isolated():
    reg = ai_registry.AIProviderRegistry()
    good = StubAIProvider(provider_id="good")
    reg.register(_BrokenClose(provider_id="bad"))
    reg.register(good)
    reg.close_all()  # must not raise
    assert good.closed == 1


def test_missing_dependency_module_is_safe(tmp_path, monkeypatch):
    (tmp_path / "e6_provider_needs_missing_dep.py").write_text(
        "import a_framework_that_is_not_installed_e6\n"
        "def create_provider():\n    raise AssertionError('never reached')\n", encoding="utf-8")
    (tmp_path / "e6_provider_factory_fails.py").write_text(
        "def create_provider():\n    raise RuntimeError('weights path not configured')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    reg = ai_registry.load_known_providers(
        ai_registry.AIProviderRegistry(),
        ["e6_provider_needs_missing_dep", "e6_provider_factory_fails", "no_such_module_e6"])
    assert reg.list_providers() == []
    assert [name for name, _ in reg.load_errors] == [
        "e6_provider_needs_missing_dep", "e6_provider_factory_fails", "no_such_module_e6"]


def test_unavailable_provider_info_is_reported_not_raised():
    stub = StubAIProvider(available=False, requires_weights=True, reason="weights not found")
    info = stub.probe()
    assert info.available is False and info.requires_weights is True
    assert stub.validate_request(_request(_prompts_with_point())) == ai_provider.REQUEST_UNAVAILABLE


# ------------------------------------------------------------------ request checks
def test_request_checks():
    point_only = StubAIProvider(prompt_types=(PromptType.POSITIVE_POINT,))
    assert point_only.validate_request(_request()) == ai_provider.REQUEST_NEEDS_PROMPT
    assert point_only.validate_request(_request(_prompts_with_point())) is None
    negative = AIPromptSet()
    negative.add_point((2.0, 2.0, 1.0), (1.0, 1.0, 1.0), (4, 6, 8), positive=False)
    assert point_only.validate_request(_request(negative)) == ai_provider.REQUEST_PROMPT_UNSUPPORTED
    assert point_only.validate_request(_request(_prompts_with_point(), device=DeviceKind.CUDA)) == \
        ai_provider.REQUEST_DEVICE_UNSUPPORTED
    automatic = StubAIProvider(capabilities=(Capability.AUTOMATIC,))
    assert automatic.validate_request(_request()) is None


def test_request_volume_is_read_only():
    request = _request(_prompts_with_point())
    with pytest.raises(ValueError):
        request.volume.array[0, 0, 0] = 1
    assert request.volume.origin_xyz == (0.0, 0.0, 0.0)
    assert request.volume.index_order == ("z", "y", "x")


# ------------------------------------------------------------------ production policy
def test_feature_flag_default_off():
    assert ENABLE_AI_SEGMENTATION is False


def test_only_the_totalsegmentator_provider_is_shipped():
    """E6 shipped none; E6b adds exactly the real TotalSegmentator provider
    (no fake one). Loading it works whether or not the package is installed."""
    assert ai_registry.KNOWN_PROVIDER_MODULES == (".providers.totalsegmentator_provider",)
    reg = ai_registry.load_known_providers(ai_registry.AIProviderRegistry())
    assert [i.provider_id for i in reg.list_providers()] == ["totalsegmentator"] and reg.load_errors == []


def test_loading_and_probing_providers_imports_no_framework_when_package_missing():
    """Fresh interpreter: load the production registry (what ticking AI does)
    and probe it. Without TotalSegmentator installed nothing heavy loads."""
    import importlib.util

    if importlib.util.find_spec("totalsegmentator") is not None:
        pytest.skip("TotalSegmentator is installed here - its probe legitimately imports torch")
    code = (
        "import sys\n"
        "from plugins.roi_viewer.core.ai import registry as r\n"
        "reg = r.load_known_providers(r.AIProviderRegistry()); info = reg.probe_all()[0]\n"
        "print(info.available, info.unavailable_reason.split(':')[0])\n"
        f"print([m for m in {_HEAVY!r} + ('nnunetv2', 'nibabel') if m in sys.modules])\n"
    )
    root = pathlib.Path(__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    lines = out.stdout.strip().splitlines()
    assert lines[-2] == "False package_missing" and lines[-1] == "[]"


def test_no_fake_provider_in_plugin_source():
    for path in _PLUGIN.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                assert not any(w in node.name.lower() for w in ("dummy", "fake", "random", "stub", "mock")), \
                    f"{path.name}: {node.name}"


def test_no_ai_framework_or_download_code_in_plugin():
    for path in _PLUGIN.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                assert root not in _HEAVY, f"{path.name} imports {name}"
                assert root not in ("urllib", "requests", "http", "pip", "ensurepip"), f"{path.name} imports {name}"


def test_importing_plugin_loads_no_ai_framework():
    """Fresh interpreter: import the AI package and the Segmentation panel
    (which wires it) - none of the heavy frameworks may appear."""
    code = (
        "import sys\n"
        "import plugins.roi_viewer.core.ai.registry, plugins.roi_viewer.core.ai.job_controller\n"
        "import plugins.roi_viewer.gui.segmentation_panel\n"
        f"print([m for m in {_HEAVY!r} if m in sys.modules])\n"
    )
    root = pathlib.Path(__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


def test_provider_loads_when_invesalius_imports_the_plugin_as_roi_viewer():
    """Regression (30/09/2026, seen in the real application): InVesalius's
    PluginManager imports the plugin as the package "ROI Viewer"
    (invesalius.plugins.import_source). An absolute "plugins.roi_viewer..."
    provider module then loaded a second copy of core/ai and the registry
    rejected the probe ("probe returned invalid provider info"). Fresh
    interpreter, same loader as the application."""
    code = chr(10).join([
        "import sys, importlib",
        "import invesalius.data.slice_",
        "from invesalius.plugins import import_source",
        "sys.modules['ROI Viewer'] = import_source('ROI Viewer', 'plugins/roi_viewer/__init__.py')",
        "r = importlib.import_module('ROI Viewer.core.ai.registry')",
        "reg = r.load_known_providers(r.AIProviderRegistry())",
        "info = reg.probe_all()[0]",
        "print(repr(info.display_name))",
        "print(repr(info.unavailable_reason.split(':')[0]) if not info.available else 'AVAILABLE')",
        "print(any(m.startswith('plugins.roi_viewer') for m in sys.modules))",
    ])
    root = pathlib.Path(__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-2000:]
    name, state, duplicate = out.stdout.strip().splitlines()[-3:]
    assert name == "'TotalSegmentator'"  # the provider's own info, not the registry's rejection
    assert state in ("AVAILABLE", "'package_missing'", "'dependency_missing'", "'api_incompatible'",
                     "'weights_missing'")
    assert duplicate == "False"  # no second copy of the plugin package
