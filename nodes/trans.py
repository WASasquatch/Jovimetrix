"""Transform nodes: crop, flatten, split, stack and geometric transforms."""

from __future__ import annotations

import math
import sys

from comfy_api.latest import io

from ..modules.enums import \
    EnumConvertType, EnumCropMode, EnumEdge, EnumInterpolation, EnumMirrorMode, EnumOrientation, \
    EnumProjection, EnumScaleMode
from ..modules.limits import check_canvas
from ..modules.node import Progress, category, image_stack
from ..modules.params import IMAGE_SIZE_MIN, parse_dynamic, parse_param, zip_longest_fill
from ..modules.types import IMAGE_OUTPUTS, IMAGE_TYPES, VEC2, VEC4

CATEGORY = category("TRANSFORM")

#: Largest stride STACK accepts.
MAX_STRIDE = 4096

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

SAMPLE_IN = io.Combo.Input(
    "sample", options=EnumInterpolation._member_names_, default=EnumInterpolation.LANCZOS4.name,
    optional=True,
    tooltip="Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels.",
)

TLTR_LABEL = ["TL X", "TL Y", "TR X", "TR Y"]
BLBR_LABEL = ["BL X", "BL Y", "BR X", "BR Y"]


class CropNode(io.ComfyNode):
    """Cut a region out of an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CROP (JOV) ✂️",
            display_name="CROP ✂️",
            category=CATEGORY,
            description="Cut a region out of a picture: a centred window, a window at a position, "
                        "or any four-cornered shape. Pulls a region of interest out of a frame.",
            search_aliases=["CROP (JOV) ✂️", "crop", "cut", "region", "trim"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True, tooltip="The picture to crop."),
                io.Combo.Input(
                    "func", options=EnumCropMode._member_names_,
                    default=EnumCropMode.CENTER.name, optional=True,
                    tooltip="CENTER = a wh window from the middle; XY = a wh window whose top-left "
                            "corner is at xy; FREE = the shape inside the four corners.",
                ),
                VEC2.Input("xy", optional=True,
                           tooltip="XY mode: top-left corner of the window. 0 to 1 is a share of "
                                   "the picture; above 1 is pixels.",
                           extra_dict={"default": (0, 0), "mij": 0, "maj": 1, "label": ["X", "Y"]}),
                VEC2.Input("wh", optional=True, tooltip="Width and height of the window, in pixels.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                VEC4.Input("tl-tr", optional=True,
                           tooltip="FREE mode: x, y of the first corner, then x, y of the second, "
                                   "each 0 to 1 of the picture.",
                           extra_dict={"default": (0, 0, 0, 1), "mij": 0, "maj": 1, "label": TLTR_LABEL}),
                VEC4.Input("bl-br", optional=True,
                           tooltip="FREE mode: x, y of the fourth corner, then x, y of the third.",
                           extra_dict={"default": (1, 0, 1, 1), "mij": 0, "maj": 1, "label": BLBR_LABEL}),
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_crop, image_crop_center, image_crop_polygonal
        from ..modules.image.convert import cv_to_tensor_full, image_mask, tensor_to_cv

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        func = parse_param(kw, "func", EnumCropMode, EnumCropMode.CENTER.name)
        xy = parse_param(kw, "xy", EnumConvertType.VEC2, (0, 0))
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        tltr = parse_param(kw, "tl-tr", EnumConvertType.VEC4, (0, 0, 0, 1))
        blbr = parse_param(kw, "bl-br", EnumConvertType.VEC4, (1, 0, 1, 1))
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, func, xy, wihi, tltr, blbr, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, func, xy, wihi, tltr, blbr, matte) in enumerate(params):
            width, height = check_canvas(*wihi)
            pA = channel_solid(width, height) if pA is None else tensor_to_cv(pA)
            alpha = image_mask(pA) if pA.ndim == 3 and pA.shape[2] == 4 else None

            if func == EnumCropMode.FREE:
                h, w = pA.shape[:2]
                x1, y1, x2, y2 = tltr
                x4, y4, x3, y3 = blbr
                points = (x1 * w, y1 * h), (x2 * w, y2 * h), (x3 * w, y3 * h), (x4 * w, y4 * h)
                pA = image_crop_polygonal(pA, points)
                if alpha is not None:
                    alpha = image_crop_polygonal(alpha, points)
                    pA[..., 3] = alpha[..., 0]
            elif func == EnumCropMode.XY:
                pA = image_crop(pA, width, height, xy)
            else:
                pA = image_crop_center(pA, width, height)
            images.append(cv_to_tensor_full(pA, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class FlattenNode(io.ComfyNode):
    """Add many images together into one."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="FLATTEN (JOV) ⬇️",
            display_name="FLATTEN ⬇️",
            category=CATEGORY,
            description="Add every picture wired into its growing image inputs, and every frame of "
                        "each batch, into one picture. A quick slap comp of layers or masks.",
            search_aliases=["FLATTEN (JOV) ⬇️", "flatten", "merge layers", "add images", "sum"],
            is_input_list=True,
            inputs=[
                MODE_IN,
                VEC2.Input("wh", optional=True,
                           tooltip="Canvas width and height when mode is not MATTE. MATTE uses the "
                                   "largest input.",
                           extra_dict={"default": (512, 512), "mij": 1, "int": True, "label": ["W", "H"]}),
                SAMPLE_IN,
                MATTE_IN,
                VEC2.Input("offset", optional=True,
                           tooltip="Shift every layer by this many pixels before adding.",
                           extra_dict={"default": (0, 0), "mij": 0, "int": True, "label": ["X", "Y"]}),
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.compose import image_flatten
        from ..modules.image.convert import cv_to_tensor_full, tensor_to_cv
        from ..modules.image.misc import image_minmax

        imgs = [i for i in parse_dynamic(kw, "image", EnumConvertType.IMAGE, None) if i is not None]
        if not imgs:
            raise ValueError("FLATTEN has nothing to flatten. Connect at least one picture to an "
                             "image input.")
        pA = [tensor_to_cv(i) for i in imgs]
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)[0]
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), 1)[0]
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)[0]
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)[0]
        offset = parse_param(kw, "offset", EnumConvertType.VEC2INT, (0, 0), 0)[0]
        if mode == EnumScaleMode.MATTE:
            check_canvas(*image_minmax(pA)[2:], source="image")
            w, h = None, None
        else:
            w, h = check_canvas(*wihi)
        x, y = offset
        flat = image_flatten(pA, x, y, w, h, mode=mode, sample=sample)
        return io.NodeOutput(*image_stack([cv_to_tensor_full(flat, matte)]))


class SplitNode(io.ComfyNode):
    """Split an image into two parts."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SPLIT (JOV) 🎭",
            display_name="SPLIT 🎭",
            category=CATEGORY,
            description="Cut a picture in two at a chosen point, top and bottom or left and right. "
                        "Separates a side-by-side pair or a stacked comparison.",
            search_aliases=["SPLIT (JOV) 🎭", "split image", "halves", "side by side"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True, tooltip="The picture to split."),
                io.Float.Input("value", default=0.5, min=0, max=1, step=0.001, optional=True,
                               tooltip="Where to cut, 0 to 1 of the picture. 0.5 = in half."),
                io.Boolean.Input("flip", default=False, optional=True,
                                 tooltip="Off = cut across into top and bottom; on = cut down into "
                                         "left and right."),
                MODE_IN,
                VEC2.Input("wh", optional=True, tooltip="Size each half is fitted to when mode is not MATTE.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                SAMPLE_IN,
                MATTE_IN,
            ],
            outputs=[
                io.Image.Output("IMAGEA", display_name="IMAGEA", tooltip="The top or left part."),
                io.Image.Output("IMAGEB", display_name="IMAGEB", tooltip="The bottom or right part."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_scalefit
        from ..modules.image.convert import cv_to_tensor, tensor_to_cv

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        percent = parse_param(kw, "value", EnumConvertType.FLOAT, 0.5, 0, 1)
        flip = parse_param(kw, "flip", EnumConvertType.BOOLEAN, False)
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, percent, flip, mode, wihi, sample, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, percent, flip, mode, wihi, sample, matte) in enumerate(params):
            w, h = check_canvas(*wihi)
            pA = channel_solid(w, h, matte) if pA is None else tensor_to_cv(pA)

            axis = 1 if flip else 0
            size = pA.shape[axis]
            cut = max(1, min(size - 1, int(size * percent)))
            if flip:
                image_a, image_b = pA[:, :cut], pA[:, cut:]
            else:
                image_a, image_b = pA[:cut, :], pA[cut:, :]

            if mode != EnumScaleMode.MATTE:
                image_a = image_scalefit(image_a, w, h, mode, sample)
                image_b = image_scalefit(image_b, w, h, mode, sample)
            images.append([cv_to_tensor(img) for img in (image_a, image_b)])
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


class StackNode(io.ComfyNode):
    """Place many images side by side, on top of each other or in a grid."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="STACK (JOV) ➕",
            display_name="STACK ➕",
            category=CATEGORY,
            description="Place every picture wired into its growing image inputs, and every frame "
                        "of each batch, in a row, a column or a grid. Contact sheets and "
                        "side-by-side comparisons.",
            search_aliases=["STACK (JOV) ➕", "stack", "grid", "contact sheet", "concatenate", "side by side"],
            is_input_list=True,
            inputs=[
                io.Combo.Input("axis", options=EnumOrientation._member_names_,
                               default=EnumOrientation.GRID.name, optional=True,
                               tooltip="HORIZONTAL = one row; VERTICAL = one column; GRID = rows "
                                       "of step pictures."),
                io.Int.Input("step", default=1, min=0, max=MAX_STRIDE, optional=True,
                             tooltip="GRID only: pictures per row. 0 = as square as possible."),
                MODE_IN,
                VEC2.Input("wh", optional=True, tooltip="Size the result is fitted to when mode is not MATTE.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                SAMPLE_IN,
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.compose import image_scalefit, image_stacker
        from ..modules.image.convert import cv_to_tensor_full, tensor_to_cv
        from ..modules.image.misc import image_by_size

        images = [i for i in parse_dynamic(kw, "image", EnumConvertType.IMAGE, None) if i is not None]
        if not images:
            raise ValueError("STACK has nothing to stack. Connect at least one picture to an image input.")
        images = [tensor_to_cv(i) for i in images]
        axis = parse_param(kw, "axis", EnumOrientation, EnumOrientation.GRID.name)[0]
        stride = parse_param(kw, "step", EnumConvertType.INT, 1, 0, MAX_STRIDE)[0]
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)[0]
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)[0]
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)[0]
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)[0]

        count = len(images)
        _, cell_w, cell_h = image_by_size(images)
        if axis == EnumOrientation.HORIZONTAL:
            cols, rows = count, 1
        elif axis == EnumOrientation.VERTICAL:
            cols, rows = 1, count
        else:
            cols = stride if stride >= 1 else int(math.ceil(math.sqrt(count)))
            cols = max(1, min(cols, count))
            rows = int(math.ceil(count / cols))
        check_canvas(cell_w * cols, cell_h * rows, source="image")

        img = image_stacker(images, axis, stride)
        if mode != EnumScaleMode.MATTE:
            w, h = check_canvas(*wihi)
            img = image_scalefit(img, w, h, mode, sample)
        return io.NodeOutput(*image_stack([cv_to_tensor_full(img, matte)]))


class TransformNode(io.ComfyNode):
    """Move, rotate, scale, tile, mirror and project an image."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TRANSFORM (JOV) 🏝️",
            display_name="TRANSFORM 🏝️",
            category=CATEGORY,
            description="Move, rotate, scale, tile and mirror a picture, then optionally project it "
                        "through a perspective, sphere, fisheye or polar warp.",
            search_aliases=["TRANSFORM (JOV) 🏝️", "transform", "rotate", "scale", "translate",
                            "mirror", "tile", "perspective"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("image", IMAGE_TYPES, optional=True, tooltip="The picture to transform."),
                io.MultiType.Input("mask", IMAGE_TYPES, optional=True,
                                   tooltip="Replaces the picture's alpha before transforming."),
                VEC2.Input("xy", optional=True,
                           tooltip="Move, -1 to 1 of the picture. (0.5, 0) = half a width right.",
                           extra_dict={"default": (0, 0), "mij": -1, "maj": 1, "label": ["X", "Y"]}),
                io.Float.Input("angle", default=0, min=-sys.float_info.max, max=sys.float_info.max,
                               step=0.1, optional=True, tooltip="Rotation in degrees, clockwise."),
                VEC2.Input("size", optional=True,
                           tooltip="Scale on each axis. 1 = unchanged; 2 = double; negative mirrors.",
                           extra_dict={"default": (1, 1), "mij": 0.001, "label": ["X", "Y"]}),
                VEC2.Input("tile", optional=True,
                           tooltip="Repeat the picture this many times across and down. 1 = once.",
                           extra_dict={"default": (1, 1), "mij": 1, "label": ["X", "Y"]}),
                io.Combo.Input("edge", options=EnumEdge._member_names_, default=EnumEdge.CLIP.name,
                               optional=True,
                               tooltip="What fills the space a move or rotation uncovers. CLIP = "
                                       "empty; WRAP = the opposite edge; WRAPX, WRAPY = one axis."),
                io.Combo.Input("mirror", options=EnumMirrorMode._member_names_,
                               default=EnumMirrorMode.NONE.name, optional=True,
                               tooltip="Mirror one half onto the other across the pivot. X = left "
                                       "onto right; Y = top onto bottom; FLIP_ = the other half."),
                VEC2.Input("pivot", optional=True,
                           tooltip="Where the mirror line sits, 0 to 1 of the picture.",
                           extra_dict={"default": (0.5, 0.5), "mij": 0, "maj": 1, "step": 0.01,
                                       "label": ["X", "Y"]}),
                io.Combo.Input("proj", options=EnumProjection._member_names_,
                               default=EnumProjection.NORMAL.name, optional=True,
                               tooltip="Projection after the transform. PERSPECTIVE uses the four "
                                       "corners; SPHERICAL and FISHEYE use strength; POLAR wraps "
                                       "into a circle."),
                VEC4.Input("tl-tr", optional=True,
                           tooltip="PERSPECTIVE: where the top-left and top-right corners land, "
                                   "x, y pairs 0 to 1.",
                           extra_dict={"default": (0, 0, 1, 0), "mij": 0, "maj": 1, "step": 0.005,
                                       "label": TLTR_LABEL}),
                VEC4.Input("bl-br", optional=True,
                           tooltip="PERSPECTIVE: where the bottom-left and bottom-right corners "
                                   "land, x, y pairs 0 to 1.",
                           extra_dict={"default": (0, 1, 1, 1), "mij": 0, "maj": 1, "step": 0.005,
                                       "label": BLBR_LABEL}),
                io.Float.Input("strength", default=1, min=0, max=1, step=0.005, optional=True,
                               tooltip="SPHERICAL and FISHEYE amount. 0 = flat; 1 = full."),
                MODE_IN,
                VEC2.Input("wh", optional=True, tooltip="Size the result is fitted to when mode is not MATTE.",
                           extra_dict={"default": (512, 512), "mij": IMAGE_SIZE_MIN, "int": True,
                                       "label": ["W", "H"]}),
                SAMPLE_IN,
                MATTE_IN,
            ],
            outputs=[*IMAGE_OUTPUTS],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.image.channel import channel_solid
        from ..modules.image.compose import image_crop_center, image_edge_wrap, image_mirror, \
            image_scalefit, image_transform
        from ..modules.image.convert import cv_to_tensor_full, image_mask, image_mask_add, tensor_to_cv
        from ..modules.image.mapping import remap_fisheye, remap_perspective, remap_polar, remap_sphere

        pA = parse_param(kw, "image", EnumConvertType.IMAGE, None)
        mask = parse_param(kw, "mask", EnumConvertType.IMAGE, None)
        offset = parse_param(kw, "xy", EnumConvertType.VEC2, (0, 0), -1, 1)
        angle = parse_param(kw, "angle", EnumConvertType.FLOAT, 0)
        size = parse_param(kw, "size", EnumConvertType.VEC2, (1, 1), 0.001)
        edge = parse_param(kw, "edge", EnumEdge, EnumEdge.CLIP.name)
        mirror = parse_param(kw, "mirror", EnumMirrorMode, EnumMirrorMode.NONE.name)
        mirror_pivot = parse_param(kw, "pivot", EnumConvertType.VEC2, (0.5, 0.5), 0, 1)
        tile_xy = parse_param(kw, "tile", EnumConvertType.VEC2, (1, 1), 1)
        proj = parse_param(kw, "proj", EnumProjection, EnumProjection.NORMAL.name)
        tltr = parse_param(kw, "tl-tr", EnumConvertType.VEC4, (0, 0, 1, 0), 0, 1)
        blbr = parse_param(kw, "bl-br", EnumConvertType.VEC4, (0, 1, 1, 1), 0, 1)
        strength = parse_param(kw, "strength", EnumConvertType.FLOAT, 1, 0, 1)
        mode = parse_param(kw, "mode", EnumScaleMode, EnumScaleMode.MATTE.name)
        wihi = parse_param(kw, "wh", EnumConvertType.VEC2INT, (512, 512), IMAGE_SIZE_MIN)
        sample = parse_param(kw, "sample", EnumInterpolation, EnumInterpolation.LANCZOS4.name)
        matte = parse_param(kw, "matte", EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
        params = list(zip_longest_fill(pA, mask, offset, angle, size, edge, tile_xy, mirror,
                                       mirror_pivot, proj, strength, tltr, blbr, mode, wihi, sample, matte))
        images = []
        pbar = Progress(len(params))
        for idx, (pA, mask, offset, angle, size, edge, tile_xy, mirror, mirror_pivot, proj, strength,
                  tltr, blbr, mode, wihi, sample, matte) in enumerate(params):
            pA = channel_solid() if pA is None else tensor_to_cv(pA)
            mask = image_mask(pA, 255) if mask is None else tensor_to_cv(mask)
            pA = image_mask_add(pA, mask)

            h, w = pA.shape[:2]
            check_canvas(abs(w * size[0]) * (3 if edge != EnumEdge.CLIP else 1),
                         abs(h * size[1]) * (3 if edge != EnumEdge.CLIP else 1), source="size")
            tx, ty = tile_xy
            check_canvas(w * max(1.0, tx), h * max(1.0, ty), source="tile")

            pA = image_transform(pA, offset, angle, size, sample, edge)
            pA = image_crop_center(pA, w, h)

            if mirror != EnumMirrorMode.NONE:
                mpx, mpy = mirror_pivot
                pA = image_mirror(pA, mirror, mpx, mpy)
                pA = image_scalefit(pA, w, h, EnumScaleMode.FIT, sample)

            if tx != 1. or ty != 1.:
                pA = image_edge_wrap(pA, tx / 2 - 0.5, ty / 2 - 0.5)
                pA = image_scalefit(pA, w, h, EnumScaleMode.FIT, sample)

            match proj:
                case EnumProjection.PERSPECTIVE:
                    x1, y1, x2, y2 = tltr
                    x4, y4, x3, y3 = blbr
                    sh, sw = pA.shape[:2]
                    x1, x2, x3, x4 = (x * sw for x in (x1, x2, x3, x4))
                    y1, y2, y3, y4 = (y * sh for y in (y1, y2, y3, y4))
                    pA = remap_perspective(pA, [[x1, y1], [x2, y2], [x3, y3], [x4, y4]])
                case EnumProjection.SPHERICAL:
                    pA = remap_sphere(pA, strength)
                case EnumProjection.FISHEYE:
                    pA = remap_fisheye(pA, strength)
                case EnumProjection.POLAR:
                    pA = remap_polar(pA)

            if proj != EnumProjection.NORMAL:
                pA = image_scalefit(pA, w, h, EnumScaleMode.FIT, sample)

            if mode != EnumScaleMode.MATTE:
                w, h = check_canvas(*wihi)
                pA = image_scalefit(pA, w, h, mode, sample)

            images.append(cv_to_tensor_full(pA, matte))
            pbar.update(idx)
        return io.NodeOutput(*image_stack(images))


NODES = [CropNode, FlattenNode, SplitNode, StackNode, TransformNode]
