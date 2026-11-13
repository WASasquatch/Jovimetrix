"""Settings read from ``ComfyUI/user/jovimetrix/config.json``.

The file is optional and is read again whenever it changes. Environment variables
``JOV_GIFSKI``, ``JOV_DELAY_MIN`` and ``JOV_DELAY_MAX`` override the matching keys.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from . import log

logger = log.get_logger("config")

#: Every key the file may hold, with its default.
DEFAULTS: dict[str, Any] = {
    "allow_read": [],
    "allow_write": [],
    "allow_network": False,
    "gifski": "",
    "delay_min": 5,
    "delay_max": 10000000,
}

#: Environment variable overriding a key.
ENVIRONMENT = {
    "gifski": "JOV_GIFSKI",
    "delay_min": "JOV_DELAY_MIN",
    "delay_max": "JOV_DELAY_MAX",
}

#: Largest settings file read, in bytes.
MAX_BYTES = 256 * 1024

_lock = threading.Lock()
_cache: dict[str, Any] = {"stamp": None, "values": dict(DEFAULTS)}


def config_path() -> Path:
    """Return where the settings file is read from.

    Returns:
        The path, whether or not the file exists.
    """
    import folder_paths

    return Path(folder_paths.get_user_directory()) / "jovimetrix" / "config.json"


def _coerce(key: str, value: Any) -> Any:
    """Return ``value`` shaped like the default for ``key``, or the default when it cannot be."""
    default = DEFAULTS[key]
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, list):
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return default
        return [str(v) for v in value if isinstance(v, str) and v.strip()]
    return str(value) if value is not None else default


def _read_file(path: Path) -> dict[str, Any]:
    """Read the settings file into a dict of known keys."""
    values = dict(DEFAULTS)
    try:
        if path.stat().st_size > MAX_BYTES:
            logger.warning("config.json is larger than %d bytes and was not read", MAX_BYTES)
            return values
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return values
    except (OSError, ValueError) as error:
        logger.warning("config.json could not be read (%s), using the defaults", type(error).__name__)
        return values
    if not isinstance(data, dict):
        logger.warning("config.json does not hold a JSON object, using the defaults")
        return values
    for key, value in data.items():
        if key not in DEFAULTS:
            logger.warning("config.json key '%s' is not a Jovimetrix setting and is ignored", key)
            continue
        values[key] = _coerce(key, value)
    return values


def settings() -> dict[str, Any]:
    """Return the current settings, environment overrides applied.

    Returns:
        A dict holding every key in ``DEFAULTS``.
    """
    path = config_path()
    try:
        stat = path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None
    with _lock:
        if stamp != _cache["stamp"]:
            _cache["values"] = _read_file(path) if stamp is not None else dict(DEFAULTS)
            _cache["stamp"] = stamp
        values = dict(_cache["values"])
    for key, name in ENVIRONMENT.items():
        if (raw := os.getenv(name)) is not None and raw.strip():
            values[key] = _coerce(key, raw.strip())
    return values


def get(key: str) -> Any:
    """Return one setting.

    Args:
        key: A key of ``DEFAULTS``.

    Returns:
        The value.
    """
    return settings()[key]
