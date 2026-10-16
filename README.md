# fabula-bench

fabula-bench measures how well language models understand fiction. It tests two things:

1. **Salient information** — whether a model can identify the salient information in a story.
2. **Causal plots** — whether it can identify the story's causal plots.

## The stories

The benchmark is built on bespoke short stories. Most focus on one, two or three salient concepts; some simpler ones carry plots.

## The tasks and how they are measured

The model under test is given three tasks. Each is measured by counting true positives, false positives and false negatives against the labelled stories.

### 1. Salient concepts

The model reads the story and enumerates all its salient concepts, each with a brief explanation.

An answered concept is compared with the labelled concepts using embedding cosine similarity and n-gram similarity, to make sure the two speak of similar things.

- **True positive** — the concept's description matches a labelled concept's.
- **False positive** — the model invented a concept that is not in the labels.
- **False negative** — the model missed a labelled concept.

### 2. Examples of the concepts

The model identifies the places in the story that correspond to its concepts — the concepts' examples.

- **True positive** — a major (p80) overlap of a labelled example and the model's example.
- **False positive** — the model's example does not overlap a labelled one, or overlaps it only partially (below p80).
- **False negative** — the model missed an example that is in the labelled set.

**What p80 means.** For a labelled example of *n* words, the model's example overlaps it at p80 when at most 20% of the label's words are missing from the model's example, and at most 20% of the model's example's words are not in the label. Words are compared in order, ignoring case and punctuation: a word counts as shared only when it appears in both examples in the same order. For a 10-word labelled example, at most 2 words may differ each way.

Labelled example: *It is a beautiful day here in New York City*

| The model's example | Missing from it | Not in the label | p80 |
|---|---|---|---|
| A beautiful day here in New York City | It, is | — | yes |
| A beautiful day here in New York City for now. | It, is | for, now | yes |
| It is a beautiful day in New York | here, City | — | yes |
| A 100-word paragraph that contains the whole sentence | — | 90 words | no |

### 3. Plots

A plot is a special class of salient concept and shares its properties: a name and a description. Unlike a salient concept, it does not list examples of where it occurs. It lists, in order, the text spans that form it.

Those spans form a substory: copied out in the order the plot gives them, they read as a complete story — with stylistic or grammatical errors, but readable.

- **True positive** — the plot's description matches a labelled plot's (semantic similarity and n-gram similarity), and p80 of its sequence of spans matches the labelled plot's.
- **False positives and false negatives** follow as they do for salient concepts.

**What p80 means for a plot.** A plot holds two sequences: the sequence of its spans, and within each span, the sequence of its words. p80 is the same rule at both levels — the elements of the two sequences may differ by at most 20% each way, in order:

1. **Words within a span.** A model's span matches a labelled span when they are at p80 as defined for [examples](#2-examples-of-the-concepts).
2. **Spans within the plot.** The model's sequence of spans matches the labelled plot's when at most 20% of the labelled spans have no matching span in the model's plot, at most 20% of the model's spans have no matching span in the labelled plot, and the matched spans come in the same order. For a 10-span labelled plot, at most 2 spans may differ each way.

### How the results are reported

A run reports, for each task type, the true positives, false positives and false negatives, and the precision, recall and F1 computed from them:

- **Precision** = TP / (TP + FP) — of what the model said, how much was right.
- **Recall** = TP / (TP + FN) — of what is labelled, how much the model found.
- **F1** = 2·TP / (2·TP + FP + FN) — one number that balances the two.

Accuracy is not reported. It needs true negatives — what the model rightly did not say — and those cannot be counted: there is no fixed list of non-concepts in a story.

The totals add up the counts across all stories and compute the metrics from those sums. Below the totals, the same table for each story, with its own metrics. For example (the numbers are illustrative):

```
task              TP  FP  FN  precision  recall    F1
salient concepts  12   3   5       0.80    0.71  0.75
examples          40  18  22       0.69    0.65  0.67
plots              4   1   2       0.80    0.67  0.73
```

## Running the benchmark

> **What works today:** asking a Claude model, or a model of your own, all three tasks from Python, and reading its answers into the same shape as the labels. Every other case below is described but **not implemented yet**. Scoring is not implemented either, so a run gives you the model's answers beside the labels, not a score.

Find your case:

| You want to benchmark | How | Status |
|---|---|---|
| A Claude model | [`Claude`](#a-claude-model) | works |
| A model you are developing, in your own code | [subclass `Model`](#a-model-you-are-developing) | works |
| An OpenAI or Google model | [`openai:` / `google:`](#an-openai-or-google-model) | not implemented |
| A model served on your machine or another — Ollama, vLLM, llama.cpp, LM Studio | [a server URL](#a-model-served-on-your-machine-or-another) | not implemented |
| A model deployed on a cortexgrid cluster | [`cortexgrid:`](#a-model-deployed-on-cortexgrid) | not implemented |
| An agent of your own — your code around a model — kept isolated | [its own container](#an-agent-of-your-own) | not implemented |

### Installing

From a clone of this repository:

```
uv sync
```

### The stories

A run takes a directory of `.author` files. A story with salient concepts labelled (`salient-concept` cells) is asked for its salient concepts and their examples — tasks 1 and 2, in one answer. A story with plots labelled (`plot` cells, written like a salient concept but with their spans in the plot's order) is asked for its plots — task 3. The model is given the story's prose and nothing else: the labels never reach it. It answers in JSON, quoting examples and spans word for word.

### What a run gives you

`fabula_bench.evaluate` returns one `StoryAnswers` per story: the story's path, its labels, the concepts the model answered (each with a title, description and examples), the plots it answered (each with a title, description and spans), the model's replies as written, and any problems reading them. A reply that is not the JSON asked for gives no answers and says why in `problems`. Once scoring is implemented, a run will report its results as described in [How the results are reported](#how-the-results-are-reported).

### A Claude model

```python
from pathlib import Path

import fabula_bench
from fabula_bench.models.claude import Claude

claude = Claude("claude-opus-5-5")
answers = fabula_bench.evaluate(claude, Path("stories"))
```

`Claude` takes any model id the Anthropic API accepts. Credentials resolve as the Anthropic SDK resolves them: `ANTHROPIC_API_KEY`, then `ANTHROPIC_AUTH_TOKEN`, then an `ant auth login` profile. It sends up to four stories at once (`concurrency=`) and gives each reply up to 64,000 tokens (`max_tokens=`). If the model refuses a story, the run stops with an error naming the refusal.

### A model you are developing

You do not need to serve your model or put it behind an API. Subclass `fabula_bench.Model` and implement one method, `generate`. It receives a batch of conversations and returns one reply per conversation, in the same order. The benchmark does everything else: which stories to ask, the prompt, and collecting the replies.

```python
from pathlib import Path

import fabula_bench


class MyModel(fabula_bench.Model):
    def generate(self, conversations: list[list[fabula_bench.Turn]]) -> list[str]:
        ...  # run your model however you like


answers = fabula_bench.evaluate(MyModel(), Path("stories"))
```

A `Turn` has a `role` (`"user"` or `"assistant"`) and a `text`. There is no system turn and no sampling setting: whatever your model runs with is yours to set inside `generate`.

For example, a `transformers` model you already have in memory:

```python
class TransformersModel(fabula_bench.Model):
    def __init__(self, model, tokenizer, max_new_tokens=4096):
        self.model = model
        self.tokenizer = tokenizer
        self.max_new_tokens = max_new_tokens

    def generate(self, conversations):
        replies = []
        for conversation in conversations:
            messages = [{"role": turn.role, "content": turn.text} for turn in conversation]
            inputs = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_dict=True, return_tensors="pt"
            )
            inputs_on_device = inputs.to(self.model.device)
            output_ids = self.model.generate(**inputs_on_device, max_new_tokens=self.max_new_tokens)
            prompt_length = inputs_on_device["input_ids"].shape[1]
            reply_ids = output_ids[0, prompt_length:]
            reply = self.tokenizer.decode(reply_ids, skip_special_tokens=True)
            replies.append(reply)
        return replies
```

This one generates for one conversation at a time; batch them inside `generate` if your model can.

Because the model is an object in your own process, you can run the benchmark on a checkpoint straight from your training loop, without saving or serving it:

```python
for step in range(total_steps):
    train_one_step(model)
    if step % evaluate_every == 0:
        answers = fabula_bench.evaluate(TransformersModel(model, tokenizer), Path("stories"))
```

The tasks are instructions, so the model has to be able to follow them: an instruction-tuned model, not a base checkpoint partway through pretraining.

### An OpenAI or Google model

*Not implemented yet.* Each will be a class like `Claude`, calling that provider's public API with your API key.

### A model served on your machine or another

*Not implemented yet.* A model served by anything that speaks the OpenAI-compatible Chat Completions API — Ollama, vLLM, llama.cpp, LM Studio — will be reached by the server's URL, for example `http://localhost:11434/v1` for Ollama on your own machine. From inside a Docker container, your machine is `host.docker.internal` (on Linux, add `--add-host=host.docker.internal:host-gateway`).

If your model is only weights on disk, either serve it with one of those servers, or run it in your own process as [a model you are developing](#a-model-you-are-developing). On a Mac, Docker cannot use the GPU, so a local model has to run outside the container.

### A model deployed on cortexgrid

*Not implemented yet.* A model deployed on a cortexgrid cluster will be named by its registry key, `<family>/<suffix>`, optionally with the run whose trained weights to use. The benchmark will get the deployment's client with `cortexgrid.deploy_model(...).client()` — which reuses the deployment if it is already up — and call its `complete`.

That needs `cortexgrid-infer` installed, and so Python 3.11 and torch, and a connection to the cluster's head over the tailnet with `CORTEXGRID_HEAD_URL` set. cortexgrid's client reports no token counts.

###  User's local model

*Not implemented yet.* An agent — your own code around a model — will run in its own Docker container and serve a small HTTP API. The benchmark will send it one story's prose at a time and collect its replies. The agent's code never shares a container with the annotations, so nothing it runs can read them.
