from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.llm.client import LLMClient
from backend.app.retrieval.retriever import ScopedRetriever
from backend.app.safety.verifier import FaithfulnessVerifier
from backend.app.safety.router import RiskRouter, RouteDecision
from backend.app.agent.nodes import ClassificationOutput, PipelineNodes
from backend.app.agent.state import PipelineState
from backend.app.agent.graph import build_triage_graph


class BaselineA_NoRetrieval:
    """
    Baseline A: Plain LLM generation without any video retrieval context.
    Directly asks the LLM to answer the comment.
    Highly prone to hallucinations on unanswerable and video-specific questions.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def run(self, comment_text: str) -> Dict[str, Any]:
        prompt = f"""You are a helpful YouTube assistant. Answer this user comment concisely:
"{comment_text}"
"""
        res = self.llm_client.call_role(
            role="drafter",
            messages=[{"role": "user", "content": prompt}],
            estimated_tokens=250,
        )
        return {
            "baseline": "Baseline_A_NoRetrieval",
            "draft_text": res.content.strip(),
            "abstained": "ABSTAIN" in res.content.upper(),
            "retrieval_score": 0.0,
            "faithfulness": 0.0,
            "action": "AUTO",  # Naive baseline auto-replies to everything
        }


class BaselineB_NaiveRAG:
    """
    Baseline B: Standard RAG without Faithfulness Verifier or Abstention guards.
    Retrieves chunks and generates an answer without checking for hallucinated claims.
    """

    def __init__(self, db: Session, llm_client: LLMClient):
        self.db = db
        self.llm_client = llm_client
        self.retriever = ScopedRetriever(db=db)

    def run(self, comment_text: str, video_id: int) -> Dict[str, Any]:
        chunks, top_score = self.retriever.retrieve(comment_text, video_id, top_k=3)
        context_str = "\n".join([f"{c.formatted_timestamp} {c.text}" for c in chunks])

        prompt = f"""You are a YouTube assistant. Use this video context to answer the user question:
{context_str}

User Question:
"{comment_text}"

Answer concisely:"""

        res = self.llm_client.call_role(
            role="drafter",
            messages=[{"role": "user", "content": prompt}],
            estimated_tokens=300,
        )

        draft = res.content.strip()
        return {
            "baseline": "Baseline_B_NaiveRAG",
            "draft_text": draft,
            "abstained": "ABSTAIN" in draft.upper(),
            "retrieval_score": top_score,
            "faithfulness": top_score,  # Naively assumes faithfulness equals retrieval score
            "action": "AUTO" if top_score > 0.25 else "DRAFT",
        }


class BaselineC_FullPipeline:
    """
    Baseline C: Full Agent Pipeline.
    LangGraph classification + Scoped retrieval + Grounded drafter (with ABSTAIN)
    + Two-stage faithfulness verifier + Deterministic risk router.
    """

    def __init__(self, db: Session, llm_client: LLMClient, router: Optional[RiskRouter] = None):
        self.db = db
        self.llm_client = llm_client
        self.retriever = ScopedRetriever(db=db)
        self.nodes = PipelineNodes(llm_client=llm_client, retriever=self.retriever)
        self.graph = build_triage_graph(self.nodes)
        self.verifier = FaithfulnessVerifier(llm_client=llm_client)
        self.router = router or RiskRouter(auto_publish_enabled=True)

    def run(self, comment_text: str, video_id: int, author: str = "User") -> Dict[str, Any]:
        initial_state = PipelineState(
            comment_text=comment_text,
            video_id=video_id,
            author=author,
        )
        final_state_dict = self.graph.invoke(initial_state)
        state = PipelineState(**final_state_dict)

        category = state.category or "question"
        confidence = state.confidence
        sensitive = state.sensitive
        retrieval_score = state.top_retrieval_score
        draft_text = state.draft_text or ""
        abstained = state.abstained

        # Verify faithfulness
        chunk_texts = [c.get("text", "") for c in state.retrieved_chunks]
        faithfulness = 1.0
        is_independent = state.judge_independent
        if category == "question" and draft_text and not abstained:
            faithfulness, _, is_independent = self.verifier.verify(
                draft_text=draft_text,
                context_chunks=chunk_texts,
                comment_text=comment_text,
                drafter_model_used=state.model_used,
                fallback_used=state.fallback_used,
            )

        # Route action
        decision: RouteDecision = self.router.route(
            category=category,
            confidence=confidence,
            sensitive=sensitive,
            retrieval_score=retrieval_score,
            faithfulness=faithfulness,
            draft_text=draft_text,
            abstained=abstained,
            comment_text=comment_text,
        )

        return {
            "baseline": "Baseline_C_FullPipeline",
            "category": category,
            "confidence": confidence,
            "draft_text": draft_text,
            "abstained": abstained,
            "retrieval_score": retrieval_score,
            "faithfulness": faithfulness,
            "action": decision.action,
            "reason": decision.reason,
            "judge_independent": is_independent,
        }

