import asyncio

from llm import Model, Conversation

from textual.reactive import var
from textual import work
from textual.widgets import Markdown
from textual.widgets.markdown import MarkdownStream
from toad import messages

SYSTEM = """\
If asked to output code add inline documentation in the google style format, and always use type hinting where appropriate.
Avoid using external libraries where possible, and favor code that writes output to the terminal.
"""


class AgentResponse(Markdown):
    def __init__(self, conversation: Conversation, markdown: str | None = None) -> None:
        self.conversation = conversation
        super().__init__(markdown)

    async def _add_chunk(self, chunk: str) -> None:
        await self.append(chunk)
        await asyncio.sleep(0.01)

    @work
    async def send_prompt(self, prompt: str) -> None:
        stream = Markdown.get_stream(self)
        try:
            await self._send_prompt(prompt).wait()
        finally:
            await stream.stop()

    @work(thread=True)
    def _send_prompt(self, prompt: str) -> None:
        """Get the response in a thread."""
        self.post_message(messages.WorkStarted())
        llm_response = self.conversation.prompt(prompt, system=SYSTEM)
        for chunk in llm_response:
            self.app.call_from_thread(self._add_chunk, chunk)
        self.post_message(messages.WorkFinished())
