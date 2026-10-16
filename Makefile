# The API key is read from .env.

MODEL ?= claude-opus-5-5
STORIES ?= fabula_bench/stories/

define RUN_ON_CLAUDE
from pathlib import Path
import fabula_bench
from fabula_bench.models.claude import Claude
claude = Claude("$(MODEL)")
answers = fabula_bench.evaluate(claude, Path("$(STORIES)"))
for answer in answers:
    print(answer.story, answer.reply, sep="\n", end="\n\n")
endef
export RUN_ON_CLAUDE

.PHONY: claude

# Runs the benchmark on a Claude model: make claude STORIES=path/to/stories [MODEL=claude-opus-5-5]
claude:
	@test -n "$(STORIES)" || { echo "Set STORIES to a directory of .author files: make claude STORIES=path/to/stories"; exit 1; }
	uv run --env-file .env python -c "$$RUN_ON_CLAUDE"
