from functools import cached_property
from pathlib import Path
import json

import platformdirs

from textual.reactive import var
from textual.app import App, ComposeResult
from textual.screen import Screen

from toad.settings import Schema, Settings
from toad.settings_schema import SCHEMA
from toad.main_screen import MainScreen


class ToadApp(App):
    BINDING_GROUP_TITLE = "System"
    CSS_PATH = "toad.tcss"

    _settings = var(dict)

    @property
    def config_path(self) -> Path:
        path = Path(
            platformdirs.user_config_dir("toad", "willmcgugan", ensure_exists=True)
        )
        return path

    @property
    def settings_path(self) -> Path:
        return self.config_path / "settings.json"

    @cached_property
    def settings_schema(self) -> Schema:
        return Schema(SCHEMA)

    @cached_property
    def settings(self) -> Settings:
        return Settings(self.settings_schema, self._settings)

    def on_ready(self) -> None:
        settings_path = self.settings_path
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
        else:
            settings = self.settings_schema.build_default()
            settings_path.write_text(json.dumps(settings), "utf-8")
            self.notify(f"Wrote default settings to {settings_path}")
        self._settings = settings

    def on_mount(self) -> None:
        self.theme = "dracula"

    def get_default_screen(self) -> Screen:
        return MainScreen()
