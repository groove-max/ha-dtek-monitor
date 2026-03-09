"""Helpers for loading component modules without importing Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

COMPONENT_ROOT = (
    Path(__file__).resolve().parents[1] / "custom_components" / "dtek_monitor"
)


def load_component_module(module_name: str):
    """Load a component module while bypassing the package __init__ import."""
    _ensure_namespace_package("custom_components", COMPONENT_ROOT.parent)
    _ensure_namespace_package("custom_components.dtek_monitor", COMPONENT_ROOT)

    full_name = f"custom_components.dtek_monitor.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = COMPONENT_ROOT / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_namespace_package(name: str, path: Path) -> None:
    """Ensure a namespace package exists in sys.modules for relative imports."""
    if name in sys.modules:
        return

    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module
