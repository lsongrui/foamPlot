from math import exp, sin, log10
from random import Random

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

    Characteristics:
    - all residuals start at 1.0
    - each line converges to a different residual floor
    - convergence is steep at first and progressively flattens
    - deterministic pseudo-random fluctuations are added
    - no third-party dependencies
    """
    line_count = max(1, min(len(MARKERS), line_count))
    max_points = max(1, max_points)
    iteration = max(1, iteration)

    start_iter = max(1, iteration - max_points + 1)
    end_iter = iteration

    x_values = list(range(start_iter, end_iter + 1))
    out = []

    # Fixed floors for typical CFD residual fields.
    # Extend/reuse safely if line_count exceeds this list.
    floor_pool = [
        1.0e-3,
        1.0e-2,
        2.0e-4,
        5.0e-2,
        3.0e-2,
    ]

    for j in range(line_count):
        floor = floor_pool[j % len(floor_pool)]

        # Deterministic per-line random generator.
        # This freezes the "personality" of each residual curve.
        rng = Random(1000 + j)

        # Line-specific convergence parameters.
        # power < 1 gives steep early decay and slow late convergence.
        power = 0.58 + 0.06 * rng.random()
        rate = 0.20 + 0.08 * rng.random()

        floor_log = -log10(floor)

        scale_factor = 10.0 ** (-(floor_log - 3.0) * 0.50)
        scale_factor = max(0.005, min(1.0, scale_factor))

        # Mild line-specific fluctuation settings.
        wave_amp = (0.04 + 0.03 * rng.random()) * scale_factor
        # wave_amp = 0.04 + 0.03 * rng.random()
        wave_freq = 0.08 + 0.04 * rng.random()
        wave_phase = 6.283185307179586 * rng.random()

        values = []

        for i in x_values:
            if i == 1:
                values.append(1.0)
                continue

            # Base convergence: starts at 1, approaches floor.
            progress = i - 1
            fast_iters = 20

            fast_rate = 0.22 + 0.06 * rng.random()
            slow_rate = 0.035 + 0.015 * rng.random()
            power = 0.55 + 0.08 * rng.random()

            early_progress = min(progress, fast_iters)
            late_progress = max(progress - fast_iters, 0)

            fast_drop = exp(-fast_rate * early_progress)
            slow_drop = exp(-slow_rate * (late_progress ** power))

            base = floor + (1.0 - floor) * fast_drop * slow_drop

            # Noise is stronger early and weaker near convergence.
            # This avoids unrealistically large oscillations near the floor.
            relative_position = log10(max(base / floor, 1.0))
            noise_strength = min(0.12, 0.015 + 0.025 * relative_position)* scale_factor

            # Deterministic pseudo-random jitter for this exact point.
            # The seed depends on line and iteration, so the result is stable
            # even when the rolling window moves.
            point_rng = Random(100000 * j + i)
            random_jitter = 1.0 + noise_strength * (2.0 * point_rng.random() - 1.0)

            # Smooth low-frequency residual wobble.
            wave = 1.0 + wave_amp * exp(-0.002 * progress) * \
                __import__("math").sin(wave_freq * progress + wave_phase)

            value = base * random_jitter * wave

            # Never allow values below the intended floor.
            # The residual may fluctuate above the floor but should not cross it.
            if value < floor:
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
