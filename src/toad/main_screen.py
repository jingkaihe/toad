from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.reactive import var
from textual import getters
from textual.widgets import Footer
from textual import containers

from toad.widgets.throbber import Throbber
from toad.widgets.conversation import Conversation
from toad.widgets.explain import Explain
from toad.widgets.version import Version


class MainScreen(Screen, can_focus=False):
    BINDING_GROUP_TITLE = "Screen"
    busy_count = var(0)
    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    conversation = getters.query_one(Conversation)

    def compose(self) -> ComposeResult:
        yield Version("Toad v0.1")
        with containers.Center():
            yield Explain()
            yield Conversation()
            yield Footer()

    def action_focus_prompt(self) -> None:
        self.conversation.focus_prompt()
