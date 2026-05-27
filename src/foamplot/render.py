import os

import plotille

from .model import RESET
from .postprocess import postprocess_chart_lines
from .text import colorize, strip_ansi
from .transform import make_series_list
from .viewport import prepare_visible_series

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
    fig.width = max(2, width)
    fig.height = height
    fig.color_mode = "byte"

    max_n = max(len(series.plot_data) for series in series_list)

    # Use 1..n instead of 0..n-1. This keeps plotille's internal x=0 y-axis
    # outside the visible plot.
    #
    # plotille requires min_ < max_. During the first live/demo frame there may
    # be only one point, so force the x-range to 1..2 until at least two points exist.
    xmax = max(2, max_n)

    fig.set_x_limits(min_=1, max_=xmax)
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
# Frame construction
# -----------------------------------------------------------------------------

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
                "max={mx:>11.4e}  min={mn:>11.4e}  latest={latest:>11.4e}"
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
                "max=          -  min=          -  latest=          -"
            ).format(
                name=name,
                name_width=name_width + 2 + len(series.ansi_color) + len(RESET),
                source=source_name,
                source_width=source_width,
            )

        lines.append(line)

    return lines


def format_plot_header_line(scale, start_index, end_index,
                            visible_points, max_points,
                            plot_width, requested_width):
    return (
        "scale: {scale}, range: {start}-{end}, "
        "points: {points}/{max_points}, width: {width}/{requested_width}"
    ).format(
        scale=scale,
        start=start_index,
        end=end_index,
        points=visible_points,
        max_points=max_points,
        width=plot_width,
        requested_width=requested_width,
    )


def build_frame(raw_series_list, names, sources, title, height, source_summary,
                plot_width, scale, visible_points, max_points,
                requested_width, start_index, end_index,
                show_stop_hint=False):
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
            start_index=start_index,
            end_index=end_index,
            visible_points=visible_points,
            max_points=max_points,
            plot_width=plot_width,
            requested_width=requested_width,
        ),
        "series:",
    ]

    header.extend(format_series_status_lines(series_list))

    if show_stop_hint:
        header.append("Press Ctrl+C to stop")

    header.append("")

    return header + chart_lines


def build_frame_from_raw(raw_series_list, names, sources, title, height,
                         source_summary, requested_width, max_points, scale,
                         total_points=None, show_stop_hint=False):
    """
    Single shared frame path for static, follow, and demo modes.

    total_points:
        Total logical point count before the visible window is cut.

        Demo mode should pass the current iteration here.

        File mode can omit it for now because the current file reader only reads
        the tailed window, not the full file count.
    """
    visible_series_list, plot_width, visible_points = prepare_visible_series(
        raw_series_list=raw_series_list,
        max_points=max_points,
        requested_width=requested_width,
    )

    if total_points is None:
        total_points = visible_points

    if visible_points > 0:
        end_index = total_points
        start_index = max(1, end_index - visible_points + 1)
    else:
        start_index = 0
        end_index = 0

    return build_frame(
        raw_series_list=visible_series_list,
        names=names,
        sources=sources,
        title=title,
        height=height,
        source_summary=source_summary,
        plot_width=plot_width,
        scale=scale,
        visible_points=visible_points,
        max_points=max_points,
        requested_width=requested_width,
        start_index=start_index,
        end_index=end_index,
        show_stop_hint=show_stop_hint,
    )
