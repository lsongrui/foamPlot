import re

from .model import RESET


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FLOAT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def strip_ansi(s):
    return ANSI_RE.sub("", s)


def colorize(s, color):
    return color + s + RESET


def format_residual(v):
    return "{:9.2e}".format(v)