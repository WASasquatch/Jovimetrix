"""Variable nodes: a typed value with optional randomising, and 2, 3 and 4 component vectors."""

from __future__ import annotations

import random
import sys

from comfy_api.latest import io

from ..modules.enums import EnumConvertType
from ..modules.node import Progress, category
from ..modules.params import parse_param, parse_value, zip_longest_fill
from ..modules.types import NUMERICAL_TYPES, VEC2, VEC3, VEC4

CATEGORY = category("VARIABLE")

CONVERT_TYPES = EnumConvertType._member_names_[:6]

FLOAT_RANGE = {"mij": -sys.float_info.max, "maj": sys.float_info.max}


class ValueNode(io.ComfyNode):
    """Supply a typed value, built from inputs or widgets, optionally randomised."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VALUE (JOV) 🧬",
            display_name="VALUE 🧬",
            category=CATEGORY,
            description="Supply a boolean, integer, float or vector, typed in or converted from "
                        "whatever is wired in, with its components on separate outputs. With a "
                        "seed it picks a random value between aa and bb.",
            search_aliases=["VALUE (JOV) 🧬", "value", "number", "convert", "random", "primitive"],
            is_input_list=True,
            inputs=[
                io.AnyType.Input("a", optional=True,
                                 tooltip="A value to convert to the chosen type. When empty, aa is used."),
                io.MultiType.Input("x", NUMERICAL_TYPES, optional=True, tooltip="Overrides the X of aa.",
                                   extra_dict={"forceInput": True}),
                io.MultiType.Input("y", NUMERICAL_TYPES, optional=True, tooltip="Overrides the Y of aa.",
                                   extra_dict={"forceInput": True}),
                io.MultiType.Input("z", NUMERICAL_TYPES, optional=True, tooltip="Overrides the Z of aa.",
                                   extra_dict={"forceInput": True}),
                io.MultiType.Input("w", NUMERICAL_TYPES, optional=True, tooltip="Overrides the W of aa.",
                                   extra_dict={"forceInput": True}),
                io.Combo.Input("type", options=CONVERT_TYPES, default=EnumConvertType.BOOLEAN.name,
                               optional=True,
                               tooltip="Type of the value: BOOLEAN, INT, FLOAT, or a VEC2 to VEC4 vector."),
                VEC4.Input("aa", optional=True,
                           tooltip="The value. With a seed, the low end of the random range.",
                           extra_dict={"default": (0, 0, 0, 0), **FLOAT_RANGE,
                                       "label": ["x", "y", "z", "w"]}),
                VEC4.Input("bb", optional=True,
                           tooltip="With a seed, the high end of the random range. Otherwise unused.",
                           extra_dict={"default": (1, 1, 1, 1), **FLOAT_RANGE,
                                       "label": ["x", "y", "z", "w"]}),
                io.Int.Input("seed", default=0, min=0, max=sys.maxsize, optional=True,
                             tooltip="0 = no randomising. Any other value picks a random value "
                                     "between aa and bb per component; the same seed repeats it."),
            ],
            outputs=[
                io.AnyType.Output("❔", display_name="❔", is_output_list=True,
                                  tooltip="The value, of the chosen type."),
                io.AnyType.Output("x", display_name="x", is_output_list=True, tooltip="The X component."),
                io.AnyType.Output("y", display_name="y", is_output_list=True, tooltip="The Y component."),
                io.AnyType.Output("z", display_name="z", is_output_list=True, tooltip="The Z component."),
                io.AnyType.Output("w", display_name="w", is_output_list=True, tooltip="The W component."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        raw = parse_param(kw, "a", EnumConvertType.ANY, None)
        r_x = parse_param(kw, "x", EnumConvertType.FLOAT, None)
        r_y = parse_param(kw, "y", EnumConvertType.FLOAT, None)
        r_z = parse_param(kw, "z", EnumConvertType.FLOAT, None)
        r_w = parse_param(kw, "w", EnumConvertType.FLOAT, None)
        typ = parse_param(kw, "type", EnumConvertType, EnumConvertType.BOOLEAN.name)
        xyzw = parse_param(kw, "aa", EnumConvertType.VEC4, (0, 0, 0, 0))
        yyzw = parse_param(kw, "bb", EnumConvertType.VEC4, (1, 1, 1, 1))
        seed = parse_param(kw, "seed", EnumConvertType.INT, 0, 0)
        params = list(zip_longest_fill(raw, r_x, r_y, r_z, r_w, typ, xyzw, yyzw, seed))
        results = []
        pbar = Progress(len(params))
        for idx, (raw, r_x, r_y, r_z, r_w, typ, xyzw, yyzw, seed) in enumerate(params):
            a, b, c, d = xyzw
            default = (a if r_x is None else r_x, b if r_y is None else r_y,
                       c if r_z is None else r_z, d if r_w is None else r_w)
            default2 = tuple(yyzw)

            val = parse_value(default if raw is None else raw, typ, default)
            val2 = parse_value(default2, typ, default2)

            if seed != 0:
                rng = random.Random(seed)
                val = list(val) if isinstance(val, (tuple, list)) else [val]
                val2 = list(val2) if isinstance(val2, (tuple, list)) else [val2]
                for i in range(len(val)):
                    mn, mx = min(val[i], val2[i]), max(val[i], val2[i])
                    if mn == mx:
                        val[i] = mn
                    elif typ in (EnumConvertType.INT, EnumConvertType.BOOLEAN):
                        val[i] = rng.randint(int(mn), int(mx))
                    else:
                        val[i] = mn + rng.random() * (mx - mn)

            out = parse_value(val, typ, val)
            items = list(out) if isinstance(out, (tuple, list)) else [out, 0, 0, 0]
            items = (items + [0, 0, 0, 0])[:4]
            results.append([out, *items])
            pbar.update(idx)

        return io.NodeOutput(*[list(col) for col in zip(*results)])


X_IN = io.MultiType.Input("x", NUMERICAL_TYPES, optional=True,
                          tooltip="X component. Overrides the X of default when wired.")
Y_IN = io.MultiType.Input("y", NUMERICAL_TYPES, optional=True,
                          tooltip="Y component. Overrides the Y of default when wired.")
Z_IN = io.MultiType.Input("z", NUMERICAL_TYPES, optional=True,
                          tooltip="Z component. Overrides the Z of default when wired.")
W_IN = io.MultiType.Input("w", NUMERICAL_TYPES, optional=True,
                          tooltip="W component. Overrides the W of default when wired.")


def build_vectors(kw: dict, size: int) -> list[tuple[float, ...]]:
    """Read a vector node's inputs and build its vectors.

    Args:
        kw: The node's keyword inputs.
        size: Components per vector, 2 to 4.

    Returns:
        One vector per entry of the longest input.
    """
    names = "xyzw"[:size]
    typ = getattr(EnumConvertType, f"VEC{size}")
    comps = [parse_param(kw, n, EnumConvertType.FLOAT, None) for n in names]
    default = parse_param(kw, "default", typ, (0,) * size)
    result = []
    params = list(zip_longest_fill(*comps, default))
    pbar = Progress(len(params))
    for idx, entry in enumerate(params):
        *values, dflt = entry
        result.append(tuple(round(dflt[i] if v is None else v, 9) for i, v in enumerate(values)))
        pbar.update(idx)
    return result


class Vector2Node(io.ComfyNode):
    """Build a two component vector."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VECTOR2 (JOV)",
            display_name="VECTOR2",
            category=CATEGORY,
            description="Build a two component float vector, such as a size or a position, from "
                        "typed values or wired numbers.",
            search_aliases=["VECTOR2 (JOV)", "vector", "vec2", "xy"],
            is_input_list=True,
            inputs=[
                X_IN, Y_IN,
                VEC2.Input("default", optional=True,
                           tooltip="Typed vector used for any component not wired in.",
                           extra_dict={"default": (0, 0), **FLOAT_RANGE}),
            ],
            outputs=[VEC2.Output("VEC2", display_name="VEC2", is_output_list=True,
                                 tooltip="The two component vector.")],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        return io.NodeOutput(build_vectors(kw, 2))


class Vector3Node(io.ComfyNode):
    """Build a three component vector."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VECTOR3 (JOV)",
            display_name="VECTOR3",
            category=CATEGORY,
            description="Build a three component float vector, such as an RGB colour or a 3D "
                        "position, from typed values or wired numbers.",
            search_aliases=["VECTOR3 (JOV)", "vector", "vec3", "xyz"],
            is_input_list=True,
            inputs=[
                X_IN, Y_IN, Z_IN,
                VEC3.Input("default", optional=True,
                           tooltip="Typed vector used for any component not wired in.",
                           extra_dict={"default": (0, 0, 0), **FLOAT_RANGE}),
            ],
            outputs=[VEC3.Output("VEC3", display_name="VEC3", is_output_list=True,
                                 tooltip="The three component vector.")],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        return io.NodeOutput(build_vectors(kw, 3))


class Vector4Node(io.ComfyNode):
    """Build a four component vector."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="VECTOR4 (JOV)",
            display_name="VECTOR4",
            category=CATEGORY,
            description="Build a four component float vector, such as an RGBA colour or a "
                        "rectangle, from typed values or wired numbers.",
            search_aliases=["VECTOR4 (JOV)", "vector", "vec4", "xyzw"],
            is_input_list=True,
            inputs=[
                X_IN, Y_IN, Z_IN, W_IN,
                VEC4.Input("default", optional=True,
                           tooltip="Typed vector used for any component not wired in.",
                           extra_dict={"default": (0, 0, 0, 0), **FLOAT_RANGE}),
            ],
            outputs=[VEC4.Output("VEC4", display_name="VEC4", is_output_list=True,
                                 tooltip="The four component vector.")],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        return io.NodeOutput(build_vectors(kw, 4))


NODES = [ValueNode, Vector2Node, Vector3Node, Vector4Node]
