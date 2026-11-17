"""Playing an environment from the terminal."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, ListItem, ListView, Static

from fabula_bench.story_player.story_player import StoryPlayer

BLUE = "#8fb4ff"


class Continuations(ListView):
    """The continuations of the current scene, with the keys that choose one."""

    BINDINGS = [
        Binding("up", "cursor_up", "Previous"),
        Binding("down", "cursor_down", "Next"),
        Binding("enter", "select_cursor", "Choose"),
    ]


class PlayScreen(App):
    """The story so far in the main panel, the continuations of its current
    scene in the panel on the right, and the keys along the bottom. The
    continuation chosen is the action."""

    ENABLE_COMMAND_PALETTE = False

    CSS = f"""
    Screen {{ background: black; }}
    #story, Continuations {{
        background: black;
        border: double {BLUE};
        border-title-color: #f0d080;
        padding: 0 1;
    }}
    #story {{ width: 2fr; }}
    Continuations {{ width: 1fr; }}
    .scene {{ color: white; margin-bottom: 1; }}
    .chosen {{ color: #f0d080; margin-bottom: 1; }}
    Continuations > ListItem {{ color: {BLUE}; padding-bottom: 1; }}
    Continuations:focus > ListItem.-highlight {{ color: white; background: #22335a; }}
    Footer, FooterKey, FooterKey .footer-key--key {{ background: black; color: white; }}
    FooterKey .footer-key--description {{ background: black; color: {BLUE}; }}
    """

    BINDINGS = [
        Binding("pageup", "scroll_story_up", "Scroll story up", priority=True),
        Binding("pagedown", "scroll_story_down", "Scroll story down", priority=True),
        Binding("escape", "quit", "Exit"),
    ]

    def __init__(self, env: StoryPlayer) -> None:
        super().__init__()
        self._env = env
        self._continuations: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield VerticalScroll(id="story")
            yield Continuations()
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#story").border_title = "Story"
        self.query_one(Continuations).border_title = "Continuations"
        self._env.reset()
        await self._tell_scene()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        chosen = Static(self._continuations[event.index], markup=False, classes="chosen")
        await self.query_one("#story").mount(chosen)
        self._env.step(event.index)
        await self._tell_scene()

    async def _tell_scene(self) -> None:
        description, self._continuations = self._env.get_current_scene()
        scene = Static(description, markup=False, classes="scene")
        await self.query_one("#story").mount(scene)
        scene.scroll_visible(top=True, animate=False)
        items = [ListItem(Static(continuation, markup=False)) for continuation in self._continuations]
        continuations = self.query_one(Continuations)
        await continuations.clear()
        await continuations.extend(items)
        continuations.index = 0
        continuations.focus()

    def action_scroll_story_up(self) -> None:
        self.query_one("#story").scroll_page_up()

    def action_scroll_story_down(self) -> None:
        self.query_one("#story").scroll_page_down()


class HumanPlayer:
    """Plays the environment on a screen in the terminal, until the story ends
    and the human exits."""

    def play(self, env: StoryPlayer) -> None:
        screen = PlayScreen(env)
        screen.run()
