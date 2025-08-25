from dataclasses import dataclass

from textual.widget import Widget
from textual.message import Message


class WorkStarted(Message):
    """Work has started."""


class WorkFinished(Message):
    """Work has finished."""


@dataclass
class UserInputSubmitted(Message):
    body: str
    shell: bool = False


@dataclass
class PromptSuggestion(Message):
    suggestion: str


@dataclass
class Dismiss(Message):
    widget: Widget

    @property
    def control(self) -> Widget:
        return self.widget


@dataclass
class InsertPath(Message):
    path: str
