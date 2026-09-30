# --------------------------------------------------------------------------
# E6 provider registry. One misbehaving provider (import error, probe()
# raising, close() raising) is isolated: it is reported unavailable, never
# allowed to break the plugin or the other providers.
# --------------------------------------------------------------------------
import importlib
from typing import Dict, List, Optional, Tuple

from .provider import AISegmentationProvider
from .types import AIProviderInfo

# Production providers, as importable module names exposing
# create_provider() -> AISegmentationProvider. EMPTY in E6: there is no
# real model yet, and no fake one is shipped. E6b adds its module here.
KNOWN_PROVIDER_MODULES: Tuple[str, ...] = ()


def _unavailable(provider_id: str, reason: str) -> AIProviderInfo:
    return AIProviderInfo(provider_id=provider_id, display_name=provider_id, available=False,
                          unavailable_reason=reason)


class AIProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, AISegmentationProvider] = {}
        self._info: Dict[str, AIProviderInfo] = {}
        self.load_errors: List[Tuple[str, str]] = []  # (module, error) from load_known_providers()

    def register(self, provider: AISegmentationProvider) -> None:
        pid = getattr(provider, "provider_id", "")
        if not pid:
            raise ValueError("provider has no provider_id")
        if pid in self._providers:
            raise ValueError(f"provider '{pid}' already registered")
        self._providers[pid] = provider
        self._info[pid] = _unavailable(pid, "not probed")

    def unregister(self, provider_id: str) -> bool:
        provider = self._providers.pop(provider_id, None)
        self._info.pop(provider_id, None)
        if provider is None:
            return False
        self._close_one(provider_id, provider)
        return True

    def get(self, provider_id: str) -> Optional[AISegmentationProvider]:
        return self._providers.get(provider_id)

    def info(self, provider_id: str) -> Optional[AIProviderInfo]:
        return self._info.get(provider_id)

    def list_providers(self) -> List[AIProviderInfo]:
        """Last probed info of every registered provider, registration order."""
        return [self._info[pid] for pid in self._providers]

    def probe(self, provider_id: str) -> Optional[AIProviderInfo]:
        provider = self._providers.get(provider_id)
        if provider is None:
            return None
        try:
            info = provider.probe()
            if not isinstance(info, AIProviderInfo) or info.provider_id != provider_id:
                info = _unavailable(provider_id, "probe returned invalid provider info")
        except Exception as e:
            print(f"ROI Viewer: AI provider '{provider_id}' probe failed - {e}")
            info = _unavailable(provider_id, f"probe failed: {e}")
        self._info[provider_id] = info
        return info

    def probe_all(self) -> List[AIProviderInfo]:
        return [self.probe(pid) for pid in list(self._providers)]

    def available_providers(self) -> List[AIProviderInfo]:
        return [i for i in self.list_providers() if i.available]

    def close_all(self) -> None:
        for pid, provider in list(self._providers.items()):
            self._close_one(pid, provider)

    @staticmethod
    def _close_one(provider_id, provider):
        try:
            provider.close()
        except Exception as e:
            print(f"ROI Viewer: AI provider '{provider_id}' close failed - {e}")


def load_known_providers(registry: AIProviderRegistry, module_names=None) -> AIProviderRegistry:
    """Imports each provider module and registers create_provider()'s result.
    A module that fails to import (missing optional dependency) or to build
    its provider is recorded in registry.load_errors and skipped."""
    for name in KNOWN_PROVIDER_MODULES if module_names is None else module_names:
        try:
            module = importlib.import_module(name)
            registry.register(module.create_provider())
        except Exception as e:
            print(f"ROI Viewer: AI provider module '{name}' not loaded - {e}")
            registry.load_errors.append((name, str(e)))
    return registry
