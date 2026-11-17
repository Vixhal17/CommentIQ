#!/usr/bin/env python3
"""
Information Retrieval (IR) Evaluation Script:
Calculates Recall@k, Precision@k, and MRR (Mean Reciprocal Rank)
for the Hybrid Search (Dense Embeddings + BM25) retriever.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.session import SessionLocal, init_db
from backend.app.db.models import Video, TranscriptChunk
from backend.app.retrieval.retriever import ScopedRetriever
from eval.metrics import compute_retrieval_metrics


BENCHMARK_QUERIES = [
    {
        "query": "What python version is required for this setup?",
        "relevant_targets": ["section 1", "python 3.10", "page 1"],
        "expected_relevant_chunks": 1,
        "is_answerable": True,
    },
    {
        "query": "How do I configure the pgvector docker container?",
        "relevant_targets": ["section 2", "create extension", "page 2"],
        "expected_relevant_chunks": 1,
        "is_answerable": True,
    },
    {
        "query": "Can I deploy this on AWS Lambda or GCP Cloud Run?",
        "relevant_targets": [],  # Intentionally unanswerable (out of scope)
        "expected_relevant_chunks": 0,
        "is_answerable": False,
    },
]


def evaluate_retrieval_on_video(
    video_id: int,
    queries: Optional[List[Dict[str, Any]]] = None,
    k: int = 5,
) -> Dict[str, Any]:
    """
    Evaluates the Hybrid Search ScopedRetriever on a given video/document
    and computes Precision@k, Recall@k, and MRR.
    """
    db = SessionLocal()
    retriever = ScopedRetriever(db=db)
    test_queries = queries or BENCHMARK_QUERIES

    eval_data = []
    print(f"\n========================================================")
    print(f"  Hybrid Search Evaluation (k={k}) for Video ID: {video_id}")
    print(f"========================================================\n")

    for idx, q_item in enumerate(test_queries, start=1):
        q_text = q_item["query"]
        targets = q_item["relevant_targets"]

        chunks, top_score = retriever.retrieve(query=q_text, video_id=video_id, top_k=k)
        retrieved_texts = [f"{c.formatted_timestamp} {c.text}" for c in chunks]

        # Determine rank of first hit
        hit_rank = None
        for r, txt in enumerate(retrieved_texts, start=1):
            if any(t.lower() in txt.lower() for t in targets):
                hit_rank = r
                break

        print(f"Query {idx}: '{q_text}'")
        print(f"  Targets: {targets}")
        print(f"  Retrieved: {len(chunks)} chunks | First Hit Rank: {hit_rank if hit_rank else 'None (Miss)'} | Top Score: {top_score:.4f}")
        for r, c in enumerate(chunks, 1):
            is_match = any(t.lower() in f"{c.formatted_timestamp} {c.text}".lower() for t in targets)
            flag = "[RELEVANT]" if is_match else "[OTHER]"
            print(f"    Rank {r} {flag} {c.formatted_timestamp}: {c.text[:70]}...")
        print()

        eval_data.append({
            "query": q_text,
            "relevant_targets": targets,
            "retrieved_chunks": retrieved_texts,
        })

    metrics = compute_retrieval_metrics(eval_data, k=k)

    print("--------------------------------------------------------")
    print(f"  BENCHMARK RESULTS (k={k}):")
    print(f"  - Precision@{k}: {metrics.get(f'precision@{k}', 0.0):.4f} ({metrics.get(f'precision@{k}', 0.0)*100:.1f}%)")
    print(f"  - Recall@{k}:    {metrics.get(f'recall@{k}', 0.0):.4f} ({metrics.get(f'recall@{k}', 0.0)*100:.1f}%)")
    print(f"  - MRR:          {metrics.get('mrr', 0.0):.4f}")
    print(f"  - Total Answerable Queries Evaluated: {metrics.get('num_queries', 0)}")
    print("--------------------------------------------------------\n")

    return metrics


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    # Find latest video with indexed chunks
    v = db.query(Video).filter(Video.transcript_status.in_(["processed", "done"])).order_by(Video.id.desc()).first()
    if not v:
        v = db.query(Video).order_by(Video.id.desc()).first()
    
    if v:
        evaluate_retrieval_on_video(video_id=v.id, k=5)
    else:
        print("No videos/documents found in database. Run ingestion or upload a document first.")
