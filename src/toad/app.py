from textual.app import App, ComposeResult
from textual.screen import Screen

from toad.main_screen import MainScreen


class ToadApp(App):
    BINDING_GROUP_TITLE = "System"
    CSS_PATH = "toad.tcss"

    def on_mount(self) -> None:
        self.theme = "dracula"

    def get_default_screen(self) -> Screen:
        return MainScreen()
