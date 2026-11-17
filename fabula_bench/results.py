from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConceptExplanation:
    concept: str  # the concept's title
    exposure: float
    explanation: str


@dataclass
class UnderstandingPlay:
    plot: str  # the title of the plot the play started from
    salient_concept_comprehension: float
    plot_following: float
    concepts: list[ConceptExplanation]


@dataclass
class StoryUnderstanding:
    story: str  # the story's file name, e.g. love_story.author
    plays: list[UnderstandingPlay]


@dataclass
class RunResults:
    model: str
    started: datetime
    understanding: list[StoryUnderstanding]
