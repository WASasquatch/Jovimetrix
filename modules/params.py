"""Conversion of node inputs, which arrive as lists, into typed values.

Vectors are tuples, images are float tensors in ``[0, 1]`` shaped ``(H, W, C)``.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any, Generator, Optional, TypeAlias

import torch

from . import log
from .enums import EnumConvertType

logger = log.get_logger("params")

TensorType: TypeAlias = torch.Tensor
RGBAMaskType: TypeAlias = tuple[TensorType, ...]
InputType: TypeAlias = dict[str, Any]

IMAGE_SIZE_MIN: int = 32
IMAGE_SIZE_MAX: int = 8192
IMAGE_SIZE_DEFAULT: int = 512

#: Highest numbered slot ``parse_dynamic`` looks for.
DYNAMIC_SLOTS = 100

_FALSE_TEXT = ("", "0", "0.0", "False", "false")
_TENSOR_TYPES = (EnumConvertType.IMAGE, EnumConvertType.MASK, EnumConvertType.LATENT)


def parse_dynamic(data: InputType, prefix: str, typ: EnumConvertType, default: Any,
                  extend: bool = True) -> list[Any]:
    """Collect the numbered inputs a growing node adds, ``0_name``, ``1_name`` and so on.

    Args:
        data: The node's keyword inputs.
        prefix: Name the slots carry after the number, matched loosely.
        typ: Type each value is converted to.
        default: Value used where a slot holds nothing.
        extend: Flatten every slot into one list; otherwise one list per slot.

    Returns:
        The converted values, in slot order.
    """
    vals: list[Any] = []
    fail = 0
    keys = list(data.keys())
    for i in range(DYNAMIC_SLOTS):
        if fail > 2:
            break
        found = False
        for k in keys:
            if k.startswith(f"{i}_") or k.startswith(f"{i}_{prefix}_"):
                val = parse_param(data, k, typ, default)
                if extend:
                    vals.extend(val)
                else:
                    vals.append(val)
                found = True
                break
        if not found:
            fail += 1
    return vals


def single_frame(tensor: TensorType) -> bool:
    """Whether a tensor is one picture with no batch dimension.

    ComfyUI passes pictures as ``(B, H, W, C)`` and masks as ``(B, H, W)``, but some nodes hand
    on a single mask as ``(H, W)`` or a single picture as ``(H, W, C)``. A three dimensional
    tensor whose last dimension is 1, 3 or 4 is read as one picture: a mask batch that narrow
    does not occur in practice.

    Args:
        tensor: The tensor.

    Returns:
        True for ``(H, W)`` and ``(H, W, 1|3|4)``.
    """
    return tensor.ndim == 2 or (tensor.ndim == 3 and tensor.shape[-1] in (1, 3, 4))


def tensor_frames(tensor: TensorType) -> list[TensorType]:
    """Split a picture or mask tensor into ``(H, W, C)`` frames.

    Args:
        tensor: ``(B, H, W, C)``, ``(B, H, W)``, or a single ``(H, W)`` or ``(H, W, C)``.

    Returns:
        One frame per picture; masks gain a channel dimension of 1.
    """
    if tensor.ndim >= 4:
        return list(tensor)
    if single_frame(tensor):
        return [tensor.unsqueeze(-1) if tensor.ndim == 2 else tensor]
    if tensor.ndim == 3:
        return [t.unsqueeze(-1) for t in tensor]
    return [tensor]


def _solid_image(val: Any) -> TensorType:
    """Build a small RGBA image filled with a colour read from ``val``."""
    color = parse_value(val, EnumConvertType.VEC4INT, (0, 0, 0, 255), 0, 255)
    pixel = torch.tensor(color, dtype=torch.float32) / 255.0
    return pixel.expand(IMAGE_SIZE_MIN, IMAGE_SIZE_MIN, 4).clone()


def _solid_mask(val: Any) -> TensorType:
    """Build a small mask filled with a level read from ``val``."""
    level = parse_value(val, EnumConvertType.INT, 0, 0, 255)
    return torch.full((IMAGE_SIZE_MIN, IMAGE_SIZE_MIN, 1), level / 255.0, dtype=torch.float32)


def parse_value(val: Any, typ: EnumConvertType, default: Any,
                clip_min: Optional[float] = None, clip_max: Optional[float] = None,
                zero: float = 0.) -> Any:
    """Convert one value into ``typ``.

    Args:
        val: The value. ``None`` falls back to ``default``.
        typ: Target type, or an ``Enum`` class whose member is named by ``val``.
        default: Fallback value, and the source of any missing vector component.
        clip_min: Lowest value a number or vector component may take.
        clip_max: Highest value a number or vector component may take.
        zero: Value a component equal to zero is replaced with.

    Returns:
        The converted value; a scalar for a one-component type, a tuple for a vector.
    """
    if typ == EnumConvertType.ANY:
        return val

    if isinstance(default, torch.Tensor) and typ not in _TENSOR_TYPES:
        h, w = default.shape[:2]
        cc = default.shape[2] if len(default.shape) > 2 else 1
        default = (w, h, cc)

    if val is None:
        if default is None:
            return None
        val = default

    if isinstance(val, dict):
        if '0' in val or 0 in val:
            val = [val.get(i, val.get(str(i), 0)) for i in range(min(len(val), 4))]
        elif 'x' in val:
            val = [val.get(c, 0) for c in 'xyzw']
        elif 'r' in val:
            val = [val.get(c, 0) for c in 'rgba']
        elif '__value__' in val:
            val = val['__value__']

    elif isinstance(val, torch.Tensor) and typ not in _TENSOR_TYPES:
        h, w = val.shape[:2]
        cc = val.shape[2] if len(val.shape) > 2 else 1
        val = (w, h, cc)

    new_val: Any = val
    if typ in (EnumConvertType.FLOAT, EnumConvertType.INT,
               EnumConvertType.VEC2, EnumConvertType.VEC2INT,
               EnumConvertType.VEC3, EnumConvertType.VEC3INT,
               EnumConvertType.VEC4, EnumConvertType.VEC4INT):

        if not isinstance(val, (list, tuple, torch.Tensor)):
            val = [val]

        is_float = typ in (EnumConvertType.FLOAT, EnumConvertType.VEC2,
                           EnumConvertType.VEC3, EnumConvertType.VEC4)
        if clip_min is None:
            clip_min = -sys.float_info.max if is_float else -sys.maxsize
        if clip_max is None:
            clip_max = sys.float_info.max if is_float else sys.maxsize

        size = max(1, int(typ.value / 10))
        new_val = []
        for idx in range(size):
            d: Any = default
            try:
                d = default[idx] if idx < len(default) else 0
            except Exception:
                try:
                    d = default.get(str(idx), 0)
                except Exception:
                    d = default

            v: Any = d if val is None else val[idx] if idx < len(val) else d
            if isinstance(v, str):
                v = v.strip('\n').strip()
                if v == '':
                    v = 0
            elif isinstance(v, torch.Tensor):
                v = v.mean()

            try:
                v = round(float(v or 0), 16) if is_float else int(v)
            except Exception as error:
                logger.warning("could not read %r as a number (%s), using 0", type(v).__name__, error)
                v = 0

            if v == 0:
                v = zero if is_float else int(zero)

            v = max(clip_min, min(v, clip_max))
            new_val.append(v)
        new_val = new_val[0] if size == 1 else tuple(new_val)

    elif typ == EnumConvertType.DICT:
        if isinstance(new_val, str):
            try:
                new_val = json.loads(new_val)
            except json.decoder.JSONDecodeError:
                new_val = {}
        else:
            if not isinstance(new_val, (list, tuple)):
                new_val = [new_val]
            new_val = {i: v for i, v in enumerate(new_val)}

    elif typ == EnumConvertType.LIST:
        if isinstance(new_val, (str, list, int, float)):
            new_val = [new_val]
        else:
            new_val = list(new_val)

    elif typ == EnumConvertType.STRING:
        if isinstance(new_val, (str, list, int, float)):
            new_val = [new_val]
        new_val = ", ".join(map(str, new_val)) if not isinstance(new_val, str) else new_val

    elif typ == EnumConvertType.BOOLEAN:
        if isinstance(new_val, torch.Tensor):
            new_val = True
        elif isinstance(new_val, dict):
            new_val = len(new_val.keys()) > 0
        elif isinstance(new_val, (list, tuple)) and len(new_val) > 0 and (nv := new_val[0]) is not None:
            if isinstance(nv, str):
                new_val = nv not in _FALSE_TEXT
            elif isinstance(nv, (int, float)):
                new_val = nv > 0
        elif isinstance(new_val, str):
            new_val = new_val not in _FALSE_TEXT
        elif isinstance(new_val, (int, float)):
            new_val = new_val > 0

    elif typ == EnumConvertType.LATENT:
        if isinstance(new_val, torch.Tensor):
            new_val = {'samples': new_val.unsqueeze(0)}
        else:
            new_val = {'samples': torch.zeros((1, 4, 64, 64), dtype=torch.float32)}

    elif typ == EnumConvertType.IMAGE:
        if not isinstance(new_val, torch.Tensor):
            new_val = _solid_image(new_val)

    elif typ == EnumConvertType.MASK:
        if not isinstance(new_val, torch.Tensor):
            new_val = _solid_mask(new_val)

    elif isinstance(typ, type) and issubclass(typ, Enum):
        new_val = typ[val]

    return new_val


def parse_param(data: InputType, key: str, typ: EnumConvertType, default: Any,
                clip_min: Optional[float] = None, clip_max: Optional[float] = None,
                zero: float = 0) -> list[Any]:
    """Read input ``key`` from the node's keyword inputs and convert every entry.

    Args:
        data: The node's keyword inputs.
        key: Input id.
        typ: Target type.
        default: Value used where the input is absent.
        clip_min: Lowest value a number may take.
        clip_max: Highest value a number may take.
        zero: Value a zero component is replaced with.

    Returns:
        One converted value per entry the input carried.
    """
    values = data.get(key, default)
    if typ == EnumConvertType.ANY and values is None:
        return [default]
    return parse_param_list(values, typ, default, clip_min, clip_max, zero)


def parse_param_list(values: Any, typ: EnumConvertType, default: Any,
                     clip_min: Optional[float] = None, clip_max: Optional[float] = None,
                     zero: float = 0) -> list[Any]:
    """Convert a list of values into ``typ``, splitting batches into single entries.

    Args:
        values: A value, or a list of them.
        typ: Target type.
        default: Fallback value.
        clip_min: Lowest value a number may take.
        clip_max: Highest value a number may take.
        zero: Value a zero component is replaced with.

    Returns:
        The converted values.
    """
    if not isinstance(values, list):
        values = [values]

    value_array: list[Any] = []
    for val in values:
        if isinstance(val, str):
            if val.startswith("#"):
                val = val[1:]
                if len(val) < 8:
                    val += 'ff'
                try:
                    val = [int(val[i:i + 2], 16) for i in range(0, len(val), 2)]
                except ValueError:
                    logger.warning("'#%s' is not a hex colour", val[:16])
            else:
                try:
                    val = json.loads(val.replace("'", '"'))
                except json.JSONDecodeError:
                    pass
            value_array.append(val)
        elif isinstance(val, dict):
            if (image := val.get('image', None)) is not None:
                ret = image
                if (mask := val.get('mask', None)) is not None:
                    while len(mask.shape) < len(image.shape):
                        mask = mask.unsqueeze(-1)
                    ret = torch.cat((image, mask), dim=-1)
                value_array.extend([t for t in ret])
                continue
            elif 'xyzw' in val:
                val = tuple(x for x in val["xyzw"])
            elif 'samples' in val:
                val = tuple(x for x in val["samples"])
            elif ('0' in val) or (0 in val):
                val = tuple(val.get(i, val.get(str(i), 0)) for i in range(min(len(val), 4)))
            elif 'x' in val and 'y' in val:
                val = tuple(val.get(c, 0) for c in 'xyzw')
            elif 'r' in val and 'g' in val:
                val = tuple(val.get(c, 0) for c in 'rgba')
            elif len(val) == 0:
                val = tuple()
            value_array.append(val)
        elif isinstance(val, torch.Tensor):
            if val.ndim >= 2:
                value_array.extend(tensor_frames(val))
            elif val.ndim == 1:
                value_array.extend(val)
            else:
                value_array.append(val)
        elif isinstance(val, (list, tuple, set)):
            value_array.append(list(val))
        elif isinstance(val, Enum):
            value_array.append(str(val.name))
        else:
            value_array.append(val)

    return [parse_value(v, typ, default, clip_min, clip_max, zero) for v in value_array]


def zip_longest_fill(*iterables: Any) -> Generator[tuple[Any, ...], None, None]:
    """Zip lists of unequal length, repeating the last value of each shorter one.

    Args:
        *iterables: The lists.

    Yields:
        One tuple per position of the longest list.
    """
    lists = [list(iterable) for iterable in iterables]
    longest = max((len(entry) for entry in lists), default=0)
    for idx in range(longest):
        yield tuple(
            (entry[idx] if idx < len(entry) else entry[-1]) if entry else None
            for entry in lists
        )
