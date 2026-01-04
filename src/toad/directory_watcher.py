import rich.repr

from textual.message import Message
from textual.widget import Widget

from pathlib import Path
import threading
from watchdog.events import (
    DirModifiedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer


class DirectoryChanged(Message):
    """The directory was changed."""


@rich.repr.auto
class DirectoryWatcher(threading.Thread, FileSystemEventHandler):
    """Watch a directory for changes."""

    def __init__(self, path: Path, widget: Widget) -> None:
        self._path = path
        self._widget = widget
        self._observer = Observer()
        self._exit_event = threading.Event()
        super().__init__(name=repr(self))

    def on_any_event(self, event: FileSystemEvent) -> None:
        if not isinstance(event, (DirModifiedEvent, FileModifiedEvent)):
            # We aren't interested in modifications. Only when files are potentially added / removed
            self._widget.post_message(DirectoryChanged())

    def __rich_repr__(self) -> rich.repr.Result:
        yield self._path
        yield self._widget

    def start(self) -> None:
        """Start the watcher."""

        self._observer.schedule(self, str(self._path), recursive=True)
        self._observer.start()
        super().start()

    def stop(self) -> None:
        """Stop the watcher."""
        self._exit_event.set()

    def run(self):
        """Run the thread."""
        while not self._exit_event.wait(1):
            # Nothing to do here. The Observer object is doing the work.
            pass
