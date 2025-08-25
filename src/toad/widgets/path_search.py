from __future__ import annotations

from os import PathLike
from operator import itemgetter
from pathlib import Path
import re
from typing import Sequence

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual import work
from textual import getters
from textual import containers
from textual.reactive import var, Initialize
from textual.content import Content, Span

from textual.fuzzy import FuzzySearch
from textual.widgets import OptionList, Input
from textual.widgets.option_list import Option


from toad import directory
from toad.messages import Dismiss, InsertPath, PromptSuggestion


class PathSearch(containers.VerticalGroup):
    CURSOR_BINDING_GROUP = Binding.Group(description="Move selection")
    BINDINGS = [
        Binding(
            "up", "cursor_up", "Cursor up", group=CURSOR_BINDING_GROUP, priority=True
        ),
        Binding(
            "down",
            "cursor_down",
            "Cursor down",
            group=CURSOR_BINDING_GROUP,
            priority=True,
        ),
        Binding("enter", "submit", "Insert path", priority=True),
        Binding("escape", "dismiss", "Dismiss", priority=True),
    ]

    def get_fuzzy_search(self) -> FuzzySearch:
        return FuzzySearch(case_sensitive=True)

    root: var[Path] = var(Path("./"))
    paths: var[list[Path]] = var(list)
    highlighted_paths: var[list[Content]] = var(list)
    filtered_path_indices: var[list[int]] = var(list)
    loaded = var(False)
    filter = var("")
    fuzzy_search: var[FuzzySearch] = var(Initialize(get_fuzzy_search))

    option_list = getters.query_one(OptionList)
    input = getters.query_one(Input)

    def compose(self) -> ComposeResult:
        yield Input(compact=True, placeholder="fuzzy search")
        yield OptionList()

    async def search(self, search: str) -> None:
        if not search:
            self.option_list.set_options(
                [
                    Option(highlighted_path, highlighted_path.plain)
                    for highlighted_path in self.highlighted_paths
                ],
            )
            return

        fuzzy_search = self.fuzzy_search
        fuzzy_search.cache.grow(len(self.paths))
        scores: list[tuple[float, Sequence[int], Content]] = [
            (
                *fuzzy_search.match(search, self.highlighted_paths[index].plain),
                self.highlighted_paths[index],
            )
            for index, path in enumerate(self.paths)
        ]
        scores = sorted(
            [score for score in scores if score[0]], key=itemgetter(0), reverse=True
        )

        def highlight_offsets(path: Content, offsets: Sequence[int]) -> Content:
            return path.add_spans(
                [Span(offset, offset + 1, "underline") for offset in offsets]
            )

        self.option_list.set_options(
            [
                Option(highlight_offsets(path, offsets), id=path.plain)
                for score, offsets, path in scores
            ]
        )
        self.post_message(PromptSuggestion(""))

    def action_cursor_down(self) -> None:
        self.option_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.option_list.action_cursor_up()

    def action_dismiss(self) -> None:
        self.post_message(Dismiss(self))

    def focus(self) -> None:
        self.input.focus()

    @on(Input.Changed)
    async def on_input_changed(self, event: Input.Changed):
        await self.search(event.value)

    @on(OptionList.OptionHighlighted)
    async def on_option_list_changed(self, event: OptionList.OptionHighlighted):
        event.stop()
        if event.option:
            self.post_message(PromptSuggestion(event.option.id))

    def action_submit(self):
        if highlighted := self.option_list.highlighted:
            option = self.option_list.options[highlighted]
            if option.id:
                self.post_message(InsertPath(option.id))
                self.post_message(Dismiss(self))

    def watch_root(self, root: Path) -> None:
        pass

    @work(exclusive=True)
    async def load_paths(self, root_path: str | Path) -> None:
        self.input.clear()
        self.input.focus()
        if isinstance(root_path, str):
            root = Path(root_path)
        else:
            root = root_path

        self.loading = True
        paths = await directory.scan(root, exclude_dirs=[".*", "__*__"])
        paths.sort(key=lambda path: (len(path.parts), str(path)))
        self.root = root
        self.paths = paths
        self.loading = False

    def highlight_path(self, path: str) -> Content:
        if path.startswith("."):
            return Content.styled(path, "$foreground-muted")
        content = Content.styled(path, "$foreground-muted")
        if "/" in path:
            content = content.stylize("$text-success dim", path.rfind("/") + 1)
        else:
            content = content.stylize("$text-success dim")
        if (match := re.search(r"\.(.*$)", content.plain)) is not None:
            content = content.stylize("not dim", match.start(1), match.end(1))
        return content

    def watch_paths(self, paths: list[Path]) -> None:
        self.highlighted_paths = [self.highlight_path(str(path)) for path in paths]
        self.option_list.set_options(
            [
                Option(highlighted_path, id=highlighted_path.plain)
                for highlighted_path in self.highlighted_paths
            ],
        )
        self.post_message(PromptSuggestion(""))
        self.input.focus()
