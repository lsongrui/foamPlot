RESET = "\033[0m"

LEFT_AXIS_SEPARATOR = "├"
RIGHT_AXIS_SEPARATOR = "┤"

ANSI_COLORS = [
    "\033[91m",
    "\033[92m",
    "\033[93m",
    "\033[94m",
    "\033[95m",
]

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