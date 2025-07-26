import asyncio
from contextlib import suppress
from textual import on, work
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual import events
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets._markdown import MarkdownBlock, MarkdownFence
from textual.geometry import Offset
from textual.reactive import var
from textual.css.query import NoMatches

import llm

from toad import messages
from toad.widgets.menu import Menu
from toad.widgets.prompt import MarkdownTextArea, Prompt
from toad.widgets.throbber import Throbber
from toad.widgets.welcome import Welcome
from toad.widgets.user_input import UserInput
from toad.widgets.explain import Explain
from toad.widgets.run_output import RunOutput

from toad.menus import CONVERSATION_MENUS

MD = """\
# Textual Markdown Browser - Demo

This Markdown file contains some examples of Markdown widgets.

## Headers

Headers levels 1 through 6 are supported.

### This is H3

This is H3 Content

#### This is H4

Header level 4 content. Drilling down into finer headings.

##### This is H5

Header level 5 content.

###### This is H6

Header level 6 content.

## Typography

The usual Markdown typography is supported. The exact output depends on your terminal, although most are fairly consistent.

### Emphasis

Emphasis is rendered with `*asterisks*`, and looks *like this*;

### Strong

Use two asterisks to indicate strong which renders in bold, e.g. `**strong**` render **strong**.

### Strikethrough

Two tildes indicates strikethrough, e.g. `~~cross out~~` render ~~cross out~~.

### Inline code ###

Inline code is indicated by backticks. e.g. `import this`.

## Horizontal rule

Draw a horizontal rule with three dashes (`---`).

---

Good for natural breaks in the content, that don't require another header.

[like this][example]

## Lists

1. Lists can be ordered
2. Lists can be unordered
   - I must not fear.
     - Fear is the mind-killer.
       - Fear is the little-death that brings total obliteration.
         - I will face my fear.
           - I will permit it to pass over me and through me.
     - And when it has gone past, I will turn the inner eye to see its path.
   - Where the fear has gone there will be nothing. Only I will remain.

[example]: example.com
   
### Longer list

1. **Duke Leto I Atreides**, head of House Atreides
2. **Lady Jessica**, Bene Gesserit and concubine of Leto, and mother of Paul and Alia
3. **Paul Atreides**, son of Leto and Jessica
4. **Alia Atreides**, daughter of Leto and Jessica
5. **Gurney Halleck**, troubadour warrior of House Atreides
6. **Thufir Hawat**, Mentat and Master of Assassins of House Atreides
7. **Duncan Idaho**, swordmaster of House Atreides
8. **Dr. Wellington Yueh**, Suk doctor of House Atreides
9. **Leto**, first son of Paul and Chani who dies as a toddler
10. **Esmar Tuek**, a smuggler on Arrakis
11. **Staban Tuek**, son of Esmar

## Fences

Fenced code blocks are introduced with three back-ticks and the optional parser. Here we are rendering the code in a sub-widget with syntax highlighting and indent guides.

In the future I think we could add controls to export the code, copy to the clipboard. Heck, even run it and show the output?

```python
@lru_cache(maxsize=1024)
def split(self, cut_x: int, cut_y: int) -> tuple[Region, Region, Region, Region]:
    \"\"\"Split a region into 4 from given x and y offsets (cuts).

    ```
                cut_x ↓
            ┌────────┐ ┌───┐
            │        │ │   │
            │    0   │ │ 1 │
            │        │ │   │
    cut_y → └────────┘ └───┘
            ┌────────┐ ┌───┐
            │    2   │ │ 3 │
            └────────┘ └───┘
    ```

    Args:
        cut_x (int): Offset from self.x where the cut should be made. If negative, the cut
            is taken from the right edge.
        cut_y (int): Offset from self.y where the cut should be made. If negative, the cut
            is taken from the lower edge.

    Returns:
        tuple[Region, Region, Region, Region]: Four new regions which add up to the original (self).
    \"\"\"

    x, y, width, height = self
    if cut_x < 0:
        cut_x = width + cut_x
    if cut_y < 0:
        cut_y = height + cut_y

    _Region = Region
    return (
        _Region(x, y, cut_x, cut_y),
        _Region(x + cut_x, y, width - cut_x, cut_y),
        _Region(x, y + cut_y, cut_x, height - cut_y),
        _Region(x + cut_x, y + cut_y, width - cut_x, height - cut_y),
    )
```

## Quote

Quotes are introduced with a chevron, and render like this:

> I must not fear.
> Fear is the mind-killer.
> Fear is the little-death that brings total obliteration.
> I will face my fear.
> I will permit it to pass over me and through me.
> And when it has gone past, I will turn the inner eye to see its path.
> Where the fear has gone there will be nothing. Only I will remain."

Quotes nest nicely. Here's what quotes within quotes look like:

> I must not fear.
> > Fear is the mind-killer.
> > Fear is the little-death that brings total obliteration.
> > I will face my fear.
> > > I will permit it to pass over me and through me.
> > > And when it has gone past, I will turn the inner eye to see its path.
> > > Where the fear has gone there will be nothing. Only I will remain.

## Tables

Tables are supported, and render as a Rich table.

I would like to add controls to these widgets to export the table as CSV, which I think would be a nice feature. In the future we might also have sortable columns by clicking on the headers.


| Name            | Type   | Default | Description                        |
| --------------- | ------ | ------- | ---------------------------------- |
| `show_header`   | `bool` | `True`  | Show the **table** header              |
| `fixed_rows`    | `int`  | `0`     | Number of fixed rows               |
| `fixed_columns` | `int`  | `0`     | Number of fixed columns            |
| `zebra_stripes` | `bool` | `False` | Display alternating colors on rows |
| `header_height` | `int`  | `1`     | Height of header row               |
| `show_cursor`   | `bool` | `True`  | Show a cell cursor                 |
"""

# MD = """
# ## Tables

# Tables are supported, and render as a Rich table.

# I would like to add controls to these widgets to export the table as CSV, which I think would be a nice feature. In the future we might also have sortable columns by clicking on the headers.

# `FOO`

# | Name            | Type   | Default | Description                        |
# | --------------- | ------ | ------- | ---------------------------------- |
# | `show_header`   | `bool` | `True`  | Show the **table** header              |
# | `fixed_rows`    | `int`  | `0`     | Number of fixed rows               |
# | `fixed_columns` | `int`  | `0`     | Number of fixed columns            |
# | `zebra_stripes` | `bool` | `False` | Display alternating colors on rows |
# | `header_height` | `int`  | `1`     | Height of header row               |
# | `show_cursor`   | `bool` | `True`  | Show a cell cursor                 |
# """

# MD = """
# ```python
# for n in range(10):
#     print(n)
# """

# MD = """
# 1. Lists can be ordered
# 2. Lists can be `unordered`
#    - I must not *fear*.
#      - Fear is the `mind-killer`.
#        - Fear is the little-death that brings total obliteration.
#          - I will face my fear.
#            - I will permit it to pass over me and through me.
#      - And when it has gone past, I will turn the inner eye to see its path.
#    - Where the fear has gone there will be nothing. Only I will remain.
# """


class Cursor(Static):
    follow_widget: var[Widget | None] = var(None)
    blink = var(True, toggle_class="-blink")

    def on_mount(self) -> None:
        self.display = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)
        self.set_interval(0.4, self._update_follow)

    def _update_blink(self) -> None:
        self.blink = not self.blink

    def watch_follow_widget(self, widget: Widget | None) -> None:
        self.display = widget is not None

    def _update_follow(self) -> None:
        if self.follow_widget:
            self.styles.height = max(1, self.follow_widget.size.height)
            follow_y = self.follow_widget.region.y
            self.offset = Offset(0, follow_y + self.container_scroll_offset.y)

    def follow(self, widget: Widget | None) -> None:
        self.follow_widget = widget
        self.blink = False
        if widget is None:
            self.display = False
            self.blink_timer.reset()
            self.blink_timer.pause()
        else:
            self.display = True
            self.blink_timer.reset()
            self.blink_timer.resume()
            self._update_follow()


class Contents(containers.VerticalScroll, can_focus=True):
    BINDING_GROUP_TITLE = "View"
    BINDINGS = [
        Binding("end", "screen.focus_prompt", "Focus prompt"),
    ]

    @on(events.Focus)
    def on_focus(self) -> None:
        self.query_one(Cursor).visible = True


class Conversation(containers.Vertical):
    BINDING_GROUP_TITLE = "Conversation"
    BINDINGS = [
        Binding("alt+up", "cursor_up", "Block up", priority=True),
        Binding("alt+down", "cursor_down", "Block down"),
        Binding("enter", "select_block", "Select"),
        Binding("escape", "dismiss", "Dismiss", show=False),
    ]

    busy_count = var(0)
    block_cursor = var(-1)
    _blocks: var[list[MarkdownBlock] | None] = var(None)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one("#contents", containers.VerticalScroll)
    cursor = getters.query_one(Cursor)
    prompt = getters.query_one(Prompt)
    llm_model = var(lambda: llm.get_model("gpt-4o"))
    conversation = var(lambda: llm.get_model("gpt-4o").conversation())

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        with Contents(id="contents"):
            yield Cursor()
        yield Prompt()

    @property
    def cursor_block(self) -> MarkdownBlock | None:
        """The block next to the cursor, or `None` if no block cursor."""
        blocks = self.blocks
        if self.block_cursor < 0 or self.block_cursor >= len(blocks):
            return None
        return blocks[self.block_cursor]

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        from toad.widgets.agent_response import AgentResponse

        await self.post(UserInput(event.body))
        agent_response = AgentResponse(self.conversation)
        await self.post(agent_response)
        agent_response.send_prompt(event.body)

    @on(Menu.OptionSelected)
    async def on_menu_option_selected(self, event: Menu.OptionSelected) -> None:
        await self.run_action(event.action)

    @on(events.DescendantFocus)
    def on_descendant_focus(self, event: events.DescendantFocus):
        if isinstance(event.widget, MarkdownTextArea):
            self.block_cursor = -1

    @on(events.DescendantBlur)
    def on_descendant_blur(self, event: events.DescendantBlur):
        if isinstance(event.widget, Contents):
            self.cursor.visible = False

    @on(Menu.Dismissed)
    def on_menu_dismissed(self, event: Menu.Dismissed) -> None:
        event.stop()
        self.contents.focus()
        self.cursor.visible = True

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    @work
    async def on_mount(self) -> None:
        self.screen.can_focus = False
        await self.post(Welcome(), anchor=False)

    def on_click(self, event: events.Click) -> None:
        if event.widget is not None:
            markdown_block = event.widget
            try:
                if not isinstance(
                    markdown_block, MarkdownBlock
                ) or not markdown_block.has_class("level-0"):
                    markdown_block = event.widget.query_ancestor(
                        "MarkdownBlock.level-0", MarkdownBlock
                    )

            except NoMatches:
                pass
            else:
                with suppress(ValueError):
                    clicked_block_index = self.blocks.index(markdown_block)
                    if self.block_cursor == clicked_block_index:
                        pass
                        # await self.action_select_block()
                    else:
                        self.block_cursor = clicked_block_index

        # self.notify(str(event.widget))

    async def post(self, widget: Widget, anchor: bool = True) -> None:
        self._blocks = None
        await self.contents.mount(widget)
        if anchor:
            self.contents.anchor()

    @property
    def blocks(self) -> list[MarkdownBlock]:
        from toad.widgets.agent_response import AgentResponse

        if self._blocks is None or self.busy_count:
            self._blocks = [
                block
                for response in self.contents.query_children(AgentResponse)
                for block in response.query_children(MarkdownBlock)
            ]
        return self._blocks

    def action_cursor_up(self) -> None:
        blocks = self.blocks
        if blocks:
            if self.block_cursor == 0:
                pass
            elif self.block_cursor == -1:
                self.block_cursor = len(blocks) - 1
            else:
                self.block_cursor -= 1

    def action_cursor_down(self) -> None:
        blocks = self.blocks
        if not blocks:
            return
        if self.block_cursor == -1:
            return
        else:
            if self.block_cursor < len(blocks) - 1:
                self.block_cursor += 1
            else:
                self.block_cursor = -1

    def action_dismiss(self) -> None:
        self.block_cursor = -1

    def focus_prompt(self) -> None:
        self.block_cursor = -1

    async def action_select_block(self) -> None:
        block = self.blocks[self.block_cursor]
        if block.name is None:
            self.app.bell()
            return
        menu_options = CONVERSATION_MENUS.get(block.name, []).copy()

        from toad.code_analyze import get_special_name_from_code

        if block.name == "fence" and isinstance(block, MarkdownFence):
            for numeral, name in enumerate(
                get_special_name_from_code(block._content.plain, block.lexer), 1
            ):
                menu_options.append(
                    Menu.Item(f"explain('{name}')", f"Explain '{name}'", f"{numeral}")
                )

        menu = Menu(
            [
                Menu.Item("explain", "Explain this", "e"),
                Menu.Item("copy_to_clipboard", "Copy to clipboard", "c"),
                Menu.Item("copy_to_prompt", "Copy to prompt", "p"),
                *menu_options,
            ]
        )
        await self.contents.mount(menu, before=block)
        menu.focus(scroll_visible=False)

    def action_copy_to_clipboard(self) -> None:
        if (block := self.cursor_block) is not None and block.source:
            self.app.copy_to_clipboard(block.source)
            self.notify("Copied to clipboard")

    def action_copy_to_prompt(self) -> None:
        if (block := self.cursor_block) is not None and block.source:
            self.block_cursor = -1
            self.prompt.append(block.source)

    def action_explain(self, topic: str | None = None) -> None:
        if (block := self.cursor_block) is not None and block.source:
            if topic:
                PROMPT = f"Explain the purpose of '{topic}' in the following code:\n{block.source}"
            else:
                PROMPT = f"Explain the following:\n{block.source}"
            self.screen.query_one(Explain).send_prompt(PROMPT)

    def action_run(self) -> None:
        if (block := self.cursor_block) is not None and block.source:
            assert isinstance(block, MarkdownFence)
            self.execute(block._content.plain, block.lexer)

    @work
    async def execute(self, code: str, language: str) -> None:
        self.notify(repr(language))
        if language == "python":
            command = "python run"
        elif language == "bash":
            command = "sh run"
        else:
            self.notify(
                f"Toad doesn't know how to run '{language}' code yet",
                title="Run",
                severity="error",
            )
        run_output = RunOutput()
        await self.post(run_output, anchor=True)
        with open("run", mode="wt", encoding="utf-8") as source:
            source.write(code)

        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE
        )
        while data := await process.stdout.readline():
            line = data.decode("utf-8")
            run_output.output += line

    def watch_block_cursor(self, block_cursor: int) -> None:
        if block_cursor == -1:
            self.cursor.follow(None)
            self.contents.scroll_end(immediate=True)
            self.prompt.focus()
        else:
            self.contents.focus()
            self.cursor.visible = True
            blocks = self.blocks
            block = blocks[block_cursor]
            self.cursor.follow(block)
            self.contents.release_anchor()
            self.contents.scroll_to_center(block, immediate=True)
