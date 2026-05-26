from .model import LEFT_AXIS_SEPARATOR, RIGHT_AXIS_SEPARATOR
from .text import FLOAT_RE, colorize, format_residual, strip_ansi
from .transform import value_from_plot_y

# -----------------------------------------------------------------------------
# Plotille text-output detection
# -----------------------------------------------------------------------------

def contains_plot_glyphs(s):
    """
    Return True if a line appears to contain rendered plot glyphs.

    This protects real plot rows from being mistaken for x tick-label rows.
    """
    for ch in s:
        code = ord(ch)

        # Braille block used heavily by plotille.
        if 0x2800 <= code <= 0x28FF:
            return True

        # Extra glyphs commonly seen in plotille output.
        if ch in "⠁⠂⠄⡀⢀⣀⣄⣆⣇⣧⣷⣿⡄⡆⡇⢇⢣⢱⠈⠉⠊⠔⠘⠙⠣⠢⠸⡍":
            return True

    return False


def is_x_axis_line(line):
    """
    Detect plotille x-axis and x-tick rows.

    Handles narrow-width leaks such as:
        | 1
        | 1        10.444444
    """
    clean = strip_ansi(line)

    if "(X)" in clean:
        return True

    # Horizontal x-axis ruler row.
    if "─" in clean or "┼" in clean or "┴" in clean:
        return True

    # x tick-label row.
    if "|" in clean and "│" not in clean and LEFT_AXIS_SEPARATOR not in clean:
        nums = FLOAT_RE.findall(clean)

        if len(nums) >= 1 and not contains_plot_glyphs(clean):
            return True

    return False


def remove_trailing_x_axis_block(lines):
    """
    Remove plotille's bottom x-axis block after fig.show().

    This is more reliable than detecting x labels globally, because narrow plots
    may emit only one tick label.
    """
    out = list(lines)

    while out:
        clean = strip_ansi(out[-1])

        if "(X)" in clean:
            out.pop()
            continue

        if "─" in clean or "┼" in clean or "┴" in clean:
            out.pop()
            continue

        if "|" in clean and LEFT_AXIS_SEPARATOR not in clean:
            nums = FLOAT_RE.findall(clean)

            if nums and not contains_plot_glyphs(clean):
                out.pop()
                continue

        break

    return out


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
    lines = remove_trailing_x_axis_block(lines)  # main x-axis removal
    lines = remove_plotille_x_axis(lines)        # backup filter

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

