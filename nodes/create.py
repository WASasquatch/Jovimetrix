"""Creation nodes: solid colour canvases, shapes and text."""

from __future__ import annotations

from comfy_api.latest import io

from ..modules import fonts, log
from ..modules.enums import \
    EnumAlignment, EnumConvertType, EnumEdge, EnumImageType, EnumInterpolation, EnumJustify, \
    EnumScaleMode, EnumShapes
from ..modules.limits import check_batch, check_canvas
from ..modules.node import Progress, category, image_stack
from ..modules.params import IMAGE_SIZE_MIN, parse_param, zip_longest_fill
from ..modules.types import IMAGE_OUTPUTS, IMAGE_TYPES, VEC2, VEC4

logger = log.get_logger("create")

CATEGORY = category("CREATE")

#: Largest blur, in pixels, SHAPE GEN accepts.
MAX_BLUR = 1024

#: Largest font size TEXT GEN accepts.
MAX_FONT_SIZE = 2048

#: Font chosen for a new TEXT GEN node, the first of these installed.
PREFERRED_FONTS = ("Arial", "DejaVu Sans", "Helvetica", "Liberation Sans", fonts.DEFAULT_FONT)

COLOR_FG = {"default": (255, 255, 255, 255), "rgb": True}
COLOR_BG = {"default": (0, 0, 0, 255), "rgb": True}


def _font_menu() -> tuple[list[str], str]:
    names = list(fonts.font_names().keys())
    default = next((f for f in PREFERRED_FONTS if f in names), names[0])
    return names, default


class ConstantNode(io.ComfyNode):
    """Make a solid colour canvas, or matte a picture onto a colour."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CONSTANT (JOV) 🟪",
            display_name="CONSTANT 🟪",
            category=CATEGORY,
            description="Make a solid colour picture of any size, or place a picture over a "
                        "colour through its alpha or a mask. Backgrounds, mattes and colour cards.",
            search_aliases=["CONSTANT (JOV) 🟪", "solid color", "background", "fill", "canvas"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True,
                                   tooltip="Optional picture laid over the colour. It sets the "
                                           "size when mode is MATTE."),
                io.MultiType.Input("mask", IMAGE_TYPES, optional=True,
                                   tooltip="Replaces the picture's alpha: black shows the picture, "
                                           "white shows the colour."),
                VEC4.Input("color", optional=True, tooltip="The colour, RGBA 0 to 255.",
                           extra_dict=dict(COLOR_BG)),
                io.Combo.Input(
                    "mode", options=EnumScaleMode._member_names_,
                    default=EnumScaleMode.MATTE.name, optional=True,
                    tooltip="MATTE = the picture's size, or wh with no picture; FIT, CROP and "
                            "ASPECT resize the result to wh.",
                ),
                VEC2.Input("wh", optional=True, tooltip="Width and height of the canvas.",
                           extra_dict={"default": (512, 512), "mij": 1, "int": True, "label": ["W", "H"]}),
                io.Combo.Input(
                    "sample", options=EnumInterpolation._member_names_,
                    default=EnumInterpolation.LANCZOS4.name, optional=True,
                    tooltip="Resampling filter when resizing. LANCZOS4 = sharpest; NEAREST = hard pixels.",
                ),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_blend, image_scalefit
        from ..modules.image.convert import frame_outputs, image_convert, image_mask, \
            image_mask_add, to_frame

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        mask = parse_param(kw, "mask", EnumConvertType.MASK, None)
        matte = parse_param(kw, "color", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), 1)
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)
        images = []
        params = list(zip_longest_fill(pA, mask, matte, mode, wihi, sample))
        pbar = Progress(len(params))
        for idx, (pA, mask, matte, mode, wihi, sample) in enumerate(params):
            width, height = check_canvas(*wihi)
            w, h = width, height
            if pA is None:
                pA = channel_solid(width, height, (0, 0, 0, 255))
            else:
                pA = image_convert(to_frame(pA), 4)
                h, w = pA.shape[:2]

            if mask is None:
                mask = image_mask(pA, 0)
            else:
                mask = to_frame(mask, invert=1, chan=1)
                mask = image_scalefit(mask, w, h, matte=(0, 0, 0, 255), mode=EnumScaleMode.FIT)

            pB = channel_solid(w, h, matte)
            pA = image_blend(pB, pA, mask)
            pA = image_mask_add(pA, mask)
            if mode != EnumScaleMode.MATTE:
                pA = image_scalefit(pA, width, height, mode, sample, matte)
            images.append(frame_outputs(pA, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class ShapeNode(io.ComfyNode):
    """Draw a circle, square or regular polygon."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SHAPE GEN (JOV) ✨",
            display_name="SHAPE GEN ✨",
            category=CATEGORY,
            description="Draw a circle, square or regular polygon of any size, position, angle and "
                        "softness. Its MASK output makes a ready-made shape mask.",
            search_aliases=["SHAPE GEN (JOV) ✨", "shape", "circle", "polygon", "square", "mask shape"],
            is_input_list=True,
            inputs=[
                io.Combo.Input("shape", options=EnumShapes._member_names_,
                               default=EnumShapes.CIRCLE.name, optional=True,
                               tooltip="CIRCLE, SQUARE or POLYGON. size stretches the circle and "
                                       "square into an ellipse and a rectangle."),
                io.Int.Input("sides", default=3, min=3, max=100, optional=True,
                             tooltip="Number of sides of the POLYGON. 3 = triangle; 6 = hexagon."),
                VEC4.Input("color", optional=True, tooltip="Colour of the shape, RGBA 0 to 255. "
                                                           "Alpha sets its opacity.",
                           extra_dict=dict(COLOR_FG)),
                VEC4.Input("matte", optional=True, tooltip="Background colour, RGB 0 to 255.",
                           extra_dict=dict(COLOR_BG)),
                VEC2.Input("wh", optional=True, tooltip="Width and height of the canvas.",
                           extra_dict={"default": (256, 256), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                VEC2.Input("xy", optional=True,
                           tooltip="Offset of the shape, -1 to 1 of the canvas. (0, 0) = centred.",
                           extra_dict={"default": (0, 0), "mij": -1, "maj": 1, "label": ["X", "Y"]}),
                io.Float.Input("angle", default=0, min=-180, max=180, step=0.01, optional=True,
                               tooltip="Rotation in degrees, clockwise."),
                VEC2.Input("size", optional=True,
                           tooltip="Size of the shape as a share of the canvas, 0 to 1. (1, 1) = "
                                   "as large as fits.",
                           extra_dict={"default": (1, 1), "mij": 0, "maj": 1, "label": ["X", "Y"]}),
                io.Combo.Input("edge", options=EnumEdge._member_names_,
                               default=EnumEdge.CLIP.name, optional=True,
                               tooltip="What happens past the canvas edge. CLIP = cut off; WRAP = "
                                       "reappear on the other side."),
                io.Float.Input("blur", default=0, min=0, max=MAX_BLUR, step=0.01, optional=True,
                               tooltip="Softness of the edge, in pixels. 0 = hard edge."),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.compose import image_blend, image_transform
        from ..modules.image.convert import frame_tensor, image_convert, image_mask_add, \
            image_mask_binary, pil_to_frame
        from ..modules.image.channel import channel_solid
        from ..modules.image.kernels import gaussian_blur
        from ..modules.image.shape import shape_ellipse, shape_polygon, shape_quad

        shape = parse_param(kw, "shape", EnumShapes, EnumShapes.CIRCLE.name)
        sides = parse_param(kw, "sides", EnumConvertType.INT, 3, 3, 100)
        color = parse_param(kw, "color", EnumConvertType.VEC4INT, (255, 255, 255, 255), 0, 255)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (256, 256), IMAGE_SIZE_MIN)
        offset = parse_param(kw, "xy", EnumConvertType.VEC2, (0, 0), -1, 1)
        angle = parse_param(kw, "angle", EnumConvertType.FLOAT, 0, -180, 180)
        size = parse_param(kw, "size", EnumConvertType.VEC2, (1, 1), 0, 1, zero=0.001)
        edge = parse_param(kw, "edge", EnumEdge, EnumEdge.CLIP.name)
        blur = parse_param(kw, "blur", EnumConvertType.FLOAT, 0, 0, MAX_BLUR)
        params = list(zip_longest_fill(shape, sides, color, matte, wihi, offset, angle, size, edge, blur))
        images = []
        pbar = Progress(len(params))
        for idx, (shape, sides, color, matte, wihi, offset, angle, size, edge, blur) in enumerate(params):
            width, height = check_canvas(*wihi)
            sizeX, sizeY = size
            fill = tuple(color[:3])

            match shape:
                case EnumShapes.SQUARE:
                    rgb = shape_quad(width, height, sizeX, sizeY, fill)
                case EnumShapes.POLYGON:
                    rgb = shape_polygon(width, height, sizeX, sides, fill)
                case _:
                    rgb = shape_ellipse(width, height, sizeX, sizeY, fill)

            rgb = image_transform(pil_to_frame(rgb), offset, angle, edge=edge)
            mask = image_mask_binary(rgb)

            if blur > 0:
                rgb = gaussian_blur(rgb, 0, blur)
                mask = gaussian_blur(mask, 0, blur)

            mask = mask * (color[3] / 255.)
            canvas = channel_solid(width, height, tuple(matte[:3]) + (255,), EnumImageType.RGBA)
            rgba = image_mask_add(image_blend(canvas, rgb, mask), mask)
            rgb = image_convert(rgba, 3)
            images.append([frame_tensor(rgba), frame_tensor(rgb), frame_tensor(mask, True)])
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class TextNode(io.ComfyNode):
    """Render text into an image with an installed font."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        names, default = _font_menu()
        return io.Schema(
            node_id="TEXT GEN (JOV) 📝",
            display_name="TEXT GEN 📝",
            category=CATEGORY,
            description="Render text into a picture with any installed font, aligned, justified, "
                        "rotated and optionally sized to fit. Letter mode makes one picture per "
                        "character, for animated titles.",
            search_aliases=["TEXT GEN (JOV) 📝", "text", "title", "caption", "font", "typography"],
            is_input_list=True,
            inputs=[
                io.String.Input("string", default="jovimetrix", multiline=True,
                                dynamic_prompts=False, optional=True,
                                tooltip="The text to draw. Each line break starts a new line."),
                io.Combo.Input("font", options=names, default=default, optional=True,
                               tooltip="Font family, from the fonts installed on this machine. "
                                       "'default' is the built-in font; a font missing here "
                                       "falls back to the default."),
                io.Boolean.Input("letter", default=False, optional=True,
                                 tooltip="Draw each character as its own picture, as a batch."),
                io.Boolean.Input("autosize", default=False, optional=True,
                                 tooltip="Size the text to fill wh, ignoring size."),
                VEC4.Input("color", optional=True, tooltip="Colour of the letters, RGBA 0 to 255.",
                           extra_dict=dict(COLOR_FG)),
                VEC4.Input("matte", optional=True, tooltip="Background colour, RGBA 0 to 255.",
                           extra_dict=dict(COLOR_BG)),
                io.Int.Input("cols", default=0, min=0, max=1000, optional=True,
                             tooltip="With autosize, wrap lines at this many characters. 0 = no wrap."),
                io.Int.Input("size", default=16, min=8, max=MAX_FONT_SIZE, optional=True,
                             tooltip="Font size. Ignored when autosize is on."),
                io.Combo.Input("align", options=EnumAlignment._member_names_,
                               default=EnumAlignment.CENTER.name, optional=True,
                               tooltip="Vertical placement: TOP, CENTER or BOTTOM."),
                io.Combo.Input("justify", options=EnumJustify._member_names_,
                               default=EnumJustify.CENTER.name, optional=True,
                               tooltip="Horizontal placement of each line: LEFT, CENTER or RIGHT."),
                io.Int.Input("margin", default=0, min=-1024, max=1024, optional=True,
                             tooltip="Space kept from the canvas edges, in pixels."),
                io.Int.Input("spacing", default=0, min=-1024, max=1024, optional=True,
                             tooltip="Extra space between lines, in pixels."),
                VEC2.Input("wh", optional=True, tooltip="Width and height of the canvas.",
                           extra_dict={"default": (256, 256), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                VEC2.Input("xy", optional=True,
                           tooltip="Offset of the text, -1 to 1 of the canvas.",
                           extra_dict={"default": (0, 0), "mij": -1, "maj": 1, "label": ["X", "Y"]}),
                io.Float.Input("angle", default=0, step=0.01, optional=True,
                               tooltip="Rotation in degrees, clockwise."),
                io.Combo.Input("edge", options=EnumEdge._member_names_,
                               default=EnumEdge.CLIP.name, optional=True,
                               tooltip="What happens past the canvas edge. CLIP = cut off; WRAP = "
                                       "reappear on the other side."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Invert the colours of the result."),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def validate_inputs(cls, font=None) -> bool:
        return True

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.adjust import image_invert
        from ..modules.image.compose import image_rotate, image_translate
        from ..modules.image.convert import frame_outputs
        from ..modules.image.text import text_autosize, text_draw

        names, default = _font_menu()
        full_text = parse_param(kw, "string", EnumConvertType.STRING, "jovimetrix")
        font_idx = parse_param(kw, "font", EnumConvertType.STRING, default)
        autosize = parse_param(kw, "autosize", EnumConvertType.BOOLEAN, False)
        letter = parse_param(kw, "letter", EnumConvertType.BOOLEAN, False)
        color = parse_param(kw, "color", EnumConvertType.VEC4INT, (255, 255, 255, 255), 0, 255)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        columns = parse_param(kw, "cols", EnumConvertType.INT, 0, 0, 1000)
        font_size = parse_param(kw, "size", EnumConvertType.INT, 16, 8, MAX_FONT_SIZE)
        align = parse_param(kw, "align", EnumAlignment, EnumAlignment.CENTER.name)
        justify = parse_param(kw, "justify", EnumJustify, EnumJustify.CENTER.name)
        margin = parse_param(kw, "margin", EnumConvertType.INT, 0, -1024, 1024)
        line_spacing = parse_param(kw, "spacing", EnumConvertType.INT, 0, -1024, 1024)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (256, 256), IMAGE_SIZE_MIN)
        pos = parse_param(kw, "xy", EnumConvertType.VEC2, (0, 0))
        angle = parse_param(kw, "angle", EnumConvertType.FLOAT, 0)
        edge = parse_param(kw, "edge", EnumEdge, EnumEdge.CLIP.name)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        images = []
        params = list(zip_longest_fill(full_text, font_idx, autosize, letter, color, matte, columns,
                                       font_size, align, justify, margin, line_spacing, wihi, pos,
                                       angle, edge, invert))

        pbar = Progress(len(params))
        for idx, (full_text, font_name, autosize, letter, color, matte, columns, font_size, align,
                  justify, margin, line_spacing, wihi, pos, angle, edge, invert) in enumerate(params):

            width, height = check_canvas(*wihi)
            if font_name not in names:
                logger.warning("TEXT GEN font '%s' is not installed here; using '%s'",
                               str(font_name)[:64], default)
                font_name = default
            full_text = str(full_text)

            if letter:
                full_text = full_text.replace('\n', '')
                if autosize and full_text:
                    font_size = text_autosize(full_text[0].upper(), font_name, width, height)[1]
                    margin = 0
                    line_spacing = 0
                pieces = list(full_text) or [""]
                check_batch(width, height, len(pieces), source="string")
            else:
                if autosize:
                    wm = width - margin * 2
                    hm = height - margin * 2 - line_spacing
                    columns = 0 if columns == 0 else columns * 2 + 2
                    full_text, font_size = text_autosize(full_text, font_name, wm, hm, columns)[:2]
                pieces = [full_text]

            font = fonts.load(font_name, font_size * 2.5)
            for ch in pieces:
                img = text_draw(ch, font, width, height, align, justify, margin, line_spacing, color)
                img = image_rotate(img, angle, edge=edge)
                img = image_translate(img, pos, edge=edge)
                if invert:
                    img = image_invert(img, 1)
                images.append(frame_outputs(img, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


NODES = [ConstantNode, ShapeNode, TextNode]
