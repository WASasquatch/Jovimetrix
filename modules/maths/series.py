"""Linear number series with looping and ping-pong."""


def seriesLinear(start=0.0, step=1.0, count=10, loop=None, pingpong=False) -> list[float]:
    """Generate ``count`` values from ``start`` in steps of ``step``.

    Args:
        start: First value.
        step: Amount added per value.
        count: Number of values.
        loop: Values per loop before the series starts over; ``None`` or 0 = ``count``.
        pingpong: Run back down at the end of each loop instead of starting over.

    Returns:
        The series.
    """
    result = []
    count = max(1, count)
    loop_size = loop or count

    for i in range(count):
        loop_position = i % loop_size if loop is not None else i

        if pingpong:
            span = loop_size if loop is not None else count
            cycle_length = span * 2 - 2
            cycle_position = i % cycle_length if cycle_length > 0 else 0
            if cycle_position < span:
                current = start + cycle_position * step
            else:
                span_end = start + (span - 1) * step
                current = span_end - (cycle_position - span + 1) * step
        else:
            current = start + loop_position * step
        result.append(current)

    return result
