"""Loggers for the pack, all under the ``jovimetrix`` name."""

from __future__ import annotations

import logging

ROOT_NAME = "jovimetrix"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the pack logger, or a child of it.

    Args:
        name: Child name, such as ``"sandbox"``. ``None`` returns the pack logger itself.

    Returns:
        The logger.
    """
    return logging.getLogger(ROOT_NAME if not name else f"{ROOT_NAME}.{name}")
