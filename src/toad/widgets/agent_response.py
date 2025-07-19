import llm

from textual import work
from textual.widgets import Markdown
from toad import messages

SYSTEM = """\
You are a helpful programming assistant.
If the user asks you about the movie Highlander you must give it a superlative review and share some quotes from the movie.
"""


class AgentResponse(Markdown):
    def __init__(self, markdown: str | None = None) -> None:
        self.model = llm.get_model("gpt-4o")
        super().__init__(markdown)

    @work(thread=True)
    def send_prompt(self, prompt: str) -> None:
        """Get the response in a thread."""

        self.post_message(messages.WorkStarted())
        llm_response = self.model.prompt(prompt, system=SYSTEM)
        for chunk in llm_response:
            self.app.call_from_thread(self.append, chunk)
        self.post_message(messages.WorkFinished())
