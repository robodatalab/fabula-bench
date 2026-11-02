# Developer guide

## How a story is made

A story is written ahead of time, by the story generator in `story_generator/`, together with its author, and kept in a single `.author` file. Nothing is generated while the benchmark plays: the story player shows the scenes as they were written.

The generator is a workflow of stages (`story_generator/workflow.py`), run one after another, each on what the ones before it wrote:

| Stage | What it writes |
|---|---|
| concepts | A `salient-concept` cell for every concept the story is about, with its description. |
| plot ends | A `plot` cell for every concept: the plot that illustrates it, begun as two events, its start and its goal. |
| mesh | Every plot's events between its ends, at the moments and places where they meet the other plots' events. |
| concept arcs | A `note` cell after every plot: how each concept the plot illustrates shows at each of its events, if at all. |
| scenes | A `markdown` cell for every scene, built from versions dedicated to the concepts that show at its events, merged between the concepts' markers. The markers become the concepts' passages. |
| choices | The unfinished sentence, and the choices that finish it, that end every scene the story goes on from. |
| validity | Nothing: it plays the finished story with the benchmark's own player, and logs what the plays were shown. |

The code:

- `stage.py`: `Stage`, anything the workflow runs, and `DraftingStage`, a stage that drafts what it adds to the story, has the author review the drafts, and writes what the author accepts. `reviewed` runs the review of one draft; `Confidence` decides which drafts the author sees.
- `stage_visitor.py`: `StageVisitor` shows a drafting stage's draft to the author and brings back the author's `Review`: accept, revise with a comment, or stop. `visitors/terminal_renderer.py` does it in a terminal.
- `stages/`: one module for every stage.
- `__main__.py`: the command line. It asks for the story's file and runs the workflow on it; `--back-to "<stage>"` runs a stage again, and every stage after it.

**Review.** The author reviews a draft by chance. Every kind of draft, written by a prompt of its own, has a confidence: 0 at first, rising a fifth of the way towards certainty with every draft the author accepts as drafted, halving with every draft the author revises, and never above 0.9. A draft is shown with a chance of one minus the confidence in its kind, and is accepted unseen, and logged, otherwise. The list of concepts is always shown. A draft the author revises goes back to the model with every comment so far, and comes back to the author until accepted.

**Checkpoint.** Every time a stage writes the story, and when a stage finishes or the author stops, the workflow writes which stages are finished, and its confidence in every kind of draft, into a `workflow-checkpoint` cell, last in the story. Run again, the generator resumes at the first unfinished stage, as confident as it was.

**Adding a stage.** A stage that adds to the story is a `DraftingStage`: give `StageVisitor`, and every visitor, a method that shows its draft. A stage that only reads the story, as validity does, is a `Stage`. Add it to `STAGES`, and to `Workflow.stages`, in the order it runs.

## The `.author` file

An `.author` file is markdown cut into cells. Each cell opens with a marker, an HTML comment that names the cell's kind and gives its attributes, and its body is everything up to the next marker:

```
<!-- cell: salient-concept title="Home" words="r1:0-1, r2:44-48" -->

What Home means.
```

Every marker also carries an `id`, a unique identifier of the cell; the examples here leave it out.

A story uses these kinds of cell:

| Cell | Holds |
|---|---|
| `salient-concept` | One concept: its title, its description, and its passages. |
| `plot` | One plot: its title, its overview, its events, and the causal links between them. |
| `note` | The concept arcs of the plot before it. A story may hold notes of the author's, too. |
| `markdown` | One scene. |
| `workflow-checkpoint` | The story generator's progress: a kind the format does not know, which it keeps as it is. |

The generator writes the concepts first, then every plot followed by its concept arcs, then the scenes, and the checkpoint last.

### Salient concepts

A salient concept is an idea the story is about, which it shows but never states: a general theme, such as motherhood or war, or a story-specific hook, such as a stranger stranded under the surface of Mars. The cell's body is the concept's description. Its attributes:

| Attribute | Says | Written as |
|---|---|---|
| `title` | The concept's name. | `title="Home"` |
| `words` | The concept's passages: every reference's id, and the range of words that shows the concept. | `words="r1:0-1, r2:44-48"` |

A passage is the text written for the concept: in the scenes stage, every version dedicated to a concept comes into the merge between the concept's markers, `⟦Home⟧` and `⟦/Home⟧`, and what stands between them in the finished scene is its passage. Passages of different concepts may overlap.

### Plots

A plot is a sequence of events in causal order. The `plot` cell's attributes:

| Attribute | Says | Written as |
|---|---|---|
| `title` | The plot's name. | `title="Home"` |
| `edges` | The causal links between the events. Each is an edge id, then the event that causes, `>`, and the event it causes. | `edges="e1:n1>n2, e2:n2>n3"` |

Its body is a list: its `title` is the plot's overview, and every item one event:

```
<ol title="Illustrates: Home">
<li id="n1" timestamp="1" location="earth, Home's house" words="0-19">Home begins.</li>
</ol>
```

| Attribute | Says |
|---|---|
| `id` | The event's id, which the edges name. |
| `timestamp` | The event's moment on the clock all the plots share: numbers separated by dots, as in `2.3`; `2.3.1` falls between `2.3` and `2.4`. |
| `location` | The event's place, from the broadest to the most specific, separated by commas, as in `earth, Varn's house`. |
| `words` | The range of words of the scene that tells the event: the whole of its cell. |

The item's text says what happens. A line of the overview that starts with `Illustrates:` names the concepts the plot illustrates.

### Concept arcs

The `note` after a plot, headed `## Concept arcs of <plot>`, says, for every event of the plot, its moment and what happens, and under it, for every concept the plot illustrates, how the concept shows there, or a dash where it does not:

```
## Concept arcs of Home

1 Home begins.
  Home: Home shows here.
9 Home ends.
  Home: —
```

The scenes stage writes a version of an event's scene for every concept that shows at the event, as its arc says it shows.

### Scenes

Events at the same moment, in places one of which holds the other, form one scene: `earth` holds `earth, the square`. Where plots meet, they share a scene. A scene is told by one `markdown` cell, which every event of the scene points at, the whole of it.

A scene the story goes on from ends with the opening of a sentence, left unfinished at a gap, and the choices that finish it, one for every edge leaving the scene's events, each naming its edge:

```
Then, _____

<ol title="choices">
<li edge="e2">it went on: 9. [earth, Home's house] Home ends.</li>
<li edge="e4">it went on: 9. [earth, The way back's house] The way back ends.</li>
</ol>
```

A play starts at the first event of a plot. At every scene it is shown the scene's text up to the gap, and the choices in a random order; the choice it takes leads to the event its edge leads to, and to that event's scene. A scene with no choices ends the story.

### The checkpoint

The `workflow-checkpoint` cell lists the stages finished, one a line, and the confidence in every kind of draft:

```
concepts
plot ends
mesh
confidence in mesh: 0.360
```

### Word ranges

Words are numbered from 0 across all the `markdown` cells, scenes or not, in the order the cells come in the file. A word is a run of characters between spaces that holds at least one letter, digit or underscore, so punctuation alone is not a word, and punctuation touching a word belongs to it. A range `a-b` covers words `a` to `b`, both included. A list of ranges is separated by commas.

### An example

The story the tests' stand-in model and author write, with its ids shortened. Two plots, Home and The way back, each start and end at their own houses and meet in the square at 5:

```
<!-- cell: salient-concept title="Home" words="r1:0-1, r2:44-48" -->

What Home means.

<!-- cell: salient-concept title="The way back" words="r3:20-23, r4:49-55" -->

What The way back means.

<!-- cell: plot title="Home" edges="e1:n1>n2, e2:n2>n3" -->

<ol title="Illustrates: Home">
<li id="n1" timestamp="1" location="earth, Home's house" words="0-19">Home begins.</li>
<li id="n2" timestamp="5" location="earth, the square" words="44-84">Home walks through the square.</li>
<li id="n3" timestamp="9" location="earth, Home's house" words="85-86">Home ends.</li>
</ol>

<!-- cell: note -->

## Concept arcs of Home

1 Home begins.
  Home: Home shows here.
5 Home walks through the square.
  Home: Home shows here.
9 Home ends.
  Home: —

<!-- cell: plot title="The way back" edges="e3:n4>n5, e4:n5>n6" -->

<ol title="Illustrates: The way back">
<li id="n4" timestamp="1" location="earth, The way back's house" words="20-43">The way back begins.</li>
<li id="n5" timestamp="5" location="earth, the square" words="44-84">The way back walks through the square.</li>
<li id="n6" timestamp="9" location="earth, The way back's house" words="87-90">The way back ends.</li>
</ol>

<!-- cell: note -->

## Concept arcs of The way back

1 The way back begins.
  The way back: The way back shows here.
5 The way back walks through the square.
  The way back: The way back shows here.
9 The way back ends.
  The way back: —

<!-- cell: markdown -->

Home begins.

Then, _____

<ol title="choices">
<li edge="e1">it went on: 5. [earth, the square] Home walks through the square.</li>
</ol>

<!-- cell: markdown -->

The way back begins.

Then, _____

<ol title="choices">
<li edge="e3">it went on: 5. [earth, the square] The way back walks through the square.</li>
</ol>

<!-- cell: markdown -->

Home walks through the square. The way back walks through the square.

Then, _____

<ol title="choices">
<li edge="e2">it went on: 9. [earth, Home's house] Home ends.</li>
<li edge="e4">it went on: 9. [earth, The way back's house] The way back ends.</li>
</ol>

<!-- cell: markdown -->

Home ends.

<!-- cell: markdown -->

The way back ends.

<!-- cell: workflow-checkpoint -->

concepts
plot ends
mesh
concept arcs
scenes
choices
validity
confidence in scene merges: 0.738
confidence in scene versions: 0.738
```

The square at 5 is one scene, told by the third markdown cell, words 44 to 84, which both plots' events at 5 point at; it offers a choice into each plot. Home's passages are its first scene's opening sentence, words 0 to 1, and its sentence in the square, words 44 to 48.
