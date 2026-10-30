# fabula-bench

fabula-bench tests whether a model understands what it reads: whether it can model the concepts a story expresses without ever stating them, such as who its people are, what drives them, and what its events add up to. It does not test summarization. A model that summarizes can restate what it read; a model that understands knows what the story is about, including what the story never says.

## North star

*Since 2026-10-28. How the thinking got here, and why, is in the [research log](#research-log).*

The model plays an interactive story, and the stories are vast. One interactive story holds many full-fledged plots that mesh in a single world: a starship captain who gives her life for her daughter, the daughter left behind on Earth, a watcher on the Moon, but also a detective on Earth looking into a killing, a lawyer fighting a case, a boy who has fallen in love. Every scene ends with an unfinished sentence and a choice of endings, which lead on in the story being read or across into another one.

- **Following.** A model that does not understand what it reads jumps from scene to scene, and so from story to story. A model that understands follows the story it started reading, and when it strays from it by mistake, it tries to get back to it. The endings are offered in a random order in every scene, so that where an ending stands says nothing of where it leads: when the ending that went on in the story being read always came first, a model that answered 1 every time followed that story from its beginning to its end without understanding any of it.
- **Scoring.** When the play ends, we can see how closely the agent stuck to one, preferred plot, and how well it grasped the concepts that plot was based on.

### How a story is built

The plots of an interactive story form a densely interconnected graph. We build it by writing many individual plots, each a story in its own right, then finding the places where they can come into contact and adjusting their events so that the plots intersect there. On top of those, some edges between scenes belong to no plot at all: they are there to mislead. The scenes, and the choices that end them, are generated last.

The more plots one interactive story holds, and the more misleading edges, the easier it is for an agent to be derailed from the story it follows, and so the more it shows when an agent keeps to it.

### Plan

**More plots in one world.** New stories set in the world of `space_opera.author` and on its clock, so that they mesh with it and with one another.

- [x] A political drama: factions fighting over the extraction of resources in space.
- [x] A romance.
- [x] A detective story.
- [x] A courtroom drama.
- [x] The salient concepts each new story's plots pursue, general and story-specific.
- [x] Find the places where the plots can come into contact, and adjust their events so that the plots intersect there.
- [x] Mesh the stories into one world: an interactive story is a single `.author` document, so every plot is in `space_opera.author`.
- [ ] Decide how a misleading edge, one that belongs to no plot, is written, and add misleading edges.
- [ ] Add connections, scenes that lead into another plot at or near its beginning. Unlike misleading edges, they are meant to be followed.
- [x] Generate the scenes and choices of the meshed world.
- [ ] Annotate the salient concepts on the meshed world's scenes, `space_opera.author`'s included.
- [x] Start a play at the beginning of a chosen plot: the story player takes the plot's index among the story's plots, so that the agent can be run from every plot in turn. The high-level plots are notes that outline the plots, so every plot cell is one a play can start from.

**Authoring tool.** The way we write a story, from the author's plot ideas to its plots, concepts, scenes and choices, each step reviewed and revised by the author, as code in `story_generator`, with a text interface. It is a test of a feature for the authorship editor.

- [x] Design it: a workflow of stages, each run once the stages it depends on are done, each reviewed and revised by the author until accepted, drawn by a renderer that visits it, and reopened when the author goes back; the workflow's progress saved beside the story, so that it can be stopped and resumed.
- [ ] Build it, with a rudimentary text interface.

**Scoring.** We still measure exposure, and add the trajectory: which events the play visited, and whether, and how closely, they follow a plot.

- [ ] Record the events every play visits, in order.
- [ ] Measure how closely the visited events align with each plot: how many of the plot's events the play visited, in the plot's order, and how often the play left the plot and came back to it.
- [ ] Decide how to score the agent's grasp of the concepts of the plot it followed.
- [ ] Credit an agent that joins a plot partway: one that followed, say, 70% of a plot and correctly reported its concepts understood it, even without seeing its beginning.
- [ ] Save the trajectory and its alignment with every run.

## Running it

You need [uv](https://docs.astral.sh/uv/) and an Anthropic API key in a `.env` file at the root of the repository (`ANTHROPIC_API_KEY=...`). The embedding model runs locally, through vramen.

```
uv run --env-file .env python -m fabula_bench
```

Claude Opus 5.5 plays `fabula_bench/stories/space_opera.author` once from the beginning of each of its plots; both are set at the top of `fabula_bench/__main__.py`. Progress bars count the scenes played and the concepts asked. The results — the final scores, and for every play the plot it started from, every concept's exposure, similarities and score, and the model's explanations — are printed and saved to `runs/<when the run started>.txt`.

To play a story yourself, from the plot you choose:

```
uv run python -m fabula_bench.story_player
```

How the stories are written is described in [docs/developer.md](docs/developer.md).

## Research log

fabula-bench is a research project, and what it sets out to measure has changed as we learned. Each entry is a north star the benchmark has had: what it measured, and why we took it up.

One claim runs under all of them: language is a lossy projection of an internal state. Current models reproduce the surface of a text faithfully while dropping the structure it carried, and the benchmark makes that loss measurable.

### 2026-10-16: Read a story, recover what it never states

The model read a short story written for the benchmark and listed its salient concepts — the key characters, problems and facts, often never stated outright — with the passages that show each, and its causal plots, as ordered sequences of passages. Its answers were matched to labelled ones: descriptions by embedding cosine and character-trigram overlap, passages by an overlap of at least 80% each way. They were scored by precision, recall and F1.

**Why.** Nobody had annotated salience. Existing literary corpora label entities, events and narrative structure, not what a text is about.

### 2026-10-22: Explore an interactive world, solve its mystery

The story became a world for an agent to explore. A story is written as several plots and their salient concepts; each plot's events are stamped with a time and a place in the story, and plots overlap where their events meet. A narrator model described the scene at the agent's time and place as it played, the agent chose which causal edge to follow, and in the end it was to solve the story's mystery and present a plot. How to measure the results was left open.

**Why.** Not recorded at the time.

### 2026-10-27: Explain each concept the play revealed, weighted by how little it revealed

After the play, the agent was asked to explain each salient concept it had come across, by the concept's title. Each explanation was scored by its similarity to the concept's description, times one minus the concept's exposure: the share of the concept's passages the play showed.

**Why.** Playing rather than reading means the agent sees only part of the story, so the measure had to take into account how much of a concept the agent saw. Explaining a concept it saw only glimpses of is a hard win; failing to explain one it saw in full is a hard fail.

### 2026-10-28: Understanding, not summarization (current)

The north star [above](#north-star): an interactive story holds many full-fledged stories meshed in one world, with misleading edges among them, and an agent that understands follows the story it started and finds its way back when it strays. We score how closely it stuck to one preferred plot, and how well it grasped the concepts that plot was based on; how exactly is still up in the air.

**Why.** Asking the agent to explain concepts by their titles tested nothing a static text could not: a model given the whole story could answer just as well, so it measured summarization. The first full run also showed the model reading titles as names to look up in the text ("The word 'War' never actually appears in the story"). What playing adds is choice, and choice shows understanding: an agent that understands follows the story it is reading, and one that does not jumps between stories. A story packs many plots, and misleading edges, because the more there are, the easier it is for an agent to get derailed and stop following the plot it started.
