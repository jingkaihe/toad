import asyncio
import codecs

import os
import fcntl
import pty
import termios


from toad.shell_read import shell_read
from toad.widgets.ansi_log import ANSILog

MAX_BUFFER_DURATION = 1 / 60


class CommandError(Exception):
    """An error occurred running the command."""


class CommandPane(ANSILog):
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        self._execute_task: asyncio.Task | None = None
        self._return_code: int | None = None
        super().__init__(name=name, id=id, classes=classes)

    async def execute(self, command: str) -> None:
        self._execute_task = asyncio.create_task(self._execute(command))

    async def _execute(self, command: str) -> None:
        master, slave = pty.openpty()

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Get terminal attributes
        attrs = termios.tcgetattr(slave)

        # Disable echo (ECHO flag)
        attrs[3] &= ~termios.ECHO
        attrs[0] |= termios.ISIG

        # Apply the changes
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TTY_COMPATIBLE"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["TOAD"] = "1"
        env["CLICOLOR"] = "1"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                start_new_session=True,  # Linux / macOS only
            )
        except Exception as error:
            raise CommandError(f"Failed to execute {command!r}; {error}")

        os.close(slave)
        BUFFER_SIZE = 64 * 1024
        reader = asyncio.StreamReader(BUFFER_SIZE)
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        transport, _ = await loop.connect_read_pipe(
            lambda: protocol, os.fdopen(master, "rb", 0)
        )

        # Create write transport
        writer_protocol = asyncio.BaseProtocol()
        write_transport, _ = await loop.connect_write_pipe(
            lambda: writer_protocol,
            os.fdopen(os.dup(master), "wb", 0),
        )
        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        try:
            while True:
                data = await shell_read(reader, BUFFER_SIZE, MAX_BUFFER_DURATION)
                if line := unicode_decoder.decode(data, final=not data):
                    self.write(line)
                if not data:
                    break
        finally:
            transport.close()

        await process.wait()
        return_code = self._return_code = process.returncode
        self.set_class(return_code == 0, "-success")
        self.set_class(return_code != 0, "-fail")


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    class CommandApp(App):
        CSS = """
        CommandPane {
            max-height: 10;
        }
        """

        def compose(self) -> ComposeResult:
            yield CommandPane()

        def on_mount(self) -> None:
            command_pane = self.query_one(CommandPane)
            self.call_after_refresh(command_pane.execute, "ls -al")

    app = CommandApp()
    app.run()
