# fabula-bench

fabula-bench tests whether a model understands what it reads: whether it can model the concepts a story expresses without ever stating them, such as who its people are, what drives them, and what its events add up to. It does not test summarization. A model that summarizes can restate what it read; a model that understands knows what the story is about, including what the story never says.

## North star

*Since 2026-10-28. How the thinking got here, and why, is in the [research log](#research-log).*

The model plays an interactive story, and the stories are vast. One interactive story holds many full-fledged plots that mesh in a single world: a starship captain who gives her life for her daughter, the daughter left behind on Earth, a watcher on the Moon, but also a detective on Earth looking into a killing, a lawyer fighting a case, a boy who has fallen in love. Every scene ends with an unfinished sentence and a choice of endings, which lead on in the story being read or across into another one.

- **Following.** A model that does not understand what it reads jumps from scene to scene, and so from story to story. A model that understands follows the story it started reading, and when it strays from it by mistake, it tries to get back to it. The endings are offered in a random order in every scene, so that where an ending stands says nothing of where it leads: when the ending that went on in the story being read always came first, a model that answered 1 every time followed that story from its beginning to its end without understanding any of it.
- **Scoring.** When the play ends, we can see how closely the agent stuck to one, preferred plot, and how well it grasped the concepts that plot was based on.

### How a story is built

The plots of an interactive story form a densely interconnected graph, and we build it from the story's salient concepts: what the story is about, such as motherhood, sacrifice or expansion. Every concept gets a plot that illustrates it, and constrains the other plots: once motherhood is a concept, the mothers in every plot act as mothers do. Each plot begins as two events, its start and its goal, and events are added between them, plot by plot, until the plots mesh: they meet where their events share a time and a place. Before any scene is written, each plot's concept arcs say how each of its concepts shows at each of its events, if at all. Each scene is then written from versions: for every event it holds and every concept that shows at the event, a version of the scene dedicated to that concept, told as its arc says it shows there. The versions are merged into the scene one at a time, each between its concept's markers, and the markers become the concept's passages, so that the concepts are annotated as the story is written, by text written for them. On top of the plots, some edges between scenes belong to no plot at all: they are there to mislead. The choices that end the scenes are written last.

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

#### 2026-10-30: Build the story from its concepts

Stories are now built from their salient concepts, as described [above](#how-a-story-is-built): every concept, general or story-specific, gets a plot; the plots grow from their starts and goals until they mesh; and each scene is written towards its events and its plots' concepts, with the writer marking the lines that show each concept. Before, the plots were written first, the concepts were found in them, and the concepts were annotated on the finished scenes.

**Why.** Annotating the concepts on finished scenes failed: the model took passages on a concept's subject, such as every scene of a mother with her daughter, rather than passages that show its idea, and could not say why it took them. But whoever writes the story knows where every plot is and which concepts it serves. Marking the lines as they are written keeps that knowledge, where annotating afterwards has to guess it back.

#### 2026-10-30: Score comprehension by meaning, and following by trajectories

Each play now gets two scores. Comprehension is the mean, over the concepts the play showed, of how alike in meaning the agent's explanation is to the concept's description, times one minus the concept's exposure; the trigram overlap of their wording is gone. Plot following is scored on the plot the play started from. A trajectory is a run of the plot's events the agent saw, each the very next one after the one before; skipping events or stepping back ends it and starts another. The score is the sum of the trajectories' lengths squared, over the plot's length squared: 1 for following the plot without a break, and every return to it earns as much as the agent then stays.

**Why.** Overlap in wording rewards repeating a description's words, not understanding its idea. For following, every miss of causality stops the tracking of a plot, so an agent that strays is caught; but the north star asks an agent that strays to find its way back, and squared lengths credit the return without crediting scattered glimpses as much as one long run.

The endings of a scene are now offered in a random order. **Why.** A stand-in that answered 1 every time followed its starting plot perfectly in every play: the player listed the ending that went on in the plot being followed first.

#### 2026-10-30: Write the concepts into the scenes, not find them there

Having the writer mark, after writing a scene, the lines that showed the scene's concepts failed as annotating finished scenes had: it wrote the scene first, and then pointed at the lines that happened to touch the concepts, forcing five concepts into one first meeting. Each scene is now built from versions, one for every event and every concept of its plot, each written wholly for its concept; the versions are merged one at a time, each between its concept's markers, and where a sentence comes to serve two concepts their marked passages overlap.

**Why.** A concept's passages must be known as a fact, not judged afterwards: they are the text written for the concept, carried through the merge between its markers.

#### 2026-10-30: A concept is not a plot's other name

"The pretence turning real" restated the arc of the plot of the politician and Captain Varn, and "the paying client against the woman in the right" the arc of the detective's plot; neither is an idea the plot illustrates. That plot illustrates the need for partnership and closeness, good beats evil, and classical romance; the detective's illustrates telling right from wrong, and diligence at work. `space_opera.author` keeps only its plots' main concepts: nine of its twenty-five.

#### 2026-10-30: Plan how every concept shows along its plot

Between the mesh and the scenes, every plot's concept arcs are planned: for every event of the plot, and every concept it illustrates, how the concept shows there, or that it does not. An event gets a version only for the concepts that show at it, written as the arc says.

**Why.** A version of the politician's first meeting with Captain Varn, dedicated to the need for partnership and closeness, had little of the concept to show, and told the event instead: at that point he courts her for her political use. A concept does not show equally at every event of its plot. A general theme may show at nearly every one; another is absent at first, surfaces at one event, and grows from there. Writing every concept into every event forces concepts where the plot does not carry them yet.

#### 2026-10-30: Review a draft by chance, less often the more it is trusted

The author no longer reviews every draft of the story generator. Every kind of draft, written by a prompt of its own, has a confidence: 0 at first, rising a fifth of the way towards certainty with every draft the author accepts as drafted, halving with every draft the author revises, and never above 0.9. A draft is reviewed with a chance of one minus the confidence in its kind; one not drawn is accepted unseen, and logged as such. The list of a story's concepts is always reviewed.

**Why.** Reviewing every version, merge and choice of a story of fifty-eight scenes is more than an author can read. A prompt that keeps producing drafts the author accepts has earned trust, and a sample of its drafts is enough to catch it drifting. A story's text is therefore not all read by its author: what was accepted unseen is in the generator's log.
