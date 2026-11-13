"""The folders a node may read and write, and the only place a typed path becomes a real one.

Reads: ComfyUI ``input``, ``output`` and ``temp``, the pack's own ``res`` folder, and every
``allow_read`` folder. Writes: ``output``, ``temp`` and every ``allow_write`` folder.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import config, log

logger = log.get_logger("sandbox")

PACK_ROOT = Path(__file__).resolve().parent.parent

#: Windows device names, refused as a file or folder name on every platform.
_DEVICE = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9]|conin\$|conout\$)(\..*)?$", re.IGNORECASE)

#: Longest value echoed back in a refusal.
_SHOWN = 200


class PathNotAllowed(PermissionError):
    """A path names a place outside the folders a node may use."""


def _shown(value: str) -> str:
    """Return ``value`` as typed, cut short for a message."""
    value = str(value)
    return value if len(value) <= _SHOWN else value[:_SHOWN] + "..."


def _folder(path: str | Path) -> Path:
    """Resolve a folder without requiring it to exist."""
    return Path(os.path.abspath(os.path.expanduser(str(path)))).resolve(strict=False)


def read_roots() -> list[tuple[str, Path]]:
    """Return every folder a node may read, each with the label a message uses.

    Returns:
        ``(label, folder)`` pairs.
    """
    import folder_paths

    roots = [
        ("input", _folder(folder_paths.get_input_directory())),
        ("output", _folder(folder_paths.get_output_directory())),
        ("temp", _folder(folder_paths.get_temp_directory())),
        ("jovimetrix/res", _folder(PACK_ROOT / "res")),
    ]
    roots.extend(("allow_read", _folder(p)) for p in config.get("allow_read"))
    return roots


def write_roots() -> list[tuple[str, Path]]:
    """Return every folder a node may write into, each with the label a message uses.

    Returns:
        ``(label, folder)`` pairs.
    """
    import folder_paths

    roots = [
        ("output", _folder(folder_paths.get_output_directory())),
        ("temp", _folder(folder_paths.get_temp_directory())),
    ]
    roots.extend(("allow_write", _folder(p)) for p in config.get("allow_write"))
    return roots


def contains(root: Path, path: Path) -> bool:
    """Report whether ``path`` lies inside ``root``. Both must already be resolved.

    Args:
        root: A resolved folder.
        path: A resolved path.

    Returns:
        ``True`` when ``path`` is ``root`` or below it.
    """
    root_text = os.path.normcase(str(root))
    path_text = os.path.normcase(str(path))
    if path_text == root_text:
        return True
    return path_text.startswith(root_text.rstrip("\\/") + os.sep)


def _within(path: Path, roots: list[tuple[str, Path]]) -> bool:
    return any(contains(root, path) for _, root in roots)


def _permitted(roots: list[tuple[str, Path]]) -> str:
    labels = list(dict.fromkeys(label for label, _ in roots))
    return ", ".join(labels)


def resolve_read(value: str) -> Path:
    """Turn a typed path into one a node may read.

    A relative path is looked up under the pack folder first, then under ComfyUI ``input``.

    Args:
        value: The path as the workflow holds it.

    Returns:
        The resolved path, which need not exist.

    Raises:
        PathNotAllowed: The path is empty or lies outside every readable folder.
    """
    text = str(value or "").strip()
    if not text:
        raise PathNotAllowed("No path was given. Type a file or folder path to read.")
    roots = read_roots()
    raw = Path(text)
    if raw.is_absolute() or raw.drive:
        candidates = [raw]
    else:
        import folder_paths

        candidates = [PACK_ROOT / raw, Path(folder_paths.get_input_directory()) / raw]
    resolved = [Path(os.path.abspath(c)).resolve(strict=False) for c in candidates]
    chosen = next((p for p in resolved if p.exists()), resolved[-1])
    if not _within(chosen, roots):
        logger.debug("read refused for %s", chosen)
        raise PathNotAllowed(
            f"refusing to read `{_shown(text)}`. It is outside every folder Jovimetrix may "
            f"read: {_permitted(roots)}. Add the folder to allow_read in "
            "ComfyUI/user/jovimetrix/config.json to permit it."
        )
    return chosen


def check_name(name: str) -> str:
    """Refuse a file name that is not one plain name.

    Args:
        name: The name, such as ``"render_0001.png"``.

    Returns:
        The name, stripped of surrounding spaces.

    Raises:
        PathNotAllowed: The name is empty, holds a separator, a drive, ``..`` or a device name.
    """
    text = str(name or "").strip()
    if not text:
        raise PathNotAllowed("The file name is empty. Type a name for the file.")
    if any(ch in text for ch in ("/", "\\", ":", "\0")) or text in (".", "..") \
            or _DEVICE.match(text.rstrip(". ")) or text != text.rstrip(". "):
        raise PathNotAllowed(
            f"`{_shown(text)}` is not a plain file name. A name holds no folder separator, "
            "drive, '..', trailing dot or Windows device name such as NUL or COM1."
        )
    return text


def resolve_write_dir(value: str) -> Path:
    """Turn a typed folder into one a node may write into.

    An empty value is ComfyUI ``output``; a relative one lies below it.

    Args:
        value: The folder as the workflow holds it.

    Returns:
        The resolved folder, which need not exist yet.

    Raises:
        PathNotAllowed: The folder lies outside every writable folder.
    """
    import folder_paths

    text = str(value or "").strip()
    roots = write_roots()
    output = Path(folder_paths.get_output_directory())
    raw = Path(text) if text else output
    if not (raw.is_absolute() or raw.drive):
        raw = output / raw
    for part in raw.parts[1:]:
        if _DEVICE.match(part.rstrip(". ")):
            raise PathNotAllowed(f"`{_shown(text)}` names a Windows device and cannot be written to.")
    resolved = Path(os.path.abspath(raw)).resolve(strict=False)
    if not _within(resolved, roots):
        logger.debug("write refused for %s", resolved)
        raise PathNotAllowed(
            f"refusing to write into `{_shown(text)}`. It is outside every folder Jovimetrix "
            f"may write: {_permitted(roots)}. Leave the path empty to use ComfyUI's output "
            "folder, or add the folder to allow_write in ComfyUI/user/jovimetrix/config.json."
        )
    return resolved


def resolve_write_file(folder: Path, name: str) -> Path:
    """Place a file name inside an already resolved writable folder.

    Args:
        folder: A folder returned by ``resolve_write_dir``.
        name: One plain file name.

    Returns:
        The resolved file path.

    Raises:
        PathNotAllowed: The name is not plain, or the result leaves the writable folders.
    """
    target = Path(os.path.abspath(folder / check_name(name))).resolve(strict=False)
    if not contains(folder, target) or not _within(target, write_roots()):
        raise PathNotAllowed(f"refusing to write `{_shown(name)}`: it would land outside its folder.")
    return target


def check_pattern(pattern: str) -> str:
    """Refuse a file pattern that could leave the folder it is matched in.

    Args:
        pattern: A pattern such as ``"*.png"``.

    Returns:
        The pattern.

    Raises:
        PathNotAllowed: The pattern is absolute, or holds a separator or ``..``.
    """
    text = str(pattern or "").strip()
    if not text or any(ch in text for ch in ("/", "\\", ":")) or ".." in text:
        raise PathNotAllowed(
            f"`{_shown(text)}` is not a file pattern Jovimetrix accepts. Use a plain pattern "
            "such as *.png, with no folder separator or '..'."
        )
    return text


def readable(path: Path) -> bool:
    """Report whether an already resolved path lies inside a readable folder.

    Args:
        path: A path, resolved or not.

    Returns:
        ``True`` when a node may read it.
    """
    resolved = Path(os.path.abspath(path)).resolve(strict=False)
    return _within(resolved, read_roots())
