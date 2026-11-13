"""Input and output nodes: a pause with a cancel prompt, picture and animation export, a pass
through router, and PNG saving with metadata."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from comfy_api.latest import io

from ...modules import config, log, messages, sandbox
from ...modules.enums import EnumConvertType
from ...modules.node import Progress, category, node_id
from ...modules.params import parse_param
from ...modules.types import BUS, IMAGE_TYPES, JSON

logger = log.get_logger("io")

CATEGORY = category("UTILITY/IO")

#: Longest DELAY the timer widget offers, in seconds.
DELAY_LIMIT = 10000000

#: Formats EXPORT writes.
FORMATS = ["gif", "png", "jpg", "gifski"]

#: Value outputs on ROUTE, after its BUS output.
ROUTE_SLOTS = 10

#: Longest a gifski encode may run, in seconds.
GIFSKI_TIMEOUT = 600

#: Most numbered names EXPORT and SAVE OUTPUT try for a new file.
MAX_NUMBERED = 1000000


def _next_free(folder: Path, stem: str, ext: str, overwrite: bool) -> Path:
    """Return the file to write: ``stem.ext``, or the first free ``stem_N.ext`` unless overwriting."""
    first = sandbox.resolve_write_file(folder, f"{stem}.{ext}")
    if overwrite or not first.exists():
        return first
    lo, hi = 1, 1
    while sandbox.resolve_write_file(folder, f"{stem}_{hi}.{ext}").exists():
        lo, hi = hi, hi * 2
        if hi > MAX_NUMBERED:
            raise ValueError(f"Too many files named '{stem}_N.{ext}' already exist. Pick another prefix.")
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if sandbox.resolve_write_file(folder, f"{stem}_{mid}.{ext}").exists():
            lo = mid
        else:
            hi = mid
    return sandbox.resolve_write_file(folder, f"{stem}_{hi}.{ext}")


def _preview_entry(path: Path) -> dict[str, str] | None:
    """Describe a written file for ComfyUI's previews when it lies under output or temp."""
    import folder_paths

    for kind, root in (("output", folder_paths.get_output_directory()),
                       ("temp", folder_paths.get_temp_directory())):
        root = Path(root).resolve()
        if sandbox.contains(root, path):
            sub = os.path.relpath(path.parent, root)
            return {"filename": path.name, "subfolder": "" if sub == "." else sub.replace("\\", "/"),
                    "type": kind}
    return None


class DelayNode(io.ComfyNode):
    """Hold a value for a time, with a prompt to continue or cancel."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DELAY (JOV) ✋🏽",
            display_name="DELAY ✋🏽",
            category=CATEGORY,
            description="Pause the run for a set time, then pass its input on. A pause of more than "
                        "a few seconds shows a prompt to continue now or cancel the run.",
            search_aliases=["DELAY (JOV) ✋🏽", "delay", "pause", "wait", "sleep", "gate"],
            is_input_list=True,
            not_idempotent=True,
            hidden=[io.Hidden.unique_id],
            inputs=[
                io.AnyType.Input("in", optional=True,
                                 tooltip="The value held until the pause ends, then passed to OUT."),
                io.Int.Input("timer", default=0, min=-1, max=DELAY_LIMIT, optional=True,
                             tooltip="Seconds to wait. 0 = no pause; -1 = wait until continued or "
                                     "cancelled, up to the configured maximum."),
                io.Boolean.Input("enable", default=True, optional=True,
                                 tooltip="Show floating bubbles on the canvas while the prompt is up."),
            ],
            outputs=[io.AnyType.Output("OUT", display_name="OUT", is_output_list=True,
                                       tooltip="The input, passed on unchanged when the pause ends.")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import comfy.model_management
        from nodes import interrupt_processing

        ident = node_id(cls)
        settings = config.settings()
        delay_max = max(0, int(settings["delay_max"]))
        delay = parse_param(kw, "timer", EnumConvertType.INT, 0, -1, DELAY_LIMIT)[0]
        if delay < 0 or delay > delay_max:
            delay = delay_max
        if delay > max(1, int(settings["delay_min"])):
            messages.send("jovi-delay-user", ident, {"timeout": delay})

        messages.reset_requested(ident)
        pbar = Progress(delay)
        for step in range(delay):
            comfy.model_management.throw_exception_if_processing_interrupted()
            if (message := messages.poll(ident, timeout=1)) is not None:
                if message.get("cmd") is False:
                    logger.warning("delay on node %s cancelled after %d s", ident, step)
                    interrupt_processing(True)
                break
            pbar.update(step)

        data = kw.get("in", [None])
        return io.NodeOutput(data if isinstance(data, list) and data else [data])


class ExportNode(io.ComfyNode):
    """Save pictures as files or an animation."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="EXPORT (JOV) 📽",
            display_name="EXPORT 📽",
            category=CATEGORY,
            description="Save a batch of pictures as numbered PNG or JPG files, or as one animated "
                        "GIF, into ComfyUI's output folder or a folder below it.",
            search_aliases=["EXPORT (JOV) 📽", "export", "save gif", "animated gif", "save frames", "gifski"],
            is_input_list=True,
            is_output_node=True,
            not_idempotent=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The pictures to save, one file or frame each."),
                io.String.Input("path", default="", optional=True,
                                tooltip="Folder to save into. Empty = ComfyUI's output folder; a "
                                        "relative path such as 'renders/shot1' is placed below it."),
                io.Combo.Input("format", options=FORMATS, default=FORMATS[0], optional=True,
                               tooltip="gif = one animated GIF; png and jpg = one file per picture; "
                                       "gifski = a high quality GIF through the gifski program."),
                io.String.Input("prefix", default="jovi", optional=True,
                                tooltip="File name without extension. Example: 'shot' gives shot.gif, "
                                        "then shot_1.gif."),
                io.Boolean.Input("overwrite", default=False, optional=True,
                                 tooltip="Replace a file of the same name. Off = add a number instead."),
                io.Boolean.Input("opt", default=False, optional=True,
                                 tooltip="gif and png: spend longer making the file smaller."),
                io.Int.Input("quality", default=90, min=1, max=100, optional=True,
                             tooltip="gifski and jpg: picture quality. 100 = best, largest files."),
                io.Int.Input("motion", default=100, min=1, max=100, optional=True,
                             tooltip="gifski: motion quality. Lower values shrink files of moving "
                                     "scenes."),
                io.Int.Input("fps", default=24, min=1, max=60, optional=True,
                             tooltip="gif and gifski: frames per second."),
                io.Int.Input("loop", default=0, min=0, max=65535, optional=True,
                             tooltip="gif: how many times the animation repeats. 0 = forever."),
            ],
            outputs=[],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import folder_paths

        from ...modules.image.convert import tensor_to_pil

        images = [i for i in parse_param(kw, "image", EnumConvertType.IMAGE, None) if i is not None]
        if not images:
            raise ValueError("EXPORT has nothing to save. Connect pictures to 'image'.")
        prefix = sandbox.check_name(parse_param(kw, "prefix", EnumConvertType.STRING, "jovi")[0] or "jovi")
        fmt = parse_param(kw, "format", EnumConvertType.STRING, "gif")[0]
        if fmt not in FORMATS:
            raise ValueError(f"EXPORT cannot write '{fmt[:16]}'. Pick one of: {', '.join(FORMATS)}.")
        overwrite = parse_param(kw, "overwrite", EnumConvertType.BOOLEAN, False)[0]
        optimize = parse_param(kw, "opt", EnumConvertType.BOOLEAN, False)[0]
        quality = parse_param(kw, "quality", EnumConvertType.INT, 90, 1, 100)[0]
        motion = parse_param(kw, "motion", EnumConvertType.INT, 100, 1, 100)[0]
        fps = parse_param(kw, "fps", EnumConvertType.INT, 24, 1, 60)[0]
        loop = parse_param(kw, "loop", EnumConvertType.INT, 0, 0, 65535)[0]
        folder = sandbox.resolve_write_dir(parse_param(kw, "path", EnumConvertType.STRING, "")[0])
        folder.mkdir(parents=True, exist_ok=True)

        frames = [tensor_to_pil(i) for i in images]
        written: list[Path] = []
        if fmt == "gifski":
            gifski = str(config.get("gifski") or "")
            if not gifski or not os.path.isfile(gifski):
                raise ValueError("gifski is not set up. Put the full path of the gifski program in "
                                 "the gifski key of ComfyUI/user/jovimetrix/config.json, or set "
                                 "JOV_GIFSKI, then run again.")
            work = Path(folder_paths.get_temp_directory()) / f"jovi_gifski_{uuid.uuid4().hex[:16]}"
            work.mkdir(parents=True, exist_ok=False)
            frame_files = []
            try:
                for idx, frame in enumerate(frames):
                    name = work / f"frame_{idx:06d}.png"
                    frame.save(name)
                    frame_files.append(str(name))
                out = _next_free(folder, prefix, "gif", overwrite)
                cmd = [gifski, "-o", str(out), "--quality", str(quality),
                       "--motion-quality", str(motion), "--fps", str(fps), *frame_files]
                result = subprocess.run(cmd, capture_output=True, timeout=GIFSKI_TIMEOUT, check=False)
                if result.returncode != 0:
                    raise RuntimeError(f"gifski stopped with exit code {result.returncode}. Check that "
                                       "the configured program is gifski and runs on its own.")
                written.append(out)
            finally:
                for name in frame_files:
                    try:
                        os.remove(name)
                    except OSError as error:
                        logger.warning("a gifski frame could not be removed (%s)", error.strerror)
                try:
                    work.rmdir()
                except OSError:
                    pass
        elif fmt == "gif":
            out = _next_free(folder, prefix, "gif", overwrite)
            frames[0].save(out, append_images=frames[1:], disposal=2, duration=1000 / fps,
                           loop=loop, optimize=optimize, save_all=True)
            written.append(out)
        else:
            for frame in frames:
                out = _next_free(folder, prefix, fmt, overwrite)
                if fmt == "jpg":
                    frame.convert("RGB").save(out, quality=quality, optimize=optimize)
                else:
                    frame.save(out, optimize=optimize)
                written.append(out)

        logger.info("EXPORT wrote %d file(s)", len(written))
        previews = [p for p in (_preview_entry(w) for w in written) if p]
        return io.NodeOutput(ui={"images": previews} if previews else None)


class RouteNode(io.ComfyNode):
    """Pass several values through one node, keeping their order."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ROUTE (JOV) 🚌",
            display_name="ROUTE 🚌",
            category=CATEGORY,
            description="Pass up to ten values of any type through one node, each to the output "
                        "beside its input. Tidies long links across a large graph.",
            search_aliases=["ROUTE (JOV) 🚌", "route", "reroute", "bus", "pass through"],
            is_input_list=True,
            inputs=[
                BUS.Input("route", optional=True,
                          tooltip="Another ROUTE's ROUTE output, passed straight on."),
            ],
            outputs=[
                BUS.Output("ROUTE", display_name="ROUTE", tooltip="The incoming route, passed on."),
                *[io.AnyType.Output(f"out_{i}", display_name="🔮", is_output_list=True,
                                    tooltip="The value wired into the matching input.")
                  for i in range(1, ROUTE_SLOTS + 1)],
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        bus = kw.get("route", [None])
        bus = bus if isinstance(bus, list) else [bus]
        values = [v if isinstance(v, list) else [v] for k, v in kw.items() if k != "route"]
        values = values[:ROUTE_SLOTS]
        values += [[None]] * (ROUTE_SLOTS - len(values))
        return io.NodeOutput(bus[0] if len(bus) == 1 else bus, *values)


class SaveOutputNode(io.ComfyNode):
    """Save pictures as PNG files with metadata."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SAVE OUTPUT (JOV) 💾",
            display_name="SAVE OUTPUT 💾",
            category=CATEGORY,
            description="Save pictures as PNG files with a name you choose, carrying the workflow "
                        "and any extra metadata you add, into ComfyUI's output folder or a folder "
                        "below it.",
            search_aliases=["SAVE OUTPUT (JOV) 💾", "save png", "save image", "metadata"],
            is_input_list=True,
            is_output_node=True,
            not_idempotent=True,
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            inputs=[
                io.Image.Input("image", optional=True, tooltip="The pictures to save."),
                io.String.Input("path", default="", dynamic_prompts=False, optional=True,
                                tooltip="Folder to save into. Empty = ComfyUI's output folder; a "
                                        "relative path such as 'renders' is placed below it."),
                io.String.Input("name", default="output", dynamic_prompts=False, optional=True,
                                tooltip="File name without extension. Several pictures add _0, _1, "
                                        "and so on."),
                JSON.Input("meta", optional=True,
                           tooltip="Extra metadata as a dictionary, written into the file."),
                io.String.Input("user", default="", multiline=True, dynamic_prompts=False,
                                optional=True,
                                tooltip='Extra metadata typed as JSON. Example: {"artist": "me"}'),
                io.Boolean.Input("overwrite", default=False, optional=True,
                                 tooltip="Replace a file of the same name. Off = add a number instead."),
            ],
            outputs=[],
        )

    @classmethod
    def fingerprint_inputs(cls, **kw) -> float:
        return float("nan")

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import numpy as np
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        from ...modules.image.convert import tensor_to_cv

        images = [i for i in parse_param(kw, "image", EnumConvertType.IMAGE, None) if i is not None]
        if not images:
            raise ValueError("SAVE OUTPUT has nothing to save. Connect pictures to 'image'.")
        folder = sandbox.resolve_write_dir(parse_param(kw, "path", EnumConvertType.STRING, "")[0])
        stem = sandbox.check_name(parse_param(kw, "name", EnumConvertType.STRING, "output")[0] or "output")
        if stem.lower().endswith(".png"):
            stem = stem[:-4]
        overwrite = parse_param(kw, "overwrite", EnumConvertType.BOOLEAN, False)[0]

        metadata: dict[str, Any] = {}
        for value in kw.get("meta", []) or []:
            if isinstance(value, dict):
                metadata.update(value)
        for text in kw.get("user", []) or []:
            if isinstance(text, str) and text.strip():
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("SAVE OUTPUT's user metadata is not valid JSON and was skipped")
                    continue
                if isinstance(data, dict):
                    metadata.update(data)

        meta_png = PngInfo()
        try:
            from comfy.cli_args import args
            with_workflow = not args.disable_metadata
        except Exception:
            with_workflow = True
        if with_workflow:
            if cls.hidden.prompt is not None:
                meta_png.add_text("prompt", json.dumps(cls.hidden.prompt))
            for key, value in (cls.hidden.extra_pnginfo or {}).items():
                meta_png.add_text(str(key), json.dumps(value))
        for key, value in metadata.items():
            try:
                meta_png.add_text(str(key), json.dumps(value, default=str))
            except (TypeError, ValueError):
                logger.warning("SAVE OUTPUT metadata key '%s' could not be written", str(key)[:64])

        folder.mkdir(parents=True, exist_ok=True)
        written = []
        pbar = Progress(len(images))
        for idx, image in enumerate(images):
            name = stem if len(images) == 1 else f"{stem}_{idx}"
            out = _next_free(folder, name, "png", overwrite)
            pixels = np.clip(tensor_to_cv(image), 0, 255).astype(np.uint8)
            if pixels.ndim == 3 and pixels.shape[2] == 1:
                pixels = pixels[..., 0]
            Image.fromarray(pixels).save(out, pnginfo=meta_png)
            written.append(out)
            pbar.update(idx)

        logger.info("SAVE OUTPUT wrote %d file(s)", len(written))
        previews = [p for p in (_preview_entry(w) for w in written) if p]
        return io.NodeOutput(ui={"images": previews} if previews else None)


NODES = [DelayNode, ExportNode, RouteNode, SaveOutputNode]
