# Developer guide

## How an adventure is made

An adventure is built around its salient concepts and its plots, and those are written first. We write them down, very specifically, in an `.author` file: each plot, and how the plots overlap and interact. The story itself is not written. At runtime a model generates it from the `.author` file as the agent explores.

## The `.author` file

An `.author` file is markdown cut into cells. Each cell opens with a marker — an HTML comment that names the cell's kind and gives its attributes — and its body is everything up to the next marker:

```
<!-- cell: salient-concept title="The shed key" words="4-13, 39-44" -->

The only key to the garden shed, kept on a hook by the back door.
```

Every marker also carries an `id`, a unique identifier of the cell; the examples here leave it out.

An adventure uses four kinds of cell:

| Cell | Holds |
|---|---|
| `title-page` | The adventure's title. |
| `salient-concept` | One salient concept: its title, its description, and the places in the plots' details that show it. |
| `plot` | One plot: its title, its abstract, its events and the causal links between them. |
| `markdown` | The details of one plot. |

They come in this order: the title page, then the salient concepts, then the plots, each `plot` cell followed by its own `markdown` cell.

### Plots

A plot is written in two cells:

1. **The `plot` cell.** Its body is the plot's abstract: a general description of the plot.
2. **Its `markdown` cell.** It holds the plot's details: specific enough that each can be used as an event in the agent's trajectory. Every plot has a markdown cell of its own, and every markdown cell belongs to one plot.

The `plot` cell's attributes:

| Attribute | Says | Written as |
|---|---|---|
| `title` | The plot's name. | `title="The borrowed key"` |
| `nodes` | The plot's events, in order. Each is a node id and the range of words in the plot's markdown cell that tells the event. | `nodes="n1:0-15, n2:16-30"` |
| `edges` | The causal links between the events. Each is an edge id, then the node that causes, `>`, and the node it causes. | `edges="e1:n1>n2"` |

### Salient concepts

A salient concept is the idea of something in the adventure, not its name. There are four kinds:

| Kind | Its idea |
|---|---|
| Character | Who they are, their motives, goals and fears, and what they are doing. |
| Place | What the place is and what happens there. |
| Object | What the object is, where it is, and what it means to the plots. |
| Hidden fact | A truth about the world that is not apparent and that the agent has to uncover. |

The `salient-concept` cell's body is the description of that idea. Its attributes:

| Attribute | Says | Written as |
|---|---|---|
| `title` | The concept's name. | `title="Ada"` |
| `words` | The ranges of words, in the plots' markdown cells, that show the concept. | `words="2-15, 16-30"` |

Salient concepts are annotated directly on the plots' markdown cells. A range shows the concept's idea — for a character, behaviour that reveals a motive — and is never a span that merely names it. A range may be part of a sentence, ranges of different concepts may overlap, and one concept may have ranges in several plots' details. That is how plots overlap: they share the characters, places, objects and hidden facts annotated on their details.

### Word ranges

Words are numbered from 0 across all the markdown cells, in the order the cells come in the file. A word is a run of characters between spaces that holds at least one letter or digit, so punctuation alone is not a word, and punctuation touching a word belongs to it. A range `a-b` covers words `a` to `b`, both included. A list of ranges is separated by commas.

### An example

Two plots that share an object and a place:

```
<!-- cell: title-page title="The Shed Key" -->

<!-- cell: salient-concept title="Ada" words="2-15, 16-30" -->

Takes what she wants without asking, and says nothing when she loses it.

<!-- cell: salient-concept title="Tom" words="33-44, 45-48" -->

Finds the shed key gone and blames the gardener rather than his own household.

<!-- cell: salient-concept title="The shed key" words="4-13, 39-44" -->

The only key to the garden shed, kept on a hook by the back door.

<!-- cell: salient-concept title="The orchard" words="19-30, 49-57" -->

The plum orchard behind the house, where the grass grows long.

<!-- cell: salient-concept title="The key in the grass" words="16-25" -->

The key was never stolen: it lies in the orchard grass where Ada dropped it.

<!-- cell: plot title="The borrowed key" nodes="n1:0-15, n2:16-30" edges="e1:n1>n2" -->

Ada borrows the shed key without asking and loses it in the orchard.

<!-- cell: markdown -->

On Sunday Ada took the shed key from its hook by the back door without asking.

She dropped it in the long grass of the orchard while she was picking plums.

<!-- cell: plot title="The locked shed" nodes="n1:31-44, n2:45-57" edges="e2:n1>n2" -->

Tom finds the shed locked and blames the gardener.

<!-- cell: markdown -->

On Monday Tom found the shed locked and the key gone from its hook.

He accused the gardener, who had been working in the orchard all week.
```

The words of the first markdown cell are numbered 0 to 30 and those of the second 31 to 57. The shed key and the orchard are annotated on both plots' details, and the hidden fact — where the key really is — is what the agent has to uncover to explain why the shed is locked.
