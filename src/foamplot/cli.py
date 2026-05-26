#!/usr/bin/env python3
import argparse
import os
import sys
import time

from .demo import (
    demo_generator_for_kind,
    demo_scale_for_kind,
    demo_source_summary_for_kind,
)
from .input import parse_names, tail_series_from_files
from .model import MARKERS
from .render import build_frame_from_raw
from .terminal import draw_frame, enter_alt_screen, exit_alt_screen

# -----------------------------------------------------------------------------
# Runtime modes
# -----------------------------------------------------------------------------

def get_file_frame(args):
    names = parse_names(args.names, len(args.files), sources=args.files)

    raw_series_list = tail_series_from_files(
        paths=args.files,
        max_points=args.points,
        column=args.column,
    )

    source_summary = ", ".join(args.files)

    return build_frame_from_raw(
        raw_series_list=raw_series_list,
        names=names,
        sources=args.files,
        title="foamPlot plot",
        height=args.height,
        source_summary=source_summary,
        requested_width=args.plot_width,
        max_points=args.points,
        scale=args.scale,
        show_stop_hint=args.follow,
    )


def run_demo(args):
    previous_line_count = 0
    iteration = 1

    demo_lines = max(1, min(len(MARKERS), args.demo_lines))
    names = ["demo{}".format(i + 1) for i in range(demo_lines)]
    sources = ["demo{}".format(i + 1) for i in range(demo_lines)]

    generator = demo_generator_for_kind(args.demo_kind)
    scale = demo_scale_for_kind(args.demo_kind)
    source_summary = demo_source_summary_for_kind(args.demo_kind)

    while True:
        raw_series_list = generator(
            iteration=iteration,
            max_points=args.demo_points,
            line_count=demo_lines,
        )

        lines = build_frame_from_raw(
            raw_series_list=raw_series_list,
            names=names,
            sources=sources,
            title="foamPlot demo",
            height=args.height,
            source_summary=source_summary,
            requested_width=args.plot_width,
            max_points=args.demo_points,
            scale=scale,
            total_points=iteration,
            show_stop_hint=True,
        )

        previous_line_count = draw_frame(lines, previous_line_count)

        iteration += 1
        time.sleep(args.interval)


def run_file_plot(args):
    previous_line_count = 0

    while True:
        lines = get_file_frame(args)

        if args.follow:
            previous_line_count = draw_frame(lines, previous_line_count)
        else:
            for line in lines:
                print(line)

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

    parser.add_argument(
        "files",
        nargs="*",
        help="foamLog-generated file(s); each file becomes one line",
    )
    parser.add_argument(
        "-p",
        "--points",
        type=int,
        default=1000,
        help="latest lines to read from each file",
    )
    parser.add_argument(
        "-W",
        "--plot-width",
        type=int,
        default=100,
        help="maximum plot width in terminal columns",
    )
    parser.add_argument(
        "-H",
        "--height",
        type=int,
        default=20,
        help="chart height",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0.5,
        help="refresh interval in seconds",
    )
    parser.add_argument(
        "-c",
        "--column",
        type=int,
        default=None,
        help="zero-based numeric token; default: last number",
    )
    parser.add_argument(
        "--names",
        default=None,
        help="comma-separated series names, e.g. pa,p,ux",
    )
    parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="keep refreshing the file(s)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run demo instead of reading files",
    )
    parser.add_argument(
        "--demo-kind",
        choices=["sine", "cfd"],
        default="sine",
        help="demo data type",
    )
    parser.add_argument(
        "--demo-points",
        type=int,
        default=150,
        help="maximum retained demo points before the live window starts scrolling",
    )
    parser.add_argument(
        "--demo-lines",
        type=int,
        default=3,
        help="number of demo lines, 1 to 5",
    )
    parser.add_argument(
        "--scale",
        choices=["log", "linear"],
        default="log",
        help="plot scale for file mode",
    )

    return parser.parse_args()


def validate_args(args):
    if args.points <= 0:
        sys.stderr.write("Error: --points must be greater than 0.\n")
        sys.exit(2)

    if args.demo_points <= 0:
        sys.stderr.write("Error: --demo-points must be greater than 0.\n")
        sys.exit(2)

    if args.plot_width <= 0:
        sys.stderr.write("Error: --plot-width must be greater than 0.\n")
        sys.exit(2)

    if args.height <= 0:
        sys.stderr.write("Error: --height must be greater than 0.\n")
        sys.exit(2)

    if args.interval < 0:
        sys.stderr.write("Error: --interval must be non-negative.\n")
        sys.exit(2)

    if not args.demo and not args.files:
        sys.stderr.write("Error: provide one or more foamLog files or use --demo.\n")
        sys.exit(2)

    if len(args.files) > len(MARKERS):
        sys.stderr.write(
            "Error: too many files. This script supports up to {} series.\n".format(len(MARKERS))
        )
        sys.exit(2)

    if args.demo_lines > len(MARKERS):
        sys.stderr.write(
            "Error: --demo-lines supports up to {} series.\n".format(len(MARKERS))
        )
        sys.exit(2)

    for path in args.files:
        if not os.path.exists(path):
            sys.stderr.write("Error: file not found: {}\n".format(path))
            sys.exit(1)

def main():
    args = parse_args()
    validate_args(args)

    use_alt_screen = args.demo or args.follow

    try:
        if use_alt_screen:
            enter_alt_screen()

        if args.demo:
            run_demo(args)
        else:
            run_file_plot(args)

    except KeyboardInterrupt:
        pass

    finally:
        if use_alt_screen:
            exit_alt_screen()


if __name__ == "__main__":
    main()