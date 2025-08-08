from textual.app import ComposeResult
from textual import containers
from textual.widgets import Label
from textual.reactive import var
from textual import getters

from toad.widgets.ansi_log import ANSILog


class RunOutput(ANSILog):
    pass
    # code_display = getters.child_by_id("output", Label)
    # output = var("")

    # def compose(self) -> ComposeResult:
    #     yield Label(id="output")

    # def watch_output(self, code: str) -> None:
    #     self.code_display.update(code)
