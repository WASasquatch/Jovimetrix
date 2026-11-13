"""The custom socket types the pack declares, and the socket lists its nodes share.

``VEC2``, ``VEC3`` and ``VEC4`` carry a tuple of numbers and draw the vector widget.
"""

from __future__ import annotations

from comfy_api.latest import io

VEC2 = io.Custom("VEC2")
VEC3 = io.Custom("VEC3")
VEC4 = io.Custom("VEC4")
BUS = io.Custom("BUS")
JLUT = io.Custom("JLUT")
JSON = io.Custom("JSON")

#: Socket types for an input taking a picture or a mask: ``IMAGE,MASK``.
IMAGE_TYPES = [io.Image, io.Mask]

#: Socket types for an input taking a number or a vector: ``BOOLEAN,FLOAT,INT,VEC2,VEC3,VEC4``.
NUMERICAL_TYPES = [io.Boolean, io.Float, io.Int, VEC2, VEC3, VEC4]

#: Every value type the pack converts between, pictures included.
FULL_TYPES = [*NUMERICAL_TYPES, io.Image, io.Mask]

#: Outputs of every node that hands back a picture.
IMAGE_OUTPUTS = [
    io.Image.Output(
        "RGBA", display_name="RGBA",
        tooltip="The picture with its alpha channel. Where there is alpha, it masks the picture.",
    ),
    io.Image.Output(
        "RGB", display_name="RGB",
        tooltip="The picture as three colour channels, with no alpha.",
    ),
    io.Mask.Output(
        "MASK", display_name="MASK",
        tooltip="The alpha channel as a mask: white where the picture is opaque.",
    ),
]
