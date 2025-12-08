from __future__ import annotations


from contextlib import suppress
import os
import asyncio
import codecs
import fcntl
import platform
import pty
import struct
import termios
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.message import Message

from toad.shell_read import shell_read

from toad.widgets.terminal import Terminal

if TYPE_CHECKING:
    from toad.widgets.conversation import Conversation

IS_MACOS = platform.system() == "Darwin"


def resize_pty(fd, cols, rows):
    """Resize the pseudo-terminal"""
    # Pack the dimensions into the format expected by TIOCSWINSZ
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        # Possibly file descriptor closed
        pass


@dataclass
class CurrentWorkingDirectoryChanged(Message):
    """Current working directory has changed in shell."""

    path: str


@dataclass
class ShellFinished(Message):
    """The shell finished."""


class Shell:
    """Responsible for shell interactions in Conversation."""

    def __init__(
        self,
        conversation: Conversation,
        working_directory: str,
        shell="",
        start="",
    ) -> None:
        self.conversation = conversation
        self.working_directory = working_directory

        self.terminal: Terminal | None = None
        self.new_log: bool = False
        self.shell = shell or os.environ.get("SHELL", "sh")
        self.shell_start = start
        self.master: int | None = None
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None

        self._finished: bool = False
        self._ready_event: asyncio.Event = asyncio.Event()

        self._hide_echo: set[bytes] = set()
        """A set of byte strings to remove from output."""

    @property
    def is_finished(self) -> bool:
        return self._finished

    async def send(self, command: str, width: int, height: int) -> None:
        if self.master is None:
            return
        self._hide_echo.clear()
        await self._ready_event.wait()
        await asyncio.to_thread(resize_pty, self.master, width, max(height, 1))
        # await self.write(f"{command}\n", hide_echo=True)
        # await self.write(r'printf "\e]2025;$(pwd);\e\\"' + "\n", hide_echo=True)
        get_pwd_command = f"{command};" + r'printf "\e]2025;$(pwd);\e\\"' + "\n"
        await self.write(get_pwd_command, hide_echo=True)

        # await self.write(get_pwd_command.encode("utf-8"), hide_echo=True)

        self.terminal = None

    def start(self) -> None:
        assert self._task is None
        self._task = asyncio.create_task(self.run(), name=repr(self))

    async def interrupt(self) -> None:
        """Interrupt the running command."""
        await self.write(b"\x03")

    def update_size(self, width: int, height: int) -> None:
        """Update the size of the shell pty.

        Args:
            width: Desired width.
            height: Desired height.
        """
        if self.master is None:
            return
        with suppress(OSError):
            resize_pty(self.master, width, max(height, 1))

    async def write(self, text: str | bytes, hide_echo: bool = False) -> int:
        if self.master is None:
            return 0
        text_bytes = text.encode("utf-8", "ignore") if isinstance(text, str) else text
        if hide_echo:
            self._hide_echo.add(text_bytes)
        return await asyncio.to_thread(os.write, self.master, text_bytes)

    async def run(self) -> None:
        current_directory = self.working_directory

        master, slave = pty.openpty()
        self.master = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TTY_COMPATIBLE"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["TOAD"] = "1"
        env["CLICOLOR"] = "1"

        shell = self.shell

        def setup_pty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        try:
            _process = await asyncio.create_subprocess_shell(
                shell,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                cwd=current_directory,
                preexec_fn=setup_pty,
            )
        except Exception as error:
            self.conversation.notify(
                f"Unable to start shell: {error}\n\nCheck your settings.",
                title="Shell",
                severity="error",
            )
            return

        os.close(slave)
        BUFFER_SIZE = 64 * 1024
        reader = asyncio.StreamReader(BUFFER_SIZE)
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        transport, _ = await loop.connect_read_pipe(
            lambda: protocol, os.fdopen(master, "rb", 0)
        )

        if shell_start := self.shell_start.strip():
            shell_start = self.shell_start.strip()
            if not shell_start.endswith("\n"):
                shell_start += "\n"
            await self.write(shell_start, hide_echo=True)

        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        self._ready_event.set()

        while True:
            data = await shell_read(reader, BUFFER_SIZE)

            for string_bytes in list(self._hide_echo):
                remove_bytes = string_bytes.replace(b"\n", b"\r\n")
                if remove_bytes in data:
                    data = data.replace(remove_bytes, b"", 1)
                    self._hide_echo.discard(string_bytes)
                    if not data:
                        continue

            if line := unicode_decoder.decode(data, final=not data):
                if self.terminal is None or self.terminal.is_finalized:
                    previous_state = (
                        None if self.terminal is None else self.terminal.state
                    )
                    self.terminal = await self.conversation.new_terminal()
                    # if previous_state is not None:
                    #     self.terminal.set_state(previous_state)
                    self.terminal.set_write_to_stdin(self.write)
                if await self.terminal.write(line):
                    self.terminal.display = True
                new_directory = self.terminal.current_directory
                if new_directory and new_directory != current_directory:
                    current_directory = new_directory
                    self.conversation.post_message(
                        CurrentWorkingDirectoryChanged(current_directory)
                    )
            if (
                self.terminal is not None
                and self.terminal.is_finalized
                and self.terminal.state.scrollback_buffer.is_blank
            ):
                await self.terminal.remove()
                self.terminal = None
            if not data:
                break

        self.master = None
        self._finished = True
        self.conversation.post_message(ShellFinished())
