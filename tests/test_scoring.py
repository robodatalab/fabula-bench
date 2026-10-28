import unittest

from fabula_bench.scoring import trigram_similarity


class TrigramSimilarity(unittest.TestCase):
    def test_is_one_for_the_same_text_whatever_its_case_and_spacing(self) -> None:
        similarity = trigram_similarity("The  Front door", "the front DOOR")

        self.assertEqual(similarity, 1.0)

    def test_is_zero_for_texts_that_share_no_trigram(self) -> None:
        similarity = trigram_similarity("abc", "xyz")

        self.assertEqual(similarity, 0.0)
