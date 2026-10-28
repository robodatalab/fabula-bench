"""These run the real embedding model through vramen; the first run downloads it."""

import unittest

import torch
from vramen import InferenceModelResourceManager

from fabula_bench.embeddings import EMBEDDING_MODEL_MEMORY_GB, DescriptionEmbedder

LABELLED = "Someone knocks when no one is expected, and is never seen."
PARAPHRASE = "A visitor nobody was waiting for knocks at the door and never shows themselves."
UNRELATED = "A widowed rancher faces down a cattle baron who has dammed the creek."


# vramen loads every model onto Apple's GPU, so the real model runs only where there is one.
@unittest.skipUnless(torch.backends.mps.is_available(), "vramen runs models only on Apple's MPS")
class CosineSimilarities(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manager = InferenceModelResourceManager(quota_gb=EMBEDDING_MODEL_MEMORY_GB)
        cls.embedder = DescriptionEmbedder(cls.manager)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.manager.shutdown()

    def test_compare_every_labelled_description_with_every_answered_one(self) -> None:
        similarities = self.embedder.cosine_similarities(
            [LABELLED, UNRELATED], [PARAPHRASE, UNRELATED, LABELLED]
        )

        row_lengths = [len(row) for row in similarities]
        self.assertEqual(row_lengths, [3, 3])

    def test_put_a_description_closest_to_itself(self) -> None:
        ((with_itself,),) = self.embedder.cosine_similarities([LABELLED], [LABELLED])

        self.assertAlmostEqual(with_itself, 1.0, places=2)

    def test_put_a_paraphrase_closer_than_a_description_of_something_else(self) -> None:
        ((with_the_paraphrase, with_something_else),) = self.embedder.cosine_similarities(
            [LABELLED], [PARAPHRASE, UNRELATED]
        )

        self.assertGreater(with_the_paraphrase, with_something_else)
