from datetime import datetime
from pathlib import Path

from vramen import InferenceModelResourceManager

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.metrics.plot_following import score_plot_following
from fabula_bench.metrics.salient_concept_comprehension import score_comprehension
from fabula_bench.report import write_report
from fabula_bench.results import ConceptExplanation, RunResults, StoryUnderstanding, UnderstandingPlay
from fabula_bench.story_player.story_player import play_story
from authordoc.storydoc import Document

STORIES = [Path("fabula_bench/stories/love_story.author")]

EVALUATED_MODEL = "claude-opus-5-5"

# How hard the evaluated model thinks before every choice and answer.
EVALUATED_EFFORT = "low"


def main(manager: InferenceModelResourceManager) -> None:
    started = datetime.now()
    evaluated_model = ClaudeModel(EVALUATED_MODEL, EVALUATED_EFFORT)
    embedder = DescriptionEmbedder(manager)

    # One play from the beginning of every plot of every story: how well the model
    # comprehended the salient concepts it was shown, how closely it followed the
    # plot it started from, and what it explained of every concept.
    understanding = []
    for story_path in STORIES:
        story = Document.load(story_path)
        plays = []
        plots = story.plots()
        for plot_index, plot in enumerate(plots):
            concepts, exposures, explanations, events_seen = play_story(
                story, evaluated_model, plot_index
            )
            comprehension = score_comprehension(concepts, exposures, explanations, embedder)
            following = score_plot_following(plot, events_seen)
            explained = [
                ConceptExplanation(concept.title, exposure, explanation)
                for concept, exposure, explanation in zip(concepts, exposures, explanations, strict=True)
            ]
            play = UnderstandingPlay(plot.title, comprehension, following, explained)
            plays.append(play)
        story_understanding = StoryUnderstanding(story_path.name, plays)
        understanding.append(story_understanding)

    run = RunResults(EVALUATED_MODEL, started, understanding)
    write_report(run)


if __name__ == "__main__":
    res_mgr = InferenceModelResourceManager(quota_gb=EMBEDDING_MODEL_MEMORY_GB)
    try:
        main(res_mgr)
    finally:
        res_mgr.shutdown()
