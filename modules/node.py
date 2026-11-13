"""Small pieces every node module shares: the menu root, progress, node identity and stacking."""

from __future__ import annotations

from typing import Any

import torch

#: Root of every Jovimetrix menu category.
CATEGORY_ROOT = "JOVIMETRIX 🔺🟩🔵"


def category(name: str) -> str:
    """Return a full menu category under the Jovimetrix root.

    Args:
        name: Sub-category, such as ``"ADJUST"``.

    Returns:
        The category path.
    """
    return f"{CATEGORY_ROOT}/{name}"


class Progress:
    """ComfyUI's progress bar for one node run, or nothing when there is no server."""

    def __init__(self, total: int) -> None:
        try:
            from comfy.utils import ProgressBar

            self._bar = ProgressBar(max(1, int(total)))
        except Exception:
            self._bar = None

    def update(self, index: int) -> None:
        """Report that step ``index`` has finished."""
        if self._bar is not None:
            self._bar.update_absolute(index + 1)


def node_id(cls: Any) -> str:
    """Return the unique id of the node being run.

    Args:
        cls: The per-run node class ``execute`` receives.

    Returns:
        The id as a string, empty when the run carries none.
    """
    hidden = getattr(cls, "hidden", None)
    ident = getattr(hidden, "unique_id", None) if hidden is not None else None
    return "" if ident is None else str(ident)


def image_stack(images: list[Any]) -> list[torch.Tensor]:
    """Turn one tuple of tensors per batch entry into one batch tensor per output.

    Args:
        images: ``[(rgba, rgb, mask), ...]`` or any equal-length tuples of ``(H, W, ...)`` tensors.

    Returns:
        One stacked tensor per position.

    Raises:
        ValueError: There is nothing to stack.
    """
    if not images:
        raise ValueError("The node produced no images. Connect an input or check its settings.")
    return [torch.stack(list(parts)) for parts in zip(*images)]
