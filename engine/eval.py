"""Evaluation harness — all metrics from 07-EVALUATION-PROTOCOL.md.

Usage:
    python -m engine.eval --selftest          # emit baseline scorecard
    python -m engine.eval --week N            # score prediction for week N
    python -m engine.eval --backtest          # leave-one-week-out
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from engine.schemas import (
    EnglishQuestionsFile,
    LabelledFile,
    PredictionFile,
    RankedFile,
)


# ---------------------------------------------------------------------------
# Metric functions
# ---------------------------------------------------------------------------

def concept_recall_at_k(
    actual_concepts: set[str],
    predicted_concepts: list[str],
    k: int,
) -> float:
    """|A ∩ P_k| / |A|"""
    if not actual_concepts:
        return 0.0
    top_k = set(predicted_concepts[:k])
    return len(actual_concepts & top_k) / len(actual_concepts)


def concept_precision_at_k(
    actual_concepts: set[str],
    predicted_concepts: list[str],
    k: int,
) -> float:
    """|A ∩ P_k| / k"""
    if k == 0:
        return 0.0
    top_k = set(predicted_concepts[:k])
    return len(actual_concepts & top_k) / k


def weighted_recall(
    actual_concepts: set[str],
    predicted_concepts: list[str],
    concept_weights: dict[str, float],
    k: int,
) -> float:
    """Σ_{c∈A∩P_k} n_c / Σ_{c∈A} n_c"""
    top_k = set(predicted_concepts[:k])
    hit_weight = sum(concept_weights.get(c, 1.0) for c in actual_concepts & top_k)
    total_weight = sum(concept_weights.get(c, 1.0) for c in actual_concepts)
    if total_weight == 0:
        return 0.0
    return hit_weight / total_weight


def mean_reciprocal_rank(
    actual_concepts: set[str],
    predicted_concepts: list[str],
) -> float:
    """mean over c∈A of 1/rank(c), 0 if unranked."""
    if not actual_concepts:
        return 0.0
    rr_sum = 0.0
    for c in actual_concepts:
        try:
            rank = predicted_concepts.index(c) + 1
            rr_sum += 1.0 / rank
        except ValueError:
            pass
    return rr_sum / len(actual_concepts)


def brier_score(
    actual_concepts: set[str],
    predictions: list[tuple[str, float]],
) -> float:
    """mean( (p_c - y_c)^2 ) over all concepts."""
    pred_dict = {c: p for c, p in predictions}
    all_concepts = set(pred_dict.keys()) | actual_concepts
    if not all_concepts:
        return 0.0
    total = 0.0
    for c in all_concepts:
        y = 1.0 if c in actual_concepts else 0.0
        p = pred_dict.get(c, 0.0)
        total += (p - y) ** 2
    return total / len(all_concepts)


# ---------------------------------------------------------------------------
# Scorecard generation
# ---------------------------------------------------------------------------

def build_scorecard(
    target_week: int,
    concept_recall: dict[int, float],
    weighted_recall_30: float,
    brier: float,
    mrr: float,
    stage_metrics: dict[str, float] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a scorecard dict matching 07-EVALUATION-PROTOCOL.md format."""
    return {
        "target_week": target_week,
        "concept_recall": {f"@{k}": round(v, 4) for k, v in sorted(concept_recall.items())},
        "weighted_recall@30": round(weighted_recall_30, 4),
        "brier": round(brier, 4),
        "mrr": round(mrr, 4),
        "stage_metrics": stage_metrics or {},
        "warnings": warnings or [],
    }


def scorecard_to_markdown(card: dict[str, Any]) -> str:
    """Render scorecard as human-readable markdown."""
    lines = [
        f"SCORECARD -- target week {card['target_week']}",
        "",
        "PREDICTION",
    ]
    for k, v in card.get("concept_recall", {}).items():
        label = " <- HEADLINE" if k == "@30" else ""
        lines.append(f"  concept_recall{k}    {v:.4f}{label}")
    lines.append(f"  weighted_recall@30   {card.get('weighted_recall@30', 0):.4f}")
    lines.append(f"  brier                {card.get('brier', 0):.4f}")
    lines.append(f"  MRR                  {card.get('mrr', 0):.4f}")

    if card.get("stage_metrics"):
        lines.append("")
        lines.append("STAGE HEALTH")
        for k, v in card["stage_metrics"].items():
            lines.append(f"  {k:<30s}  {v}")

    if card.get("warnings"):
        lines.append("")
        lines.append("WARNINGS")
        for w in card["warnings"]:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Leakage assertions
# ---------------------------------------------------------------------------

def assert_no_leakage(
    held_out_week: int,
    feature_concepts: list[str],
    taxonomy_source: str = "books",
) -> list[str]:
    """Check for data leakage. Returns list of warnings (empty = clean)."""
    warnings = []
    # In a real backtest, we'd verify timestamps. Skeleton only.
    if taxonomy_source != "books":
        warnings.append(
            f"Taxonomy source is '{taxonomy_source}', expected 'books' — "
            "concepts derived from exam questions inflate recall"
        )
    return warnings


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def selftest() -> dict[str, Any]:
    """Emit a baseline scorecard with zero data — proves the harness runs."""
    card = build_scorecard(
        target_week=0,
        concept_recall={10: 0.0, 20: 0.0, 30: 0.0, 50: 0.0},
        weighted_recall_30=0.0,
        brier=0.0,
        mrr=0.0,
        warnings=["selftest — no data loaded"],
    )
    return card


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="prediction-engine eval")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true", help="emit baseline scorecard")
    group.add_argument("--week", type=int, help="score prediction for week N")
    group.add_argument("--backtest", action="store_true", help="leave-one-week-out")
    args = parser.parse_args()

    if args.selftest:
        card = selftest()
        print(scorecard_to_markdown(card))
        return

    # Future: load data, run scoring
    if args.week:
        print(f"Scoring week {args.week} — not yet implemented")
    if args.backtest:
        print("Backtest — not yet implemented")


if __name__ == "__main__":
    main()
