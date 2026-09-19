"""Tests for engine.eval — metric functions and selftest."""
from __future__ import annotations

import pytest

from engine.eval import (
    brier_score,
    build_scorecard,
    concept_precision_at_k,
    concept_recall_at_k,
    mean_reciprocal_rank,
    scorecard_to_markdown,
    selftest,
    weighted_recall,
)


class TestConceptRecallAtK:
    def test_perfect(self):
        assert concept_recall_at_k({"a", "b", "c"}, ["a", "b", "c", "d"], 3) == 1.0

    def test_partial(self):
        assert concept_recall_at_k({"a", "b", "c"}, ["a", "x", "c", "y"], 3) == pytest.approx(2 / 3)

    def test_empty_actual(self):
        assert concept_recall_at_k(set(), ["a", "b"], 10) == 0.0

    def test_k_larger_than_list(self):
        assert concept_recall_at_k({"a"}, ["a"], 100) == 1.0


class TestConceptPrecisionAtK:
    def test_perfect(self):
        assert concept_precision_at_k({"a"}, ["a", "b", "c"], 1) == 1.0

    def test_diluted(self):
        assert concept_precision_at_k({"a"}, ["a", "b", "c"], 3) == pytest.approx(1 / 3)

    def test_k_zero(self):
        assert concept_precision_at_k({"a"}, [], 0) == 0.0


class TestWeightedRecall:
    def test_equal_weights(self):
        wr = weighted_recall({"a", "b"}, ["a", "x"], {"a": 1.0, "b": 1.0}, 2)
        assert wr == pytest.approx(0.5)

    def test_unequal_weights(self):
        wr = weighted_recall({"a", "b"}, ["a"], {"a": 3.0, "b": 1.0}, 1)
        assert wr == pytest.approx(0.75)


class TestMRR:
    def test_first_rank(self):
        assert mean_reciprocal_rank({"a"}, ["a", "b", "c"]) == pytest.approx(1.0)

    def test_second_rank(self):
        assert mean_reciprocal_rank({"a"}, ["x", "a", "c"]) == pytest.approx(0.5)

    def test_not_found(self):
        assert mean_reciprocal_rank({"z"}, ["a", "b", "c"]) == 0.0

    def test_multiple_concepts(self):
        mrr = mean_reciprocal_rank({"a", "c"}, ["a", "b", "c", "d"])
        assert mrr == pytest.approx((1.0 + 1 / 3) / 2)


class TestBrier:
    def test_perfect(self):
        assert brier_score({"a"}, [("a", 1.0)]) == pytest.approx(0.0)

    def test_worst(self):
        assert brier_score({"a"}, [("a", 0.0)]) == pytest.approx(1.0)


class TestSelftest:
    def test_runs(self):
        card = selftest()
        assert card["target_week"] == 0
        assert "selftest" in card["warnings"][0]

    def test_markdown_renders(self):
        card = selftest()
        md = scorecard_to_markdown(card)
        assert "SCORECARD" in md
        assert "concept_recall@30" in md
