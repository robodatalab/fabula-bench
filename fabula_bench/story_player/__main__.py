from pathlib import Path

from fabula_bench.story_player.exposure_tracker import ExposureTracker
from fabula_bench.players.human_player import HumanPlayer
from fabula_bench.story_player.story_player import StoryPlayer
from authordoc.storydoc import Document


def main() -> None:
    story = Document.load(Path("fabula_bench/stories/space_opera.author"))
    exposure_tracker = ExposureTracker(story)
    player = StoryPlayer(story, exposure_tracker)

    human = HumanPlayer()
    human.play(player)

    print("\nExposure to salient concepts:")
    for concept in exposure_tracker.concepts:
        seen_references = exposure_tracker.get_seen_references(concept)
        exposure = exposure_tracker.get_exposure(concept)
        print(f"  {concept.title}: {exposure:.0%} ({len(seen_references)} of {len(concept.references)} references)")



if __name__ == "__main__":
    main()
