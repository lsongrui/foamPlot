from math import log10

from .model import ANSI_COLORS, MARKERS, PLOTILLE_COLORS, Series

# -----------------------------------------------------------------------------
# Data preparation for plotting
# -----------------------------------------------------------------------------

def downsample_minmax(data, max_points):
    """Downsample to at most max_points while preserving spikes."""
    if max_points <= 0 or len(data) <= max_points:
        return data

    if max_points < 2:
        return [data[-1]]

    bucket_count = max(1, max_points // 2)
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
    Return two aligned arrays.

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
