from pathlib import Path

from vramen import CausalModel, InferenceModelResourceManager, qwen_chat_prompt

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.scoring import StoryScores, report, report_by_story, score_concepts
from fabula_bench.story_player.scene_descriptor import DESCRIPTION_MODEL, DESCRIPTION_MODEL_MEMORY_GB
from fabula_bench.story_player.story_player import play_story
from authordoc.storydoc import Document

STORY = Path("fabula_bench/stories/hostage.author")

EVALUATED_MODEL = "claude-opus-5-5"


def main(manager: InferenceModelResourceManager) -> None:
    story = Document.load(STORY)
    evaluated_model = ClaudeModel(EVALUATED_MODEL)
    narrator_model = CausalModel(DESCRIPTION_MODEL, qwen_chat_prompt, manager, mem_required_gb=DESCRIPTION_MODEL_MEMORY_GB)
    embedder = DescriptionEmbedder(manager)

    concepts, exposures, explanations = play_story(story, evaluated_model, narrator_model)
    concept_scores = score_concepts(concepts, exposures, explanations, embedder)

    scored_concepts = tuple(concept_scores)
    story_scores = StoryScores(STORY, scored_concepts, ())
    scores = [story_scores]
    print(report(scores))
    print()
    print(report_by_story(scores))


if __name__ == "__main__":
    res_mgr = InferenceModelResourceManager(quota_gb=DESCRIPTION_MODEL_MEMORY_GB + EMBEDDING_MODEL_MEMORY_GB)
    try:
        main(res_mgr)
    finally:
        res_mgr.shutdown()
