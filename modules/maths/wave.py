"""Periodic and shaped waveforms sampled at one time step."""

import math
import random

from ..enums import EnumWave


def _heaviside(x: float) -> float:
    return 1.0 if x >= 0 else 0.0

def wave_sin(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * math.sin(frequency * math.pi * 2 * timestep + phase) + offset

def wave_cos(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * math.cos(frequency * math.pi * 2 * timestep + phase) + offset

def wave_tan(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * math.tan(frequency * math.pi * 2 * timestep + phase) + offset

def wave_sawtooth(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * (2 * (frequency * timestep + phase) % 1 - 0.5) + offset

def wave_triangle(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * (4 * abs((frequency * timestep + phase) % 1 - 0.5) - 1) + offset

def wave_ramp(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * (frequency * timestep + phase % 1) + offset

def wave_step(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * _heaviside(frequency * timestep + phase) + offset

def wave_haversine(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * (1 - math.cos(frequency * math.pi * 2 * (timestep + phase))) + offset

def wave_noise(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * random.uniform(-1, 1) + offset

def wave_square(phase, frequency, amplitude, offset, timestep) -> float:
    s = math.sin(math.pi * 2 * timestep + phase) - frequency
    return amplitude * (0.0 if s == 0 else math.copysign(1.0, s)) + offset

def wave_pulse(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * (1.0 if (frequency * timestep + phase) % 1 < 0.5 else 0.0) + offset

def wave_exponential(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * math.exp(-frequency * (timestep + phase)) + offset

def wave_rectangular_pulse(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * _heaviside(timestep + phase) * _heaviside(-(timestep + phase) + frequency) + offset

def wave_logarithmic(phase, frequency, amplitude, offset, timestep) -> float:
    x = timestep + phase
    if x <= 0:
        return offset
    return amplitude * math.log10(x) / max(1.0, math.log10(frequency) if frequency > 0 else 1.0) + offset

def wave_chirp(phase, frequency, amplitude, offset, timestep) -> float:
    return amplitude * math.sin(math.pi * 2 * frequency * (timestep + phase) ** 2) + offset

def wave_gaussian(phase, mean, amplitude, offset, timestep, std_dev: float = 1) -> float:
    std_dev = std_dev or 1.0
    return amplitude * math.exp(-0.5 * ((timestep + phase - mean) / std_dev) ** 2) + offset


def wave_op(op: EnumWave, phase: float, frequency: float, amplitude: float,
            offset: float, timestep: float, std_dev: float = 1) -> float:
    """Sample a waveform at one time step.

    Args:
        op: The waveform.
        phase: Phase shift, in cycles for the periodic shapes.
        frequency: Cycles per unit of time; the mean for ``GAUSSIAN``.
        amplitude: Peak height.
        offset: Value added to every sample.
        timestep: Time of the sample.
        std_dev: Width of ``GAUSSIAN``.

    Returns:
        The sample.
    """
    name = op.name.lower()
    if (func := globals().get(f"wave_{name}")) is None:
        raise ValueError(f"'{op.name}' is not a waveform Jovimetrix knows.")
    if name == "gaussian":
        return func(phase, frequency, amplitude, offset, timestep, std_dev)
    return func(phase, frequency, amplitude, offset, timestep)
