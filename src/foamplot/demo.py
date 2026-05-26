from math import exp, sin

from .model import MARKERS

# -----------------------------------------------------------------------------
# Demo data
# -----------------------------------------------------------------------------

def generate_demo_series(iteration, max_points=500, line_count=1):
    """
    Generate live-growing sine-wave demo series.

    The visible history grows from 1 point up to max_points.
    After max_points, it becomes a rolling window over the latest max_points.
    """
    line_count = max(1, min(len(MARKERS), line_count))
    max_points = max(1, max_points)
    iteration = max(1, iteration)

    start_iter = max(1, iteration - max_points + 1)
    end_iter = iteration

    x_values = list(range(start_iter, end_iter + 1))
    out = []

    for j in range(line_count):
        amplitude = 3.0 - 0.35 * j
        phase_offset = 0.75 * j
        vertical_offset = 0.15 * j
        frequency = 0.1 + 0.015 * j

        values = [
            amplitude * sin(i * frequency + phase_offset) + vertical_offset
            for i in x_values
        ]

        out.append(values)

    return out


def generate_cfd_demo_series(iteration, max_points=500, line_count=1):
    """
    Generate CFD-like residual histories for demo mode.

    Kept available as an optional demo kind, but the default demo remains sine.
    """
    line_count = max(1, min(len(MARKERS), line_count))
    max_points = max(1, max_points)
    iteration = max(1, iteration)

    start_iter = max(1, iteration - max_points + 1)
    end_iter = iteration

    x_values = list(range(start_iter, end_iter + 1))
    out = []

    for j in range(line_count):
        initial = 1.0e-2 * (1.0 + 0.35 * j)
        floor = 1.0e-6 * (1.0 + 0.25 * j)
        decay = 0.018 + 0.003 * j
        wobble_amp = 0.10 + 0.02 * j
        wobble_freq = 0.12 + 0.015 * j
        phase_offset = 0.8 * j

        values = []

        for i in x_values:
            trend = initial * exp(-decay * i)
            wobble = 1.0 + wobble_amp * sin(i * wobble_freq + phase_offset)
            value = floor + trend * wobble

            if value <= 0.0:
                value = floor

            values.append(value)

        out.append(values)

    return out


def demo_generator_for_kind(kind):
    if kind == "cfd":
        return generate_cfd_demo_series
    return generate_demo_series


def demo_scale_for_kind(kind):
    if kind == "cfd":
        return "log"
    return "linear"


def demo_source_summary_for_kind(kind):
    if kind == "cfd":
        return "live CFD-like residuals"
    return "live sine waves"
