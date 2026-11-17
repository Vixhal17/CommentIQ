from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.agent.state import PipelineState
from backend.app.llm.client import LLMClient
from backend.app.retrieval.retriever import ScopedRetriever
from backend.app.core.logging import logger, current_comment_id

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CLASSIFY_PROMPT = (PROMPTS_DIR / "classify.txt").read_text(encoding="utf-8")
DRAFT_PROMPT = (PROMPTS_DIR / "draft.txt").read_text(encoding="utf-8")


class ClassificationOutput(BaseModel):
    category: str = Field(..., description="One of the 7 triage categories")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = Field(default="")
    sensitive: bool = Field(default=False)


class PipelineNodes:
    """
    Modular LangGraph nodes for YouTube comment triage.
    Enforces grounding, abstention, and correlation ID tracing.
    """

    def __init__(self, llm_client: LLMClient, retriever: Optional[ScopedRetriever] = None):
        self.llm_client = llm_client
        self.retriever = retriever

    def classify_node(self, state: PipelineState) -> Dict[str, Any]:
        """Classifies the comment using the primary/fallback classifier LLM."""
        token = current_comment_id.set(state.youtube_comment_id)
        try:
            if state.custom_categories:
                cats_str = "\n".join([f'{i+1}. "{c["name"].lower()}": {c.get("description", "")}' for i, c in enumerate(state.custom_categories)])
                names_str = " | ".join([f'"{c["name"].lower()}"' for c in state.custom_categories])
                custom_inst = f"\nCUSTOM USER INSTRUCTIONS:\n{state.custom_instructions}\n" if state.custom_instructions else ""
                prompt_content = f"""You are an intelligent feedback and comment triage classifier.
Your job is to analyze incoming comments and classify them into exactly ONE category based on the defined categories.

CATEGORIES:
{cats_str}

RULES:
- Return ONLY valid JSON matching this schema:
{{
  "category": {names_str},
  "confidence": <float between 0.0 and 1.0>,
  "rationale": "<concise one-line explanation>",
  "sensitive": <true if sensitive/safety issue, else false>
}}
- Do not output any markdown code fence or thinking tags. Output raw JSON only.
{custom_inst}
COMMENT TO CLASSIFY:
"{state.comment_text}"
"""
            else:
                prompt_content = CLASSIFY_PROMPT.replace("{comment_text}", state.comment_text)
                if state.custom_instructions:
                    prompt_content += f"\n\nCUSTOM USER INSTRUCTIONS:\n{state.custom_instructions}"

            messages = [{"role": "user", "content": prompt_content}]

            result = self.llm_client.call_role(
                role="classifier",
                messages=messages,
                schema=ClassificationOutput,
                estimated_tokens=250,
            )

            if result.error:
                logger.error(f"Classification failed: {result.error}")
                return {
                    "category": "question",  # Default safe fallback
                    "confidence": 0.0,
                    "rationale": f"Classifier error: {result.error}",
                    "model_used": result.model_used,
                    "fallback_used": result.fallback_used,
                }

            parsed: ClassificationOutput = result.parsed or ClassificationOutput(
                category="question", confidence=0.5, rationale="Fallback parse"
            )

            logger.info(
                f"Classified comment as '{parsed.category}' (confidence: {parsed.confidence:.2f}, "
                f"sensitive: {parsed.sensitive})"
            )

            return {
                "category": parsed.category.strip().lower(),
                "confidence": parsed.confidence,
                "rationale": parsed.rationale,
                "sensitive": parsed.sensitive,
                "model_used": result.model_used,
                "fallback_used": result.fallback_used,
            }
        finally:
            current_comment_id.reset(token)

    def retrieve_node(self, state: PipelineState) -> Dict[str, Any]:
        """Retrieves top-k scoped transcript chunks for questions."""
        token = current_comment_id.set(state.youtube_comment_id)
        try:
            if not self.retriever or not state.video_id:
                logger.warning("No retriever or video_id configured for retrieval node.")
                return {"retrieved_chunks": [], "top_retrieval_score": 0.0}

            chunks, top_score = self.retriever.retrieve(
                query=state.comment_text,
                video_id=state.video_id,
                top_k=3,
            )

            serialized_chunks = [c.model_dump() for c in chunks]
            logger.info(
                f"Retrieved {len(serialized_chunks)} chunks for video_id {state.video_id}. "
                f"Top similarity score: {top_score:.4f}"
            )

            return {
                "retrieved_chunks": serialized_chunks,
                "top_retrieval_score": top_score,
            }
        finally:
            current_comment_id.reset(token)

    def draft_node(self, state: PipelineState) -> Dict[str, Any]:
        """Drafts a grounded answer citing timestamps, or outputs ABSTAIN if unsupported."""
        token = current_comment_id.set(state.youtube_comment_id)
        try:
            # Format retrieved context
            context_blocks = []
            for ch in state.retrieved_chunks:
                context_blocks.append(f"{ch.get('formatted_timestamp', '[00:00]')} {ch.get('text', '')}")

            context_str = "\n\n".join(context_blocks) if context_blocks else "[No relevant transcript chunks found]"

            prompt_content = (
                DRAFT_PROMPT.replace("{tone_setting}", state.channel_tone)
                .replace("{transcript_context}", context_str)
                .replace("{comment_text}", state.comment_text)
            )
            if state.persona_instructions:
                prompt_content += f"\n\n{state.persona_instructions}"
            if state.custom_instructions:
                prompt_content += f"\n\nCUSTOM USER INSTRUCTIONS:\n{state.custom_instructions}"
            messages = [{"role": "user", "content": prompt_content}]

            result = self.llm_client.call_role(
                role="drafter",
                messages=messages,
                estimated_tokens=500,
            )

            raw_reply = result.content.strip()

            # Check for abstention
            is_abstain = "ABSTAIN" in raw_reply.upper() or len(raw_reply) == 0

            if is_abstain:
                logger.info("Drafter returned ABSTAIN (evidence insufficient in transcript).")
                final_draft = "ABSTAIN"
            else:
                logger.info(f"Generated grounded draft: {raw_reply[:80]}...")
                final_draft = raw_reply

            return {
                "draft_text": final_draft,
                "abstained": is_abstain,
                "model_used": result.model_used,
                "fallback_used": result.fallback_used,
                "judge_independent": result.judge_independent,
            }
        finally:
            current_comment_id.reset(token)

