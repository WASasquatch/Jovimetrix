"""The TrueType and OpenType fonts installed on the machine, keyed by family name.

The list is built once, on a worker thread when ``warm`` is called, and kept for the session.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from . import log

logger = log.get_logger("fonts")

#: Extensions read as fonts.
FONT_EXTENSIONS = (".ttf", ".otf", ".ttc")

#: Most font files read from all folders together.
MAX_FONTS = 5000

#: Menu entry that draws with Pillow's built-in font.
DEFAULT_FONT = "default"

_lock = threading.Lock()
_fonts: dict[str, str] | None = None


def font_folders() -> list[Path]:
    """Return the folders this platform keeps fonts in.

    Returns:
        Existing folders only.
    """
    home = Path.home()
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        folders = [windir / "Fonts", local / "Microsoft/Windows/Fonts"]
    elif sys.platform == "darwin":
        folders = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library/Fonts"]
    else:
        folders = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                   home / ".fonts", home / ".local/share/fonts"]
    folders.extend(_bundled_folders())
    return [f for f in folders if f.is_dir()]


def _bundled_folders() -> list[Path]:
    """Return the font folder matplotlib ships, when it is installed, without importing it."""
    import importlib.util

    try:
        spec = importlib.util.find_spec("matplotlib")
    except (ImportError, ValueError):
        return []
    if spec is None or not spec.origin:
        return []
    return [Path(spec.origin).parent / "mpl-data" / "fonts" / "ttf"]


def _walk(folder: Path):
    """Yield font files below ``folder`` without descending links or junctions."""
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))
                   and not _is_junction(os.path.join(root, d))]
        for name in files:
            if name.lower().endswith(FONT_EXTENSIONS):
                yield Path(root) / name


def _is_junction(path: str) -> bool:
    checker = getattr(os.path, "isjunction", None)
    return bool(checker and checker(path))


def _scan() -> dict[str, str]:
    from PIL import ImageFont

    found: dict[str, tuple[int, str]] = {}
    count = 0
    for folder in font_folders():
        for path in _walk(folder):
            count += 1
            if count > MAX_FONTS:
                logger.warning("more than %d font files found; the rest are not listed", MAX_FONTS)
                break
            try:
                family, style = ImageFont.truetype(str(path), 12).getname()
            except Exception:
                continue
            if not family:
                continue
            family = str(family).strip()
            style = str(style or "").strip()
            regular = style.lower() in ("regular", "normal", "book", "roman", "")
            rank = 0 if regular else 1
            if family not in found or rank < found[family][0]:
                found[family] = (rank, str(path))
            if not regular:
                styled = f"{family} {style}"
                found.setdefault(styled, (0, str(path)))
    fonts = {name: path for name, (_, path) in sorted(found.items(), key=lambda kv: kv[0].lower())}
    logger.info("%d font families found", len(fonts))
    return fonts


def font_names() -> dict[str, str]:
    """Return every installed font family mapped to a file, plus the built-in font.

    Returns:
        ``{name: path}``, names sorted; ``DEFAULT_FONT`` maps to an empty path.
    """
    global _fonts
    with _lock:
        if _fonts is None:
            try:
                _fonts = _scan()
            except Exception as error:
                logger.warning("fonts could not be listed (%s)", type(error).__name__)
                _fonts = {}
            _fonts.setdefault(DEFAULT_FONT, "")
        return dict(_fonts)


def warm() -> None:
    """Build the font list on a worker thread."""
    threading.Thread(target=font_names, name="jovimetrix-fonts", daemon=True).start()


def load(name: str, size: float):
    """Open a font by menu name at a size in pixels.

    Args:
        name: A key of ``font_names()``.
        size: Size in pixels.

    Returns:
        A Pillow font.
    """
    from PIL import ImageFont

    size = max(1, int(round(size)))
    path = font_names().get(name, "")
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            logger.warning("font '%s' could not be opened, using the built-in font", name)
    return ImageFont.load_default(size)
