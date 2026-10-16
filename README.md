# fabula-bench

fabula-bench measures how well language models understand fiction. It tests two things:

1. **Salient information** — whether a model can identify the salient information in a story.
2. **Causal plots** — whether it can identify the story's causal plots.

## The stories

The benchmark is built on bespoke short stories. Most focus on one, two or three salient concepts; some simpler ones carry plots.

## Running the benchmark

> **What works today:** running the salient-information task on a Claude model, or on a model of your own, from Python. Every other case below is described but **not implemented yet**. The plot task is not implemented, because the `.author` format does not yet say how plots are annotated. Scoring is not implemented either, so a run gives you the model's replies, not a score.

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

A run takes a directory of `.author` files. Every story in it that has salient concepts annotated is asked the salient-information task. The model is given the story's prose and nothing else: the annotations never reach it.

### What a run gives you

`fabula_bench.evaluate` returns one `Answer` per story and task: the story's path, the task (`"salient-information"`), and the model's reply as text.

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

### An agent of your own

*Not implemented yet.* An agent — your own code around a model — will run in its own Docker container and serve a small HTTP API. The benchmark will send it one story's prose at a time and collect its replies. The agent's code never shares a container with the annotations, so nothing it runs can read them.
