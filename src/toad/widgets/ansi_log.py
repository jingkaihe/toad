from __future__ import annotations
from dataclasses import dataclass, field
import os
from typing import NamedTuple


from textual.geometry import Size, clamp, Region
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
        self.minimum_terminal_width = minimum_terminal_width

        self.cursor_line = 0
        """folded line index."""
        self.cursor_offset = 0
        """folded line offset"""

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
        window_width = self.scrollable_content_region.width
        if self.minimum_terminal_width == -1 and window_width:
            self.minimum_terminal_width = window_width
        width = max(self.minimum_terminal_width, window_width)
        return width

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def last_line_index(self) -> int:
        return self.line_count - 1

    @property
    def cursor_line_offset(self) -> int:
        """The cursor offset within the un-folded lines."""
        cursor_folded_line = self._folded_lines[self.cursor_line]
        cursor_line_offset = cursor_folded_line.line_offset
        line_no = cursor_folded_line.line_no
        line = self._lines[line_no]
        position = 0
        for folded_line_offset, folded_line in enumerate(line.folds):
            if folded_line_offset == cursor_line_offset:
                position += self.cursor_offset
                break
            position += len(folded_line.content)
        return position

    def on_mount(self):
        self.anchor()

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
        folded_lines = self._folded_lines

        for ansi_token in self._ansi_stream.feed(text):
            (
                delta_x,
                delta_y,
                absolute_x,
                absolute_y,
                content,
                replace,
            ) = ansi_token
            while self.cursor_line >= len(folded_lines):
                self.add_line(Content())

            folded_line = folded_lines[self.cursor_line]
            line = self._lines[folded_line.line_no]

            if content is not None:
                cursor_line_offset = self.cursor_line_offset

                if replace is not None:
                    start_replace, end_replace = ansi_token.get_replace_offsets(
                        cursor_line_offset, len(line.content)
                    )
                    updated_line = Content.assemble(
                        line.content[:start_replace],
                        content,
                        line.content[end_replace + 1 :],
                    )
                else:
                    updated_line = Content.assemble(
                        line.content[:cursor_line_offset],
                        content,
                        line.content[cursor_line_offset + len(content) :],
                    )

                self.update_line(folded_line.line_no, updated_line)

            if delta_x is not None:
                self.cursor_offset += delta_x
                while self.cursor_offset > self._width:
                    self.cursor_line += 1
                    self.cursor_offset -= self._width
            if delta_y is not None:
                self.cursor_line = max(0, self.cursor_line + delta_y)

            if absolute_x is not None:
                self.cursor_offset = absolute_x
            if absolute_y is not None:
                self.cursor_line = max(0, absolute_y)

    def _fold_line(self, line_no: int, line: Content, width: int) -> list[LineFold]:
        if not width:
            return [LineFold(0, 0, 0, line)]
        line_length = line.cell_length
        divide_offsets = list(range(width, line_length, width))
        folded_line = line.divide(divide_offsets)
        offsets = [0, *divide_offsets]
        folds = [
            LineFold(line_no, line_offset, offset, line)
            for line_offset, (offset, line) in enumerate(zip(offsets, folded_line))
        ]
        assert len(folds)
        return folds

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
        line_no = self.line_count
        width = self._width
        line_record = LineRecord(content, self._fold_line(line_no, content, width))
        self._lines.append(line_record)
        # if not width:
        #     return
        folds = line_record.folds
        self._line_to_fold.append(len(self._folded_lines))
        self._folded_lines.extend(folds)
        self.virtual_size = Size(width, len(self._folded_lines))

    def update_line(self, line_index: int, line: Content) -> None:
        line.simplify()
        while line_index >= len(self._lines):
            self.add_line(Content())

        line_record = self._lines[line_index]
        line_record.content = line
        line_record.folds[:] = self._fold_line(line_index, line, self._width)
        line_record.updates += 1

        fold_line = self._line_to_fold[line_index]
        del self._line_to_fold[line_index:]
        del self._folded_lines[fold_line:]

        refresh_lines = 0

        for line_no in range(line_index, self.line_count):
            line_record = self._lines[line_no]
            self._line_to_fold.append(len(self._folded_lines))
            for fold in line_record.folds:
                self._folded_lines.append(fold)
                refresh_lines += 1

        width = self._width
        self.virtual_size = Size(width, len(self._folded_lines))
        self.refresh(Region(0, line_no, width, refresh_lines))

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
            if cached_strip is not None:
                cached_strip = cached_strip.crop_extend(x, x + width, rich_style)
                cached_strip = cached_strip.apply_offsets(x + offset, line_no)
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

        if not selection:
            self._render_line_cache[cache_key] = strip
        strip = strip.crop_extend(x, x + width, rich_style)
        strip = strip.apply_offsets(x + offset, line_no)
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
            env["FORCE_COLOR"] = "1"

            process = await asyncio.create_subprocess_shell(
                "python -m rich.progress",
                # "python ansi_mandel.py",
                # "python simple_test.py",
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

    ANSIApp().run()
