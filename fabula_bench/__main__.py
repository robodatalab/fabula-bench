import argparse
import sys
from datetime import datetime
from pathlib import Path

import vramen
import yaml
from vramen import CausalModel, InferenceModelResourceManager

from fabula_bench.models.claude_model import ClaudeModel
from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder
from fabula_bench.metrics.plot_following import score_plot_following
from fabula_bench.metrics.salient_concept_comprehension import score_comprehension
from fabula_bench.players.agent_player import AgentPlayer
from fabula_bench.players.human_player import HumanPlayer
from fabula_bench.report import write_report
from fabula_bench.results import ConceptExplanation, RunResults, StoryUnderstanding, UnderstandingPlay
from fabula_bench.story_player.story_player import play_story
from authordoc.storydoc import Document


def make_agent(config: dict, manager: InferenceModelResourceManager) -> AgentPlayer | HumanPlayer:
    """The player an agent config describes: Claude, a local model vramen
    serves, or a human."""
    match config["agent"]:
        case "claude":
            model = ClaudeModel(config["model"], config["effort"])
            agent = AgentPlayer(model)
        case "vramen":
            prompt = getattr(vramen, config["prompt"])
            model = CausalModel(config["model"], prompt, manager, config["memory_gb"])
            agent = AgentPlayer(model)
        case "human":
            agent = HumanPlayer()
    return agent


def main(manager: InferenceModelResourceManager, config: dict, stories: list[Path]) -> None:
    started = datetime.now()
    agent = make_agent(config, manager)
    embedder = DescriptionEmbedder(manager)

    # One play from the beginning of every plot of every story: how well the agent
    # comprehended the salient concepts it was shown, how closely it followed the
    # plot it started from, and what it explained of every concept.
    understanding = []
    for story_path in stories:
        story = Document.load(story_path)
        plays = []
        plots = story.plots()
        for plot_index, plot in enumerate(plots):
            concepts, exposures, explanations, events_seen = play_story(story, agent, plot_index)
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

    # The model scored, or the human.
    scored = config.get("model", "human")
    run = RunResults(scored, started, understanding)
    write_report(run)


if __name__ == "__main__":
    argsparse = argparse.ArgumentParser()
    argsparse.add_argument("--story", type=str)
    argsparse.add_argument("--config", type=str)
    args = argsparse.parse_args()
    
    config_path = Path(args.config)
    config_text = config_path.read_text()

    stories = [Path(args.story)]

    agent_config = yaml.safe_load(config_text)
    # A local model is served beside the embedding model.
    quota_gb = EMBEDDING_MODEL_MEMORY_GB + agent_config.get("memory_gb", 0)
    res_mgr = InferenceModelResourceManager(quota_gb=quota_gb)
    try:
        main(res_mgr, agent_config, stories)
    finally:
        res_mgr.shutdown()
