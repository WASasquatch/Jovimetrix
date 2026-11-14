"""Colour nodes: colour blindness simulation, colour matching, dominant colours, harmonies and
gradient maps."""

from __future__ import annotations

from comfy_api.latest import io

from ..modules.enums import \
    EnumCBDeficiency, EnumCBSimulator, EnumColorMap, EnumColorMatchMap, EnumColorMatchMode, \
    EnumColorTheory, EnumConvertType, EnumInterpolation, EnumScaleMode
from ..modules.limits import check_batch, check_canvas
from ..modules.node import Progress, category, image_stack
from ..modules.params import IMAGE_SIZE_MIN, parse_param, zip_longest_fill
from ..modules.types import IMAGE_OUTPUTS, IMAGE_TYPES, JLUT, VEC2, VEC4

CATEGORY = category("COLOR")

MATTE_IN = VEC4.Input(
    "matte", optional=True,
    tooltip="Colour behind transparent areas and around a resized picture, RGBA 0 to 255.",
    extra_dict={"default": (0, 0, 0, 255), "rgb": True},
)


class ColorBlindNode(io.ComfyNode):
    """Simulate a colour vision deficiency."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="COLOR BLIND (JOV) 👁‍🗨",
            display_name="COLOR BLIND 👁‍🗨",
            category=CATEGORY,
            description="Show how a picture looks to someone with red, green or blue colour "
                        "blindness. Check that a design still reads for everyone.",
            search_aliases=["COLOR BLIND (JOV) 👁‍🗨", "color blind", "protanopia", "deuteranopia",
                            "tritanopia", "accessibility"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The picture to check: RGBA, RGB or a mask."),
                io.Combo.Input(
                    "mode", options=EnumCBDeficiency._member_names_,
                    default=EnumCBDeficiency.PROTAN.name, optional=True,
                    tooltip="PROTAN = red-blind; DEUTAN = green-blind, the most common; "
                            "TRITAN = blue-blind.",
                ),
                io.Combo.Input(
                    "solver", options=EnumCBSimulator._member_names_,
                    default=EnumCBSimulator.AUTOSELECT.name, optional=True,
                    tooltip="Simulation model. AUTOSELECT picks the best one for the deficiency; "
                            "MACHADO2009 handles partial severity well.",
                ),
                io.Float.Input(
                    "value", default=1.0, min=0, max=1, step=0.01, optional=True,
                    tooltip="Severity. 0 = normal vision; 1 = full deficiency.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.color import color_blind
        from ..modules.image.convert import frame_outputs, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        deficiency = parse_param(kw, "mode", EnumCBDeficiency, EnumCBDeficiency.PROTAN.name)
        simulator = parse_param(kw, "solver", EnumCBSimulator, EnumCBSimulator.AUTOSELECT.name)
        severity = parse_param(kw, "value", EnumConvertType.FLOAT, 1, 0, 1)
        params = list(zip_longest_fill(pA, deficiency, simulator, severity))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, deficiency, simulator, severity) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            pA = color_blind(pA, deficiency, simulator, severity)
            images.append(frame_outputs(pA))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class ColorMatchNode(io.ComfyNode):
    """Recolour one image to match another, or through a colour map."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="COLOR MATCH (JOV) 💞",
            display_name="COLOR MATCH 💞",
            category=CATEGORY,
            description="Recolour a picture to match a target picture's palette, or map its tones "
                        "through a built-in colour map. Keeps a sequence or a set of renders in "
                        "one grade.",
            search_aliases=["COLOR MATCH (JOV) 💞", "color match", "color transfer", "reinhard", "lut", "grade"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("source", IMAGE_TYPES, optional=True,
                                   tooltip="The picture to recolour."),
                io.MultiType.Input("target", IMAGE_TYPES, optional=True,
                                   tooltip="The picture whose colours are copied."),
                io.Combo.Input(
                    "mode", options=EnumColorMatchMode._member_names_,
                    default=EnumColorMatchMode.REINHARD.name, optional=True,
                    tooltip="REINHARD = match the target's colour statistics, natural results; "
                            "LUT = map the source's brightness through a colour table.",
                ),
                io.Combo.Input(
                    "map", options=EnumColorMatchMap._member_names_,
                    default=EnumColorMatchMap.USER_MAP.name, optional=True,
                    tooltip="LUT mode only. USER_MAP = build the table from the target's dominant "
                            "colours; PRESET_MAP = use the colormap below.",
                ),
                io.Combo.Input(
                    "colormap", options=EnumColorMap._member_names_,
                    default=EnumColorMap.HSV.name, optional=True,
                    tooltip="Built-in colour table for PRESET_MAP, such as VIRIDIS, JET or HOT.",
                ),
                io.Int.Input(
                    "value", default=255, min=0, max=255, optional=True,
                    tooltip="USER_MAP only: how many colours the table keeps. Fewer colours give "
                            "a flatter, posterised look.",
                ),
                io.Boolean.Input("swap", default=False, optional=True,
                                 tooltip="Exchange source and target."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert the colours of the result."),
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_invert
        from ..modules.image.channel import channel_solid
        from ..modules.image.color import color_lut_match, color_match_reinhard
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "source", EnumConvertType.IMAGE, None)
        pB = parse_param(kw, "target", EnumConvertType.IMAGE, None)
        mode = parse_param(kw, "mode", EnumColorMatchMode, EnumColorMatchMode.REINHARD.name)
        cmap = parse_param(kw, "map", EnumColorMatchMap, EnumColorMatchMap.USER_MAP.name)
        colormap = parse_param(kw, "colormap", EnumColorMap, EnumColorMap.HSV.name)
        num_colors = parse_param(kw, "value", EnumConvertType.INT, 255, 0, 255)
        swap = parse_param(kw, "swap", EnumConvertType.BOOLEAN, False)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, pB, mode, cmap, colormap, num_colors, swap, invert, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, pB, mode, cmap, colormap, num_colors, swap, invert, matte) in enumerate(params):
            if swap:
                pA, pB = pB, pA

            mask = None
            if pA is None:
                pA = channel_solid()
            else:
                pA = to_frame(pA)
                if pA.ndim == 3 and pA.shape[2] == 4:
                    mask = image_mask(pA)
            pB = channel_solid() if pB is None else to_frame(pB)

            if mode == EnumColorMatchMode.LUT:
                usermap = None if cmap == EnumColorMatchMap.PRESET_MAP else pB
                pA = color_lut_match(pA, colormap.value, usermap, max(1, num_colors))
            else:
                pA = color_match_reinhard(pA, pB)

            if invert:
                pA = image_invert(pA, 1)
            if mask is not None:
                pA = image_mask_add(pA, mask)
            images.append(frame_outputs(pA, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class ColorKMeansNode(io.ComfyNode):
    """Find an image's dominant colours and build palettes and a LUT from them."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="COLOR MEANS (JOV) 〰️",
            display_name="COLOR MEANS 〰️",
            category=CATEGORY,
            description="Find a picture's most used colours and hand them on as swatches, a tonal "
                        "palette, a gradient and a 3D LUT. Use them to keep other pictures in "
                        "the same colour range.",
            search_aliases=["COLOR MEANS (JOV) 〰️", "palette", "dominant colors", "kmeans", "lut"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The picture to read colours from."),
                io.Int.Input("value", default=12, min=1, max=255, optional=True,
                             tooltip="How many dominant colours to find."),
                io.Int.Input("size", default=32, min=1, max=256, optional=True,
                             tooltip="Height of each row of the PALETTE output, in pixels."),
                io.Int.Input("count", default=33, min=1, max=255, optional=True,
                             tooltip="Nodes per axis of the LUT. 17 = coarse; 33 = standard; 65 = fine."),
                VEC2.Input(
                    "wh", optional=True,
                    tooltip="Width and height of the IMAGE swatches and the GRADIENT; the height "
                            "also sizes the RGB preview.",
                    extra_dict={"default": (256, 256), "mij": IMAGE_SIZE_MIN, "int": True,
                                "label": ["W", "H"]},
                ),
            ],
            outputs=[
                io.Image.Output("IMAGE", display_name="IMAGE",
                                tooltip="One solid swatch per colour, most used first, as a batch."),
                io.Image.Output("PALETTE", display_name="PALETTE",
                                tooltip="One row per colour, fading to black; as wide as the input."),
                io.Image.Output("GRADIENT", display_name="GRADIENT",
                                tooltip="The colours blended into one left-to-right gradient."),
                JLUT.Output("LUT", display_name="LUT",
                            tooltip="A 3D LUT mapping every colour to its nearest dominant colour."),
                io.Image.Output("RGB", display_name="RGB",
                                tooltip="A picture of the LUT, one tile per blue level."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import torch

        from ..modules.image.channel import channel_solid
        from ..modules.image.color import color_lut_full, color_lut_palette, color_lut_tonal, \
            color_lut_visualize, color_top_used, image_gradient_expand
        from ..modules.image.convert import frame_tensor, to_frame
        from ..modules.image.sample import resize

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        kcolors = parse_param(kw, "value", EnumConvertType.INT, 12, 1, 255)
        lut_height = parse_param(kw, "size", EnumConvertType.INT, 32, 1, 256)
        nodes = parse_param(kw, "count", EnumConvertType.INT, 33, 1, 255)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (256, 256), IMAGE_SIZE_MIN)

        params = list(zip_longest_fill(pA, kcolors, nodes, lut_height, wihi))
        top_colors, lut_tonal, lut_full, lut_visualized, gradients = [], [], [], [], []
        pbar = Progress(len(params))
        for idx, (pA, kcolors, nodes, lut_height, wihi) in enumerate(params):
            width, height = check_batch(*wihi, kcolors)
            pA = channel_solid() if pA is None else to_frame(pA)
            colors = color_top_used(pA, kcolors)

            top_colors.extend([frame_tensor(channel_solid(width, height, color=c)) for c in colors])
            lut_tonal.append(frame_tensor(color_lut_tonal(colors, width=pA.shape[1], height=lut_height)))
            full = color_lut_full(colors, nodes)
            lut_full.append(full)
            lut_visualized.append(frame_tensor(color_lut_visualize(full, height)))
            gradient = image_gradient_expand(color_lut_palette(colors, 1))
            gradients.append(frame_tensor(resize(gradient, width, height)))
            pbar.update(idx)

        return io.NodeOutput(torch.stack(top_colors), torch.stack(lut_tonal), torch.stack(gradients),
                             lut_full, torch.stack(lut_visualized))


class ColorTheoryNode(io.ComfyNode):
    """Build a colour harmony from an image's mean colour."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="COLOR THEORY (JOV) 🛞",
            display_name="COLOR THEORY 🛞",
            category=CATEGORY,
            description="Build a colour harmony, such as complementary, triadic or analogous, "
                        "from a picture's average colour. Each colour comes out as a solid picture.",
            search_aliases=["COLOR THEORY (JOV) 🛞", "harmony", "complementary", "triadic", "palette"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The picture whose average colour starts the harmony."),
                io.Combo.Input(
                    "scheme", options=EnumColorTheory._member_names_,
                    default=EnumColorTheory.COMPLIMENTARY.name, optional=True,
                    tooltip="COMPLIMENTARY = opposite hue; TRIADIC = three evenly spaced; "
                            "ANALOGOUS = neighbours; MONOCHROMATIC = one hue, varied shades; "
                            "CUSTOM_TETRAD uses value as the spacing.",
                ),
                io.Int.Input("value", default=45, min=-90, max=90, optional=True,
                             tooltip="CUSTOM_TETRAD only: separation of the colours, in degrees."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert every colour of the harmony."),
            ],
            outputs=[
                io.Image.Output("C1", display_name="C1", tooltip="The picture's average colour."),
                io.Image.Output("C2", display_name="C2", tooltip="First harmony colour."),
                io.Image.Output("C3", display_name="C3",
                                tooltip="Second harmony colour, black when the scheme has one colour."),
                io.Image.Output("C4", display_name="C4",
                                tooltip="Third harmony colour, black when the scheme has fewer."),
                io.Image.Output("C5", display_name="C5",
                                tooltip="Fourth harmony colour, black when the scheme has fewer."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_invert
        from ..modules.image.channel import channel_solid
        from ..modules.image.color import color_theory
        from ..modules.image.convert import frame_tensor, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        scheme = parse_param(kw, "scheme", EnumColorTheory, EnumColorTheory.COMPLIMENTARY.name)
        value = parse_param(kw, "value", EnumConvertType.INT, 45, -90, 90)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        params = list(zip_longest_fill(pA, scheme, value, invert))
        images = []
        pbar = Progress(len(params))
        for idx, (img, scheme, value, invert) in enumerate(params):
            img = channel_solid() if img is None else to_frame(img)
            img = color_theory(img, value, scheme)
            if invert:
                img = [image_invert(s, 1) for s in img]
            images.append([frame_tensor(a) for a in img])
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class GradientMapNode(io.ComfyNode):
    """Recolour an image's tones through a gradient picture."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GRADIENT MAP (JOV) 🇲🇺",
            display_name="GRADIENT MAP 🇲🇺",
            category=CATEGORY,
            description="Recolour a picture by its brightness: dark tones take the gradient's left "
                        "colour and bright tones its right. Good for duotones, heat maps and "
                        "stylised grades.",
            search_aliases=["GRADIENT MAP (JOV) 🇲🇺", "gradient map", "duotone", "colorize", "lut"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="The picture to recolour."),
                io.MultiType.Input("gradient", IMAGE_TYPES, optional=True,
                                   tooltip="The gradient, read along its top row from left "
                                           "(darkest tone) to right (brightest)."),
                io.Boolean.Input("reverse", default=False, optional=True,
                                 tooltip="Read the gradient right to left."),
                io.Combo.Input(
                    "mode", options=EnumScaleMode._member_names_,
                    default=EnumScaleMode.MATTE.name, optional=True,
                    tooltip="Resize of the result. MATTE = keep its size; FIT = stretch to wh; "
                            "CROP = fill wh and trim; ASPECT = scale keeping proportions.",
                ),
                VEC2.Input(
                    "wh", optional=True,
                    tooltip="Target width and height when mode is not MATTE.",
                    extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                "label": ["W", "H"]},
                ),
                io.Combo.Input(
                    "sample", options=EnumInterpolation._member_names_,
                    default=EnumInterpolation.LANCZOS4.name, optional=True,
                    tooltip="Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = "
                            "hard pixels.",
                ),
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.color import image_gradient_map
        from ..modules.image.compose import image_scalefit
        from ..modules.image.convert import frame_outputs, image_mask, image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        gradient = parse_param(kw, "gradient", EnumConvertType.IMAGE, None)
        reverse = parse_param(kw, "reverse", EnumConvertType.BOOLEAN, False)
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        images = []
        params = list(zip_longest_fill(pA, gradient, reverse, mode, sample, wihi, matte))
        pbar = Progress(len(params))
        for idx, (pA, gradient, reverse, mode, sample, wihi, matte) in enumerate(params):
            pA = channel_solid() if pA is None else to_frame(pA)
            mask = image_mask(pA) if pA.ndim == 3 and pA.shape[2] == 4 else None
            gradient = channel_solid() if gradient is None else to_frame(gradient)
            pA = image_gradient_map(pA, gradient, reverse)
            if mode != EnumScaleMode.MATTE:
                w, h = check_canvas(*wihi)
                pA = image_scalefit(pA, w, h, mode, sample)
            if mask is not None:
                pA = image_mask_add(pA, mask)
            images.append(frame_outputs(pA, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


NODES = [ColorBlindNode, ColorMatchNode, ColorKMeansNode, ColorTheoryNode, GradientMapNode]
