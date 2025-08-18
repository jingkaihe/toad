from functools import cached_property
from pathlib import Path
import json

import platformdirs

from rich import terminal_theme

from textual.reactive import var, reactive
from textual.app import App
from textual.screen import Screen
from textual.signal import Signal

from toad.settings import Schema, Settings
from toad.settings_schema import SCHEMA
from toad.screens.main import MainScreen
from toad import atomic


class ToadApp(App):
    BINDING_GROUP_TITLE = "System"

    CSS_PATH = "toad.tcss"

    _settings = var(dict)
    column: reactive[bool] = reactive(False)
    column_width: reactive[int] = reactive(100)
    scrollbar: reactive[str] = reactive("normal")

    def __init__(self) -> None:
        self.settings_changed_signal = Signal(self, "settings_changed")
        super().__init__()

    @property
    def config_path(self) -> Path:
        path = Path(
            platformdirs.user_config_dir("toad", "textualize", ensure_exists=True)
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
        return Settings(
            self.settings_schema, self._settings, on_set_callback=self.setting_updated
        )

    def save_settings(self) -> None:
        if self.settings.changed:
            path = str(self.settings_path)
            try:
                atomic.write(path, self.settings.json)
            except Exception as error:
                self.notify(str(error), title="Settings", severity="error")
            else:
                self.notify(
                    f"Saved settings to [$text-success]{path!r}",
                    title="Settings",
                    severity="information",
                )
                self.settings.up_to_date()

    def setting_updated(self, key: str, value: object) -> None:
        if key == "ui.column":
            if isinstance(value, bool):
                self.column = value
        elif key == "ui.column-width":
            if isinstance(value, int):
                self.column_width = value
        elif key == "ui.theme":
            if isinstance(value, str):
                self.theme = value
        elif key == "ui.scrollbar":
            if isinstance(value, str):
                self.scrollbar = value

        self.settings_changed_signal.publish((key, value))

    def on_load(self) -> None:
        settings_path = self.settings_path
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
        else:
            settings = self.settings_schema.defaults
            settings_path.write_text(
                json.dumps(settings, indent=4, separators=(", ", ": ")), "utf-8"
            )
            self.notify(f"Wrote default settings to {settings_path}")
        self.ansi_theme_dark = terminal_theme.DIMMED_MONOKAI
        self._settings = settings
        self.settings.set_all()

    def get_default_screen(self) -> Screen:
        return MainScreen().data_bind(
            column=ToadApp.column,
            column_width=ToadApp.column_width,
            scrollbar=ToadApp.scrollbar,
        )
