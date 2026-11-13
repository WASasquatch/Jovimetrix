"""
     ██  ██████  ██    ██ ██ ███    ███ ███████ ████████ ██████  ██ ██   ██
     ██ ██    ██ ██    ██ ██ ████  ████ ██         ██    ██   ██ ██  ██ ██
     ██ ██    ██ ██    ██ ██ ██ ████ ██ █████      ██    ██████  ██   ███
██   ██ ██    ██  ██  ██  ██ ██  ██  ██ ██         ██    ██   ██ ██  ██ ██
 █████   ██████    ████   ██ ██      ██ ███████    ██    ██   ██ ██ ██   ██

              Animation, Image Compositing & Procedural Creation

Jovimetrix, a ComfyUI custom node pack created by Alexander G. Morano. ``comfy_entrypoint`` is
the only name this package exports.
"""

from __future__ import annotations

import importlib
import traceback

from .modules import log

__author__ = "Alexander G. Morano"

logger = log.get_logger()

#: Oldest ComfyUI carrying every API the pack calls.
COMFYUI_MIN_VERSION = "0.14.0"

#: Node modules under ``nodes/``, each publishing a ``NODES`` list.
NODE_MODULES = (
    "adjust", "anim", "calc", "color", "compose", "create", "trans", "vars",
    "utility.batch", "utility.info", "utility.io",
)

try:
    from comfy_api.latest import ComfyExtension, io
except ImportError:
    ComfyExtension = io = None


def load_nodes() -> list:
    """Import every node module and return the node classes whose schema builds.

    Returns:
        The node classes, in module order.
    """
    nodes = []
    seen: set[str] = set()
    for name in NODE_MODULES:
        try:
            module = importlib.import_module(f"{__name__}.nodes.{name}")
        except Exception as error:
            logger.error("nodes.%s could not be imported, so its nodes are missing (%s: %s)",
                         name, type(error).__name__, error)
            logger.debug("%s", traceback.format_exc())
            continue
        for node in getattr(module, "NODES", ()):
            try:
                schema = node.GET_SCHEMA()
            except Exception as error:
                logger.error("%s was not registered: its schema failed (%s: %s)",
                             node.__name__, type(error).__name__, error)
                continue
            if schema.node_id in seen:
                logger.error("%s was not registered: the id '%s' is already taken",
                             node.__name__, schema.node_id)
                continue
            seen.add(schema.node_id)
            nodes.append(node)
    logger.info("%d nodes loaded", len(nodes))
    return nodes


if io is None:
    logger.error(
        "comfy_api.latest is missing, so no Jovimetrix nodes were loaded. Jovimetrix 3 needs "
        "ComfyUI %s or newer; update ComfyUI, or stay on Jovimetrix 2.x.",
        COMFYUI_MIN_VERSION,
    )
else:

    class Jovimetrix(ComfyExtension):
        async def on_load(self) -> None:
            from .modules import fonts, messages

            try:
                messages.register_routes()
            except Exception as error:
                logger.warning("the message route could not be registered (%s), so Delay, "
                               "Queue and Graph cannot be reset from the browser",
                               type(error).__name__)
            fonts.warm()

        async def get_node_list(self) -> list[type[io.ComfyNode]]:
            return load_nodes()

    async def comfy_entrypoint() -> Jovimetrix:
        return Jovimetrix()

    __all__ = ["comfy_entrypoint"]
