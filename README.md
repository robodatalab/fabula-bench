# fabula-bench

fabula-bench tests whether a model grasps what a story is about from the part of it the model gets to see. The model plays an interactive story: every scene ends with an unfinished sentence and a choice of endings, each leading the story somewhere else. When the story ends, the model is asked to explain the story's salient concepts that it came across on the way.

## What it measures

A story's salient concepts are of two kinds: the general themes it is built on, such as motherhood or war, and the concepts specific to the story that keep a reader wanting to learn more, such as a strange object found buried under Mars. Each concept is annotated on the passages of the story that show it.

For every concept the play showed, in full or in part:

- **exposure** is the share of the concept's passages the model saw;
- **similarity** is how alike the model's explanation is to the concept's description, measured twice: by the cosine of their embeddings, and by their character trigrams;
- **score** is similarity × (1 − exposure), so explaining a concept from a glimpse of it counts for more than explaining one seen in full.

The benchmark reports the mean and the standard deviation of the scores, for each similarity, over every concept asked.

## Running it

You need [uv](https://docs.astral.sh/uv/) and an Anthropic API key in a `.env` file at the root of the repository (`ANTHROPIC_API_KEY=...`). The embedding model runs locally, through vramen.

```
uv run --env-file .env python -m fabula_bench
```

Claude Opus 5.5 plays `fabula_bench/stories/hostage.author`; both are set at the top of `fabula_bench/__main__.py`. Progress bars count the scenes played and the concepts asked. The results — the final scores, every concept's exposure, similarities and score, and the model's explanations — are printed and saved to `runs/<when the run started>.txt`.

To play a story yourself:

```
uv run python -m fabula_bench.story_player
```

How the stories are written is described in [docs/developer.md](docs/developer.md).
