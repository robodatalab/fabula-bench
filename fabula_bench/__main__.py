from datetime import datetime
from pathlib import Path

from vramen import InferenceModelResourceManager

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.metrics.plot_following import get_trajectories
from fabula_bench.metrics.salient_concept_comprehension import score_comprehension
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

    # One play from the beginning of every plot of the story: how well the model
    # comprehended the salient concepts it was shown, and the trajectories along
    # which it followed every plot it saw, each as the numbers of its events in
    # the plot; then what the model explained of every concept.
    plays = []
    plots = story.plots()
    for plot_index, plot in enumerate(plots):
        concepts, exposures, explanations, events_seen = play_story(story, evaluated_model, plot_index)
        comprehension = score_comprehension(concepts, exposures, explanations, embedder)
        trajectories_of_plots = get_trajectories(plots, events_seen)
        rows = [
            f"{STORY.name}, from {plot.title}",
            f"salient concept comprehension: {comprehension:.3f}",
            "plot following:",
        ]
        for followed, trajectories in zip(plots, trajectories_of_plots, strict=True):
            if not trajectories:
                continue
            numbers = {event.node_id: number for number, event in enumerate(followed.nodes, start=1)}
            written_trajectories = []
            for trajectory in trajectories:
                event_numbers = [str(numbers[event.node_id]) for event in trajectory]
                written_numbers = ", ".join(event_numbers)
                written_trajectories.append(f"[{written_numbers}]")
            written = ", ".join(written_trajectories)
            event_count = len(followed.nodes)
            rows.append(f"  {followed.title}: {written} of {event_count} events")
        for concept, exposure, explanation in zip(concepts, exposures, explanations, strict=True):
            rows.append(f"\n{concept.title} ({exposure:.0%} shown): {explanation}")
        play = "\n".join(rows)
        plays.append(play)
    results = "\n\n".join(plays)
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
