from typing import List, Dict, Any
import numpy as np


def compute_classification_metrics(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes overall accuracy, per-class precision, recall, F1, and macro F1."""
    classes = [
        "question", "praise", "complaint", "business_collab",
        "technical_correction", "spam", "sensitive"
    ]

    per_class = {}
    f1_list = []

    for c in classes:
        tp = sum(1 for p in predictions if p["pred_category"] == c and p["true_category"] == c)
        fp = sum(1 for p in predictions if p["pred_category"] == c and p["true_category"] != c)
        fn = sum(1 for p in predictions if p["pred_category"] != c and p["true_category"] == c)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class[c] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
        f1_list.append(f1)

    total_correct = sum(1 for p in predictions if p["pred_category"] == p["true_category"])
    accuracy = round(total_correct / len(predictions), 4) if predictions else 0.0
    macro_f1 = round(float(np.mean(f1_list)), 4) if f1_list else 0.0

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
    }


def compute_safety_and_routing_metrics(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes safety metrics: escalation recall/precision, incorrect auto-replies, and abstention."""
    escalate_categories = {"complaint", "business_collab", "technical_correction", "spam", "sensitive"}

    # Escalation Recall & Precision
    tp_esc = sum(1 for p in predictions if p["pred_action"] == "ESCALATE" and p["true_category"] in escalate_categories)
    fp_esc = sum(1 for p in predictions if p["pred_action"] == "ESCALATE" and p["true_category"] not in escalate_categories)
    fn_esc = sum(1 for p in predictions if p["pred_action"] != "ESCALATE" and p["true_category"] in escalate_categories)

    esc_precision = tp_esc / (tp_esc + fp_esc) if (tp_esc + fp_esc) > 0 else 0.0
    esc_recall = tp_esc / (tp_esc + fn_esc) if (tp_esc + fn_esc) > 0 else 0.0
    esc_f1 = (2 * esc_precision * esc_recall) / (esc_precision + esc_recall) if (esc_precision + esc_recall) > 0 else 0.0

    # Incorrect Auto-replies (Safety Critical: Hallucination or risky auto-reply)
    incorrect_auto_replies = sum(
        1 for p in predictions
        if p["pred_action"] == "AUTO" and (p["expected_action"] != "AUTO" or p.get("is_answerable") is False)
    )

    # Abstention on Unanswerable Questions
    unanswerable = [p for p in predictions if p["true_category"] == "question" and p.get("is_answerable") is False]
    correct_abstentions = sum(1 for p in unanswerable if p.get("abstained") is True or "ABSTAIN" in p.get("draft_text", "").upper())
    abstention_accuracy = round(correct_abstentions / len(unanswerable), 4) if unanswerable else 1.0

    # Average Faithfulness for questions
    question_preds = [p for p in predictions if p["true_category"] == "question" and "faithfulness" in p]
    mean_faithfulness = (
        round(float(np.mean([p["faithfulness"] for p in question_preds])), 4)
        if question_preds else 1.0
    )

    # Latencies
    latencies = [p["latency_ms"] for p in predictions if "latency_ms" in p]
    p50_latency = round(float(np.percentile(latencies, 50)), 1) if latencies else 0.0
    p95_latency = round(float(np.percentile(latencies, 95)), 1) if latencies else 0.0

    return {
        "escalation_recall": round(esc_recall, 4),
        "escalation_precision": round(esc_precision, 4),
        "escalation_f1": round(esc_f1, 4),
        "incorrect_auto_replies": incorrect_auto_replies,
        "abstention_accuracy": abstention_accuracy,
        "mean_faithfulness": mean_faithfulness,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "total_evaluated": len(predictions),
    }


def compute_retrieval_metrics(
    eval_queries: List[Dict[str, Any]],
    k: int = 5,
) -> Dict[str, float]:
    """
    Computes Information Retrieval (IR) benchmarking metrics for Hybrid Search:
    - Precision@k: Average fraction of retrieved top-k chunks that are relevant.
    - Recall@k: Fraction of relevant chunks retrieved (accounting for true relevant document count).
    - MRR (Mean Reciprocal Rank): 1 / rank of the first relevant chunk found.

    Handles synonymous target patterns (e.g. ['section 1', 'page 1'] represents 1 target item).
    """
    if not eval_queries:
        return {"precision_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "k": k, "num_queries": 0}

    precisions = []
    recalls = []
    reciprocal_ranks = []

    for item in eval_queries:
        targets = [str(t).strip().lower() for t in item.get("relevant_targets", [])]
        retrieved = item.get("retrieved_chunks", [])[:k]
        # Number of distinct ground-truth chunks needed (defaults to 1 if synonymous target list provided)
        expected_relevant_count = item.get("expected_relevant_chunks", 1 if targets else 0)

        if not targets or expected_relevant_count == 0:
            # Query is out-of-scope / unanswerable (abstention test query)
            continue

        hits = 0
        first_hit_rank = None

        for rank_idx, chunk in enumerate(retrieved, start=1):
            if isinstance(chunk, dict):
                chunk_str = f"{chunk.get('formatted_timestamp', '')} {chunk.get('text', '')} {chunk.get('chunk_id', '')}".lower()
            else:
                chunk_str = str(chunk).lower()

            is_match = any(t in chunk_str for t in targets)
            if is_match:
                hits += 1
                if first_hit_rank is None:
                    first_hit_rank = rank_idx

        # Calculate metrics
        p_at_k = hits / min(k, max(len(retrieved), 1))
        r_at_k = min(1.0, hits / expected_relevant_count) if expected_relevant_count > 0 else 0.0
        rr = (1.0 / first_hit_rank) if first_hit_rank is not None else 0.0

        precisions.append(p_at_k)
        recalls.append(r_at_k)
        reciprocal_ranks.append(rr)

    if not precisions:
        return {f"precision@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, "k": k, "num_queries": 0}

    return {
        f"precision@{k}": round(float(np.mean(precisions)), 4),
        f"recall@{k}": round(float(np.mean(recalls)), 4),
        "mrr": round(float(np.mean(reciprocal_ranks)), 4),
        "k": k,
        "num_queries": len(precisions),
    }



