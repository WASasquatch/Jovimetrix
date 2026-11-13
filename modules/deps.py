"""Third-party packages, imported when a node first needs one."""

from __future__ import annotations

import importlib
from types import ModuleType

#: Import name to the name pip installs it under.
PIP_NAMES = {
    "cv2": "opencv-contrib-python",
    "blendmodes": "blendmodes",
    "daltonlens": "daltonlens",
}


class DependencyError(ImportError):
    """A package a node needs is not installed."""


def install_command(module: str) -> str:
    """Return the pip command that installs ``module``.

    Args:
        module: Import name, such as ``"cv2"``.

    Returns:
        The command line.
    """
    return f"python -m pip install {PIP_NAMES.get(module.split('.')[0], module)}"


def require(module: str) -> ModuleType:
    """Import ``module`` or raise with the command that installs it.

    Args:
        module: Import name, such as ``"cv2"`` or ``"blendmodes.blend"``.

    Returns:
        The imported module.

    Raises:
        DependencyError: The package is not installed.
    """
    try:
        return importlib.import_module(module)
    except ImportError as error:
        raise DependencyError(
            f"Jovimetrix needs the '{PIP_NAMES.get(module.split('.')[0], module)}' package "
            f"for this node and it is not installed. Run `{install_command(module)}` with the "
            "Python that runs ComfyUI (python_embeded\\python.exe on the Windows portable "
            "build), then restart ComfyUI."
        ) from error
