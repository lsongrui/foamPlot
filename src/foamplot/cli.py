#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import time
from math import log10, sin

import plotille


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FLOAT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")

RESET = "\033[0m"

LEFT_AXIS_SEPARATOR = "├"
RIGHT_AXIS_SEPARATOR = "┤"

ANSI_COLORS = [
    "\033[91m",  # red
    "\033[92m",  # green
    "\033[93m",  # yellow
    "\033[94m",  # blue
    "\033[95m",  # magenta
]

# plotille byte-color IDs. These are intentionally simple and distinct.
PLOTILLE_COLORS = [196, 46, 226, 33, 201]

MARKERS = ["●", "◆", "■", "▲", "✦"]


class Series(object):
    """Python-3.5-compatible replacement for a dataclass."""

    def __init__(self, name, source, raw_data, plot_data, label_data,
                 ansi_color, plotille_color, marker):
        self.name = name
        self.source = source
        self.raw_data = raw_data
        self.plot_data = plot_data
        self.label_data = label_data
        self.ansi_color = ansi_color
        self.plotille_color = plotille_color
        self.marker = marker


# -----------------------------------------------------------------------------
# Basic text helpers
# -----------------------------------------------------------------------------

def strip_ansi(s):
    return ANSI_RE.sub("", s)


def colorize(s, color):
    return color + s + RESET


def format_residual(v):
    """Fixed-width scientific notation for axis labels."""
    return "{:9.2e}".format(v)


# -----------------------------------------------------------------------------
# Input data
# -----------------------------------------------------------------------------

def extract_numbers(line):
    values = []

    for match in FLOAT_RE.findall(strip_ansi(line)):
        try:
            values.append(float(match))
        except ValueError:
            pass

    return values


def value_from_numeric_tokens(tokens, column=None):
    if not tokens:
        return None

    try:
        if column is None:
            return tokens[-1]
        return tokens[column]
    except IndexError:
        return None


def parse_names(names_arg, count, sources=None):
    if names_arg is not None and names_arg.strip() != "":
        names = [item.strip() for item in names_arg.split(",") if item.strip()]
    else:
        names = []

    if sources is None:
        sources = []

    while len(names) < count:
        i = len(names)
        if i < len(sources):
            names.append(os.path.basename(sources[i]))
        else:
            names.append("s{}".format(i + 1))

    return names[:count]


def tail_values_from_file(path, max_points, column=None):
    """Read the last max_points lines from one file and extract one numeric token per line."""
    values = []

    if max_points <= 0:
        return values

    try:
        proc = subprocess.Popen(
            ["tail", "-n", str(max_points), path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )

        if proc.stdout is None:
            return values

        for line in proc.stdout:
            tokens = extract_numbers(line)
            value = value_from_numeric_tokens(tokens, column=column)
            if value is not None:
                values.append(value)

        proc.wait()

    except Exception:
        return values

    return values


def tail_series_from_files(paths, max_points, column=None):
    """Return one raw data array per file path."""
    return [
        tail_values_from_file(path, max_points=max_points, column=column)
        for path in paths
    ]


def generate_demo_series(width=100, phase=0.0, line_count=1):
    """Generate up to five sine-like demo series."""
    line_count = max(1, min(5, line_count))
    out = []

    for j in range(line_count):
        amplitude = 3.0 - 0.35 * j
        phase_offset = 0.75 * j
        vertical_offset = 0.15 * j
        frequency = 0.1 + 0.015 * j

        out.append([
            amplitude * sin(i * frequency + phase + phase_offset) + vertical_offset
            for i in range(width)
        ])

    return out


# -----------------------------------------------------------------------------
# Data preparation for plotting
# -----------------------------------------------------------------------------

def downsample_minmax(data, max_points):
    """Downsample to at most max_points while preserving spikes."""
    if max_points <= 0 or len(data) <= max_points:
        return data

    if max_points < 2:
        return [data[-1]]

    bucket_count = max_points // 2
    bucket_size = float(len(data)) / float(bucket_count)

    out = []

    for i in range(bucket_count):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)

        if end <= start:
            end = start + 1

        bucket = data[start:end]
        if not bucket:
            continue

        mn = min(bucket)
        mx = max(bucket)

        if bucket[0] <= bucket[-1]:
            out.extend([mn, mx])
        else:
            out.extend([mx, mn])

    return out[:max_points]


def transform_data_with_labels(data, scale):
    """
    Return two aligned arrays:

    plot_data:
        Values passed to plotille.
        For log scale, these are log10(value).

    label_data:
        Original values used for axis labels and endpoint markers.
    """
    if scale == "linear":
        return data, data

    if scale == "log":
        plot_data = []
        label_data = []

        for v in data:
            if v > 0:
                plot_data.append(log10(v))
                label_data.append(v)

        return plot_data, label_data

    raise ValueError("Unknown scale: {}".format(scale))


def value_from_plot_y(y, scale):
    """Convert a plot-space y value back to displayed/original value."""
    if scale == "log":
        return 10 ** y
    return y


def make_series_list(raw_series_list, names, sources, plot_width, scale):
    series_list = []

    for i, raw_data in enumerate(raw_series_list):
        sampled_data = downsample_minmax(raw_data, plot_width)
        plot_data, label_data = transform_data_with_labels(sampled_data, scale)

        source = sources[i] if i < len(sources) else ""
        name = names[i] if i < len(names) else "s{}".format(i + 1)

        series_list.append(
            Series(
                name=name,
                source=source,
                raw_data=raw_data,
                plot_data=plot_data,
                label_data=label_data,
                ansi_color=ANSI_COLORS[i % len(ANSI_COLORS)],
                plotille_color=PLOTILLE_COLORS[i % len(PLOTILLE_COLORS)],
                marker=MARKERS[i % len(MARKERS)],
            )
        )

    return series_list


# -----------------------------------------------------------------------------
# Plotille text-output detection
# -----------------------------------------------------------------------------

def is_x_axis_line(line):
    """Detect plotille x-axis and x-tick rows."""
    clean = strip_ansi(line)

    if "(X)" in clean:
        return True

    # Tick-label row after x-axis. It usually has several numbers and no
    # Unicode vertical plot border.
    if "|" in clean and "│" not in clean and LEFT_AXIS_SEPARATOR not in clean:
        nums = FLOAT_RE.findall(clean)
        if len(nums) >= 3:
            return True

    return False


def is_axis_header_line(line):
    """Detect plotille's '(Y) ^' header line."""
    clean = strip_ansi(line)
    return "(Y)" in clean and "^" in clean


def is_plot_row(line):
    """Detect rows that contain actual plot canvas content."""
    clean = strip_ansi(line)

    if is_axis_header_line(clean):
        return False

    if is_x_axis_line(clean):
        return False

    return "|" in clean or "│" in clean or LEFT_AXIS_SEPARATOR in clean


def remove_plotille_headers(lines):
    return [line for line in lines if not is_axis_header_line(line)]


def remove_plotille_x_axis(lines):
    return [line for line in lines if not is_x_axis_line(line)]


# -----------------------------------------------------------------------------
# Plot post-processing layout helpers
# -----------------------------------------------------------------------------

def get_plot_rows(lines):
    return [i for i, line in enumerate(lines) if is_plot_row(line)]


def find_left_separator(line):
    """Find the left axis separator, before or after restyling."""
    for sep in (LEFT_AXIS_SEPARATOR, "|"):
        pos = line.find(sep)
        if pos >= 0:
            return pos
    return -1


def row_for_plot_value(plot_rows, ymin, ymax, value):
    """Map a plot-space y value to a rendered text row."""
    top = plot_rows[0]
    bottom = plot_rows[-1]
    span = max(1, bottom - top)

    if ymax == ymin:
        return top + span // 2

    row = top + int(round((ymax - value) / (ymax - ymin) * span))
    return max(top, min(bottom, row))


def plot_value_for_row(plot_rows, ymin, ymax, row):
    """Map a rendered text row back to a plot-space y value."""
    top = plot_rows[0]
    bottom = plot_rows[-1]
    span = max(1, bottom - top)

    t = float(row - top) / float(span)
    return ymax - t * (ymax - ymin)


def pad_lines_to_same_width(lines):
    """Pad lines using visible width, ignoring ANSI escape codes."""
    if not lines:
        return lines

    width = max(len(strip_ansi(line)) for line in lines)

    return [
        line + " " * (width - len(strip_ansi(line)))
        for line in lines
    ]


# -----------------------------------------------------------------------------
# Endpoint grouping
# -----------------------------------------------------------------------------

def group_series_endpoints_by_row(series_list, plot_rows, ymin, ymax, which):
    """
    Group first or last series endpoints by rendered row.

    which:
        'first' or 'last'
    """
    grouped = {}

    for series in series_list:
        if not series.plot_data or not series.label_data:
            continue

        if which == "first":
            plot_value = series.plot_data[0]
            label_value = series.label_data[0]
        elif which == "last":
            plot_value = series.plot_data[-1]
            label_value = series.label_data[-1]
        else:
            raise ValueError("Unknown endpoint type: {}".format(which))

        row = row_for_plot_value(plot_rows, ymin, ymax, plot_value)

        grouped.setdefault(row, []).append({
            "series": series,
            "plot_value": plot_value,
            "label_value": label_value,
        })

    return grouped


# -----------------------------------------------------------------------------
# Plot post-processing stages
# -----------------------------------------------------------------------------

def replace_left_axis_values(lines, plot_rows, ymin, ymax, scale):
    """
    Replace plotille's native left y-axis labels with displayed values.

    In log scale, plotille's native left labels are log10(value). This function
    writes original values instead. In linear scale, it regenerates labels in the
    same scientific notation for visual consistency.
    """
    if not plot_rows:
        return lines

    out = []

    for i, line in enumerate(lines):
        if i not in plot_rows:
            out.append(line)
            continue

        sep = find_left_separator(line)
        if sep < 0:
            out.append(line)
            continue

        left_field = line[:sep]
        rest = line[sep:]

        row_y = plot_value_for_row(plot_rows, ymin, ymax, i)
        row_value = value_from_plot_y(row_y, scale)

        # Preserve one trailing space before the left separator.
        label_width = max(1, len(left_field) - 1)
        new_left_field = "{:>{width}.2e} ".format(
            row_value,
            width=label_width,
        )

        out.append(new_left_field + rest)

    return out


def replace_left_axis_separator(lines, plot_rows):
    """Replace plotille's left '|' separator with '├' on plot rows."""
    if not plot_rows:
        return lines

    out = []

    for i, line in enumerate(lines):
        if i not in plot_rows:
            out.append(line)
            continue

        sep = line.find("|")
        if sep < 0:
            out.append(line)
            continue

        out.append(line[:sep] + LEFT_AXIS_SEPARATOR + line[sep + 1:])

    return out


def add_left_start_markers(lines, left_groups):
    """
    Mark first values on the left axis.

    Collision policy:
        If several series start on the same rendered row, show all their colored
        markers before the left separator, but keep only one axis value.

    Example:
        '  4.56e-05 ├ ...'
    becomes:
        '  4.56e-05●◆├ ...'
    """
    if not left_groups:
        return lines

    out = []

    for i, line in enumerate(lines):
        group = left_groups.get(i)
        if not group:
            out.append(line)
            continue

        sep = find_left_separator(line)
        if sep < 0:
            out.append(line)
            continue

        left_field = line[:sep]
        rest = line[sep:]

        markers = "".join(
            colorize(item["series"].marker, item["series"].ansi_color)
            for item in group
        )
        marker_width = len(group)

        # Use trailing spaces before the separator first. If there are not
        # enough, truncate the right edge of the label field to keep the
        # separator column fixed.
        if len(left_field) > marker_width:
            label_part = left_field[:-marker_width]
        else:
            label_part = ""

        out.append(label_part + markers + rest)

    return out


def add_right_axis(lines, plot_rows, ymin, ymax, scale, right_groups):
    """
    Add a right-side axis in displayed/original values.

    Collision policy:
        If several latest values land on the same rendered row, replace the
        normal right-axis value with a list of all current values.

    Example:
        ┤ ●3.27e-05 ◆4.10e-05 ■2.80e-05
    """
    if not plot_rows:
        return lines

    lines = pad_lines_to_same_width(lines)
    out = []

    for i, line in enumerate(lines):
        if i not in plot_rows:
            out.append(line)
            continue

        group = right_groups.get(i)

        if group:
            labels = []
            for item in group:
                series = item["series"]
                label_value = item["label_value"]
                label = series.marker + format_residual(label_value).strip()
                labels.append(colorize(label, series.ansi_color))

            suffix = " {} {}".format(
                RIGHT_AXIS_SEPARATOR,
                " ".join(labels),
            )
        else:
            row_y = plot_value_for_row(plot_rows, ymin, ymax, i)
            row_value = value_from_plot_y(row_y, scale)
            suffix = " {} {}".format(
                RIGHT_AXIS_SEPARATOR,
                format_residual(row_value),
            )

        out.append(line + suffix)

    return out


def postprocess_chart_lines(lines, ymin, ymax, scale, series_list):
    """
    All plotille text-output customization lives here.

    Pipeline:
        1. remove plotille header/x-axis clutter
        2. compute plot rows once
        3. group first/latest endpoints by row
        4. replace left-axis labels with displayed/original values
        5. restyle the left separator as '├'
        6. mark start values on the left axis
        7. add custom right axis and latest-value labels
    """
    lines = remove_plotille_headers(lines)
    lines = remove_plotille_x_axis(lines)

    plot_rows = get_plot_rows(lines)
    if not plot_rows:
        return lines

    left_groups = group_series_endpoints_by_row(
        series_list=series_list,
        plot_rows=plot_rows,
        ymin=ymin,
        ymax=ymax,
        which="first",
    )

    right_groups = group_series_endpoints_by_row(
        series_list=series_list,
        plot_rows=plot_rows,
        ymin=ymin,
        ymax=ymax,
        which="last",
    )

    lines = replace_left_axis_values(
        lines=lines,
        plot_rows=plot_rows,
        ymin=ymin,
        ymax=ymax,
        scale=scale,
    )

    lines = replace_left_axis_separator(
        lines=lines,
        plot_rows=plot_rows,
    )

    lines = add_left_start_markers(
        lines=lines,
        left_groups=left_groups,
    )

    lines = add_right_axis(
        lines=lines,
        plot_rows=plot_rows,
        ymin=ymin,
        ymax=ymax,
        scale=scale,
        right_groups=right_groups,
    )

    return lines


# -----------------------------------------------------------------------------
# Chart rendering
# -----------------------------------------------------------------------------

def nonempty_series(series_list):
    return [s for s in series_list if s.plot_data and s.label_data]


def render_chart(series_list, height, width, scale):
    series_list = nonempty_series(series_list)

    if not series_list:
        return ["No numeric data found."]

    all_plot_values = [
        value
        for series in series_list
        for value in series.plot_data
    ]

    if not all_plot_values:
        return ["No numeric data found."]

    ymin = min(all_plot_values)
    ymax = max(all_plot_values)

    if ymin == ymax:
        ymin -= 1.0
        ymax += 1.0

    fig = plotille.Figure()
    fig.width = width
    fig.height = height
    fig.color_mode = "byte"

    max_n = max(len(series.plot_data) for series in series_list)

    # Use 1..n instead of 0..n-1. This keeps plotille's internal x=0 y-axis
    # outside the visible plot.
    fig.set_x_limits(min_=1, max_=max(1, max_n))
    fig.set_y_limits(min_=ymin, max_=ymax)

    for series in series_list:
        n = len(series.plot_data)
        x = list(range(1, n + 1))

        try:
            fig.plot(
                x,
                series.plot_data,
                label=series.name,
                lc=series.plotille_color,
            )
        except TypeError:
            # Fallback for plotille versions that do not accept lc.
            fig.plot(x, series.plot_data, label=series.name)

    return postprocess_chart_lines(
        lines=fig.show(legend=False).splitlines(),
        ymin=ymin,
        ymax=ymax,
        scale=scale,
        series_list=series_list,
    )


# -----------------------------------------------------------------------------
# Terminal drawing
# -----------------------------------------------------------------------------

def draw_frame(lines, previous_line_count):
    sys.stdout.write("\033[H")

    for line in lines:
        sys.stdout.write("\033[2K")
        sys.stdout.write(line)
        sys.stdout.write("\n")

    for _ in range(max(0, previous_line_count - len(lines))):
        sys.stdout.write("\033[2K")
        sys.stdout.write("\n")

    sys.stdout.flush()
    return len(lines)


# -----------------------------------------------------------------------------
# Frame construction and runtime modes
# -----------------------------------------------------------------------------

def format_legend(series_list):
    parts = []

    for series in series_list:
        marker_name = "{} {}".format(series.marker, series.name)
        parts.append(colorize(marker_name, series.ansi_color))

    return "series: " + "  ".join(parts)


def format_series_status_lines(series_list):
    if not series_list:
        return ["series: none"]

    name_width = max(len(strip_ansi(series.name)) for series in series_list)
    source_width = max(len(strip_ansi(os.path.basename(series.source))) for series in series_list)

    lines = []

    for series in series_list:
        source_name = os.path.basename(series.source) if series.source else "-"
        name = colorize("{} {}".format(series.marker, series.name), series.ansi_color)

        if series.raw_data:
            latest = series.raw_data[-1]
            mn = min(series.raw_data)
            mx = max(series.raw_data)
            line = (
                "  {name:<{name_width}}  file={source:<{source_width}}  "
                "min={mn:>11.4e}  max={mx:>11.4e}  latest={latest:>11.4e}"
            ).format(
                name=name,
                name_width=name_width + 2 + len(series.ansi_color) + len(RESET),
                source=source_name,
                source_width=source_width,
                mn=mn,
                mx=mx,
                latest=latest,
            )
        else:
            line = (
                "  {name:<{name_width}}  file={source:<{source_width}}  "
                "min=          -  max=          -  latest=          -"
            ).format(
                name=name,
                name_width=name_width + 2 + len(series.ansi_color) + len(RESET),
                source=source_name,
                source_width=source_width,
            )

        lines.append(line)

    return lines


def format_plot_header_line(scale, plot_width, points):
    return "scale: {scale}, points: {points}, width: {plot_width}".format(
        scale=scale,
        points=points,
        plot_width=plot_width,
    )


def build_frame(raw_series_list, names, sources, title, height, source_summary,
                plot_width, scale, points, show_stop_hint=False):
    series_list = make_series_list(
        raw_series_list=raw_series_list,
        names=names,
        sources=sources,
        plot_width=plot_width,
        scale=scale,
    )

    chart_lines = render_chart(
        series_list=series_list,
        height=height,
        width=plot_width,
        scale=scale,
    )

    header = [
        title,
        "source: {}".format(source_summary),
        format_plot_header_line(
            scale=scale,
            plot_width=plot_width,
            points=points,
        ),
        "series:",
    ]

    header.extend(format_series_status_lines(series_list))

    if show_stop_hint:
        header.append("Press Ctrl+C to stop")

    header.append("")

    return header + chart_lines


def get_file_frame(args):
    names = parse_names(args.names, len(args.files), sources=args.files)

    raw_series_list = tail_series_from_files(
        paths=args.files,
        max_points=args.points,
        column=args.column,
    )

    source_summary = ", ".join(args.files)

    return build_frame(
        raw_series_list=raw_series_list,
        names=names,
        sources=args.files,
        title="foamPlot plot",
        height=args.height,
        source_summary=source_summary,
        plot_width=args.plot_width,
        scale=args.scale,
        points=args.points,
        show_stop_hint=args.follow,
    )


def run_demo(args):
    phase = 0.0
    previous_line_count = 0

    demo_lines = max(1, min(5, args.demo_lines))
    names = ["demo{}".format(i + 1) for i in range(demo_lines)]
    sources = ["demo{}".format(i + 1) for i in range(demo_lines)]

    while True:
        raw_series_list = generate_demo_series(
            width=args.demo_points,
            phase=phase,
            line_count=demo_lines,
        )

        lines = build_frame(
            raw_series_list=raw_series_list,
            names=names,
            sources=sources,
            title="foamPlot demo",
            height=args.height,
            source_summary="demo sine waves",
            plot_width=args.plot_width,
            scale="linear",
            points=args.demo_points,
            show_stop_hint=True,
        )

        previous_line_count = draw_frame(lines, previous_line_count)

        phase += args.phase_step
        time.sleep(args.interval)


def run_file_plot(args):
    previous_line_count = 0

    while True:
        lines = get_file_frame(args)
        previous_line_count = draw_frame(lines, previous_line_count)

        if not args.follow:
            break

        time.sleep(args.interval)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot one or more foamLog-generated files in the terminal."
    )

    parser.add_argument("files", nargs="*", help="foamLog-generated file(s); each file becomes one line")
    parser.add_argument("-p", "--points", type=int, default=1000, help="latest lines to read from each file")
    parser.add_argument("-W", "--plot-width", type=int, default=120, help="plot width in terminal columns")
    parser.add_argument("-H", "--height", type=int, default=20, help="chart height")
    parser.add_argument("-i", "--interval", type=float, default=0.5, help="refresh interval in seconds")
    parser.add_argument("-c", "--column", type=int, default=None, help="zero-based numeric token; default: last number")
    parser.add_argument("--names", default=None, help="comma-separated series names, e.g. pa,p,ux")
    parser.add_argument("-f", "--follow", action="store_true", help="keep refreshing the file(s)")
    parser.add_argument("--demo", action="store_true", help="run sine-wave demo instead of reading files")
    parser.add_argument("--demo-points", type=int, default=100, help="number of demo points")
    parser.add_argument("--demo-lines", type=int, default=1, help="number of demo lines, 1 to 5")
    parser.add_argument("--phase-step", type=float, default=0.25, help="demo mode phase increment")
    parser.add_argument("--scale", choices=["log", "linear"], default="log", help="plot scale")

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.demo and not args.files:
        sys.stderr.write("Error: provide one or more foamLog files or use --demo.\n")
        sys.exit(2)

    if len(args.files) > len(MARKERS):
        sys.stderr.write(
            "Error: too many files. This script supports up to {} series.\n".format(len(MARKERS))
        )
        sys.exit(2)

    for path in args.files:
        if not os.path.exists(path):
            sys.stderr.write("Error: file not found: {}\n".format(path))
            sys.exit(1)

    use_alt_screen = args.demo or args.follow

    try:
        if use_alt_screen:
            sys.stdout.write("\033[?1049h")
            sys.stdout.write("\033[?25l")
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

        if args.demo:
            run_demo(args)
        elif args.follow:
            run_file_plot(args)
        else:
            for line in get_file_frame(args):
                print(line)

    except KeyboardInterrupt:
        pass

    finally:
        if use_alt_screen:
            sys.stdout.write("\033[?25h")
            sys.stdout.write("\033[?1049l")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
