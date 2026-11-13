"""Ceilings on what a node may allocate from its inputs. Sizes are in pixels."""

from __future__ import annotations

#: Largest width or height of a canvas a node builds.
MAX_CANVAS_SIDE = 16384

#: Largest pixel count of a canvas a node builds.
MAX_CANVAS_PIXELS = 268435456

#: Largest pixel count of all the frames of one batch a node builds together.
MAX_BATCH_PIXELS = 1073741824

#: Largest number of entries a Queue list holds.
MAX_QUEUE_ENTRIES = 50000

#: Largest text or JSON file a Queue reads, in bytes.
MAX_QUEUE_FILE_BYTES = 16 * 1024 * 1024


def check_canvas(width: int, height: int, source: str = "wh") -> tuple[int, int]:
    """Refuse a canvas size past the ceilings.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        source: Name of the input the size came from, for the message.

    Returns:
        ``(width, height)`` as integers.

    Raises:
        ValueError: A side or the pixel count is past its ceiling.
    """
    width, height = int(width), int(height)
    if width > MAX_CANVAS_SIDE or height > MAX_CANVAS_SIDE:
        raise ValueError(
            f"{width} x {height} from '{source}' is larger than Jovimetrix allows: each side "
            f"is limited to {MAX_CANVAS_SIDE} pixels. Lower '{source}'."
        )
    if width * height > MAX_CANVAS_PIXELS:
        raise ValueError(
            f"{width} x {height} from '{source}' is {width * height} pixels, past the "
            f"{MAX_CANVAS_PIXELS} pixel limit. Lower '{source}'."
        )
    return width, height


def check_batch(width: int, height: int, count: int, source: str = "wh") -> tuple[int, int]:
    """Refuse a batch of frames past the ceilings.

    Args:
        width: Width of each frame in pixels.
        height: Height of each frame in pixels.
        count: Number of frames.
        source: Name of the input the size came from, for the message.

    Returns:
        ``(width, height)`` as integers.

    Raises:
        ValueError: A frame or the whole batch is past its ceiling.
    """
    width, height = check_canvas(width, height, source)
    total = width * height * max(1, int(count))
    if total > MAX_BATCH_PIXELS:
        raise ValueError(
            f"{count} frames of {width} x {height} from '{source}' come to {total} pixels, past "
            f"the {MAX_BATCH_PIXELS} pixel limit for one batch. Use fewer or smaller frames."
        )
    return width, height
