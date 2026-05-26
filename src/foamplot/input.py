import os
import subprocess

from .text import FLOAT_RE, strip_ansi

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
