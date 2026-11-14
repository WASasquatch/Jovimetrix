"""Adjust nodes: blur, colour, edges, emboss, levels, light, morphology, pixel effects and sharpen."""

from __future__ import annotations

import sys

from comfy_api.latest import io

from ..modules.enums import \
    EnumAdjustBlur, EnumAdjustColor, EnumAdjustEdge, EnumAdjustMorpho, EnumAdjustPixel, \
    EnumAutoLevel, EnumConvertType

from ..modules.node import Progress, category, image_stack
from ..modules.params import parse_param, zip_longest_fill
from ..modules.types import IMAGE_OUTPUTS, IMAGE_TYPES, VEC2, VEC3

CATEGORY = category("ADJUST")

#: Largest kernel radius an adjust node accepts.
MAX_RADIUS = 1023

IMAGE_IN = [
    io.MultiType.Input(
        "image", IMAGE_TYPES, optional=True,
        tooltip="The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by "
                "frame. With nothing connected a small black square is used.",
    ),
]


class AdjustBlurNode(io.ComfyNode):
    """Blur an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: BLUR (JOV)",
            display_name="ADJUST: BLUR",
            category=CATEGORY,
            description="Soften a picture with a box, stack, Gaussian or median blur. Median "
                        "blur removes speckle noise while keeping edges.",
            search_aliases=["ADJUST: BLUR (JOV)", "blur", "gaussian", "median", "soften"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "func", options=EnumAdjustBlur._member_names_,
                    default=EnumAdjustBlur.BLUR.name, optional=True,
                    tooltip="BLUR = box average; STACK_BLUR = fast near-Gaussian; GAUSSIAN_BLUR "
                            "= smooth falloff; MEDIAN_BLUR = removes speckles and keeps edges.",
                ),
                io.Int.Input(
                    "radius", default=3, min=3, max=MAX_RADIUS, optional=True,
                    tooltip="Size of the blur in pixels. Even values are raised to the next odd "
                            "number. 3 = slight; 31 = heavy.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_blur
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        op = parse_param(kw, "func", EnumAdjustBlur, EnumAdjustBlur.BLUR.name)
        radius = parse_param(kw, "radius", EnumConvertType.INT, 3, 3, MAX_RADIUS)
        params = list(zip_longest_fill(pA, op, radius))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, op, radius) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            pA = image_blur(pA, op, radius)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustColorNode(io.ComfyNode):
    """Shift the channels of an image in a chosen colour space."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: COLOR (JOV)",
            display_name="ADJUST: COLOR",
            category=CATEGORY,
            description="Shift a picture's three colour channels in RGB, HSV, YUV, LAB, LUV or "
                        "XYZ space. Useful for hue rotation, saturation pushes and tints.",
            search_aliases=["ADJUST: COLOR (JOV)", "hue", "saturation", "tint", "color shift"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "func", options=EnumAdjustColor._member_names_,
                    default=EnumAdjustColor.RGB.name, optional=True,
                    tooltip="Colour space the three shifts apply in. HSV: hue, saturation, value; "
                            "LAB: lightness and two colour axes; RGB: red, green, blue.",
                ),
                VEC3.Input(
                    "vector", optional=True,
                    tooltip="Shift for each channel of the chosen space, -1 to 1. 0 = unchanged; "
                            "in HSV, x = 0.5 turns the hue half way round.",
                    extra_dict={"default": (0, 0, 0), "mij": -1, "maj": 1, "step": 0.025},
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_color
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        op = parse_param(kw, "func", EnumAdjustColor, EnumAdjustColor.RGB.name)
        vec = parse_param(kw, "vector", EnumConvertType.VEC3, (0, 0, 0))
        params = list(zip_longest_fill(pA, op, vec))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, op, vec) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            pA = image_color(pA, op, vec[0], vec[1], vec[2])
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustEdgeNode(io.ComfyNode):
    """Find the edges in an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: EDGE (JOV)",
            display_name="ADJUST: EDGE",
            category=CATEGORY,
            description="Find the edges in a picture with Canny, Sobel, Laplacian, Prewitt, "
                        "Scharr or a morphological outline. Good for line art and edge masks.",
            search_aliases=["ADJUST: EDGE (JOV)", "edge", "canny", "sobel", "outline", "line art"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "func", options=EnumAdjustEdge._member_names_,
                    default=EnumAdjustEdge.CANNY.name, optional=True,
                    tooltip="CANNY = thin clean lines; SOBEL, SCHARR, PREWITT = gradient strength; "
                            "LAPLACIAN = fine detail; OUTLINE = thick shape border.",
                ),
                io.Int.Input(
                    "radius", default=1, min=1, max=MAX_RADIUS, optional=True,
                    tooltip="Kernel size in pixels, raised to the next odd number. Larger values "
                            "pick out broader edges. Sobel and Laplacian stop at 31.",
                ),
                io.Int.Input(
                    "iter", default=1, min=1, max=1000, optional=True,
                    tooltip="How many times OUTLINE grows the border. The other methods ignore it.",
                ),
                VEC2.Input(
                    "lo-hi", optional=True,
                    tooltip="CANNY's two thresholds, 0 to 1. Edges stronger than hi are kept; "
                            "those between lo and hi are kept only when joined to a strong edge.",
                    extra_dict={"default": (0, 1), "mij": 0, "maj": 1, "step": 0.01},
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_edge
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, image_convert, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        op = parse_param(kw, "func", EnumAdjustEdge, EnumAdjustEdge.CANNY.name)
        radius = parse_param(kw, "radius", EnumConvertType.INT, 1, 1, MAX_RADIUS)
        count = parse_param(kw, "iter", EnumConvertType.INT, 1, 1, 1000)
        lohi = parse_param(kw, "lo-hi", EnumConvertType.VEC2, (0, 1), 0, 1)
        params = list(zip_longest_fill(pA, op, radius, count, lohi))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, op, radius, count, lohi) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            alpha = image_mask(pA)
            pA = image_edge(image_convert(pA, 3), op, radius, count, lohi[0], lohi[1])
            pA = image_mask_add(pA, alpha)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustEmbossNode(io.ComfyNode):
    """Emboss an image as if lit from one direction."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: EMBOSS (JOV)",
            display_name="ADJUST: EMBOSS",
            category=CATEGORY,
            description="Turn a picture into a raised relief lit from one direction. Useful for "
                        "stamped, carved or height-map looks.",
            search_aliases=["ADJUST: EMBOSS (JOV)", "emboss", "relief", "bump"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Float.Input(
                    "heading", default=-45, min=-sys.float_info.max, max=sys.float_info.max,
                    step=0.1, optional=True,
                    tooltip="Direction the light comes from, in degrees. 0 = right; 90 = below; "
                            "180 = left; -90 = above.",
                ),
                io.Float.Input(
                    "elevation", default=45, min=-sys.float_info.max, max=sys.float_info.max,
                    step=0.1, optional=True,
                    tooltip="Height of the light, in degrees. 0 = grazing, deep shadows; "
                            "90 = straight down, flat.",
                ),
                io.Float.Input(
                    "depth", default=10, min=0, max=sys.float_info.max, step=0.1, optional=True,
                    tooltip="How deep the relief looks. 0 = flat grey; 10 = moderate; 50 = sharp.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_emboss
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        heading = parse_param(kw, "heading", EnumConvertType.FLOAT, -45)
        elevation = parse_param(kw, "elevation", EnumConvertType.FLOAT, 45)
        depth = parse_param(kw, "depth", EnumConvertType.FLOAT, 10, 0)
        params = list(zip_longest_fill(pA, heading, elevation, depth))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, heading, elevation, depth) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            alpha = image_mask(pA)
            pA = image_emboss(pA, heading, elevation, depth)
            pA = image_mask_add(pA, alpha)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustLevelNode(io.ComfyNode):
    """Set an image's black, mid and white points, by hand or automatically."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: LEVELS (JOV)",
            display_name="ADJUST: LEVELS",
            category=CATEGORY,
            description="Set a picture's black point, midtone and white point by hand, or stretch "
                        "each channel so its darkest pixel becomes black and its brightest white.",
            search_aliases=["ADJUST: LEVELS (JOV)", "levels", "auto level", "contrast stretch"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                VEC3.Input(
                    "lmh", optional=True,
                    tooltip="MANUAL input points, 0 to 1: LOW becomes black, HIGH becomes white, "
                            "MID sets the midtone. 0.5 = no midtone change; lower brightens.",
                    extra_dict={"default": (0, 0.5, 1), "mij": 0, "maj": 1, "step": 0.01,
                                "label": ["LOW", "MID", "HIGH"]},
                ),
                VEC2.Input(
                    "range", optional=True,
                    tooltip="MANUAL output range, 0 to 1: the darkest and brightest values the "
                            "result may take. (0, 1) = full range.",
                    extra_dict={"default": (0, 1), "mij": 0, "maj": 1, "step": 0.01,
                                "label": ["IN", "OUT"]},
                ),
                io.Combo.Input(
                    "mode", options=EnumAutoLevel._member_names_,
                    default=EnumAutoLevel.MANUAL.name, optional=True,
                    tooltip="MANUAL = use lmh and range; AUTO = stretch each channel ignoring the "
                            "outer 1 percent; HISTOGRAM = stretch ignoring the share set by clip.",
                ),
                io.Float.Input(
                    "clip", default=0.5, min=0, max=1.0, step=0.01, optional=True,
                    tooltip="HISTOGRAM only: percent of pixels ignored at each end before "
                            "stretching. 0 = none; 0.5 = half a percent; 1 = one percent.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_autolevel, image_autolevel_histogram
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_levels
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        lmh = parse_param(kw, "lmh", EnumConvertType.VEC3, (0, 0.5, 1))
        inout = parse_param(kw, "range", EnumConvertType.VEC2, (0, 1))
        mode = parse_param(kw, "mode", EnumAutoLevel, EnumAutoLevel.MANUAL.name)
        clip = parse_param(kw, "clip", EnumConvertType.FLOAT, 0.5, 0, 1)
        params = list(zip_longest_fill(pA, lmh, inout, mode, clip))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, lmh, inout, mode, clip) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            match mode:
                case EnumAutoLevel.AUTO:
                    pA = image_autolevel(pA)
                case EnumAutoLevel.HISTOGRAM:
                    pA = image_autolevel_histogram(pA, clip)
                case _:
                    low, mid, high = lmh
                    start, end = inout
                    pA = image_levels(pA, low, mid, high, start, end)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustLightNode(io.ComfyNode):
    """Brightness, contrast, equalisation, exposure and gamma in one node."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: LIGHT (JOV)",
            display_name="ADJUST: LIGHT",
            category=CATEGORY,
            description="Tonal adjustments applied in order: brightness, contrast, histogram "
                        "equalisation, exposure and gamma. Leave a control at its default to skip it.",
            search_aliases=["ADJUST: LIGHT (JOV)", "brightness", "contrast", "exposure", "gamma", "equalize"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Float.Input(
                    "brightness", default=0.5, min=0, max=1, step=0.01, optional=True,
                    tooltip="0.5 = unchanged; 0 = black; 1 = white.",
                ),
                io.Float.Input(
                    "contrast", default=0, min=-1, max=1, step=0.01, optional=True,
                    tooltip="0 = unchanged; -1 = flat grey; 1 = maximum contrast.",
                ),
                io.Boolean.Input(
                    "equalize", default=False, optional=True,
                    tooltip="Spread the brightness histogram evenly, which lifts detail in flat "
                            "or murky pictures.",
                ),
                io.Float.Input(
                    "exposure", default=1, min=-8, max=8, step=0.01, optional=True,
                    tooltip="Light is multiplied by 2 to this power, in linear light. 1 and 0 both "
                            "leave the picture unchanged; 2 = four times brighter; -1 = half.",
                ),
                io.Float.Input(
                    "gamma", default=1, min=0, max=8, step=0.01, optional=True,
                    tooltip="1 = unchanged; above 1 brightens the midtones; below 1 darkens them; "
                            "0 = black.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_brightness, image_contrast, image_equalize, \
            image_exposure, image_gamma
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        brightness = parse_param(kw, "brightness", EnumConvertType.FLOAT, 0.5, 0, 1)
        contrast = parse_param(kw, "contrast", EnumConvertType.FLOAT, 0, -1, 1)
        equalize = parse_param(kw, "equalize", EnumConvertType.BOOLEAN, False)
        exposure = parse_param(kw, "exposure", EnumConvertType.FLOAT, 1, -8, 8)
        gamma = parse_param(kw, "gamma", EnumConvertType.FLOAT, 1, 0, 8)
        params = list(zip_longest_fill(pA, brightness, contrast, equalize, exposure, gamma))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, brightness, contrast, equalize, exposure, gamma) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            alpha = image_mask(pA)

            brightness = 2. * (brightness - 0.5)
            if brightness != 0:
                pA = image_brightness(pA, brightness)
            if contrast != 0:
                pA = image_contrast(pA, contrast)
            if equalize:
                pA = image_equalize(pA)
            if exposure != 1:
                pA = image_exposure(pA, exposure)
            if gamma != 1:
                pA = image_gamma(pA, gamma)

            pA = image_mask_add(pA, alpha)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustMorphNode(io.ComfyNode):
    """Grow, shrink, open or close the shapes in an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: MORPHOLOGY (JOV)",
            display_name="ADJUST: MORPHOLOGY",
            category=CATEGORY,
            description="Grow, shrink, open or close the shapes in a picture or mask. Use it to "
                        "thicken a mask, remove small specks, or fill small holes.",
            search_aliases=["ADJUST: MORPHOLOGY (JOV)", "dilate", "erode", "grow mask", "shrink mask"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "func", options=EnumAdjustMorpho._member_names_,
                    default=EnumAdjustMorpho.DILATE.name, optional=True,
                    tooltip="DILATE = grow bright areas; ERODE = shrink them; OPEN = remove specks; "
                            "CLOSE = fill holes; TOPHAT and BLACKHAT = keep only small bright or "
                            "dark details.",
                ),
                io.Int.Input(
                    "radius", default=1, min=1, max=MAX_RADIUS, optional=True,
                    tooltip="Size of the square kernel in pixels, raised to the next odd number.",
                ),
                io.Int.Input(
                    "iter", default=1, min=1, max=1000, optional=True,
                    tooltip="How many times the operation repeats. Each pass grows or shrinks by "
                            "the radius again.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_morphology
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        op = parse_param(kw, "func", EnumAdjustMorpho, EnumAdjustMorpho.DILATE.name)
        kernel = parse_param(kw, "radius", EnumConvertType.INT, 1, 1, MAX_RADIUS)
        count = parse_param(kw, "iter", EnumConvertType.INT, 1, 1, 1000)
        params = list(zip_longest_fill(pA, op, kernel, count))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, op, kernel, count) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            alpha = image_mask(pA)
            pA = image_morphology(pA, op, kernel, count)
            pA = image_mask_add(pA, alpha)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustPixelNode(io.ComfyNode):
    """Pixelate, pixel-scale, quantise or posterise an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: PIXEL (JOV)",
            display_name="ADJUST: PIXEL",
            category=CATEGORY,
            description="Pixel-level effects: pixelate into blocks, rescale for a retro look, "
                        "reduce to fewer colours, or posterise into bands.",
            search_aliases=["ADJUST: PIXEL (JOV)", "pixelate", "posterize", "quantize", "retro", "8 bit"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "func", options=EnumAdjustPixel._member_names_,
                    default=EnumAdjustPixel.PIXELATE.name, optional=True,
                    tooltip="PIXELATE = average into blocks; PIXELSCALE = shrink then enlarge "
                            "with hard edges; QUANTIZE = fewer colours by clustering; POSTERIZE = "
                            "fewer brightness levels.",
                ),
                io.Float.Input(
                    "value", default=0, min=0, max=1, step=0.01, optional=True,
                    tooltip="Strength, 0 to 1. 0 = unchanged; higher values give bigger blocks "
                            "or fewer colours.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_pixelate, image_pixelscale, image_posterize, \
            image_quantize
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        op = parse_param(kw, "func", EnumAdjustPixel, EnumAdjustPixel.PIXELATE.name)
        val = parse_param(kw, "value", EnumConvertType.FLOAT, 0, 0, 1)
        params = list(zip_longest_fill(pA, op, val))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, op, val) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA, chan=4)
            alpha = image_mask(pA)
            match op:
                case EnumAdjustPixel.PIXELSCALE:
                    pA = image_pixelscale(pA, val)
                case EnumAdjustPixel.QUANTIZE:
                    pA = image_quantize(pA, val)
                case EnumAdjustPixel.POSTERIZE:
                    pA = image_posterize(pA, val)
                case _:
                    pA = image_pixelate(pA, val / 2.)
            pA = image_mask_add(pA, alpha)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class AdjustSharpenNode(io.ComfyNode):
    """Sharpen an image with an unsharp mask."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ADJUST: SHARPEN (JOV)",
            display_name="ADJUST: SHARPEN",
            category=CATEGORY,
            description="Sharpen a picture with an unsharp mask. The threshold leaves flat, "
                        "low-contrast areas such as skin and sky untouched.",
            search_aliases=["ADJUST: SHARPEN (JOV)", "sharpen", "unsharp mask", "detail"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Float.Input(
                    "amount", default=0, min=0, max=1, step=0.01, optional=True,
                    tooltip="0 = unchanged; 0.05 = crisp; 1 = extreme.",
                ),
                io.Float.Input(
                    "threshold", default=0, min=0, max=1, step=0.01, optional=True,
                    tooltip="0 = sharpen everywhere; higher values skip areas whose local "
                            "contrast is below it, keeping noise in flat areas down.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_sharpen
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        amount = parse_param(kw, "amount", EnumConvertType.FLOAT, 0, 0, 1)
        threshold = parse_param(kw, "threshold", EnumConvertType.FLOAT, 0, 0, 1)
        params = list(zip_longest_fill(pA, amount, threshold))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, amount, threshold) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            pA = image_sharpen(pA, amount / 2., threshold=threshold / 25.5)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


NODES = [
    AdjustBlurNode, AdjustColorNode, AdjustEdgeNode, AdjustEmbossNode, AdjustLevelNode,
    AdjustLightNode, AdjustMorphNode, AdjustPixelNode, AdjustSharpenNode,
]
