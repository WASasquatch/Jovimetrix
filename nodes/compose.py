"""Composition nodes: blending, colour-range masks, histograms, channel split, merge and swap,
and thresholds."""

from __future__ import annotations

from comfy_api.latest import io

from ..modules.enums import \
    EnumBlendType, EnumConvertType, EnumImageType, EnumInterpolation, EnumPixelSwizzle, \
    EnumScaleInputMode, EnumScaleMode, EnumThreshold, EnumThresholdAdapt
from ..modules.limits import check_canvas
from ..modules.node import Progress, category, image_stack
from ..modules.params import IMAGE_SIZE_MIN, parse_param, zip_longest_fill
from ..modules.types import IMAGE_OUTPUTS, IMAGE_TYPES, VEC2, VEC3, VEC4

CATEGORY = category("COMPOSE")

IMAGE_IN = [
    io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                       tooltip="The picture: RGBA, RGB or a mask. A batch is processed frame by frame."),
]

MATTE_IN = VEC4.Input(
    "matte", optional=True,
    tooltip="Colour behind transparent areas and around a resized picture, RGBA 0 to 255.",
    extra_dict={"default": (0, 0, 0, 255), "rgb": True},
)

MODE_IN = io.Combo.Input(
    "mode", options=EnumScaleMode._member_names_, default=EnumScaleMode.MATTE.name, optional=True,
    tooltip="Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and "
            "trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh.",
)

WH_IN = VEC2.Input(
    "wh", optional=True,
    tooltip="Target width and height when mode is not MATTE.",
    extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True, "label": ["W", "H"]},
)

SAMPLE_IN = io.Combo.Input(
    "sample", options=EnumInterpolation._member_names_, default=EnumInterpolation.LANCZOS4.name,
    optional=True,
    tooltip="Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels.",
)


class BlendNode(io.ComfyNode):
    """Blend a foreground over a background with a blend mode."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BLEND (JOV) ⚗️",
            display_name="BLEND ⚗️",
            category=CATEGORY,
            description="Layer a foreground over a background with one of thirty blend modes, "
                        "such as multiply, screen or overlay, through an optional mask. The "
                        "workhorse for compositing.",
            search_aliases=["BLEND (JOV) ⚗️", "blend", "composite", "overlay", "multiply", "screen", "layer"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("back", IMAGE_TYPES, optional=True,
                                   tooltip="Background picture. Sets the size unless mode resizes."),
                io.MultiType.Input("fore", IMAGE_TYPES, optional=True,
                                   tooltip="Foreground picture, centred on the background."),
                io.MultiType.Input("mask", IMAGE_TYPES, optional=True,
                                   tooltip="Where the foreground shows: white shows it, black "
                                           "hides it. When empty, the foreground's own alpha is used."),
                io.Combo.Input(
                    "func", options=EnumBlendType._member_names_,
                    default=EnumBlendType.NORMAL.name, optional=True,
                    tooltip="Blend mode. NORMAL = place on top; MULTIPLY = darken; SCREEN = "
                            "lighten; OVERLAY = contrast; DIFFERENCE = compare two pictures.",
                ),
                io.Float.Input("alpha", default=1, min=0, max=1, step=0.01, optional=True,
                               tooltip="Opacity of the foreground. 0 = background only; 1 = full blend."),
                io.Boolean.Input("swap", default=False, optional=True,
                                 tooltip="Exchange background and foreground."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert the mask, so the foreground shows where it was black."),
                MODE_IN,
                WH_IN,
                SAMPLE_IN,
                MATTE_IN,
                io.Combo.Input(
                    "input", options=EnumScaleInputMode._member_names_,
                    default=EnumScaleInputMode.NONE.name, optional=True,
                    tooltip="Fit the inputs to each other before blending. NONE = centre them as "
                            "they are; FIT, CROP and ASPECT size both to the larger one.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_blend, image_scalefit
        from ..modules.image.convert import frame_outputs, image_mask, to_frame
        from ..modules.image.misc import image_by_size

        back = parse_param(kw, "back", EnumConvertType.IMAGE, None)
        fore = parse_param(kw, "fore", EnumConvertType.IMAGE, None)
        mask = parse_param(kw, "mask", EnumConvertType.MASK, None)
        func = parse_param(kw, "func", EnumBlendType, EnumBlendType.NORMAL.name)
        alpha = parse_param(kw, "alpha", EnumConvertType.FLOAT, 1, 0, 1)
        swap = parse_param(kw, "swap", EnumConvertType.BOOLEAN, False)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        inputMode = parse_param(kw, "input", EnumScaleInputMode, EnumScaleInputMode.NONE.name)
        params = list(zip_longest_fill(back, fore, mask, func, alpha, swap, invert, mode, wihi,
                                       sample, matte, inputMode))
        images = []
        pbar = Progress(len(params))
        for idx, (back, fore, mask, func, alpha, swap, invert, mode, wihi, sample, matte,
                  inputMode) in enumerate(params):
            if swap:
                back, fore = fore, back

            width, height = IMAGE_SIZE_MIN, IMAGE_SIZE_MIN
            if back is not None:
                height, width = back.shape[:2]
            elif fore is not None:
                height, width = fore.shape[:2]
            elif mask is not None:
                height, width = mask.shape[:2]
            elif mode != EnumScaleMode.MATTE:
                width, height = check_canvas(*wihi)

            back = channel_solid(width, height, matte) if back is None else to_frame(back)
            fore = channel_solid(width, height, list(matte[:3]) + [0], EnumImageType.RGBA) \
                if fore is None else to_frame(fore)
            mask = image_mask(fore, 255) if mask is None else to_frame(mask, chan=1)
            if invert:
                mask = 255 - mask

            if inputMode != EnumScaleInputMode.NONE:
                _, w, h = image_by_size([back, fore])
                back = image_scalefit(back, w, h, inputMode, sample, matte)
                fore = image_scalefit(fore, w, h, inputMode, sample, matte)
                mask = image_scalefit(mask, w, h, inputMode, sample)
                back = image_scalefit(back, w, h, EnumScaleMode.RESIZE_MATTE, sample, matte)
                fore = image_scalefit(fore, w, h, EnumScaleMode.RESIZE_MATTE, sample, (0, 0, 0, 255))
                mask = image_scalefit(mask, w, h, EnumScaleMode.RESIZE_MATTE, sample, (255, 255, 255, 255))

            img = image_blend(back, fore, mask, func, alpha)
            if mode != EnumScaleMode.MATTE:
                width, height = check_canvas(*wihi)
                img = image_scalefit(img, width, height, mode, sample, matte)
            images.append(frame_outputs(img, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class FilterMaskNode(io.ComfyNode):
    """Mask the pixels that fall inside a colour range."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FILTER MASK (JOV) 🤿",
            display_name="FILTER MASK 🤿",
            category=CATEGORY,
            description="Make a mask from the pixels close to one colour, or between two colours. "
                        "Use it to key out a background or isolate one colour for adjustment.",
            search_aliases=["FILTER MASK (JOV) 🤿", "color key", "chroma key", "color range", "select color"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                VEC3.Input("start", optional=True,
                           tooltip="The colour to keep, RGB 0 to 255; with range on, the low end.",
                           extra_dict={"default": (128, 128, 128), "rgb": True}),
                io.Boolean.Input("range", default=False, optional=True,
                                 tooltip="Keep every colour between start and end rather than "
                                         "only those near start."),
                VEC3.Input("end", optional=True,
                           tooltip="The high end of the colour range, used when range is on.",
                           extra_dict={"default": (128, 128, 128), "rgb": True}),
                VEC3.Input("fuzz", optional=True,
                           tooltip="Tolerance per channel, 0 to 1, added on both sides. 0 = exact "
                                   "colour only; 0.1 = close shades; 0.5 = half the range.",
                           extra_dict={"default": (0.5, 0.5, 0.5), "mij": 0, "maj": 1}),
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import torch

        from ..modules.image.adjust import image_filter
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        start = parse_param(kw, "start", EnumConvertType.VEC3INT, (128, 128, 128), 0, 255)
        use_range = parse_param(kw, "range", EnumConvertType.BOOLEAN, False)
        end = parse_param(kw, "end", EnumConvertType.VEC3INT, (128, 128, 128), 0, 255)
        fuzz = parse_param(kw, "fuzz", EnumConvertType.VEC3, (0.5, 0.5, 0.5), 0, 1)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, start, use_range, end, fuzz, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, start, use_range, end, fuzz, matte) in enumerate(params):
            img = torch.zeros((IMAGE_SIZE_MIN, IMAGE_SIZE_MIN, 3)) if pA is None else to_frame(pA)
            img, mask = image_filter(img, start, end, fuzz, use_range)
            if img.shape[2] == 3:
                img = torch.cat([img, torch.zeros_like(img[..., :1])], dim=2)
            img[..., 3] = mask
            images.append(frame_outputs(img, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class HistogramNode(io.ComfyNode):
    """Draw the brightness histogram of an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="HISTOGRAM (JOV)",
            display_name="HISTOGRAM",
            category=CATEGORY,
            description="Draw a picture's brightness histogram: how many pixels sit at each level "
                        "from black on the left to white on the right. Shows clipping and "
                        "contrast at a glance.",
            search_aliases=["HISTOGRAM (JOV)", "histogram", "levels graph", "exposure check"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                VEC2.Input("wh", optional=True, tooltip="Width and height of the histogram picture.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_histogram2
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_resize
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        params = list(zip_longest_fill(pA, wihi))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, wihi) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            width, height = check_canvas(*wihi)
            hist_img = image_resize(image_histogram2(pA, bins=256), width, height, EnumInterpolation.NEAREST)
            images.append(frame_outputs(hist_img))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class PixelMergeNode(io.ComfyNode):
    """Build an image from separate red, green, blue and alpha planes."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PIXEL MERGE (JOV) 🫂",
            display_name="PIXEL MERGE 🫂",
            category=CATEGORY,
            description="Build a picture from separate red, green, blue and alpha planes, filling "
                        "any missing plane from a base picture or the matte. The partner of "
                        "PIXEL SPLIT, for channel packing.",
            search_aliases=["PIXEL MERGE (JOV) 🫂", "merge channels", "channel pack", "combine rgba"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="Base picture whose channels fill any plane not connected."),
                io.MultiType.Input("❤️", IMAGE_TYPES, optional=True, tooltip="Red channel plane."),
                io.MultiType.Input("💚", IMAGE_TYPES, optional=True, tooltip="Green channel plane."),
                io.MultiType.Input("💙", IMAGE_TYPES, optional=True, tooltip="Blue channel plane."),
                io.MultiType.Input("🤍", IMAGE_TYPES, optional=True, tooltip="Alpha channel plane."),
                VEC4.Input("matte", optional=True,
                           tooltip="Level used for a channel with no plane and no base picture, "
                                   "RGBA 0 to 255.",
                           extra_dict={"default": (0, 0, 0, 255), "rgb": True}),
                VEC4.Input("flip", optional=True,
                           tooltip="How far to invert each plane before merging, R, G, B, A, 0 to 1. "
                                   "0 = as is; 1 = fully inverted.",
                           extra_dict={"default": (0, 0, 0, 0), "mij": 0, "maj": 1, "step": 0.01}),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert the colour of the merged picture, alpha kept."),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import torch

        from ..modules.image.adjust import image_invert
        from ..modules.image.channel import channel_merge
        from ..modules.image.compose import image_scalefit, image_split
        from ..modules.image.convert import frame_outputs, image_convert, to_frame
        from ..modules.image.misc import image_minmax

        rgba = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        R = parse_param(kw, "❤️", EnumConvertType.MASK, None)
        G = parse_param(kw, "💚", EnumConvertType.MASK, None)
        B = parse_param(kw, "💙", EnumConvertType.MASK, None)
        A = parse_param(kw, "🤍", EnumConvertType.MASK, None)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        flip = parse_param(kw, "flip", EnumConvertType.VEC4, (0, 0, 0, 0), 0, 1)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        params = list(zip_longest_fill(rgba, R, G, B, A, matte, flip, invert))
        images = []
        pbar = Progress(len(params))
        for idx, (rgba, r, g, b, a, matte, flip, invert) in enumerate(params):
            replace = r, g, b, a
            if rgba is not None:
                planes = image_split(to_frame(rgba, chan=4))
                img = [to_frame(replace[i]) if replace[i] is not None else x for i, x in enumerate(planes)]
            else:
                img = [to_frame(x) if x is not None else x for x in replace]

            _, _, w_max, h_max = image_minmax(img)
            for i, x in enumerate(img):
                if x is None:
                    x = torch.full((h_max, w_max, 1), float(matte[i]) / 255.0)
                else:
                    x = image_convert(x, 1)
                    x = image_scalefit(x, w_max, h_max, EnumScaleMode.ASPECT)
                if flip[i] != 0:
                    x = image_invert(x, flip[i])
                img[i] = x

            img = channel_merge(img)
            if invert:
                img = image_invert(img, 1)
            images.append(frame_outputs(img, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class PixelSplitNode(io.ComfyNode):
    """Split an image into its red, green, blue and alpha planes."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="PIXEL SPLIT (JOV) 💔",
            display_name="PIXEL SPLIT 💔",
            category=CATEGORY,
            description="Split a picture into its red, green, blue and alpha channels as masks, "
                        "plus its RGB. Edit channels separately and rebuild them with PIXEL MERGE.",
            search_aliases=["PIXEL SPLIT (JOV) 💔", "split channels", "rgba channels", "extract alpha"],
            is_input_list=True,
            inputs=[*IMAGE_IN],
            outputs=[
                io.Mask.Output("❤️", display_name="❤️", is_output_list=True,
                               tooltip="The red channel as a mask."),
                io.Mask.Output("💚", display_name="💚", is_output_list=True,
                               tooltip="The green channel as a mask."),
                io.Mask.Output("💙", display_name="💙", is_output_list=True,
                               tooltip="The blue channel as a mask."),
                io.Mask.Output("🤍", display_name="🤍", is_output_list=True,
                               tooltip="The alpha channel as a mask; white when the picture has no alpha."),
                io.Image.Output("RGB", display_name="RGB", is_output_list=True,
                                tooltip="The picture without its alpha."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_split
        from ..modules.image.convert import frame_tensor, image_convert, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        images = []
        pbar = Progress(len(pA))
        for idx, img in enumerate(pA):
            img = channel_solid(chan=EnumImageType.RGBA) if img is None else to_frame(img, chan=4)
            out = [frame_tensor(x, True) for x in image_split(img)] + [frame_tensor(image_convert(img, 3))]
            images.append(out)
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class PixelSwapNode(io.ComfyNode):
    """Build an image whose channels each come from one of two images or a constant."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        swizzle = EnumPixelSwizzle._member_names_
        return io.Schema(
            node_id="PIXEL SWAP (JOV) 🔃",
            display_name="PIXEL SWAP 🔃",
            category=CATEGORY,
            description="Build a picture whose red, green, blue and alpha each come from any "
                        "channel of picture A, picture B or a constant. Swap channels or move a "
                        "mask into alpha.",
            search_aliases=["PIXEL SWAP (JOV) 🔃", "swap channels", "channel shuffle", "swizzle"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("source", IMAGE_TYPES, optional=True,
                                   tooltip="Picture A. Sets the size of the result."),
                io.MultiType.Input("target", IMAGE_TYPES, optional=True,
                                   tooltip="Picture B, fitted to A's size."),
                io.Combo.Input("swap r", options=swizzle, default=EnumPixelSwizzle.RED_A.name,
                               optional=True,
                               tooltip="Source of red: a channel of A (_A) or B (_B), or "
                                       "CONSTANT from matte."),
                io.Combo.Input("swap g", options=swizzle, default=EnumPixelSwizzle.GREEN_A.name,
                               optional=True, tooltip="Source of green."),
                io.Combo.Input("swap b", options=swizzle, default=EnumPixelSwizzle.BLUE_A.name,
                               optional=True, tooltip="Source of blue."),
                io.Combo.Input("swap a", options=swizzle, default=EnumPixelSwizzle.ALPHA_A.name,
                               optional=True, tooltip="Source of alpha."),
                VEC4.Input("matte", optional=True,
                           tooltip="Constant for each channel set to CONSTANT, RGBA 0 to 255.",
                           extra_dict={"default": (0, 0, 0, 255), "rgb": True}),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid, channel_swap
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "source", EnumConvertType.IMAGE, None)
        pB = parse_param(kw, "target", EnumConvertType.IMAGE, None)
        swap_r = parse_param(kw, "swap r", EnumPixelSwizzle, EnumPixelSwizzle.RED_A.name)
        swap_g = parse_param(kw, "swap g", EnumPixelSwizzle, EnumPixelSwizzle.GREEN_A.name)
        swap_b = parse_param(kw, "swap b", EnumPixelSwizzle, EnumPixelSwizzle.BLUE_A.name)
        swap_a = parse_param(kw, "swap a", EnumPixelSwizzle, EnumPixelSwizzle.ALPHA_A.name)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, pB, swap_r, swap_g, swap_b, swap_a, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, pB, swap_r, swap_g, swap_b, swap_a, matte) in enumerate(params):
            if pA is None and pB is None:
                images.append(frame_outputs(channel_solid()))
                pbar.update(idx)
                continue
            if pA is None:
                h, w = pB.shape[:2]
                pA = channel_solid(w, h)
            else:
                h, w = pA.shape[:2]
                pA = to_frame(pA)
            pB = channel_solid(w, h) if pB is None else to_frame(pB)
            out = channel_swap(pA, pB, (swap_r, swap_g, swap_b, swap_a), matte)
            images.append(frame_outputs(out))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class ThresholdNode(io.ComfyNode):
    """Threshold an image, globally or adaptively."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="THRESHOLD (JOV) 📉",
            display_name="THRESHOLD 📉",
            category=CATEGORY,
            description="Cut a picture into light and dark at a threshold, either one level for "
                        "the whole picture or one adapted to each neighbourhood. Good for "
                        "masks, scans and line extraction.",
            search_aliases=["THRESHOLD (JOV) 📉", "threshold", "binarize", "black and white", "adaptive"],
            is_input_list=True,
            inputs=[
                *IMAGE_IN,
                io.Combo.Input(
                    "adapt", options=EnumThresholdAdapt._member_names_,
                    default=EnumThresholdAdapt.ADAPT_NONE.name, optional=True,
                    tooltip="ADAPT_NONE = one threshold everywhere; ADAPT_MEAN and ADAPT_GAUSS = "
                            "each pixel against its neighbourhood, for uneven lighting.",
                ),
                io.Combo.Input(
                    "func", options=EnumThreshold._member_names_,
                    default=EnumThreshold.BINARY.name, optional=True,
                    tooltip="BINARY = white above, black below; TRUNC = cap values at the "
                            "threshold; TOZERO = black below, unchanged above.",
                ),
                io.Float.Input("threshold", default=0.5, min=0, max=1, step=0.005, optional=True,
                               tooltip="The cut level, 0 to 1, for ADAPT_NONE."),
                io.Int.Input("size", default=3, min=3, max=103, optional=True,
                             tooltip="Neighbourhood size in pixels for the adaptive modes, raised "
                                     "to the next odd number."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert the result."),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_invert, image_threshold
        from ..modules.image.channel import channel_solid
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        mode = parse_param(kw, "func", EnumThreshold, EnumThreshold.BINARY.name)
        adapt = parse_param(kw, "adapt", EnumThresholdAdapt, EnumThresholdAdapt.ADAPT_NONE.name)
        threshold = parse_param(kw, "threshold", EnumConvertType.FLOAT, 0.5, 0, 1)
        block = parse_param(kw, "size", EnumConvertType.INT, 3, 3, 103)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        params = list(zip_longest_fill(pA, mode, adapt, threshold, block, invert))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, mode, adapt, th, block, invert) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            pA = image_threshold(pA, th, mode, adapt, block)
            if invert:
                pA = image_invert(pA, 1)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


NODES = [BlendNode, FilterMaskNode, HistogramNode, PixelMergeNode, PixelSplitNode, PixelSwapNode, ThresholdNode]
