import sys

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


def enter_alt_screen():
    sys.stdout.write("\033[?1049h")
    sys.stdout.write("\033[?25l")
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def exit_alt_screen():
    sys.stdout.write("\033[?25h")
    sys.stdout.write("\033[?1049l")
    sys.stdout.flush()