# The API key is read from .env.

MODEL ?= claude-opus-5-5
STORIES ?= fabula_bench/stories/

define RUN_ON_CLAUDE
from pathlib import Path
import fabula_bench
from fabula_bench.models.claude import Claude
claude = Claude("$(MODEL)")
answers = fabula_bench.evaluate(claude, Path("$(STORIES)"))
for story_answers in answers:
    print(story_answers.story)
    for concept in story_answers.concepts:
        example_count = len(concept.examples)
        print(f"  concept: {concept.title}: {concept.description} ({example_count} examples)")
    for plot in story_answers.plots:
        span_count = len(plot.spans)
        print(f"  plot: {plot.title}: {plot.description} ({span_count} spans)")
    for problem in story_answers.problems:
        print(f"  problem: {problem}")
    print()
endef
export RUN_ON_CLAUDE

.PHONY: claude

# Runs the benchmark on a Claude model: make claude STORIES=path/to/stories [MODEL=claude-opus-5-5]
claude:
	@test -n "$(STORIES)" || { echo "Set STORIES to a directory of .author files: make claude STORIES=path/to/stories"; exit 1; }
	uv run --env-file .env python -c "$$RUN_ON_CLAUDE"
