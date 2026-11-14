"""Batch nodes: list operations, batch to list, and queues that step through files or values."""

from __future__ import annotations

import glob
import json
import os
import random
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import torch
from comfy_api.latest import io

from ...modules import log, sandbox
from ...modules.enums import EnumBatchMode, EnumConvertType, EnumInterpolation, EnumScaleMode
from ...modules.limits import MAX_QUEUE_ENTRIES, MAX_QUEUE_FILE_BYTES, check_batch, check_canvas
from ...modules.node import Progress, category, node_id
from ...modules.params import IMAGE_SIZE_MIN, parse_dynamic, parse_param
from ...modules.types import VEC2, VEC3, VEC4

logger = log.get_logger("batch")

CATEGORY = category("UTILITY/BATCH")

#: Most decoded queue entries kept in memory per queue node.
QUEUE_CACHE = 16

#: Most queue nodes whose position is remembered.
QUEUE_NODES = 64

#: Most entries sent to the browser with a queue status.
QUEUE_REPORT = 1000


class ArrayNode(io.ComfyNode):
    """Merge, pick, slice, index or sample a list of values."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ARRAY (JOV) 📚",
            display_name="ARRAY 📚",
            category=CATEGORY,
            description="Gather everything wired into its growing inputs, batches split into "
                        "frames, into one list, then keep all of it, one entry, a slice, chosen "
                        "indices or a random sample. Pictures come out as one batch.",
            search_aliases=["ARRAY (JOV) 📚", "array", "list", "pick", "slice", "select from batch"],
            is_input_list=True,
            inputs=[
                io.Combo.Input(
                    "mode", options=EnumBatchMode._member_names_,
                    default=EnumBatchMode.MERGE.name, optional=True,
                    tooltip="MERGE = everything; PICK = the entry at range start; SLICE = start to "
                            "end by step; INDEX_LIST = the indices typed in index; RANDOM = a "
                            "random sample.",
                ),
                VEC3.Input("range", optional=True,
                           tooltip="Start, end and step for PICK and SLICE. End 0 = to the last "
                                   "entry; a negative step reverses.",
                           extra_dict={"default": (0, 0, 1), "mij": 0, "int": True}),
                io.String.Input("index", default="", optional=True,
                                tooltip="INDEX_LIST: comma separated indices and ranges, counted "
                                        "from 0. Example: 0,2,5-8"),
                io.Int.Input("count", default=0, min=0, max=sys.maxsize, optional=True,
                             tooltip="Keep at most this many entries. 0 = all; for RANDOM, the "
                                     "sample size."),
                io.Boolean.Input("reverse", default=False, optional=True,
                                 tooltip="Reverse the order of the result."),
                io.Int.Input("seed", default=0, min=0, max=sys.maxsize, optional=True,
                             tooltip="Seed for RANDOM. The same seed picks the same sample."),
            ],
            outputs=[
                io.AnyType.Output("ARRAY", display_name="ARRAY", is_output_list=True,
                                  tooltip="The resulting entries. Pictures arrive one per run "
                                          "downstream; other values as one list."),
                io.Int.Output("LENGTH", display_name="LENGTH", is_output_list=True,
                              tooltip="How many entries the result holds."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ...modules.image.compose import image_matte
        from ...modules.image.convert import frame_tensor, image_convert, to_frame
        from ...modules.image.misc import image_by_size

        data_list = parse_dynamic(kw, "❔", EnumConvertType.ANY, None)
        mode = parse_param(kw, "mode", EnumBatchMode, EnumBatchMode.MERGE.name)[0]
        slice_range = parse_param(kw, "range", EnumConvertType.VEC3INT, (0, 0, 1))[0]
        index = parse_param(kw, "index", EnumConvertType.STRING, "")[0]
        count = parse_param(kw, "count", EnumConvertType.INT, 0, 0)[0]
        reverse = parse_param(kw, "reverse", EnumConvertType.BOOLEAN, False)[0]
        seed = parse_param(kw, "seed", EnumConvertType.INT, 0, 0)[0]

        data = []
        output_type = None
        for b in data_list:
            if isinstance(b, dict) and "samples" in b:
                if output_type and output_type != EnumConvertType.LATENT:
                    raise ValueError("ARRAY cannot mix latents with other inputs. Wire one kind only.")
                data.extend(b["samples"])
                output_type = EnumConvertType.LATENT
            elif isinstance(b, torch.Tensor):
                if output_type and output_type not in (EnumConvertType.IMAGE, EnumConvertType.MASK):
                    raise ValueError("ARRAY cannot mix pictures with other inputs. Wire one kind only.")
                for x in ([i for i in b] if b.ndim == 4 else [b]):
                    data.append(x.unsqueeze(-1) if x.ndim == 2 else x)
                output_type = EnumConvertType.IMAGE
            elif b is not None:
                if output_type and output_type != type(b):
                    raise ValueError(f"ARRAY cannot mix {type(b).__name__} with other kinds of input.")
                data.append(b)
                output_type = type(b)

        if not data:
            raise ValueError("ARRAY has nothing to work on. Connect a value, list or batch to its input.")

        if mode == EnumBatchMode.PICK:
            start = slice_range[0]
            data = [data[start if start < len(data) else -1]]
        elif mode == EnumBatchMode.SLICE:
            start, end, step = slice_range
            start = abs(start)
            end = len(data) if end == 0 else abs(end + 1)
            if step == 0:
                step = 1
            elif step < 0:
                data = data[::-1]
                step = abs(step)
            data = data[start:end:step]
        elif mode == EnumBatchMode.RANDOM:
            k = len(data) if count == 0 else max(1, min(len(data), count))
            data = random.Random(seed).sample(data, k=k)
        elif mode == EnumBatchMode.INDEX_LIST:
            picks = []
            last = len(data) - 1
            for token in index.split(','):
                token = token.strip()
                if not token:
                    continue
                try:
                    if '-' in token:
                        lo, hi = (max(0, min(last, int(v))) for v in token.split('-', 1))
                        picks.extend(range(lo, hi - 1, -1) if lo > hi else range(lo, hi + 1))
                    else:
                        picks.append(max(0, min(last, int(token))))
                except ValueError:
                    logger.warning("ARRAY index '%s' is not a number or range and was skipped", token[:32])
            if picks:
                data = [data[i] for i in picks]

        if not data:
            raise ValueError("ARRAY's selection is empty. Check range, index and count.")

        if reverse:
            data.reverse()
        if count > 0:
            data = data[:count]

        size = len(data)
        if output_type == EnumConvertType.IMAGE:
            _, w, h = image_by_size(data)
            result = []
            for d in data:
                h2, w2, cc = d.shape
                if w != w2 or h != h2 or cc != 4:
                    d = frame_tensor(image_matte(image_convert(to_frame(d), 4), (0, 0, 0, 0), w, h))
                result.append(d.unsqueeze(0))
            return io.NodeOutput(torch.stack(result), [size])
        return io.NodeOutput([data], [size])


class BatchToList(io.ComfyNode):
    """Turn a batch into a list ComfyUI runs downstream nodes over one entry at a time."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BATCH TO LIST (JOV)",
            display_name="BATCH TO LIST",
            category=CATEGORY,
            description="Turn a batch of pictures, masks or latents, or a Python list, into a "
                        "list, so the next node runs once per entry instead of once for the batch.",
            search_aliases=["BATCH TO LIST (JOV)", "batch to list", "unbatch", "split batch"],
            is_input_list=True,
            inputs=[
                io.AnyType.Input("batch", optional=True,
                                 tooltip="A picture, mask or latent batch, or a list of values."),
            ],
            outputs=[
                io.AnyType.Output("LIST", display_name="LIST", is_output_list=True,
                                  tooltip="One entry per frame of the batch, each a batch of one."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        items: list[Any] = []
        for value in kw.get("batch", []) or []:
            if isinstance(value, torch.Tensor):
                if value.ndim in (3, 4):
                    items.extend(t.unsqueeze(0) for t in value)
                else:
                    items.append(value)
            elif isinstance(value, dict) and isinstance(value.get("samples"), torch.Tensor):
                for i in range(value["samples"].shape[0]):
                    entry = dict(value)
                    entry["samples"] = value["samples"][i:i + 1]
                    entry.pop("batch_index", None)
                    entry.pop("noise_mask", None)
                    items.append(entry)
            elif isinstance(value, (list, tuple)):
                items.extend(value)
            elif value is not None:
                items.append(value)
        if not items:
            raise ValueError("BATCH TO LIST received nothing. Connect a batch or a list to 'batch'.")
        return io.NodeOutput(items)


class _QueueState:
    """Where one queue node is in its list, kept between runs."""

    def __init__(self) -> None:
        self.index = 0
        self.queue: list[Any] | None = None
        self.index_last = 0
        self.length = 0
        self.current: Any = None
        self.previous: Any = None
        self.source: tuple[str, bool] | None = None
        self.cache: "OrderedDict[Any, Any]" = OrderedDict()

    def status(self, ident: str) -> dict[str, Any]:
        entries = self.queue or []
        return {
            "id": ident,
            "c": str(self.current) if self.current is not None else "",
            "i": self.index_last,
            "s": self.length,
            "l": [str(x) for x in entries[:QUEUE_REPORT]],
        }


_queues_lock = threading.Lock()
_queues: "OrderedDict[str, _QueueState]" = OrderedDict()


def _queue_state(ident: str) -> _QueueState:
    with _queues_lock:
        state = _queues.pop(ident, None) or _QueueState()
        _queues[ident] = state
        while len(_queues) > QUEUE_NODES:
            _queues.popitem(last=False)
        return state


def _value(text: str) -> Any:
    try:
        return float(text)
    except ValueError:
        return text


def _read_text_list(path: Path) -> list[str]:
    if path.stat().st_size > MAX_QUEUE_FILE_BYTES:
        raise ValueError(f"'{path.name}' is larger than {MAX_QUEUE_FILE_BYTES // (1024 * 1024)} MB "
                         "and was not read into the queue.")
    return path.read_text(encoding="utf-8", errors="replace").split('\n')


def parse_queue(text: str, recurse: bool = False) -> list[Any]:
    """Turn the queue text into its entries.

    Each line is a value, a file, a folder of pictures, a ``.txt`` list, or a folder and
    patterns such as ``input/frames;*.png;*.jpg``. Paths are held to the readable folders.

    Args:
        text: The queue text, one entry per line.
        recurse: Search the folders below a folder too.

    Returns:
        The entries; numbers as floats, files as resolved paths.
    """
    from ...modules.image import image_formats

    formats = set(image_formats())
    entries: list[Any] = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith(("http://", "https://")):
            entries.append(line)
            continue

        folder_text, tail = os.path.split(line)
        if any(ch in tail for ch in "*?[;"):
            folder = sandbox.resolve_read(folder_text or ".")
            found: list[str] = []
            if folder.is_dir():
                for pattern in [p.strip() for p in tail.split(';') if p.strip()]:
                    pattern = sandbox.check_pattern(pattern)
                    root = glob.escape(str(folder))
                    spec = os.path.join(root, "**", pattern) if recurse else os.path.join(root, pattern)
                    for hit in glob.iglob(spec, recursive=recurse):
                        if Path(hit).is_file() and sandbox.readable(Path(hit)):
                            found.append(str(Path(hit).resolve()))
                        if len(found) >= MAX_QUEUE_ENTRIES:
                            break
            entries.extend(sorted(set(found)) if found else [line])
        else:
            path = sandbox.resolve_read(line)
            if path.is_dir():
                walker = path.rglob("*") if recurse else path.glob("*")
                found = []
                for hit in walker:
                    if hit.suffix.lower() in formats and hit.is_file() and sandbox.readable(hit):
                        found.append(str(hit.resolve()))
                    if len(found) >= MAX_QUEUE_ENTRIES:
                        break
                entries.extend(sorted(found) if found else [line])
            elif path.is_file() and path.suffix.lower() == ".txt":
                entries.extend(_value(x.strip()) for x in _read_text_list(path) if x.strip())
            elif path.is_file():
                entries.append(str(path))
            else:
                entries.append(_value(line))

        if len(entries) >= MAX_QUEUE_ENTRIES:
            logger.warning("the queue was cut to its first %d entries", MAX_QUEUE_ENTRIES)
            return entries[:MAX_QUEUE_ENTRIES]
    return entries


def _load_entry(state: _QueueState, entry: Any) -> Any:
    """Decode a queue entry: pictures become frames, JSON files become data."""
    if not isinstance(entry, str):
        return entry
    if (cached := state.cache.get(entry)) is not None:
        state.cache.move_to_end(entry)
        return cached

    from ...modules.image import image_formats

    ext = os.path.splitext(entry.split("?")[0])[1].lower()
    value = entry
    if ext in image_formats():
        from ...modules.image.io import image_load

        source = entry if entry.lower().startswith(("http://", "https://")) else str(sandbox.resolve_read(entry))
        value = image_load(source)[0]
    elif ext == ".json" and not entry.lower().startswith(("http://", "https://")):
        path = sandbox.resolve_read(entry)
        if path.stat().st_size > MAX_QUEUE_FILE_BYTES:
            raise ValueError(f"'{path.name}' is too large to load as a queue entry.")
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        return entry

    state.cache[entry] = value
    while len(state.cache) > QUEUE_CACHE:
        state.cache.popitem(last=False)
    return value


QUEUE_INPUTS = [
    io.String.Input("queue", default="./res/img/test-a.png", multiline=True, optional=True,
                    tooltip="One entry per line: a value, a file, a folder, a .txt list, or a "
                            "folder with patterns. Example: input/frames;*.png;*.jpg"),
    io.Boolean.Input("recurse", default=False, optional=True,
                     tooltip="Also search the folders inside each folder listed."),
    io.Boolean.Input("batch", default=False, optional=True,
                     tooltip="Load every entry at once as one batch instead of one entry per run."),
    io.Int.Input("select", default=0, min=0, max=sys.maxsize, optional=True,
                 tooltip="Jump to this entry, counted from 1. 0 = step to the next entry each run."),
    io.Boolean.Input("hold", default=False, optional=True,
                     tooltip="Stay on the current entry instead of stepping."),
    io.Boolean.Input("stop", default=False, optional=True,
                     tooltip="When the list runs out, stop the run instead of carrying on."),
    io.Boolean.Input("loop", default=True, optional=True,
                     tooltip="Start over at the first entry after the last. Off = stay on the last."),
    io.Boolean.Input("reset", default=False, optional=True,
                     tooltip="Go back to the first entry and read the list again on the next run."),
]


def run_queue(cls, kw: dict) -> tuple[Any, list, Any, int, int, bool]:
    """Advance a queue node one run.

    Args:
        cls: The per-run node class.
        kw: The node's keyword inputs.

    Returns:
        ``(data, queue, current, index, total, trigger)``.
    """

    from ...modules import messages

    ident = node_id(cls)
    state = _queue_state(ident)

    if (new_val := parse_param(kw, "select", EnumConvertType.INT, 0, 0)[0]) > 0:
        state.index = new_val - 1

    recurse = parse_param(kw, "recurse", EnumConvertType.BOOLEAN, False)[0]
    text = parse_param(kw, "queue", EnumConvertType.STRING, "")[0]
    if messages.reset_requested(ident) or parse_param(kw, "reset", EnumConvertType.BOOLEAN, False)[0] \
            or state.source != (text, recurse):
        state.queue = None
        state.index = 0
        state.cache.clear()

    mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)[0]
    sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)[0]
    w, h = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)[0]
    matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)[0]

    if state.queue is None:
        state.source = (text, recurse)
        state.queue = parse_queue(text, recurse)
        state.length = len(state.queue)
        state.index_last = 0
        state.previous = _load_entry(state, state.queue[0]) if state.queue else None

    if state.length == 0:
        raise ValueError("The queue is empty. Type at least one value, file or folder into 'queue'.")

    stop = parse_param(kw, "stop", EnumConvertType.BOOLEAN, False)[0]
    if stop and state.index >= state.length:
        from nodes import interrupt_processing

        messages.send("jovi-queue-done", ident, state.status(ident))
        interrupt_processing()
        return state.previous, state.queue, state.current, state.index_last + 1, state.length, True

    wait = parse_param(kw, "hold", EnumConvertType.BOOLEAN, False)[0]
    if wait:
        state.index = state.index_last

    if parse_param(kw, "loop", EnumConvertType.BOOLEAN, True)[0]:
        state.index %= state.length
    else:
        state.index = min(state.index, state.length - 1)

    state.current = state.queue[state.index]
    data = state.previous
    state.index_last = state.index
    batched = parse_param(kw, "batch", EnumConvertType.BOOLEAN, False)[0]
    if batched:
        from ...modules.image.compose import image_matte, image_scalefit
        from ...modules.image.convert import frame_tensor, image_convert

        data = [_load_entry(state, entry) for entry in state.queue]
        shapes = [d.shape for d in data if isinstance(d, torch.Tensor)]
        if shapes:
            mh = max(s[0] for s in shapes)
            mw = max(s[1] for s in shapes)
            mc = max(s[2] for s in shapes)
            if mode != EnumScaleMode.MATTE:
                check_batch(w, h, len(shapes))
            else:
                check_batch(mw, mh, len(shapes), source="queue")
            frames = []
            pbar = Progress(len(data))
            for idx, d in enumerate(data):
                if not isinstance(d, torch.Tensor):
                    continue
                d = image_convert(d, mc)
                if mode != EnumScaleMode.MATTE:
                    d = image_scalefit(d, w, h, mode, sample, matte)
                    d = image_scalefit(d, w, h, EnumScaleMode.RESIZE_MATTE, sample, matte)
                else:
                    d = image_matte(d, matte, mw, mh)
                frames.append(frame_tensor(d))
                pbar.update(idx)
            data = torch.stack(frames)
    elif not wait:
        data = _load_entry(state, state.current)
        if isinstance(data, torch.Tensor):
            from ...modules.image.compose import image_scalefit
            from ...modules.image.convert import frame_tensor

            if mode != EnumScaleMode.MATTE:
                w, h = check_canvas(w, h)
                data = image_scalefit(data, w, h, mode, sample)
            data = frame_tensor(data).unsqueeze(0)
        state.index += 1

    state.previous = data
    messages.send("jovi-queue-ping", ident, state.status(ident))
    if stop and batched:
        from nodes import interrupt_processing

        interrupt_processing()
    trigger = state.index == state.length or batched
    return data, state.queue, state.current, state.index, state.length, trigger


QUEUE_DESCRIPTION_TAIL = ("Each run steps to the next entry; select jumps, hold pauses, and reset "
                          "starts over.")


class QueueNode(io.ComfyNode):
    """Step through a list of values or files, one per run."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="QUEUE (JOV) 🗃",
            display_name="QUEUE 🗃",
            category=CATEGORY,
            description="Step through a list of values, files or folders, one entry per run. "
                        "Pictures and JSON files are loaded; anything else passes through as "
                        "text or a number. " + QUEUE_DESCRIPTION_TAIL,
            search_aliases=["QUEUE (JOV) 🗃", "queue", "iterate", "file list", "batch files", "loop over"],
            is_input_list=True,
            not_idempotent=True,
            hidden=[io.Hidden.unique_id],
            inputs=[*QUEUE_INPUTS],
            outputs=[
                io.AnyType.Output("❔", display_name="❔",
                                  tooltip="The current entry, loaded: a picture, JSON data, text or a number."),
                io.AnyType.Output("QUEUE", display_name="QUEUE", tooltip="The whole list of entries."),
                io.String.Output("CURRENT", display_name="CURRENT",
                                 tooltip="The current entry as text, such as its file path."),
                io.Int.Output("INDEX", display_name="INDEX",
                              tooltip="Position of the next entry, counted from 1."),
                io.Int.Output("TOTAL", display_name="TOTAL", tooltip="How many entries the list holds."),
                io.Boolean.Output("TRIGGER", display_name="TRIGGER",
                                  tooltip="True on the run that reaches the end of the list."),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        data, queue, current, index, total, trigger = run_queue(cls, kw)
        return io.NodeOutput(data, queue, "" if current is None else str(current), index, total, trigger)


class QueueTooNode(io.ComfyNode):
    """Step through a list of pictures, one per run, as RGBA, RGB and mask."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="QUEUE TOO (JOV) 🗃",
            display_name="QUEUE TOO 🗃",
            category=CATEGORY,
            description="Step through a list of pictures, one per run, handing each on as RGBA, "
                        "RGB and mask, optionally resized. " + QUEUE_DESCRIPTION_TAIL,
            search_aliases=["QUEUE TOO (JOV) 🗃", "image queue", "load images", "image folder", "iterate images"],
            is_input_list=True,
            not_idempotent=True,
            hidden=[io.Hidden.unique_id],
            inputs=[
                *QUEUE_INPUTS,
                io.Combo.Input("mode", options=EnumScaleMode._member_names_,
                               default=EnumScaleMode.MATTE.name, optional=True,
                               tooltip="Resize of each picture. MATTE = as loaded, or padded to "
                                       "the largest in batch mode; FIT, CROP, ASPECT = to wh."),
                VEC2.Input("wh", optional=True, tooltip="Target width and height when mode is not MATTE.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                io.Combo.Input("sample", options=EnumInterpolation._member_names_,
                               default=EnumInterpolation.LANCZOS4.name, optional=True,
                               tooltip="Resampling filter. LANCZOS4 = sharpest; NEAREST = hard pixels."),
                VEC4.Input("matte", optional=True,
                           tooltip="Colour behind transparent areas and around resized pictures, "
                                   "RGBA 0 to 255.",
                           extra_dict={"default": (0, 0, 0, 255), "rgb": True}),
            ],
            outputs=[
                io.Image.Output("RGBA", display_name="RGBA", tooltip="The picture with its alpha."),
                io.Image.Output("RGB", display_name="RGB", tooltip="The picture without alpha."),
                io.Mask.Output("MASK", display_name="MASK", tooltip="The picture's alpha as a mask."),
                io.String.Output("CURRENT", display_name="CURRENT", tooltip="The current file path."),
                io.Int.Output("INDEX", display_name="INDEX",
                              tooltip="Position of the next entry, counted from 1."),
                io.Int.Output("TOTAL", display_name="TOTAL", tooltip="How many entries the list holds."),
                io.Boolean.Output("TRIGGER", display_name="TRIGGER",
                                  tooltip="True on the run that reaches the end of the list."),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ...modules.image.convert import frame_outputs, to_frame

        data, _, current, index, total, trigger = run_queue(cls, kw)
        if not isinstance(data, torch.Tensor):
            name = os.path.basename(str(current)) if current is not None else ""
            raise ValueError(f"QUEUE TOO's entry '{name[:80]}' is not a picture it can load. List "
                             "only picture files, or use QUEUE for other values.")
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)[0]
        frames = [frame_outputs(to_frame(d), matte) for d in data]
        rgba, rgb, mask = [torch.stack(list(part)) for part in zip(*frames)]
        return io.NodeOutput(rgba, rgb, mask, "" if current is None else str(current), index, total, trigger)


NODES = [ArrayNode, BatchToList, QueueNode, QueueTooNode]
