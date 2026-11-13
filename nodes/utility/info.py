"""Information nodes: show any value, graph values over runs, and read a picture's size."""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from typing import Any

import torch
from comfy_api.latest import io

from ...modules import messages
from ...modules.enums import EnumConvertType
from ...modules.limits import check_canvas
from ...modules.node import category, node_id
from ...modules.params import IMAGE_SIZE_MIN, parse_dynamic, parse_param
from ...modules.types import IMAGE_TYPES, VEC2, VEC3

CATEGORY = category("UTILITY/INFO")

#: Most values GRAPH keeps per line.
MAX_HISTORY = 100000

#: Most GRAPH nodes whose history is remembered.
GRAPH_NODES = 64

#: Longest text AKASHIC shows per input, in characters.
MAX_TEXT = 100000


def decode_tensor(tensor: torch.Tensor) -> str:
    """Describe a tensor's shape as ``batch x width x height x channels``."""
    if tensor.ndim > 3:
        b, h, w, cc = tensor.shape[:4]
    elif tensor.ndim > 2:
        cc = 1
        b, h, w = tensor.shape
    elif tensor.ndim == 2:
        b = cc = 1
        h, w = tensor.shape
    else:
        return f"{tuple(tensor.shape)}"
    return f"{b}x{w}x{h}x{cc}"


def describe(val: Any) -> str:
    """Return one line of JSON naming a value's type and summarising it."""
    ret: Any = ''
    typ = ''.join(repr(type(val)).split("'")[1:2])
    if isinstance(val, dict):
        if (image := val.get('image', None)) is not None and isinstance(image, torch.Tensor):
            ret = image
            if (mask := val.get('mask', None)) is not None:
                while len(mask.shape) < len(image.shape):
                    mask = mask.unsqueeze(-1)
                ret = torch.cat((image, mask), dim=-1)
            if ret.ndim < 4:
                ret = ret.unsqueeze(-1)
            ret = decode_tensor(ret)
            typ = "Mixlab Layer"
        elif 'xyzw' in val:
            ret = str(val["xyzw"])
            typ = "VECTOR"
        elif 'samples' in val and isinstance(val['samples'], torch.Tensor):
            ret = decode_tensor(val['samples'])
            typ = "LATENT"
        elif len(val) == 0:
            ret = ""
        else:
            try:
                ret = json.dumps(val, indent=3, separators=(',', ': '), default=str)
            except (TypeError, ValueError) as error:
                ret = f"<{type(error).__name__}>"
    elif isinstance(val, (tuple, set, list)):
        val = list(val)
        if val:
            if isinstance(val[0], torch.Tensor):
                ret = decode_tensor(val[0])
                typ = type(val[0]).__name__
            elif len(val) == 1 and isinstance(val[0], list) and val[0] and isinstance(val[0][0], torch.Tensor):
                ret = decode_tensor(val[0][0])
                typ = "CONDITIONING"
            elif all(isinstance(i, (tuple, set, list)) for i in val):
                ret = "[\n" + ",\n".join(f"  {list(row)}" for row in val) + "\n]"
            elif all(isinstance(i, (bool, int, float)) for i in val):
                ret = ','.join(str(x) for x in val)
            else:
                ret = str(val)
    elif isinstance(val, bool):
        ret = "True" if val else "False"
    elif isinstance(val, torch.Tensor):
        ret = decode_tensor(val)
    else:
        ret = str(val)
    ret = str(ret)
    if len(ret) > MAX_TEXT:
        ret = ret[:MAX_TEXT] + "..."
    return json.dumps({typ: ret}, separators=(',', ': '))


class AkashicNode(io.ComfyNode):
    """Show whatever is wired into it as text on the node."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="AKASHIC (JOV) 📓",
            display_name="AKASHIC 📓",
            category=CATEGORY,
            description="Show anything wired into its growing inputs as text on the node: numbers, "
                        "text, lists, and the shape of pictures, masks and latents. A quick look "
                        "inside a graph.",
            search_aliases=["AKASHIC (JOV) 📓", "show", "display", "debug", "preview any", "inspect"],
            is_input_list=True,
            is_output_node=True,
            inputs=[],
            outputs=[],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        texts = []
        for values in kw.values():
            values = values if isinstance(values, list) else [values]
            data = "::\n" if len(values) > 1 else ""
            data += "".join(describe(v) + "\n" for v in values)
            texts.append(data)
        return io.NodeOutput(ui={"b64_images": [], "text": texts})


_graph_lock = threading.Lock()
_graphs: "OrderedDict[str, list[list[float]]]" = OrderedDict()


class GraphNode(io.ComfyNode):
    """Plot values over successive runs."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GRAPH (JOV) 📈",
            display_name="GRAPH 📈",
            category=CATEGORY,
            description="Plot the numbers wired into its growing inputs as lines that grow with "
                        "every run. Watch a value change across an animation or a seed sweep.",
            search_aliases=["GRAPH (JOV) 📈", "graph", "plot", "chart", "history"],
            is_input_list=True,
            is_output_node=True,
            not_idempotent=True,
            hidden=[io.Hidden.unique_id],
            inputs=[
                io.Boolean.Input("reset", default=False, optional=True,
                                 tooltip="Clear the history before plotting this run."),
                io.Int.Input("value", default=60, min=0, max=MAX_HISTORY, optional=True,
                             tooltip="How many recent values each line shows. 0 = all, up to "
                                     f"{MAX_HISTORY}."),
                VEC2.Input("wh", optional=True, tooltip="Width and height of the graph picture.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
            ],
            outputs=[io.Image.Output("IMAGE", display_name="IMAGE", tooltip="The graph.")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import numpy as np

        from ...modules.plot import line_chart

        ident = node_id(cls)
        keep = parse_param(kw, "value", EnumConvertType.INT, 60, 0, MAX_HISTORY)[0]
        width, height = check_canvas(*parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)[0])
        reset = messages.reset_requested(ident) or parse_param(kw, "reset", EnumConvertType.BOOLEAN, False)[0]

        dynamic = parse_dynamic(kw, "❔", EnumConvertType.FLOAT, 0, extend=False)
        limit = keep if keep > 0 else MAX_HISTORY
        with _graph_lock:
            history = [] if reset else _graphs.pop(ident, [])
            for idx, val in enumerate(dynamic):
                val = list(val) if isinstance(val, (list, tuple, set)) else [val]
                while len(history) <= idx:
                    history.append([])
                history[idx].extend(float(v) for v in val)
                history[idx] = history[idx][-limit:]
            history = history[:max(1, len(dynamic))]
            _graphs[ident] = history
            while len(_graphs) > GRAPH_NODES:
                _graphs.popitem(last=False)
            series = [list(s) for s in history]

        chart = np.asarray(line_chart(series, width, height), dtype=np.float32) / 255.0
        return io.NodeOutput(torch.from_numpy(chart).unsqueeze(0))


class ImageInfoNode(io.ComfyNode):
    """Read the size and channel count of a picture."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="IMAGE INFO (JOV) 📚",
            display_name="IMAGE INFO 📚",
            category=CATEGORY,
            description="Read a picture's batch count, width, height and channel count, singly "
                        "and as vectors. Size other nodes to match an input.",
            search_aliases=["IMAGE INFO (JOV) 📚", "image size", "dimensions", "width height", "resolution"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The picture or mask to measure."),
            ],
            outputs=[
                io.Int.Output("COUNT", display_name="COUNT", tooltip="Number of frames in the batch."),
                io.Int.Output("W", display_name="W", tooltip="Width in pixels."),
                io.Int.Output("H", display_name="H", tooltip="Height in pixels."),
                io.Int.Output("C", display_name="C", tooltip="Channels: 1 = mask, 3 = RGB, 4 = RGBA."),
                VEC2.Output("WH", display_name="WH", tooltip="Width and height as a VEC2."),
                VEC3.Output("WHC", display_name="WHC", tooltip="Width, height and channels as a VEC3."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        image = [i for i in parse_param(kw, "image", EnumConvertType.IMAGE, None) if i is not None]
        if not image:
            raise ValueError("IMAGE INFO has no picture to measure. Connect a picture or mask to 'image'.")
        height, width, cc = image[0].shape[:3] if image[0].ndim == 3 else (*image[0].shape[:2], 1)
        return io.NodeOutput(len(image), width, height, cc, (width, height), (width, height, cc))


NODES = [AkashicNode, GraphNode, ImageInfoNode]
