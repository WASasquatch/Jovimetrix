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


def stack_runs(frames: list[torch.Tensor]) -> list[torch.Tensor]:
    """Stack frames into batches, starting a new batch wherever the frame size changes.

    Frames of one size give one batch, as before; a list of pictures of different sizes gives
    one batch per run of equal sizes instead of failing to stack.

    Args:
        frames: Tensors such as ``(H, W, C)`` frames or ``(H, W)`` masks.

    Returns:
        The batches, in order.
    """
    batches: list[torch.Tensor] = []
    run: list[torch.Tensor] = []
    for frame in frames:
        if run and frame.shape != run[-1].shape:
            batches.append(torch.stack(run))
            run = []
        run.append(frame)
    if run:
        batches.append(torch.stack(run))
    return batches


def image_stack(images: list[Any]) -> list[list[torch.Tensor]]:
    """Turn one tuple of tensors per batch entry into one list of batches per output.

    The outputs this feeds are list outputs. Frames that share a size become one batch, so a
    batch in gives a batch out; differently sized frames (a list of pictures, or settings that
    change the size per frame) give one batch per run of equal sizes.

    Args:
        images: ``[(rgba, rgb, mask), ...]`` or any equal-length tuples of ``(H, W, ...)`` tensors.

    Returns:
        One list of batches per position.

    Raises:
        ValueError: There is nothing to stack.
    """
    if not images:
        raise ValueError("The node produced no images. Connect an input or check its settings.")
    outputs: list[list[torch.Tensor]] = [[] for _ in images[0]]
    run: list[Any] = []
    for item in images:
        if run and any(a.shape != b.shape for a, b in zip(item, run[-1])):
            for out, parts in zip(outputs, zip(*run)):
                out.append(torch.stack(list(parts)))
            run = []
        run.append(item)
    for out, parts in zip(outputs, zip(*run)):
        out.append(torch.stack(list(parts)))
    return outputs
