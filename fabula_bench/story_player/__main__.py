from pathlib import Path

from vramen import CausalModel, InferenceModelResourceManager, qwen_chat_prompt

from fabula_bench.story_player.exposure_tracker import ExposureTracker
from fabula_bench.players.human_player import HumanPlayer
from fabula_bench.story_player.scene_descriptor import DESCRIPTION_MODEL, DESCRIPTION_MODEL_MEMORY_GB, SceneDescriptor
from fabula_bench.story_player.story_player import StoryPlayer
from authordoc.storydoc import Document


def main(manager: InferenceModelResourceManager) -> None:
    story = Document.load(Path("fabula_bench/stories/hostage.author"))
    exposure_tracker = ExposureTracker(story)
    narrator = CausalModel(DESCRIPTION_MODEL, qwen_chat_prompt, manager, mem_required_gb=DESCRIPTION_MODEL_MEMORY_GB)
    scene_descriptor = SceneDescriptor(narrator)
    player = StoryPlayer(story, exposure_tracker, scene_descriptor)

    human = HumanPlayer()
    human.play(player)

    print("\nExposure to salient concepts:")
    for concept in exposure_tracker.concepts:
        seen_references = exposure_tracker.get_seen_references(concept)
        exposure = exposure_tracker.get_exposure(concept)
        print(f"  {concept.title}: {exposure:.0%} ({len(seen_references)} of {len(concept.references)} references)")



if __name__ == "__main__":
    res_mgr = InferenceModelResourceManager(quota_gb=DESCRIPTION_MODEL_MEMORY_GB)
    try:
        main(res_mgr)
    finally:
        res_mgr.shutdown()
