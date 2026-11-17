from typing import List, Tuple, Optional
import re
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from pydantic import BaseModel

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

from backend.app.db.models import TranscriptChunk, Video
from backend.app.retrieval.embeddings import get_embedding_engine, EmbeddingEngine
from backend.app.retrieval.chunker import Chunk
from backend.app.core.logging import logger


class RetrievedChunk(BaseModel):
    chunk_id: int
    text: str
    start_time: float
    formatted_timestamp: str
    similarity_score: float


class ScopedRetriever:
    """
    Retrieves knowledge chunks scoped strictly to the comment's video_id.
    Prevents cross-video hallucinations and guarantees grounding.
    """

    def __init__(self, db: Session, embedding_engine: Optional[EmbeddingEngine] = None):
        self.db = db
        self.embedder = embedding_engine or get_embedding_engine()

    def index_video_chunks(self, video_id: int, chunks: List[Chunk]) -> int:
        """
        Embeds and stores chunks for a specific video into transcript_chunks.
        """
        if not chunks:
            return 0

        # Delete existing chunks for this video to ensure idempotency
        existing_chunks = self.db.scalars(
            select(TranscriptChunk).where(TranscriptChunk.video_id == video_id)
        ).all()
        for ec in existing_chunks:
            self.db.delete(ec)
        self.db.flush()

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_batch(texts)

        inserted_count = 0
        for chunk, emb in zip(chunks, embeddings):
            tc = TranscriptChunk(
                video_id=video_id,
                text=chunk.text,
                start_time=chunk.start_time,
                embedding=emb,
            )
            self.db.add(tc)
            inserted_count += 1

        self.db.commit()
        logger.info(f"Indexed {inserted_count} chunks for video_id {video_id}.")
        return inserted_count

    def retrieve(
        self,
        query: str,
        video_id: int,
        top_k: int = 3,
        use_hybrid: bool = True,
        dense_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> Tuple[List[RetrievedChunk], float]:
        """
        Hybrid search combining Dense Embeddings (Cosine Sim) + Lexical Search (BM25)
        scoped strictly to the given video_id / document_id.
        """
        query_vec = self.embedder.embed_text(query)
        q_arr = np.array(query_vec, dtype=np.float32)

        # Scoped query: fetch all chunks strictly for this video_id / doc_id
        stmt = select(TranscriptChunk).where(TranscriptChunk.video_id == video_id)
        db_chunks = self.db.scalars(stmt).all()

        if not db_chunks:
            logger.warning(f"No transcript or reference chunks found for video_id {video_id}.")
            return [], 0.0

        # 1. Compute Dense Cosine Similarities
        dense_scores: List[float] = []
        for ch in db_chunks:
            emb = ch.embedding
            if emb is not None:
                c_arr = np.array(emb, dtype=np.float32)
                sim = float(np.dot(q_arr, c_arr) / (np.linalg.norm(q_arr) * np.linalg.norm(c_arr) + 1e-9))
            else:
                sim = 0.0
            dense_scores.append(max(0.0, sim))

        # 2. Compute Lexical BM25 Scores (if enabled)
        if use_hybrid and HAS_BM25 and len(db_chunks) > 0:
            query_tokens = re.findall(r"\w+", query.lower())
            corpus = [re.findall(r"\w+", ch.text.lower()) for ch in db_chunks]
            try:
                bm25 = BM25Okapi(corpus)
                raw_bm25 = bm25.get_scores(query_tokens)
                max_bm25 = float(np.max(raw_bm25)) if len(raw_bm25) > 0 else 0.0
                norm_bm25 = [float(s / (max_bm25 + 1e-9)) if max_bm25 > 0 else 0.0 for s in raw_bm25]
            except Exception as bm_err:
                logger.warning(f"BM25 computation fallback: {bm_err}")
                norm_bm25 = [0.0] * len(db_chunks)
        else:
            norm_bm25 = [0.0] * len(db_chunks)

        # 3. Hybrid Fusion: Convex combination of Dense + BM25
        scored_chunks: List[Tuple[TranscriptChunk, float]] = []
        for i, ch in enumerate(db_chunks):
            if use_hybrid and HAS_BM25:
                combined_score = (dense_weight * dense_scores[i]) + (bm25_weight * norm_bm25[i])
            else:
                combined_score = dense_scores[i]
            scored_chunks.append((ch, combined_score))

        # Sort descending by hybrid similarity score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_chunks[:top_k]

        retrieved: List[RetrievedChunk] = []
        for ch, score in top_results:
            # Check for page or section markers in text (e.g. [Page 1] or [Section 2])
            marker_match = re.match(r"^(\[(?:Page|Section)[^\]]+\])", ch.text)
            if marker_match:
                ts_str = marker_match.group(1)
            else:
                total_sec = int(ch.start_time)
                mins = total_sec // 60
                secs = total_sec % 60
                ts_str = f"[{mins:02d}:{secs:02d}]"

            retrieved.append(
                RetrievedChunk(
                    chunk_id=ch.id,
                    text=ch.text,
                    start_time=ch.start_time,
                    formatted_timestamp=ts_str,
                    similarity_score=round(score, 4),
                )
            )

        top_score = retrieved[0].similarity_score if retrieved else 0.0
        return retrieved, top_score

