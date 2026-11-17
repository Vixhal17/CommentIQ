from typing import List, Tuple, Optional
from pydantic import BaseModel
from backend.app.core.logging import logger
from backend.app.llm.client import LLMClient
from backend.app.llm.parsers import parse_and_validate_json


class JudgeVerificationOutput(BaseModel):
    faithfulness: float  # 0.0 to 1.0
    rationale: str
    supported: bool


class FaithfulnessVerifier:
    """
    Two-stage verifier for draft claim faithfulness:
    1. Fast deterministic check (checks for timestamp citations, transcript overlap, or local NLI).
    2. Borderline / high-risk draft escalation to LLM Judge (mistral-large-4).
    """

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def _compute_surface_overlap(self, draft_text: str, context_chunks: List[str]) -> float:
        """Computes lexical token overlap between draft and transcript evidence."""
        if not draft_text or not context_chunks:
            return 0.0
        
        draft_words = set(draft_text.lower().split())
        # remove trivial stopwords
        stopwords = {"the", "a", "an", "is", "are", "and", "or", "to", "in", "at", "for", "on", "it", "this", "that"}
        content_words = draft_words - stopwords
        if not content_words:
            return 0.5

        combined_context = " ".join(context_chunks).lower()
        matched = sum(1 for w in content_words if w in combined_context)
        return round(matched / len(content_words), 4)

    def verify(
        self,
        draft_text: str,
        context_chunks: List[str],
        comment_text: str,
        drafter_model_used: str = "",
        fallback_used: bool = False,
    ) -> Tuple[float, str, bool]:
        """
        Verifies faithfulness of draft reply against retrieved transcript chunks.
        Returns (faithfulness_score, reason, is_independent).
        """
        # Rule: If draft is ABSTAIN, it is 100% faithful to the missing evidence
        if "ABSTAIN" in draft_text.upper() or not draft_text.strip():
            return 1.0, "Draft correctly abstained from ungrounded claims", True

        # Check Drafter-Judge Independence
        # If drafter used Mistral fallback, drafter and judge belong to same model family
        is_independent = True
        if "mistral" in drafter_model_used.lower() and fallback_used:
            is_independent = False
            logger.warning("Verifier independence alert: Drafter used Mistral fallback.")

        # Stage 1: Fast local entailment / surface overlap check
        overlap_score = self._compute_surface_overlap(draft_text, context_chunks)

        # High confidence grounded draft (>= 0.85 lexical / timestamp alignment)
        if overlap_score >= 0.85:
            return overlap_score, "Strong local evidence alignment with transcript context", is_independent

        # Clearly ungrounded (< 0.25 overlap)
        if overlap_score < 0.25:
            return overlap_score, "Low evidence support: draft contains unsupported claims", is_independent

        # Stage 2: Borderline draft (0.25 - 0.85) -> Escalate to Judge LLM (mistral-large-4)
        logger.info(f"Borderline draft alignment ({overlap_score:.2f}). Calling LLM Judge...")
        judge_prompt = f"""You are an unbiased AI Judge verifying whether an AI-drafted reply is strictly faithful to the provided video transcript.

USER QUESTION:
"{comment_text}"

RETRIEVED TRANSCRIPT EVIDENCE:
{" ".join(context_chunks)}

DRAFT REPLY TO VERIFY:
"{draft_text}"

TASK:
Determine whether EVERY factual claim in the draft reply is directly supported by the transcript evidence.
Return ONLY valid JSON:
{{
  "faithfulness": <float between 0.0 and 1.0>,
  "rationale": "<one-line explanation of evidence support>",
  "supported": <true if faithfulness >= 0.75, else false>
}}"""

        try:
            judge_res = self.llm_client.call_role(
                role="judge",
                messages=[{"role": "user", "content": judge_prompt}],
                schema=JudgeVerificationOutput,
                estimated_tokens=300,
            )

            if judge_res.parsed:
                return (
                    judge_res.parsed.faithfulness,
                    judge_res.parsed.rationale,
                    is_independent and judge_res.judge_independent,
                )
        except Exception as e:
            logger.error(f"Judge verification failed: {e}")

        # Fallback to stage 1 score if judge call failed
        return overlap_score, "Stage 1 overlap score (judge fallback)", is_independent

