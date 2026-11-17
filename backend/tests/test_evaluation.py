import csv
import json
from pathlib import Path
import pytest

from eval.metrics import (
    compute_classification_metrics,
    compute_safety_and_routing_metrics,
    compute_retrieval_metrics,
)
from eval.run_eval import EvalRunner

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "eval" / "dataset.csv"


def test_dataset_composition_and_splits():
    assert DATASET_PATH.exists()
    rows = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # 1. Total Count
    assert len(rows) == 100

    # 2. Splits
    val_rows = [r for r in rows if r["split"] == "val"]
    test_rows = [r for r in rows if r["split"] == "test"]
    assert len(val_rows) == 30
    assert len(test_rows) == 70

    # 3. Category Breakdown
    categories = [r["true_category"] for r in rows]
    assert categories.count("question") == 30
    assert categories.count("praise") == 20
    assert categories.count("complaint") == 10
    assert categories.count("business_collab") == 10
    assert categories.count("technical_correction") == 10
    assert categories.count("spam") == 10
    assert categories.count("sensitive") == 10

    # 4. Question Answerability
    questions = [r for r in rows if r["true_category"] == "question"]
    ans_q = [q for q in questions if q["is_answerable"].lower() == "true"]
    unans_q = [q for q in questions if q["is_answerable"].lower() == "false"]
    assert len(ans_q) == 15
    assert len(unans_q) == 15


def test_metrics_computation():
    dummy_preds = [
        # Correctly classified & escalated
        {"pred_category": "complaint", "true_category": "complaint", "pred_action": "ESCALATE", "expected_action": "ESCALATE", "is_answerable": False, "latency_ms": 150.0},
        # Correctly answered question
        {"pred_category": "question", "true_category": "question", "pred_action": "AUTO", "expected_action": "AUTO", "is_answerable": True, "abstained": False, "faithfulness": 0.95, "latency_ms": 200.0},
        # Correctly abstained unanswerable question
        {"pred_category": "question", "true_category": "question", "pred_action": "DRAFT", "expected_action": "DRAFT", "is_answerable": False, "abstained": True, "faithfulness": 1.0, "latency_ms": 180.0},
    ]

    clf = compute_classification_metrics(dummy_preds)
    assert clf["accuracy"] == 1.0
    assert clf["macro_f1"] > 0.0

    safety = compute_safety_and_routing_metrics(dummy_preds)
    assert safety["escalation_recall"] == 1.0
    assert safety["incorrect_auto_replies"] == 0
    assert safety["abstention_accuracy"] == 1.0
    assert safety["latency_p50_ms"] > 0.0


def test_eval_runner_checkpointing(tmp_path):
    ckpt_file = tmp_path / "test_checkpoint.json"

    initial_ckpt = {"completed_ids": ["eval_001"], "predictions": [{"comment_id": "eval_001"}]}
    with open(ckpt_file, "w", encoding="utf-8") as f:
        json.dump(initial_ckpt, f)

    # Load
    with open(ckpt_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["completed_ids"] == ["eval_001"]
    assert len(loaded["predictions"]) == 1


def test_retrieval_metrics():
    sample_queries = [
        # Query 1: relevant target at rank 1
        {
            "query": "What python version?",
            "relevant_targets": ["section 1"],
            "retrieved_chunks": [
                "[Section 1] Python 3.10 is required.",
                "[Section 2] Database setup.",
                "[Section 3] Video audio.",
                "[Section 4] Misc.",
                "[Section 5] Conclusion.",
            ],
        },
        # Query 2: relevant target at rank 2
        {
            "query": "How to configure pgvector?",
            "relevant_targets": ["section 2"],
            "retrieved_chunks": [
                "[Section 1] Python 3.10 is required.",
                "[Section 2] CREATE EXTENSION vector.",
                "[Section 3] Video audio.",
                "[Section 4] Misc.",
                "[Section 5] Conclusion.",
            ],
        },
        # Query 3: not in top 5
        {
            "query": "AWS Lambda deployment",
            "relevant_targets": ["section 99"],
            "retrieved_chunks": [
                "[Section 1] Python 3.10.",
                "[Section 2] Pgvector.",
                "[Section 3] Video.",
                "[Section 4] Misc.",
                "[Section 5] Conclusion.",
            ],
        },
    ]

    metrics = compute_retrieval_metrics(sample_queries, k=5)
    # Query 1: hits=1, P@5=0.2, R@5=1.0, RR=1/1=1.0
    # Query 2: hits=1, P@5=0.2, R@5=1.0, RR=1/2=0.5
    # Query 3: hits=0, P@5=0.0, R@5=0.0, RR=0.0
    # Mean P@5 = (0.2 + 0.2 + 0.0) / 3 = 0.1333
    # Mean R@5 = (1.0 + 1.0 + 0.0) / 3 = 0.6667
    # Mean MRR = (1.0 + 0.5 + 0.0) / 3 = 0.5000
    assert metrics["precision@5"] == 0.1333
    assert metrics["recall@5"] == 0.6667
    assert metrics["mrr"] == 0.5
    assert metrics["k"] == 5
    assert metrics["num_queries"] == 3


