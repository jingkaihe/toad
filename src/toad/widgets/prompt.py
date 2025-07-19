from textual.app import ComposeResult

from textual.widgets import TextArea
from textual.binding import Binding
from textual.message import Message
from textual import containers

from textual import events


from toad.widgets.condensed_path import CondensedPath
from toad.messages import UserInputSubmitted


class MarkdownTextArea(TextArea):
    BINDING_GROUP_TITLE = "Prompt"
    BINDINGS = [Binding("ctrl+j", "submit", "Submit markdown")]

    class Submitted(Message):
        def __init__(self, markdown: str) -> None:
            self.markdown = markdown
            super().__init__()

    def on_mount(self) -> None:
        self.highlight_cursor_line = False

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(UserInputSubmitted(self.text))
            self.clear()

    def action_submit(self) -> None:
        self.insert("\n")


class Prompt(containers.VerticalGroup):
    def focus(self) -> None:
        self.query(MarkdownTextArea).focus()

    def compose(self) -> ComposeResult:
        yield MarkdownTextArea()
        with containers.HorizontalGroup():
            yield CondensedPath()
