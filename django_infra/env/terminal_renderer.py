import os
import shutil
import sys
import typing


class FixedHeightTerminal:
    """Consume and display IO into a fixed height terminal window."""

    def __init__(self, max_height: int = 5, display_output=True):
        self.display_output = display_output
        self.max_height = max_height
        self.buffer: typing.List[str] = []
        self.max_buffer_length = 100
        self.previous_lines: int = 0
        self.log_style = "\033[34m\033[2m"  # Blue + dim
        self.reset_style = "\033[0m"
        try:
            self.display_width = os.get_terminal_size().columns
        except Exception:
            self.display_width = shutil.get_terminal_size().columns
        self.display_width = min(self.display_width, 80)

    def display(self) -> None:
        """Display buffer contents or clean up the terminal space"""

        display_lines = self.buffer[-self.max_height :]
        for line in display_lines:
            self.std_write(f"{self.log_style}{line}{self.reset_style}\n")
        sys.stdout.flush()

    def collect_output(self, read_func):
        """Collects & displays output to buffer by consuming read_func."""
        lines = read_func()
        if isinstance(lines, str):
            lines = [lines]
        while lines:
            line = lines.pop()
            line = line.replace("\n", "")
            self.add_line(line)
            if self.display_output:
                self.display()
                self.cleanup()
            line = read_func()
            if not line:
                break
        sys.stdout.flush()

    def print_buffer(self):
        """prints buffer full buffer to screen"""
        max_height = self.max_height
        self.max_height = len(self.buffer)
        self.display()
        self.max_height = max_height
        sys.stdout.flush()

    @staticmethod
    def std_write(text):
        sys.stdout.write(text)

    def add_line(self, line: str) -> None:
        """Add a line to the buffer."""
        line = line[: self.display_width - 1]
        line = line + " " * (self.display_width - len(line))
        self.buffer.append(line)
        del self.buffer[: -self.max_buffer_length]

    def cleanup(self) -> None:
        """Clear the terminal space used by the widget"""
        if not self.buffer:
            return
        cleanup_count = min(len(self.buffer), self.max_height)
        self.std_write(f"\033[{cleanup_count}F")
