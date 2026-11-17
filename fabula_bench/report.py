from pathlib import Path
from statistics import mean

from fabula_bench.results import RunResults, StoryUnderstanding, UnderstandingPlay

# Where every run's results are saved, in a file named by when the run started.
RUNS = Path("runs")


def understanding_scores(plays: list[UnderstandingPlay]) -> tuple[float, float]:
    comprehensions = [play.salient_concept_comprehension for play in plays]
    followings = [play.plot_following for play in plays]
    comprehension = mean(comprehensions)
    following = mean(followings)
    return comprehension, following


def understanding_table(plays: list[UnderstandingPlay]) -> str:
    comprehension, following = understanding_scores(plays)
    return (
        "| salient concept comprehension | plot following |\n"
        "| --- | --- |\n"
        f"| {comprehension:.3f} | {following:.3f} |"
    )


def understanding_section(stories: list[StoryUnderstanding]) -> str:
    sections = ["# understanding"]
    for story in stories:
        story_table = understanding_table(story.plays)
        sections += [f"## {story.story}", story_table]
        for play in story.plays:
            play_table = understanding_table([play])
            sections += [f"### {play.plot}", play_table]
            for explained in play.concepts:
                sections.append(
                    f"#### {explained.concept} ({explained.exposure:.0%} shown)\n\n{explained.explanation}"
                )
    section = "\n\n".join(sections)
    return section


def write_report(run: RunResults) -> None:
    """Print the results of a run as Markdown and save them to RUNS.

    A story's scores are the average of its plays', a task's the average of
    every play's.
    """
    every_play = [play for story in run.understanding for play in story.plays]
    comprehension, following = understanding_scores(every_play)
    run_table = (
        "| task | metric | score |\n"
        "| --- | --- | --- |\n"
        f"| understanding | salient concept comprehension | {comprehension:.3f} |\n"
        f"| understanding | plot following | {following:.3f} |"
    )
    understanding = understanding_section(run.understanding)
    report = f"model: {run.model}\n\n{run_table}\n\n{understanding}\n"
    print(report)

    RUNS.mkdir(exist_ok=True)
    run_name = run.started.strftime("%Y-%m-%d_%H-%M-%S")
    run_path = RUNS / f"{run_name}.md"
    run_path.write_text(report, encoding="utf-8")
    print(f"saved to {run_path}")
