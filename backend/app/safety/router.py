from typing import Optional, List, Literal, Any
from pydantic import BaseModel
from backend.config.settings import settings
from backend.app.safety.rules import matches_rule


class RouteDecision(BaseModel):
    action: Literal["AUTO", "DRAFT", "ESCALATE"]
    reason: str
    requires_human_approval: bool
    can_auto_publish: bool
    matched_rule_id: Optional[int] = None
    matched_rule_name: Optional[str] = None


class RiskRouter:
    """
    Deterministic risk router with granular autopilot rules engine.
    Strictly plain Python: the LLM NEVER decides the final action.
    Every comment routes to AUTO, DRAFT, or ESCALATE with a plain-language rationale.
    """

    def __init__(
        self,
        min_classifier_confidence: float = 0.70,
        min_retrieval_score: float = 0.35,
        min_faithfulness_score: float = 0.75,
        auto_publish_enabled: Optional[bool] = None,
    ):
        self.min_classifier_confidence = min_classifier_confidence
        self.min_retrieval_score = min_retrieval_score
        self.min_faithfulness_score = min_faithfulness_score
        self.auto_publish_enabled = (
            auto_publish_enabled
            if auto_publish_enabled is not None
            else settings.AUTO_PUBLISH_ENABLED
        )

    def route(
        self,
        category: str,
        confidence: float,
        sensitive: bool = False,
        retrieval_score: float = 0.0,
        faithfulness: float = 0.0,
        draft_text: Optional[str] = None,
        abstained: bool = False,
        comment_text: str = "",
        author: str = "",
        rules: Optional[List[Any]] = None,
    ) -> RouteDecision:
        cat = category.strip().lower()

        # Hard Invariant 1: Sensitive or safety content always ESCALATES
        if sensitive or cat == "sensitive":
            return RouteDecision(
                action="ESCALATE",
                reason="Sensitive or safety content detected; escalated for creator review",
                requires_human_approval=True,
                can_auto_publish=False,
                matched_rule_name="Sensitive Content Guardrail",
            )

        # Hard Invariant 2: Spam comments flag for review, NEVER reply
        if cat == "spam":
            return RouteDecision(
                action="ESCALATE",
                reason="Detected promotional spam or scam; flagged for deletion/review (zero automated reply)",
                requires_human_approval=True,
                can_auto_publish=False,
                matched_rule_name="Spam Suppression",
            )

        # Granular Autopilot Rules: Evaluate active rules in priority order if provided
        if rules:
            sorted_rules = sorted(
                [r for r in rules if getattr(r, "enabled", True)],
                key=lambda r: (getattr(r, "priority", 10), getattr(r, "id", 0)),
            )
            for r in sorted_rules:
                matched, explanation = matches_rule(
                    rule=r,
                    category=cat,
                    confidence=confidence,
                    retrieval_score=retrieval_score,
                    faithfulness=faithfulness,
                    draft_text=draft_text,
                    comment_text=comment_text,
                    author=author,
                )
                if matched:
                    r_action = getattr(r, "action", "DRAFT")
                    r_name = getattr(r, "name", "Custom Rule")
                    r_id = getattr(r, "id", None)
                    r_desc = getattr(r, "description", "")

                    if r_action == "ESCALATE":
                        return RouteDecision(
                            action="ESCALATE",
                            reason=f"[Rule: {r_name}] {r_desc or 'Escalated by autopilot rule'}",
                            requires_human_approval=True,
                            can_auto_publish=False,
                            matched_rule_id=r_id,
                            matched_rule_name=r_name,
                        )
                    elif r_action == "DRAFT":
                        return RouteDecision(
                            action="DRAFT",
                            reason=f"[Rule: {r_name}] {r_desc or 'Queued for human review'}",
                            requires_human_approval=True,
                            can_auto_publish=False,
                            matched_rule_id=r_id,
                            matched_rule_name=r_name,
                        )
                    elif r_action == "AUTO":
                        # Check abstention guardrail
                        if abstained or "ABSTAIN" in (draft_text or "").upper():
                            return RouteDecision(
                                action="DRAFT",
                                reason=f"[Rule: {r_name}] Insufficient evidence found in video transcript; flagged for creator answer",
                                requires_human_approval=True,
                                can_auto_publish=False,
                                matched_rule_id=r_id,
                                matched_rule_name=r_name,
                            )
                        # Check shadow mode guardrail
                        if self.auto_publish_enabled:
                            return RouteDecision(
                                action="AUTO",
                                reason=f"[Rule: {r_name}] Auto-reply enabled ({r_name})",
                                requires_human_approval=False,
                                can_auto_publish=True,
                                matched_rule_id=r_id,
                                matched_rule_name=r_name,
                            )
                        else:
                            return RouteDecision(
                                action="DRAFT",
                                reason=f"[Rule: {r_name}] Qualified for AUTO, held in review queue (Shadow Mode active)",
                                requires_human_approval=True,
                                can_auto_publish=False,
                                matched_rule_id=r_id,
                                matched_rule_name=r_name,
                            )

        # Standard Baseline Fallback Rules (if no custom rule matched or rules not provided)
        if cat in ("business_collab", "complaint", "technical_correction"):
            category_names = {
                "business_collab": "Business collaboration inquiry",
                "complaint": "Viewer complaint or frustration",
                "technical_correction": "Technical bug / code correction reported",
            }
            label = category_names.get(cat, cat)
            return RouteDecision(
                action="ESCALATE",
                reason=f"{label}; creator personal attention required",
                requires_human_approval=True,
                can_auto_publish=False,
            )

        if confidence < self.min_classifier_confidence:
            return RouteDecision(
                action="DRAFT",
                reason=f"Classifier confidence ({confidence:.2f}) below threshold ({self.min_classifier_confidence:.2f}); human confirmation required",
                requires_human_approval=True,
                can_auto_publish=False,
            )

        if cat == "question":
            if abstained or "ABSTAIN" in (draft_text or "").upper():
                return RouteDecision(
                    action="DRAFT",
                    reason="Insufficient evidence found in video transcript; flagged for creator answer",
                    requires_human_approval=True,
                    can_auto_publish=False,
                )

            if retrieval_score < self.min_retrieval_score:
                return RouteDecision(
                    action="DRAFT",
                    reason=f"Retrieval similarity score ({retrieval_score:.2f}) below threshold ({self.min_retrieval_score:.2f}); unverified context",
                    requires_human_approval=True,
                    can_auto_publish=False,
                )

            if faithfulness >= self.min_faithfulness_score:
                if self.auto_publish_enabled:
                    return RouteDecision(
                        action="AUTO",
                        reason=f"Strong evidence (RAG {retrieval_score:.2f}) and verified faithfulness ({faithfulness:.2f}); auto-reply enabled",
                        requires_human_approval=False,
                        can_auto_publish=True,
                    )
                else:
                    return RouteDecision(
                        action="DRAFT",
                        reason=f"Grounded response ready (Faithfulness {faithfulness:.2f}); held in review queue (Shadow Mode active)",
                        requires_human_approval=True,
                        can_auto_publish=False,
                    )
            else:
                return RouteDecision(
                    action="DRAFT",
                    reason=f"Draft faithfulness score ({faithfulness:.2f}) below threshold ({self.min_faithfulness_score:.2f}); requires human verification",
                    requires_human_approval=True,
                    can_auto_publish=False,
                )

        if cat == "praise":
            is_short = len(comment_text.split()) <= 15
            if is_short and self.auto_publish_enabled:
                return RouteDecision(
                    action="AUTO",
                    reason="Short safe praise; auto-reply enabled",
                    requires_human_approval=False,
                    can_auto_publish=True,
                )
            return RouteDecision(
                action="DRAFT",
                reason="Positive viewer feedback; held in review queue for optional thank you",
                requires_human_approval=True,
                can_auto_publish=False,
            )

        return RouteDecision(
            action="DRAFT",
            reason="Standard review queue routing",
            requires_human_approval=True,
            can_auto_publish=False,
        )
