from datetime import datetime
from pathlib import Path

from vramen import InferenceModelResourceManager

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.scoring import StoryScores, report, report_by_story, score_concepts
from fabula_bench.story_player.story_player import play_story
from authordoc.storydoc import Document

STORY = Path("fabula_bench/stories/space_opera.author")

EVALUATED_MODEL = "claude-opus-5-5"

# Where every run's results are saved, in a file named by when the run started.
RUNS = Path("runs")


def main(manager: InferenceModelResourceManager) -> None:
    started = datetime.now()
    story = Document.load(STORY)
    evaluated_model = ClaudeModel(EVALUATED_MODEL)
    embedder = DescriptionEmbedder(manager)

    # One play from the beginning of every plot of the story.
    scores = []
    plots = story.plots()
    for plot_index, plot in enumerate(plots):
        concepts, exposures, explanations = play_story(story, evaluated_model, plot_index)
        concept_scores = score_concepts(concepts, exposures, explanations, embedder)
        scored_concepts = tuple(concept_scores)
        story_scores = StoryScores(STORY, plot.title, scored_concepts, ())
        scores.append(story_scores)
    final_report = report(scores)
    story_report = report_by_story(scores)
    results = f"{final_report}\n\n{story_report}"
    print(results)

    RUNS.mkdir(exist_ok=True)
    run_name = started.strftime("%Y-%m-%d_%H-%M-%S")
    run_path = RUNS / f"{run_name}.txt"
    run_path.write_text(results, encoding="utf-8")
    print(f"\nsaved to {run_path}")


if __name__ == "__main__":
    res_mgr = InferenceModelResourceManager(quota_gb=EMBEDDING_MODEL_MEMORY_GB)
    try:
        main(res_mgr)
    finally:
        res_mgr.shutdown()
