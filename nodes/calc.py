"""Calculation nodes: bit splitting, comparison, interpolation, unary and binary maths,
string operations and vector swizzling."""

from __future__ import annotations

import math
import struct
import sys
from collections import Counter
from typing import Any

import torch
from comfy_api.latest import io

from ..modules import log
from ..modules.enums import \
    EnumBinaryOperation, EnumComparison, EnumConvertString, EnumConvertType, EnumSwizzle, \
    EnumUnaryOperation
from ..modules.node import Progress, category, stack_runs
from ..modules.params import parse_dynamic, parse_param, parse_value, zip_longest_fill
from ..modules.types import FULL_TYPES, NUMERICAL_TYPES, VEC3, VEC4

logger = log.get_logger("calc")

CATEGORY = category("CALC")

#: Menu of output types offered by the conversion nodes: BOOLEAN, INT, FLOAT, VEC2, VEC3, VEC4.
CONVERT_TYPES = EnumConvertType._member_names_[:6]

#: Largest integer FACTORIAL accepts; larger inputs give infinity.
MAX_FACTORIAL = 170

#: Largest bit shift BIT_LSHIFT and BIT_RSHIFT accept.
MAX_SHIFT = 1024


def _factorial(x: float) -> float:
    n = abs(int(x))
    return math.inf if n > MAX_FACTORIAL else math.factorial(n)


OP_UNARY = {
    EnumUnaryOperation.ABS: lambda x: math.fabs(x),
    EnumUnaryOperation.FLOOR: lambda x: math.floor(x),
    EnumUnaryOperation.CEIL: lambda x: math.ceil(x),
    EnumUnaryOperation.SQRT: lambda x: math.sqrt(x),
    EnumUnaryOperation.SQUARE: lambda x: math.pow(x, 2),
    EnumUnaryOperation.LOG: lambda x: math.log(x) if x != 0 else -math.inf,
    EnumUnaryOperation.LOG10: lambda x: math.log10(x) if x != 0 else -math.inf,
    EnumUnaryOperation.SIN: lambda x: math.sin(x),
    EnumUnaryOperation.COS: lambda x: math.cos(x),
    EnumUnaryOperation.TAN: lambda x: math.tan(x),
    EnumUnaryOperation.NEGATE: lambda x: -x,
    EnumUnaryOperation.RECIPROCAL: lambda x: 1 / x if x != 0 else 0,
    EnumUnaryOperation.FACTORIAL: _factorial,
    EnumUnaryOperation.EXP: lambda x: math.exp(x),
    EnumUnaryOperation.NOT: lambda x: not x,
    EnumUnaryOperation.BIT_NOT: lambda x: ~int(x),
    EnumUnaryOperation.IS_EVEN: lambda x: x % 2 == 0,
    EnumUnaryOperation.IS_ODD: lambda x: x % 2 == 1,
    EnumUnaryOperation.COS_H: lambda x: math.cosh(x),
    EnumUnaryOperation.SIN_H: lambda x: math.sinh(x),
    EnumUnaryOperation.TAN_H: lambda x: math.tanh(x),
    EnumUnaryOperation.RADIANS: lambda x: math.radians(x),
    EnumUnaryOperation.DEGREES: lambda x: math.degrees(x),
    EnumUnaryOperation.GAMMA: lambda x: math.gamma(x) if x > 0 else 0,
}


def to_bits(value: Any) -> str:
    """Return the bits of a value, most significant first.

    Args:
        value: Integer, float (64-bit IEEE), boolean or string (8 bits per character).

    Returns:
        A string of ``0`` and ``1``.
    """
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        return bin(value)[2:] if value >= 0 else bin(value)[3:]
    if isinstance(value, float):
        return ''.join(f'{byte:08b}' for byte in struct.pack('>d', value))
    if isinstance(value, str):
        return ''.join(f'{ord(c):08b}' for c in value)
    raise TypeError(f"BIT SPLIT cannot split a {type(value).__name__}; connect a number or text.")


def vector_swap(pA: list, pB: list, swap_x: EnumSwizzle, swap_y: EnumSwizzle,
                swap_z: EnumSwizzle, swap_w: EnumSwizzle, default: list[float]) -> list[float]:
    """Build a four component vector, each component taken from A, B or a constant.

    Args:
        pA: Vector A.
        pB: Vector B.
        swap_x: Source of X.
        swap_y: Source of Y.
        swap_z: Source of Z.
        swap_w: Source of W.
        default: Constants used for ``CONSTANT`` and for missing components.

    Returns:
        The new vector.
    """
    pA = list(pA) + [0] * max(0, 4 - len(pA))
    pB = list(pB) + [0] * max(0, 4 - len(pB))
    default = list(default) + [0] * max(0, 4 - len(default))

    def pick(swap: EnumSwizzle, constant: float) -> float:
        if swap == EnumSwizzle.CONSTANT:
            return constant
        source = pB if swap in (EnumSwizzle.B_X, EnumSwizzle.B_Y, EnumSwizzle.B_Z, EnumSwizzle.B_W) else pA
        return source[int(swap.value / 10)]

    return [pick(swap_x, default[0]), pick(swap_y, default[1]),
            pick(swap_z, default[2]), pick(swap_w, default[3])]


DEFAULT_VEC4 = {"mij": -sys.float_info.max, "maj": sys.float_info.max, "label": ["X", "Y", "Z", "W"]}


class BitSplitNode(io.ComfyNode):
    """Split a value into its bits."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="BIT SPLIT (JOV) ⭄",
            display_name="BIT SPLIT ⭄",
            category=CATEGORY,
            description="Split a number or text into its separate bits, least significant first, "
                        "as 0 and 1 and as booleans. Drive switches from one packed value.",
            search_aliases=["BIT SPLIT (JOV) ⭄", "bits", "binary", "flags"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input(
                    "value", NUMERICAL_TYPES, optional=True,
                    tooltip="Value to split. Integers use their binary form, floats their 64-bit "
                            "pattern, text 8 bits per character.",
                ),
                io.Int.Input(
                    "bits", default=8, min=0, max=64, optional=True,
                    tooltip="How many bits to return, padded with 0. 0 = every bit the value has.",
                ),
            ],
            outputs=[
                io.AnyType.Output("BIT", display_name="BIT", is_output_list=True,
                                  tooltip="Each bit as 0 or 1."),
                io.Boolean.Output("BOOL", display_name="BOOL", is_output_list=True,
                                  tooltip="Each bit as True or False."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        value = parse_param(kw, "value", EnumConvertType.LIST, 0)
        bits = parse_param(kw, "bits", EnumConvertType.INT, 8, 0, 64)
        params = list(zip_longest_fill(value, bits))
        pbar = Progress(len(params))
        int_out, bool_out = [], []
        for idx, (value, bits) in enumerate(params):
            bit_repr = to_bits(value[0] if value else 0)[::-1]
            if bits > 0:
                bit_repr = bit_repr[:bits] if len(bit_repr) > bits else bit_repr.ljust(bits, '0')
            int_out.append([int(b) for b in bit_repr])
            bool_out.append([b == '1' for b in bit_repr])
            pbar.update(idx)
        return io.NodeOutput(int_out, bool_out)


class ComparisonNode(io.ComfyNode):
    """Compare two values and route one of two inputs on the result."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="COMPARISON (JOV) 🕵🏽",
            display_name="COMPARISON 🕵🏽",
            category=CATEGORY,
            description="Compare A with B, component by component, and pass on 'success' when "
                        "every component passes or 'fail' otherwise. A switch driven by a test.",
            search_aliases=["COMPARISON (JOV) 🕵🏽", "compare", "if", "switch", "condition"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("a", NUMERICAL_TYPES, optional=True,
                                   tooltip="First value. Vectors compare component by component."),
                io.MultiType.Input("b", NUMERICAL_TYPES, optional=True,
                                   tooltip="Second value."),
                io.AnyType.Input("success", optional=True,
                                 tooltip="Sent to OUT when the comparison passes. Anything can "
                                         "be connected; 0 when empty."),
                io.AnyType.Input("fail", optional=True,
                                 tooltip="Sent to OUT when the comparison fails. 0 when empty."),
                io.Combo.Input(
                    "func", options=EnumComparison._member_names_,
                    default=EnumComparison.EQUAL.name, optional=True,
                    tooltip="The test. EQUAL, LESS_THAN and the like compare values; AND, OR, XOR "
                            "treat them as true or false; IN asks whether each part of A is in B.",
                ),
                io.Boolean.Input("swap", default=False, optional=True,
                                 tooltip="Exchange A and B before comparing."),
                io.Boolean.Input("invert", default=False, optional=True,
                                 tooltip="Flip the result, so success and fail trade places."),
            ],
            outputs=[
                io.AnyType.Output("OUT", display_name="OUT", is_output_list=True,
                                  tooltip="'success' or 'fail', depending on the result."),
                io.AnyType.Output("VAL", display_name="VAL", is_output_list=True,
                                  tooltip="The result of each component's test."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        in_a = parse_param(kw, "a", EnumConvertType.ANY, 0)
        in_b = parse_param(kw, "b", EnumConvertType.ANY, 0)
        size = max(len(in_a), len(in_b))
        good = parse_param(kw, "success", EnumConvertType.ANY, 0)[:size]
        fail = parse_param(kw, "fail", EnumConvertType.ANY, 0)[:size]
        op = parse_param(kw, "func", EnumComparison, EnumComparison.EQUAL.name)[:size]
        swap = parse_param(kw, "swap", EnumConvertType.BOOLEAN, False)[:size]
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)[:size]
        params = list(zip_longest_fill(in_a, in_b, good, fail, op, swap, invert))
        pbar = Progress(len(params))
        outs, vals = [], []
        for idx, (A, B, good, fail, op, swap, invert) in enumerate(params):
            A = list(A) if isinstance(A, (tuple, list)) else [A]
            B = list(B) if isinstance(B, (tuple, list)) else [B]

            size = min(4, max(len(A), len(B))) - 1
            typ = [EnumConvertType.FLOAT, EnumConvertType.VEC2, EnumConvertType.VEC3, EnumConvertType.VEC4][size]
            val_a = parse_value(A, typ, [A[-1]] * (size + 1))
            val_a = list(val_a) if isinstance(val_a, (list, tuple)) else [val_a]
            val_b = parse_value(B, typ, [B[-1]] * (size + 1))
            val_b = list(val_b) if isinstance(val_b, (list, tuple)) else [val_b]

            if swap:
                val_a, val_b = val_b, val_a

            match op:
                case EnumComparison.GREATER_THAN:
                    val = [a > b for a, b in zip(val_a, val_b)]
                case EnumComparison.GREATER_THAN_EQUAL:
                    val = [a >= b for a, b in zip(val_a, val_b)]
                case EnumComparison.LESS_THAN:
                    val = [a < b for a, b in zip(val_a, val_b)]
                case EnumComparison.LESS_THAN_EQUAL:
                    val = [a <= b for a, b in zip(val_a, val_b)]
                case EnumComparison.NOT_EQUAL:
                    val = [a != b for a, b in zip(val_a, val_b)]
                case EnumComparison.AND:
                    val = [bool(a) and bool(b) for a, b in zip(val_a, val_b)]
                case EnumComparison.NAND:
                    val = [not (bool(a) and bool(b)) for a, b in zip(val_a, val_b)]
                case EnumComparison.OR:
                    val = [bool(a) or bool(b) for a, b in zip(val_a, val_b)]
                case EnumComparison.NOR:
                    val = [not (bool(a) or bool(b)) for a, b in zip(val_a, val_b)]
                case EnumComparison.XOR:
                    val = [bool(a) != bool(b) for a, b in zip(val_a, val_b)]
                case EnumComparison.XNOR:
                    val = [bool(a) == bool(b) for a, b in zip(val_a, val_b)]
                case EnumComparison.IS:
                    val = [a is b for a, b in zip(val_a, val_b)]
                case EnumComparison.IS_NOT:
                    val = [a is not b for a, b in zip(val_a, val_b)]
                case EnumComparison.IN:
                    val = [a in val_b for a in val_a]
                case EnumComparison.NOT_IN:
                    val = [a not in val_b for a in val_a]
                case _:
                    val = [a == b for a, b in zip(val_a, val_b)]

            output = all(bool(v) for v in val)
            if invert:
                output = not output
            outs.append(good if output else fail)
            vals.append(val)
            pbar.update(idx)

        if outs and all(isinstance(o, torch.Tensor) for o in outs):
            outs = stack_runs(outs)
        return io.NodeOutput(outs, vals)


class LerpNode(io.ComfyNode):
    """Linearly interpolate between two values or vectors."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LERP (JOV) 🔰",
            display_name="LERP 🔰",
            category=CATEGORY,
            description="Blend between two numbers or vectors by a factor, per component. 0 gives "
                        "A, 1 gives B. Pair with TICK to animate between two settings.",
            search_aliases=["LERP (JOV) 🔰", "lerp", "interpolate", "mix", "blend values"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("a", NUMERICAL_TYPES, optional=True,
                                   tooltip="Start value. When empty, aa is used."),
                io.MultiType.Input("b", NUMERICAL_TYPES, optional=True,
                                   tooltip="End value. When empty, bb is used."),
                VEC4.Input(
                    "alpha", optional=True,
                    tooltip="Blend factor for each component, 0 to 1. 0 = A; 0.5 = halfway; 1 = B.",
                    extra_dict={"default": (0.5, 0.5, 0.5, 0.5), "mij": 0, "maj": 1},
                ),
                io.Combo.Input(
                    "type", options=CONVERT_TYPES, default=EnumConvertType.FLOAT.name,
                    optional=True,
                    tooltip="Type of the result. FLOAT and INT use the first component; VEC2 to "
                            "VEC4 use that many.",
                ),
                VEC4.Input("aa", optional=True, tooltip="Start value used when A is not connected.",
                           extra_dict={"default": (0, 0, 0, 0)}),
                VEC4.Input("bb", optional=True, tooltip="End value used when B is not connected.",
                           extra_dict={"default": (1, 1, 1, 1)}),
            ],
            outputs=[
                io.AnyType.Output("❔", display_name="❔", is_output_list=True,
                                  tooltip="The blended value, of the type chosen in 'type'."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        A = parse_param(kw, "a", EnumConvertType.ANY, None)
        B = parse_param(kw, "b", EnumConvertType.ANY, None)
        alpha = parse_param(kw, "alpha", EnumConvertType.VEC4, (0.5, 0.5, 0.5, 0.5))
        typ = parse_param(kw, "type", EnumConvertType, EnumConvertType.FLOAT.name)
        a_xyzw = parse_param(kw, "aa", EnumConvertType.VEC4, (0, 0, 0, 0))
        b_xyzw = parse_param(kw, "bb", EnumConvertType.VEC4, (1, 1, 1, 1))
        values = []
        params = list(zip_longest_fill(A, B, alpha, typ, a_xyzw, b_xyzw))
        pbar = Progress(len(params))
        for idx, (A, B, alpha, typ, a_xyzw, b_xyzw) in enumerate(params):
            size = max(1, int(typ.value / 10))
            if A is None:
                A = a_xyzw[:size]
            if B is None:
                B = b_xyzw[:size]

            val_a = parse_value(A, EnumConvertType.VEC4, a_xyzw)
            val_b = parse_value(B, EnumConvertType.VEC4, b_xyzw)
            alpha = parse_value(alpha, EnumConvertType.VEC4, alpha)
            val = [val_b[x] * alpha[x] + val_a[x] * (1 - alpha[x]) for x in range(size)]

            if typ == EnumConvertType.BOOLEAN:
                convert = lambda v: bool(round(v))
            elif "INT" in typ.name:
                convert = int
            else:
                convert = float
            ret = []
            for v in val:
                try:
                    ret.append(convert(v))
                except (OverflowError, ValueError):
                    ret.append(0)
            values.append(ret[0] if size == 1 else ret)
            pbar.update(idx)
        return io.NodeOutput(values)


class OPUnaryNode(io.ComfyNode):
    """Apply a single-input function to a value or vector."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="OP UNARY (JOV) 🎲",
            display_name="OP UNARY 🎲",
            category=CATEGORY,
            description="Apply a one-input function to a number, vector or picture: absolute "
                        "value, rounding, roots, trigonometry, logic, or a summary such as mean, "
                        "median or length. A picture is reduced to its mean first.",
            search_aliases=["OP UNARY (JOV) 🎲", "math", "abs", "sqrt", "sin", "round", "mean"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("a", FULL_TYPES, optional=True,
                                   tooltip="The value. When empty, aa is used."),
                io.Combo.Input(
                    "func", options=EnumUnaryOperation._member_names_,
                    default=EnumUnaryOperation.ABS.name, optional=True,
                    tooltip="The function, applied to each component. MEAN, MEDIAN, MODE, "
                            "MAXIMUM, MINIMUM and MAGNITUDE reduce the vector to one value.",
                ),
                io.Combo.Input(
                    "type", options=CONVERT_TYPES, default=EnumConvertType.FLOAT.name,
                    optional=True, tooltip="Type of the result.",
                ),
                VEC4.Input(
                    "aa", optional=True, tooltip="Value used when A is not connected.",
                    extra_dict={"default": (0, 0, 0, 0), "precision": 2, **DEFAULT_VEC4},
                ),
            ],
            outputs=[
                io.AnyType.Output("❔", display_name="❔", is_output_list=True,
                                  tooltip="The result, of the type chosen in 'type'."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        results = []
        A = parse_param(kw, "a", EnumConvertType.ANY, None)
        op = parse_param(kw, "func", EnumUnaryOperation, EnumUnaryOperation.ABS.name)
        out = parse_param(kw, "type", EnumConvertType, EnumConvertType.FLOAT.name)
        a_xyzw = parse_param(kw, "aa", EnumConvertType.VEC4, (0, 0, 0, 0))
        params = list(zip_longest_fill(A, op, out, a_xyzw))
        pbar = Progress(len(params))
        for idx, (A, op, out, a_xyzw) in enumerate(params):
            if A is None:
                A = list(a_xyzw)
            if not isinstance(A, (list, tuple)):
                A = [A]
            best_type = [EnumConvertType.FLOAT, EnumConvertType.VEC2, EnumConvertType.VEC3,
                         EnumConvertType.VEC4][max(0, min(3, len(A) - 1))]
            val = parse_value(A, best_type, a_xyzw)
            val = list(parse_value(val, EnumConvertType.VEC4, a_xyzw))
            match op:
                case EnumUnaryOperation.MEAN:
                    val = [sum(val) / len(val)]
                case EnumUnaryOperation.MEDIAN:
                    val = [sorted(val)[len(val) // 2]]
                case EnumUnaryOperation.MODE:
                    counts = Counter(val)
                    val = [max(counts, key=counts.get)]
                case EnumUnaryOperation.MAGNITUDE:
                    val = [math.sqrt(sum(x ** 2 for x in val))]
                case EnumUnaryOperation.NORMALIZE:
                    m = math.sqrt(sum(x ** 2 for x in val))
                    val = [v / m for v in val] if m > 0 else [0] * len(val)
                case EnumUnaryOperation.MAXIMUM:
                    val = [max(val)]
                case EnumUnaryOperation.MINIMUM:
                    val = [min(val)]
                case _:
                    ret = []
                    for v in val:
                        try:
                            v = OP_UNARY[op](v)
                        except (ArithmeticError, ValueError) as error:
                            logger.warning("%s of %s failed (%s), giving 0", op.name, v, type(error).__name__)
                            v = 0
                        ret.append(v)
                    val = ret

            results.append(parse_value(val, out, 0))
            pbar.update(idx)
        return io.NodeOutput(results)


class OPBinaryNode(io.ComfyNode):
    """Apply a two-input function to values or vectors."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="OP BINARY (JOV) 🌟",
            display_name="OP BINARY 🌟",
            category=CATEGORY,
            description="Combine two numbers, vectors or pictures with arithmetic, minimum and "
                        "maximum, dot and cross products, bitwise logic or set operations. A "
                        "picture is reduced to its mean first.",
            search_aliases=["OP BINARY (JOV) 🌟", "math", "add", "multiply", "subtract", "divide", "power"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("a", FULL_TYPES, optional=True,
                                   tooltip="First value. When empty, aa is used."),
                io.MultiType.Input("b", FULL_TYPES, optional=True,
                                   tooltip="Second value. When empty, bb is used."),
                io.Combo.Input(
                    "func", options=EnumBinaryOperation._member_names_,
                    default=EnumBinaryOperation.ADD.name, optional=True,
                    tooltip="The operation, applied component by component. DOT_PRODUCT gives one "
                            "value; CROSS_PRODUCT needs three components; UNION, INTERSECTION and "
                            "DIFFERENCE treat the vectors as sets.",
                ),
                io.Combo.Input(
                    "type", options=CONVERT_TYPES, default=CONVERT_TYPES[2], optional=True,
                    tooltip="Type of the result.",
                ),
                io.Boolean.Input("swap", default=False, optional=True,
                                 tooltip="Exchange A and B first, which matters for SUBTRACT, "
                                         "DIVIDE, POWER and the shifts."),
                VEC4.Input("aa", optional=True, tooltip="Value used when A is not connected.",
                           extra_dict={"default": (0, 0, 0, 0), **DEFAULT_VEC4}),
                VEC4.Input("bb", optional=True, tooltip="Value used when B is not connected.",
                           extra_dict={"default": (0, 0, 0, 0), **DEFAULT_VEC4}),
            ],
            outputs=[
                io.AnyType.Output("❔", display_name="❔", is_output_list=True,
                                  tooltip="The result, of the type chosen in 'type'."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        results = []
        A = parse_param(kw, "a", EnumConvertType.ANY, None)
        B = parse_param(kw, "b", EnumConvertType.ANY, None)
        op = parse_param(kw, "func", EnumBinaryOperation, EnumBinaryOperation.ADD.name)
        typ = parse_param(kw, "type", EnumConvertType, EnumConvertType.FLOAT.name)
        swap = parse_param(kw, "swap", EnumConvertType.BOOLEAN, False)
        a_xyzw = parse_param(kw, "aa", EnumConvertType.VEC4, (0, 0, 0, 0))
        b_xyzw = parse_param(kw, "bb", EnumConvertType.VEC4, (0, 0, 0, 0))
        params = list(zip_longest_fill(A, B, a_xyzw, b_xyzw, op, typ, swap))
        pbar = Progress(len(params))
        for idx, (A, B, a_xyzw, b_xyzw, op, typ, swap) in enumerate(params):
            if A is None:
                A = list(a_xyzw)
            if B is None:
                B = list(b_xyzw)
            if not isinstance(A, (list, tuple)):
                A = [A]
            if not isinstance(B, (list, tuple)):
                B = [B]
            size = max(0, min(3, max(len(A) - 1, len(B) - 1)))
            best_type = [EnumConvertType.FLOAT, EnumConvertType.VEC2, EnumConvertType.VEC3, EnumConvertType.VEC4][size]
            val_a = list(parse_value(parse_value(A, best_type, a_xyzw), EnumConvertType.VEC4, a_xyzw))
            val_b = list(parse_value(parse_value(B, best_type, b_xyzw), EnumConvertType.VEC4, b_xyzw))

            if swap:
                val_a, val_b = val_b, val_a

            size = max(1, int(typ.value / 10))
            val_a = val_a[:size + 1]
            val_b = val_b[:size + 1]

            match op:
                case EnumBinaryOperation.DOT_PRODUCT:
                    val = [sum(a * b for a, b in zip(val_a, val_b))]
                case EnumBinaryOperation.CROSS_PRODUCT:
                    val = [0, 0, 0]
                    if len(val_a) < 3 or len(val_b) < 3:
                        logger.warning("CROSS_PRODUCT needs three components; set type to VEC3 or VEC4")
                    else:
                        val = [
                            val_a[1] * val_b[2] - val_a[2] * val_b[1],
                            val_a[2] * val_b[0] - val_a[0] * val_b[2],
                            val_a[0] * val_b[1] - val_a[1] * val_b[0]
                        ]
                case EnumBinaryOperation.SUBTRACT:
                    val = [a - b for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.MULTIPLY:
                    val = [a * b for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.DIVIDE:
                    val = [a / b if b != 0 else 0 for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.DIVIDE_FLOOR:
                    val = [a // b if b != 0 else 0 for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.MODULUS:
                    val = [a % b if b != 0 else 0 for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.POWER:
                    val = []
                    for a, b in zip(val_a, val_b):
                        try:
                            val.append(float(a) ** float(b) if b >= 0 else 0)
                        except OverflowError:
                            val.append(math.inf)
                    val = [0 if isinstance(v, complex) else v for v in val]
                case EnumBinaryOperation.MAXIMUM:
                    val = [max(a, val_b[i]) for i, a in enumerate(val_a)]
                case EnumBinaryOperation.MINIMUM:
                    val = [min(a, val_b[i]) for i, a in enumerate(val_a)]
                case EnumBinaryOperation.BIT_AND:
                    val = [int(a) & int(b) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_NAND:
                    val = [not (int(a) & int(b)) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_OR:
                    val = [int(a) | int(b) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_NOR:
                    val = [not (int(a) | int(b)) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_XOR:
                    val = [int(a) ^ int(b) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_XNOR:
                    val = [not (int(a) ^ int(b)) for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_LSHIFT:
                    val = [int(a) << min(MAX_SHIFT, int(b)) if b >= 0 else 0 for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.BIT_RSHIFT:
                    val = [int(a) >> min(MAX_SHIFT, int(b)) if b >= 0 else 0 for a, b in zip(val_a, val_b)]
                case EnumBinaryOperation.UNION:
                    val = list(set(val_a) | set(val_b))
                case EnumBinaryOperation.INTERSECTION:
                    val = list(set(val_a) & set(val_b))
                case EnumBinaryOperation.DIFFERENCE | EnumBinaryOperation.BASE:
                    val = list(set(val_a) - set(val_b))
                case _:
                    val = [a + b for a, b in zip(val_a, val_b)]

            default = val if len(val) else [0]
            results.append(parse_value(val, typ, default))
            pbar.update(idx)
        return io.NodeOutput(results)


class StringerNode(io.ComfyNode):
    """Split, join, find, replace or slice text."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="STRINGER (JOV) 🪀",
            display_name="STRINGER 🪀",
            category=CATEGORY,
            description="Split, join, filter, replace or slice the text wired into its growing "
                        "string inputs. Each connection adds another input.",
            search_aliases=["STRINGER (JOV) 🪀", "string", "split", "join", "replace", "text list"],
            is_input_list=True,
            inputs=[
                io.Combo.Input(
                    "func", options=EnumConvertString._member_names_,
                    default=EnumConvertString.SPLIT.name, optional=True,
                    tooltip="SPLIT = break at key; JOIN = glue with key between; FIND = keep "
                            "entries holding key; REPLACE = swap key for replace; SLICE = cut "
                            "each entry by range.",
                ),
                io.String.Input(
                    "key", default="", dynamic_prompts=False, optional=True,
                    tooltip="Separator for SPLIT and JOIN, or the text to look for in FIND and "
                            "REPLACE. Example: ',' splits 'a,b,c' into three.",
                ),
                io.String.Input(
                    "replace", default="", dynamic_prompts=False, optional=True,
                    tooltip="Text that REPLACE puts where key was found.",
                ),
                VEC3.Input(
                    "range", optional=True,
                    tooltip="SLICE start, end and step in characters. -1 as end = to the end; "
                            "step -1 reverses.",
                    extra_dict={"default": (0, -1, 1), "int": True},
                ),
            ],
            outputs=[
                io.String.Output("STRING", display_name="STRING", is_output_list=True,
                                 tooltip="The resulting text entries."),
                io.Int.Output("COUNT", display_name="COUNT",
                              tooltip="How many entries STRING holds."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        data_list = [str(d) for d in parse_dynamic(kw, "string", EnumConvertType.ANY, "") if d is not None]
        op = parse_param(kw, "func", EnumConvertString, EnumConvertString.SPLIT.name)[0]
        key = parse_param(kw, "key", EnumConvertType.STRING, "")[0]
        replace = parse_param(kw, "replace", EnumConvertType.STRING, "")[0]
        stenst = parse_param(kw, "range", EnumConvertType.VEC3INT, (0, -1, 1))[0]
        results = []
        match op:
            case EnumConvertString.SPLIT:
                results = data_list
                if key != "":
                    results = []
                    for d in data_list:
                        results.extend([key if len(r) == 0 else r for r in d.split(key)])
            case EnumConvertString.JOIN:
                results = [key.join(data_list)]
            case EnumConvertString.FIND:
                results = [r for r in data_list if r.find(key) > -1]
            case EnumConvertString.REPLACE:
                results = [r.replace(key, replace) for r in data_list] if key != "" else data_list
            case EnumConvertString.SLICE:
                start, end, step = stenst
                for x in data_list:
                    s = len(x) if start < 0 else min(max(0, start), len(x))
                    e = len(x) if end < 0 else min(max(0, end), len(x))
                    results.append(x[s:e:step] if step != 0 else x)
        if not results:
            results = [""]
        return io.NodeOutput(results, len(results))


class SwizzleNode(io.ComfyNode):
    """Rearrange vector components taken from two vectors or constants."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SWIZZLE (JOV) 😵",
            display_name="SWIZZLE 😵",
            category=CATEGORY,
            description="Build a new vector whose X, Y, Z and W each come from any component of "
                        "vector A, vector B or a constant. Reorder, duplicate or mix components.",
            search_aliases=["SWIZZLE (JOV) 😵", "swizzle", "reorder", "vector components"],
            is_input_list=True,
            inputs=[
                io.MultiType.Input("a", NUMERICAL_TYPES, optional=True, tooltip="Vector A."),
                io.MultiType.Input("b", NUMERICAL_TYPES, optional=True, tooltip="Vector B."),
                io.Combo.Input("type", options=EnumConvertType._member_names_[3:6],
                               default=EnumConvertType._member_names_[3], optional=True,
                               tooltip="Size of the result: VEC2, VEC3 or VEC4."),
                io.Combo.Input("swap x", options=EnumSwizzle._member_names_,
                               default=EnumSwizzle.A_X.name, optional=True,
                               tooltip="Source of X: A_ or B_ and a component, or CONSTANT from 'default'."),
                io.Combo.Input("swap y", options=EnumSwizzle._member_names_,
                               default=EnumSwizzle.A_Y.name, optional=True, tooltip="Source of Y."),
                io.Combo.Input("swap z", options=EnumSwizzle._member_names_,
                               default=EnumSwizzle.A_Z.name, optional=True, tooltip="Source of Z."),
                io.Combo.Input("swap w", options=EnumSwizzle._member_names_,
                               default=EnumSwizzle.A_W.name, optional=True, tooltip="Source of W."),
                VEC4.Input(
                    "default", optional=True,
                    tooltip="Constants for CONSTANT sources, and for components A or B lacks.",
                    extra_dict={"default": (0, 0, 0, 0), "mij": -sys.float_info.max,
                                "maj": sys.float_info.max},
                ),
            ],
            outputs=[
                io.AnyType.Output("❔", display_name="❔", is_output_list=True,
                                  tooltip="The new vector."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        pA = parse_param(kw, "a", EnumConvertType.LIST, None)
        pB = parse_param(kw, "b", EnumConvertType.LIST, None)
        typ = parse_param(kw, "type", EnumConvertType, EnumConvertType.VEC2.name)
        swap_x = parse_param(kw, "swap x", EnumSwizzle, EnumSwizzle.A_X.name)
        swap_y = parse_param(kw, "swap y", EnumSwizzle, EnumSwizzle.A_Y.name)
        swap_z = parse_param(kw, "swap z", EnumSwizzle, EnumSwizzle.A_Z.name)
        swap_w = parse_param(kw, "swap w", EnumSwizzle, EnumSwizzle.A_W.name)
        default = parse_param(kw, "default", EnumConvertType.VEC4, (0, 0, 0, 0))
        params = list(zip_longest_fill(pA, pB, typ, swap_x, swap_y, swap_z, swap_w, default))
        results = []
        pbar = Progress(len(params))
        for idx, (pA, pB, typ, swap_x, swap_y, swap_z, swap_w, default) in enumerate(params):
            default = list(default)
            pA = list(pA or [])
            pB = list(pB or [])
            pA = pA + default[len(pA):]
            pB = pB + default[len(pB):]
            val = vector_swap(pA, pB, swap_x, swap_y, swap_z, swap_w, default)
            results.append(parse_value(val, typ, val))
            pbar.update(idx)
        return io.NodeOutput(results)


NODES = [BitSplitNode, ComparisonNode, LerpNode, OPUnaryNode, OPBinaryNode, StringerNode, SwizzleNode]
