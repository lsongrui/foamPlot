# -----------------------------------------------------------------------------
# Shared viewport/window logic
# -----------------------------------------------------------------------------

def prepare_visible_series(raw_series_list, max_points, requested_width):
    """
    Shared viewport logic for static, follow, and demo modes.

    Rules:
        1. Keep only the latest max_points values.
        2. Let plot width grow while visible points < requested_width.
        3. Never return a width smaller than 2 because plotille requires x_min < x_max.

    Examples:
        values=1,   requested_width=100 -> plot_width=2
        values=50,  requested_width=100 -> plot_width=50
        values=200, requested_width=100 -> plot_width=100
    """
    max_points = max(1, max_points)
    requested_width = max(2, requested_width)

    visible_series_list = []

    for values in raw_series_list:
        visible_series_list.append(values[-max_points:])

    visible_points = 0
    for values in visible_series_list:
        visible_points = max(visible_points, len(values))

    plot_width = max(2, min(requested_width, visible_points))

    return visible_series_list, plot_width, visible_points
