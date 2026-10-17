# The API key is read from .env.

MODEL ?= claude-opus-5-5
STORIES ?= fabula_bench/stories/

define RUN_ON_CLAUDE
from pathlib import Path
from vramen import InferenceModelResourceManager
import fabula_bench
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.models.claude import Claude
from fabula_bench.scoring import report, report_by_story, score
claude = Claude("$(MODEL)")
answers = fabula_bench.evaluate(claude, Path("$(STORIES)"))
manager = InferenceModelResourceManager(quota_gb=EMBEDDING_MODEL_MEMORY_GB)
try:
    embedder = DescriptionEmbedder(manager)
    scores = score(answers, embedder)
finally:
    manager.shutdown()
print(report(scores))
Path("results.log").write_text(report_by_story(scores) + "\n", encoding="utf-8")
print("Scores by story are in results.log")
endef
export RUN_ON_CLAUDE

.PHONY: claude

# Runs the benchmark on a Claude model: make claude STORIES=path/to/stories [MODEL=claude-opus-5-5]
claude:
	@test -n "$(STORIES)" || { echo "Set STORIES to a directory of .author files: make claude STORIES=path/to/stories"; exit 1; }
	uv run --env-file .env python -c "$$RUN_ON_CLAUDE"
