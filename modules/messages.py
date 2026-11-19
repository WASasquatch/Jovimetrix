"""Messages between a running node and the browser tab that queued it.

``POST /jovimetrix/message`` takes ``{"id": node, "cmd": value, "client_id": tab}``. A node reads
only messages sent by the tab running it, and its events go to that tab alone.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict, deque
from typing import Any

from . import log

logger = log.get_logger("messages")

ROUTE = "/jovimetrix/message"

#: Largest request body read, in bytes.
MAX_BODY = 4096

#: Most node ids holding unread messages at once.
MAX_IDS = 256

#: Most unread messages kept per node id.
MAX_PER_ID = 8

#: Longest node id or command accepted, in characters.
MAX_TEXT = 64

_lock = threading.Lock()
_messages: "OrderedDict[str, deque[dict[str, Any]]]" = OrderedDict()
_registered = False


def _executing_client() -> str | None:
    """Return the client id of the run in progress, or ``None`` for a run queued without one."""
    try:
        from server import PromptServer

        return getattr(PromptServer.instance, "client_id", None)
    except Exception:
        return None


def _store(ident: str, entry: dict[str, Any]) -> None:
    with _lock:
        queue = _messages.pop(ident, None) or deque(maxlen=MAX_PER_ID)
        queue.append(entry)
        _messages[ident] = queue
        while len(_messages) > MAX_IDS:
            _messages.popitem(last=False)


def take(ident: Any) -> dict[str, Any] | None:
    """Remove and return the oldest message for a node sent by the tab running it.

    Args:
        ident: The node's unique id.

    Returns:
        The message, or ``None`` when there is none.
    """
    if isinstance(ident, (list, tuple)):
        ident = ident[0] if ident else ""
    key = str(ident)
    client = _executing_client()
    with _lock:
        queue = _messages.get(key)
        if not queue:
            return None
        for entry in list(queue):
            if client is None or entry.get("client_id") == client:
                queue.remove(entry)
                if not queue:
                    _messages.pop(key, None)
                return entry
    return None


def poll(ident: Any, timeout: float = 3.0, period: float = 0.05) -> dict[str, Any] | None:
    """Wait for a message for a node.

    Args:
        ident: The node's unique id.
        timeout: Seconds to wait.
        period: Seconds between looks.

    Returns:
        The message, or ``None`` when none arrived in time.
    """
    deadline = time.perf_counter() + max(0.0, timeout)
    while True:
        if (entry := take(ident)) is not None:
            return entry
        if time.perf_counter() >= deadline:
            return None
        time.sleep(period)


def reset_requested(ident: Any) -> bool:
    """Report whether the tab running a node asked it to reset since the last run.

    Args:
        ident: The node's unique id.

    Returns:
        ``True`` when a message was waiting.
    """
    found = False
    while take(ident) is not None:
        found = True
    return found


def notify(event: str, ident: Any, data: dict[str, Any]) -> None:
    """Tell the tab running the node about an event, through ComfyUI's own client messages.

    Args:
        event: Event name the browser listens for.
        ident: The node's unique id.
        data: JSON-safe payload; ``id`` is added.
    """
    try:
        from server import PromptServer

        payload = dict(data)
        payload["id"] = ident
        PromptServer.instance.send_sync(event, payload, _executing_client())
    except Exception as error:
        logger.debug("event %s not sent: %s", event, type(error).__name__)


async def _post(request):
    from aiohttp import web

    if request.content_length is not None and request.content_length > MAX_BODY:
        return web.json_response({"error": "message too large"}, status=413)
    raw = await request.content.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        return web.json_response({"error": "message too large"}, status=413)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return web.json_response({"error": "not JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "not a JSON object"}, status=400)

    ident = body.get("id")
    cmd = body.get("cmd")
    client = body.get("client_id")
    if not isinstance(ident, (str, int)) or isinstance(ident, bool) or len(str(ident)) > MAX_TEXT:
        return web.json_response({"error": "bad id"}, status=400)
    if not isinstance(cmd, (str, bool)) or (isinstance(cmd, str) and len(cmd) > MAX_TEXT):
        return web.json_response({"error": "bad cmd"}, status=400)
    if client is not None and (not isinstance(client, str) or len(client) > MAX_TEXT):
        return web.json_response({"error": "bad client_id"}, status=400)

    _store(str(ident), {"id": str(ident), "cmd": cmd, "client_id": client})
    return web.json_response({"ok": True})


def register_routes() -> None:
    """Add the message route to ComfyUI's server, once."""
    global _registered
    if _registered:
        return
    from server import PromptServer

    PromptServer.instance.routes.post(ROUTE)(_post)
    _registered = True
