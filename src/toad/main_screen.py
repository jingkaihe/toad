from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.reactive import var
from textual import getters

from toad.widgets.throbber import Throbber
from toad.widgets.conversation import Conversation


class MainScreen(Screen):
    BINDING_GROUP_TITLE = "Screen"
    busy_count = var(0)
    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    conversation = getters.query_one(Conversation)

    def compose(self) -> ComposeResult:
        yield Conversation()

    def action_focus_prompt(self) -> None:
        self.conversation.focus_prompt()
