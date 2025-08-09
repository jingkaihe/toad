from __future__ import annotations
from dataclasses import dataclass, field
import os
from typing import NamedTuple


from textual.geometry import Size
from textual.cache import LRUCache

from textual.content import Content
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.visual import Visual
from textual.selection import Selection


from toad.ansi import ANSIStream


class LineFold(NamedTuple):
    line_no: int
    """The line number."""

    line_offset: int
    """The index of the folded line."""

    offset: int
    """The offset within the original line."""

    content: Content
    """The content."""


@dataclass
class LineRecord:
    content: Content
    folds: list[LineFold] = field(default_factory=list)
    updates: int = 0


class ANSILog(ScrollView, can_focus=True):
    DEFAULT_CSS = """
    ANSILog {
        overflow: auto auto;
        scrollbar-gutter: stable;
        height: 1fr;        
    }
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        minimum_terminal_width: int = -1,
    ):
        self.line_start = 0
        self.cursor_line = 0
        self.cursor_offset = 0
        self.minimum_terminal_width = minimum_terminal_width

        self._line_count = 0

        # Sequence of lines
        self._lines: list[LineRecord] = []

        # Maps the line index on to the folder lines index
        self._line_to_fold: list[int] = []

        # List of folded lines, one per line in the widget
        self._folded_lines: list[LineFold] = []

        # Cache of segments
        self._render_line_cache: LRUCache[tuple, Strip] = LRUCache(1000)

        # ANSI stream
        self._ansi_stream = ANSIStream()

        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

    @property
    def _width(self) -> int:
        if self.minimum_terminal_width == -1 and self.scrollable_content_region.width:
            self.minimum_terminal_width = self.scrollable_content_region.width
        width = max(self.minimum_terminal_width, self.scrollable_content_region.width)
        return width

    @property
    def line_count(self) -> int:
        return self._line_count

    @property
    def last_line_index(self) -> int:
        return self._line_count - 1

    def notify_style_update(self) -> None:
        self._clear_caches()
        self._reflow()

    def allow_select(self) -> bool:
        return True

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Get the text under the selection.

        Args:
            selection: Selection information.

        Returns:
            Tuple of extracted text and ending (typically "\n" or " "), or `None` if no text could be extracted.
        """
        text = "\n".join(line_record.content.plain for line_record in self._lines)
        return selection.extract(text), "\n"

    def _clear_caches(self) -> None:
        self._render_line_cache.clear()

    def on_resize(self) -> None:
        self._clear_caches()
        self._reflow()

    def clear(self) -> None:
        self._lines.clear()
        self._folded_lines.clear()
        self._clear_caches()
        self.line_start = 0
        self.refresh()

    def write(self, text: str) -> None:
        if not text:
            return
        for delta_x, delta_y, content in self._ansi_stream.feed(text):
            while self.cursor_line >= self.last_line_index:
                self.add_line(Content())

            line = self._lines[self.cursor_line].content
            if content:
                if self.cursor_offset == len(line):
                    self.update_line(self.cursor_line, content)
                else:
                    updated_line = Content("").join(
                        [
                            line[: self.cursor_offset],
                            content,
                            line[self.cursor_offset + len(content) :],
                        ]
                    )
                    self.update_line(self.cursor_line, updated_line)

            self.cursor_line += delta_y
            self.cursor_offset += delta_x

    def _fold_line(self, line_no: int, line: Content, width: int) -> list[LineFold]:
        line_length = line.cell_length
        divide_offsets = list(range(width, line_length, width))
        folded_line = line.divide(divide_offsets)
        offsets = [0, *divide_offsets]
        return [
            LineFold(line_no, line_offset, offset, line)
            for line_offset, (offset, line) in enumerate(zip(offsets, folded_line))
        ]

    def _reflow(self) -> None:
        width = self._width
        if not width:
            self._clear_caches()
            return

        folded_lines = self._folded_lines = []
        folded_lines.clear()
        self._line_to_fold.clear()
        for line_no, line in enumerate(self._lines):
            line.folds[:] = self._fold_line(line_no, line.content, width)
            self._line_to_fold.append(len(self._folded_lines))
            self._folded_lines.extend(line.folds)

        self.virtual_size = Size(width, len(self._folded_lines))

    def add_line(self, content: Content) -> None:
        line_no = self._line_count
        self._line_count += 1
        line_record = LineRecord(
            content, self._fold_line(line_no, content, self._width)
        )
        self._lines.append(line_record)
        width = self._width

        if not width:
            return

        folds = line_record.folds
        self._line_to_fold.append(len(self._folded_lines))
        self._folded_lines.extend(folds)

        self.virtual_size = Size(width, len(self._folded_lines))

    def update_line(self, line_index: int, line: Content) -> None:
        # line.simplify()
        line_record = self._lines[line_index]
        line_record.content = line
        line_record.folds[:] = self._fold_line(line_index, line, self._width)
        line_record.updates += 1

        fold_line = self._line_to_fold[line_index]
        del self._line_to_fold[line_index:]
        del self._folded_lines[fold_line:]

        for line_no in range(line_index, self.line_count):
            line_record = self._lines[line_no]
            self._line_to_fold.append(len(self._folded_lines))
            for fold in line_record.folds:
                self._folded_lines.append(fold)
                self.refresh_line(fold_line)
                fold_line += 1

        self.virtual_size = Size(self._width, len(self._folded_lines))

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        strip = self._render_line(scroll_x, scroll_y + y, self._width)
        return strip

    def _render_line(self, x: int, y: int, width: int) -> Strip:
        selection = self.text_selection

        visual_style = self.visual_style
        rich_style = visual_style.rich_style

        try:
            line_no, line_offset, offset, line = self._folded_lines[y]
        except IndexError:
            return Strip.blank(width, rich_style)

        unfolded_line = self._lines[line_no]
        cache_key = (unfolded_line.updates, y, width, visual_style)
        if not selection:
            cached_strip = self._render_line_cache.get(cache_key)
            if cached_strip:
                cached_strip = cached_strip.crop_extend(x, x + width, rich_style)
                return cached_strip

        if selection is not None:
            if select_span := selection.get_span(line_no):
                unfolded_content = self._lines[line_no].content
                start, end = select_span
                if end == -1:
                    end = len(unfolded_content)
                selection_style = self.screen.get_visual_style("screen--selection")
                unfolded_content = unfolded_content.stylize(selection_style, start, end)
                try:
                    line = self._fold_line(
                        line_no,
                        unfolded_content,
                        width,
                    )[line_offset][-1]
                except IndexError:
                    pass

        strips = Visual.to_strips(
            self, line, width, 1, self.visual_style, apply_selection=False
        )

        strip = strips[0]
        strip = strip.apply_offsets(x + offset, line_no)
        if not selection:
            self._render_line_cache[cache_key] = strip
        strip = strip.crop_extend(x, x + width, rich_style)
        return strip


if __name__ == "__main__":
    from textual import work
    from textual.app import App, ComposeResult

    import asyncio

    import codecs

    class ANSIApp(App):
        CSS = """
        ANSILog {
          
        }
        """

        def compose(self) -> ComposeResult:
            yield ANSILog()

        @work
        async def on_mount(self) -> None:
            ansi_log = self.query_one(ANSILog)
            env = os.environ.copy()
            env["LINES"] = "24"
            env["COLUMNS"] = str(self.size.width - 2)
            env["TTY_COMPATIBLE"] = "1"

            process = await asyncio.create_subprocess_shell(
                "python -m rich",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            assert process.stdout is not None
            unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            while data := await process.stdout.read(16 * 1024):
                line = unicode_decoder.decode(data)
                ansi_log.write(line)
            line = unicode_decoder.decode(b"", final=True)
            ansi_log.write(line)

            # for repeat in range(100):
            #     self.query_one(ANSILog).add_line(
            #         Content.from_markup("Hello, World! " * 20)
            #     )
            #     self.query_one(ANSILog).add_line(Content.from_markup("FOO BAR " * 20))

    ANSIApp().run()
