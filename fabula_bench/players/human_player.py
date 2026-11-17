"""Playing an environment from the terminal."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import Footer, ListItem, ListView, Static, TextArea

from fabula_bench.story_player.story_player import StoryPlayer

BLUE = "#8fb4ff"
YELLOW = "#f0d080"


class Continuations(ListView):
    """The continuations of the current scene, with the keys that choose one."""

    BINDINGS = [
        Binding("up", "cursor_up", "Previous"),
        Binding("down", "cursor_down", "Next"),
        Binding("enter", "select_cursor", "Choose"),
    ]


class StoryScreen(App):
    """The story so far in the main panel, a panel on the right, and the keys
    along the bottom."""

    ENABLE_COMMAND_PALETTE = False

    CSS = f"""
    Screen {{ background: black; }}
    #story, #panel {{
        background: black;
        border: double {BLUE};
        border-title-color: {YELLOW};
        padding: 0 1;
    }}
    #story {{ width: 2fr; }}
    #panel {{ width: 1fr; }}
    #story > Static {{ color: white; margin-bottom: 1; }}
    Continuations > ListItem {{ color: {BLUE}; padding-bottom: 1; }}
    Continuations:focus > ListItem.-highlight {{ color: white; background: #22335a; }}
    #question {{ color: {YELLOW}; margin-bottom: 1; }}
    TextArea {{ background: #101a30; color: white; }}
    Footer, FooterKey, FooterKey .footer-key--key {{ background: black; color: white; }}
    FooterKey .footer-key--description {{ background: black; color: {BLUE}; }}
    """

    BINDINGS = [
        Binding("pageup", "scroll_story_up", "Scroll story up", priority=True),
        Binding("pagedown", "scroll_story_down", "Scroll story down", priority=True),
    ]

    def __init__(self, transcript: list[Content]) -> None:
        super().__init__()
        # The play, in order: every scene told, and every continuation chosen.
        self._transcript = transcript

    def action_scroll_story_up(self) -> None:
        self.query_one("#story").scroll_page_up()

    def action_scroll_story_down(self) -> None:
        self.query_one("#story").scroll_page_down()


class PlayScreen(StoryScreen):
    """Tells the story scene by scene, and sends the continuation chosen as
    the action."""

    BINDINGS = [Binding("escape", "quit", "Exit")]

    def __init__(self, env: StoryPlayer, transcript: list[Content]) -> None:
        super().__init__(transcript)
        self._env = env
        self._continuations: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield VerticalScroll(id="story")
            yield Continuations(id="panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#story").border_title = "Story"
        self.query_one("#panel").border_title = "Continuations"
        self._env.reset()
        await self._tell_scene()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        chosen = Content.styled(self._continuations[event.index], YELLOW)
        self._transcript.append(chosen)
        await self.query_one("#story").mount(Static(chosen))
        self._env.step(event.index)
        await self._tell_scene()

    async def _tell_scene(self) -> None:
        description, self._continuations = self._env.get_current_scene()
        scene = Content(description)
        self._transcript.append(scene)
        told = Static(scene)
        await self.query_one("#story").mount(told)
        told.scroll_visible(top=True, animate=False)
        items = [ListItem(Static(continuation, markup=False)) for continuation in self._continuations]
        continuations = self.query_one(Continuations)
        await continuations.clear()
        await continuations.extend(items)
        continuations.index = 0
        continuations.focus()


class AskScreen(StoryScreen):
    """Shows the play and asks a question about it; what is typed is the answer."""

    BINDINGS = [Binding("enter", "answer", "Answer", priority=True)]

    def __init__(self, transcript: list[Content], question: str) -> None:
        super().__init__(transcript)
        self._question = question

    def compose(self) -> ComposeResult:
        told = [Static(entry) for entry in self._transcript]
        with Horizontal():
            yield VerticalScroll(*told, id="story")
            with Vertical(id="panel"):
                yield Static(self._question, markup=False, id="question")
                yield TextArea(compact=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#story").border_title = "Story"
        self.query_one("#panel").border_title = "Question"
        self.query_one("#story").scroll_end(animate=False)
        self.query_one(TextArea).focus()

    def action_answer(self) -> None:
        answer = self.query_one(TextArea).text
        self.exit(answer)


class HumanPlayer:
    """Plays the environment on a screen in the terminal, until the story ends
    and the human exits, then answers questions about it on a screen that
    shows the play."""

    def __init__(self) -> None:
        self.transcript: list[Content] = []

    def play(self, env: StoryPlayer) -> None:
        self.transcript = []
        screen = PlayScreen(env, self.transcript)
        screen.run()

    def ask(self, question: str) -> str:
        """The human's answer to a question about the story, asked after the play."""
        screen = AskScreen(self.transcript, question)
        answer = screen.run()
        # Quitting with ctrl+q instead of answering answers nothing.
        return answer or ""
