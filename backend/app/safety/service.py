from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models import Comment, Video, Analysis, Reply, AuditLog, TranscriptChunk, AutopilotRule
from backend.app.llm.client import LLMClient
from backend.app.retrieval.retriever import ScopedRetriever
from backend.app.agent.graph import TriageAgent
from backend.app.safety.verifier import FaithfulnessVerifier
from backend.app.safety.router import RiskRouter, RouteDecision
from backend.app.safety.rules import seed_default_autopilot_rules
from backend.app.core.logging import logger, current_comment_id


class TriageService:
    """
    End-to-end triage service coordinating LangGraph classification & drafting,
    faithfulness verification, deterministic risk routing, and database persistence.
    """

    def __init__(self, db: Session, llm_client: LLMClient):
        self.db = db
        self.llm_client = llm_client
        self.agent = TriageAgent(db=db, llm_client=llm_client)
        self.verifier = FaithfulnessVerifier(llm_client=llm_client)
        self.router = RiskRouter()
        self.retriever = ScopedRetriever(db=db)

    def process_and_persist_comment(
        self,
        comment_id: int,
        force: bool = False,
        user_preferences: Optional[Any] = None,
    ) -> Optional[Comment]:
        # Row locking to prevent concurrent processing race conditions
        stmt = select(Comment).where(Comment.id == comment_id)
        if "postgresql" in str(self.db.bind.url):
            stmt = stmt.with_for_update()

        comment = self.db.scalars(stmt).first()
        if not comment or (not force and comment.status not in ("new", "processing")):
            return comment

        token = current_comment_id.set(comment.youtube_comment_id)
        try:
            comment.status = "processing"
            self.db.commit()

            # 1. Run LangGraph pipeline (classify -> retrieve -> draft)
            pipeline_state = self.agent.process_comment(comment, user_preferences=user_preferences)

            category = pipeline_state.category or "question"
            confidence = pipeline_state.confidence
            sensitive = pipeline_state.sensitive
            retrieval_score = pipeline_state.top_retrieval_score
            draft_text = pipeline_state.draft_text or ""
            abstained = pipeline_state.abstained

            # Generate friendly creator draft for positive praise
            if category == "praise" and not draft_text:
                draft_text = "Thank you so much! Really glad you found the tutorial helpful!"

            # 2. Verify Faithfulness
            chunk_texts = [c.get("text", "") for c in pipeline_state.retrieved_chunks]
            faithfulness_score = 1.0
            verifier_reason = "No claims to verify"
            is_independent = pipeline_state.judge_independent

            if category == "question" and draft_text and not abstained:
                faithfulness_score, verifier_reason, is_independent = self.verifier.verify(
                    draft_text=draft_text,
                    context_chunks=chunk_texts,
                    comment_text=comment.text,
                    drafter_model_used=pipeline_state.model_used,
                    fallback_used=pipeline_state.fallback_used,
                )

            # 3. Deterministic Risk Routing (Zero-LLM decision with granular autopilot rules)
            active_rules = []
            if self.db:
                try:
                    active_rules = self.db.scalars(
                        select(AutopilotRule)
                        .where(AutopilotRule.enabled == True)
                        .order_by(AutopilotRule.priority.asc(), AutopilotRule.id.asc())
                    ).all()
                except Exception as e:
                    logger.warning(f"Could not load autopilot rules: {e}")

            route_decision: RouteDecision = self.router.route(
                category=category,
                confidence=confidence,
                sensitive=sensitive,
                retrieval_score=retrieval_score,
                faithfulness=faithfulness_score,
                draft_text=draft_text,
                abstained=abstained,
                comment_text=comment.text,
                author=comment.author,
                rules=active_rules,
            )

            # Apply user preference action override if defined and not a safety violation
            if user_preferences and hasattr(user_preferences, "get_action_for_category"):
                pref_action = user_preferences.get_action_for_category(category)
                if pref_action and not sensitive and category != "sensitive":
                    if pref_action == "ESCALATE":
                        route_decision = RouteDecision(
                            action="ESCALATE",
                            reason=f"User preference: '{category}' configured to escalate for creator review",
                            requires_human_approval=True,
                            can_auto_publish=False,
                            matched_rule_name="User Preference Override",
                        )
                    elif pref_action == "DRAFT":
                        route_decision = RouteDecision(
                            action="DRAFT",
                            reason=f"User preference: '{category}' configured for draft review queue",
                            requires_human_approval=True,
                            can_auto_publish=False,
                            matched_rule_name="User Preference Override",
                        )

            # 4. Determine final comment status
            if route_decision.action == "ESCALATE":
                final_status = "escalated"
            elif route_decision.action == "AUTO" and route_decision.can_auto_publish:
                final_status = "approved"  # or published if auto-publish is armed
            else:
                final_status = "drafted"

            comment.status = final_status
            comment.processed_at = datetime.now(timezone.utc)

            # 5. Persist Analysis record
            existing_analysis = self.db.scalars(
                select(Analysis).where(Analysis.comment_id == comment.id)
            ).first()

            if existing_analysis:
                existing_analysis.category = category
                existing_analysis.confidence = confidence
                existing_analysis.retrieval_score = retrieval_score
                existing_analysis.faithfulness = faithfulness_score
                existing_analysis.action = route_decision.action
                existing_analysis.reason = route_decision.reason
                existing_analysis.rule_name = route_decision.matched_rule_name
                existing_analysis.persona_name = pipeline_state.persona_name
                existing_analysis.model_used = pipeline_state.model_used
                existing_analysis.fallback_used = pipeline_state.fallback_used
                existing_analysis.judge_independent = is_independent
            else:
                analysis = Analysis(
                    comment_id=comment.id,
                    category=category,
                    confidence=confidence,
                    retrieval_score=retrieval_score,
                    faithfulness=faithfulness_score,
                    action=route_decision.action,
                    reason=route_decision.reason,
                    rule_name=route_decision.matched_rule_name,
                    persona_name=pipeline_state.persona_name,
                    model_used=pipeline_state.model_used,
                    fallback_used=pipeline_state.fallback_used,
                    judge_independent=is_independent,
                )
                self.db.add(analysis)

            # 6. Persist Reply draft (if generated)
            existing_reply = self.db.scalars(
                select(Reply).where(Reply.comment_id == comment.id)
            ).first()

            if draft_text and draft_text.strip():
                if existing_reply:
                    existing_reply.draft_text = draft_text
                    existing_reply.final_text = draft_text
                    existing_reply.source = "ai"
                else:
                    reply = Reply(
                        comment_id=comment.id,
                        draft_text=draft_text,
                        final_text=draft_text,
                        source="ai",
                    )
                    self.db.add(reply)
            else:
                # If no automated draft should exist (e.g. spam, complaints, collabs), remove any stale reply
                if existing_reply:
                    self.db.delete(existing_reply)

            # 7. Write Audit Log
            audit_entry = AuditLog(
                actor="system",
                event="comment_triaged",
                payload={
                    "comment_id": comment.id,
                    "youtube_comment_id": comment.youtube_comment_id,
                    "category": category,
                    "action": route_decision.action,
                    "reason": route_decision.reason,
                    "matched_rule_id": route_decision.matched_rule_id,
                    "matched_rule_name": route_decision.matched_rule_name,
                    "faithfulness": faithfulness_score,
                    "model_used": pipeline_state.model_used,
                    "fallback_used": pipeline_state.fallback_used,
                    "judge_independent": is_independent,
                },
            )
            self.db.add(audit_entry)
            self.db.commit()

            logger.info(
                f"Triaged comment #{comment.id} -> action: {route_decision.action}, "
                f"status: {comment.status}, reason: {route_decision.reason}"
            )
            return comment

        finally:
            current_comment_id.reset(token)

    def process_all_pending(self, limit: int = 50, force: bool = False) -> int:
        """Processes pending 'new' comments in batch."""
        stmt = select(Comment.id)
        if not force:
            stmt = stmt.where(Comment.status == "new")
        stmt = stmt.limit(limit)
        comment_ids = self.db.scalars(stmt).all()
        processed_count = 0
        for cid in comment_ids:
            res = self.process_and_persist_comment(cid, force=force)
            if res:
                processed_count += 1
        return processed_count

