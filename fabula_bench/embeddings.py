"""How alike two descriptions are in meaning: the cosine similarity of their
embeddings (README, task 1).

The embedding model is a local model, so vramen deploys and manages it, under
the same memory quota as any local model being benchmarked.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
from vramen import EncoderModel, InferenceModelResourceManager

# vramen's encoder pools a passage from its last token, which is how this model
# is trained to be read.
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"

# What the model takes resident, declared against vramen's quota.
EMBEDDING_MODEL_MEMORY_GB = 2.0


class DescriptionEmbedder:
    def __init__(self, manager: InferenceModelResourceManager) -> None:
        self._encoder = EncoderModel(
            EMBEDDING_MODEL, manager, mem_required_gb=EMBEDDING_MODEL_MEMORY_GB
        )

    def cosine_similarities(
        self, labelled: Sequence[str], answered: Sequence[str]
    ) -> list[list[float]]:
        """The cosine similarity of every labelled description with every
        answered one: one row per labelled description, one column per
        answered description."""
        labelled_vectors = self._encoder.encode(labelled)
        answered_vectors = self._encoder.encode(answered)
        labelled_matrix = torch.as_tensor(labelled_vectors)
        answered_matrix = torch.as_tensor(answered_vectors)
        # vramen's vectors have unit length, so their dot product is the cosine
        # of the angle between them.
        similarity_matrix = labelled_matrix @ answered_matrix.T
        similarities: list[list[float]] = similarity_matrix.tolist()
        return similarities
