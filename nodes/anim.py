"""Animation nodes: a frame series generator and a waveform generator."""

from __future__ import annotations

import math
import sys

from comfy_api.latest import io

from ..modules.enums import EnumConvertType, EnumEase, EnumNormalize, EnumWave
from ..modules.node import Progress, category
from ..modules.params import parse_param, zip_longest_fill

CATEGORY = category("ANIMATION")


class TickNode(io.ComfyNode):
    """Generate a series of frame values with looping, ping-pong, normalising and easing."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="TICK (JOV) ⏱",
            display_name="TICK ⏱",
            category=CATEGORY,
            description="Generate a list of frame values from a start and a step, with optional "
                        "looping and ping-pong, plus normalised and eased copies. Drive any "
                        "number input across a batch or an animation.",
            search_aliases=["TICK (JOV) ⏱", "tick", "frame counter", "series", "keyframes", "range"],
            is_input_list=True,
            inputs=[
                io.Float.Input(
                    "start", default=0, min=-sys.maxsize, max=sys.maxsize, optional=True,
                    tooltip="First value of the series.",
                ),
                io.Float.Input(
                    "step", default=0, min=-sys.float_info.max, max=sys.float_info.max,
                    optional=True, extra_dict={"precision": 3},
                    tooltip="Amount added for each frame. 0 = 1; negative values count down.",
                ),
                io.Int.Input(
                    "count", default=1, min=1, max=1500, optional=True,
                    tooltip="How many values to generate.",
                ),
                io.Int.Input(
                    "loop", default=0, min=0, max=sys.maxsize, optional=True,
                    tooltip="After this many values the series starts over. 0 = no loop.",
                ),
                io.Boolean.Input(
                    "pingpong", default=False, optional=True,
                    tooltip="At the loop point, run back down instead of jumping to the start.",
                ),
                io.Combo.Input(
                    "ease", options=EnumEase._member_names_, default=EnumEase.LINEAR.name,
                    optional=True,
                    tooltip="Easing curve for the EASED outputs. LINEAR = even spacing; _IN = slow "
                            "start; _OUT = slow finish; _IN_OUT = both.",
                ),
                io.Combo.Input(
                    "norm", options=EnumNormalize._member_names_,
                    default=EnumNormalize.MINMAX2.name, optional=True,
                    tooltip="Normalising for the LINEAR outputs. MINMAX1 = 0 to 1; MINMAX2 = -1 to "
                            "1; ZSCORE = standard score; L2 = unit length.",
                ),
                io.Float.Input(
                    "scalar", default=1, min=0, max=sys.float_info.max, optional=True,
                    tooltip="Multiplier for the SCALAR outputs. 1 = same as LINEAR and EASED.",
                ),
            ],
            outputs=[
                io.Float.Output("VALUE", display_name="VALUE", is_output_list=True,
                                tooltip="The raw series, start plus step per frame."),
                io.Float.Output("LINEAR", display_name="LINEAR", is_output_list=True,
                                tooltip="The series normalised as set by norm."),
                io.Float.Output("EASED", display_name="EASED", is_output_list=True,
                                tooltip="The normalised series resampled along the easing curve."),
                io.Float.Output("SCALAR_LIN", display_name="SCALAR_LIN", is_output_list=True,
                                tooltip="LINEAR multiplied by scalar."),
                io.Float.Output("SCALAR_EASE", display_name="SCALAR_EASE", is_output_list=True,
                                tooltip="EASED multiplied by scalar."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        import numpy as np

        from ..modules.maths.ease import ease_op
        from ..modules.maths.norm import norm_op
        from ..modules.maths.series import seriesLinear

        start = parse_param(kw, "start", EnumConvertType.FLOAT, 0)[0]
        step = parse_param(kw, "step", EnumConvertType.FLOAT, 0)[0]
        count = parse_param(kw, "count", EnumConvertType.INT, 1, 1, 1500)[0]
        loop = parse_param(kw, "loop", EnumConvertType.INT, 0, 0)[0]
        pingpong = parse_param(kw, "pingpong", EnumConvertType.BOOLEAN, False)[0]
        ease = parse_param(kw, "ease", EnumEase, EnumEase.LINEAR.name)[0]
        normalize = parse_param(kw, "norm", EnumNormalize, EnumNormalize.MINMAX2.name)[0]
        scalar = parse_param(kw, "scalar", EnumConvertType.FLOAT, 1, 0)[0]

        if step == 0:
            step = 1

        cycle = seriesLinear(start, step, count, loop, pingpong)
        linear = norm_op(normalize, np.array(cycle, dtype=np.float64))
        eased = ease_op(ease, linear, len(linear))
        return io.NodeOutput(
            [float(v) for v in cycle],
            linear.tolist(),
            eased.tolist(),
            (linear * scalar).tolist(),
            (eased * scalar).tolist(),
        )


class WaveGeneratorNode(io.ComfyNode):
    """Sample a waveform at a point in time."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="WAVE GEN (JOV) 🌊",
            display_name="WAVE GEN 🌊",
            category=CATEGORY,
            description="Sample a sine, square, sawtooth, noise or other waveform at a point in "
                        "time, as a float and an integer. Feed time from TICK to animate a value.",
            search_aliases=["WAVE GEN (JOV) 🌊", "wave", "oscillator", "lfo", "sine"],
            is_input_list=True,
            inputs=[
                io.Combo.Input(
                    "wave", options=EnumWave._member_names_, default=EnumWave.SIN.name,
                    optional=True,
                    tooltip="Shape of the wave. SIN, COS, TRIANGLE and SAWTOOTH repeat smoothly; "
                            "SQUARE and PULSE switch; NOISE is random; GAUSSIAN is one bump "
                            "centred at freq.",
                ),
                io.Float.Input(
                    "freq", default=1, min=0, max=sys.float_info.max, step=0.01, optional=True,
                    tooltip="Cycles per unit of time. 1 = one cycle as time runs 0 to 1. For "
                            "GAUSSIAN, the time of the peak.",
                ),
                io.Float.Input(
                    "amp", default=1, min=0, max=sys.float_info.max, step=0.01, optional=True,
                    tooltip="Height of the wave above and below its offset.",
                ),
                io.Float.Input(
                    "phase", default=0, min=0, max=1, step=0.01, optional=True,
                    tooltip="Shift along the wave, 0 to 1. 0.5 = half a cycle later.",
                ),
                io.Float.Input(
                    "offset", default=0, min=0, max=1, step=0.001, optional=True,
                    tooltip="Value added to every sample, which moves the whole wave up.",
                ),
                io.Float.Input(
                    "time", default=0, min=0, max=sys.float_info.max, step=0.0001, optional=True,
                    tooltip="The moment to sample. Wire a list of times in to get a list of samples.",
                ),
                io.Boolean.Input(
                    "invert", default=False, optional=True,
                    tooltip="Flip the wave upside down around its offset.",
                ),
                io.Boolean.Input(
                    "absolute", default=False, optional=True,
                    tooltip="Make every sample positive, which folds the lower half of the wave up.",
                ),
            ],
            outputs=[
                io.Float.Output("FLOAT", display_name="FLOAT", is_output_list=True,
                                tooltip="The sample as a float, one per time given."),
                io.Int.Output("INT", display_name="INT", is_output_list=True,
                              tooltip="The sample rounded toward zero."),
            ],
        )

    @classmethod
    def execute(cls, **kw) -> io.NodeOutput:
        from ..modules.maths.wave import wave_op

        op = parse_param(kw, "wave", EnumWave, EnumWave.SIN.name)
        freq = parse_param(kw, "freq", EnumConvertType.FLOAT, 1, 0)
        amp = parse_param(kw, "amp", EnumConvertType.FLOAT, 1, 0)
        phase = parse_param(kw, "phase", EnumConvertType.FLOAT, 0, 0)
        shift = parse_param(kw, "offset", EnumConvertType.FLOAT, 0, 0)
        delta_time = parse_param(kw, "time", EnumConvertType.FLOAT, 0, 0)
        invert = parse_param(kw, "invert", EnumConvertType.BOOLEAN, False)
        absolute = parse_param(kw, "absolute", EnumConvertType.BOOLEAN, False)
        floats, ints = [], []
        params = list(zip_longest_fill(op, freq, amp, phase, shift, delta_time, invert, absolute))
        pbar = Progress(len(params))
        for idx, (op, freq, amp, phase, shift, delta_time, invert, absolute) in enumerate(params):
            if invert:
                amp = -amp
            val = wave_op(op, phase, freq, amp, shift, delta_time)
            if absolute:
                val = abs(val)
            if math.isnan(val):
                val = 0.0
            val = max(-sys.float_info.max, min(val, sys.float_info.max))
            floats.append(float(val))
            ints.append(int(val))
            pbar.update(idx)
        return io.NodeOutput(floats, ints)


NODES = [TickNode, WaveGeneratorNode]
