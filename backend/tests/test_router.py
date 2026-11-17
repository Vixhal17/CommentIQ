import pytest
from backend.app.safety.router import RiskRouter, RouteDecision


def test_router_high_stakes_escalate():
    router = RiskRouter(auto_publish_enabled=True)

    # Business collab
    d1 = router.route(category="business_collab", confidence=0.99)
    assert d1.action == "ESCALATE"
    assert "collaboration" in d1.reason.lower()

    # Complaint
    d2 = router.route(category="complaint", confidence=0.95)
    assert d2.action == "ESCALATE"
    assert "complaint" in d2.reason.lower()

    # Sensitive
    d3 = router.route(category="question", confidence=0.90, sensitive=True)
    assert d3.action == "ESCALATE"
    assert "sensitive" in d3.reason.lower()

    # Technical correction
    d4 = router.route(category="technical_correction", confidence=0.92)
    assert d4.action == "ESCALATE"
    assert "correction" in d4.reason.lower()


def test_router_spam_flagged_for_review_no_reply():
    router = RiskRouter(auto_publish_enabled=True)
    d = router.route(category="spam", confidence=0.99)
    assert d.action == "ESCALATE"
    assert "spam" in d.reason.lower()
    assert d.can_auto_publish is False


def test_router_low_confidence_drafts():
    router = RiskRouter(min_classifier_confidence=0.70)
    d = router.route(category="question", confidence=0.65)
    assert d.action == "DRAFT"
    assert "below threshold" in d.reason.lower()


def test_router_question_abstention_drafts():
    router = RiskRouter(auto_publish_enabled=True)
    # Question where drafter output ABSTAIN
    d = router.route(
        category="question",
        confidence=0.95,
        retrieval_score=0.80,
        faithfulness=1.0,
        abstained=True,
        draft_text="ABSTAIN",
    )
    assert d.action == "DRAFT"
    assert "insufficient evidence" in d.reason.lower()


def test_router_question_low_retrieval_score_drafts():
    router = RiskRouter(min_retrieval_score=0.35, auto_publish_enabled=True)
    d = router.route(
        category="question",
        confidence=0.95,
        retrieval_score=0.20,
        faithfulness=0.85,
        draft_text="Here is some info",
    )
    assert d.action == "DRAFT"
    assert "below threshold" in d.reason.lower()


def test_router_question_shadow_mode_vs_auto_publish():
    # Shadow Mode (Default: auto_publish_enabled=False)
    router_shadow = RiskRouter(auto_publish_enabled=False)
    d_shadow = router_shadow.route(
        category="question",
        confidence=0.95,
        retrieval_score=0.75,
        faithfulness=0.90,
        draft_text="Valid answer citing [02:45].",
    )
    assert d_shadow.action == "DRAFT"
    assert "shadow mode active" in d_shadow.reason.lower()

    # Auto Mode Enabled
    router_auto = RiskRouter(auto_publish_enabled=True)
    d_auto = router_auto.route(
        category="question",
        confidence=0.95,
        retrieval_score=0.75,
        faithfulness=0.90,
        draft_text="Valid answer citing [02:45].",
    )
    assert d_auto.action == "AUTO"
    assert d_auto.can_auto_publish is True


def test_router_praise_shadow_mode_vs_auto():
    short_praise = "Thanks so much, great tutorial!"
    router_shadow = RiskRouter(auto_publish_enabled=False)
    d_shadow = router_shadow.route(category="praise", confidence=0.99, comment_text=short_praise)
    assert d_shadow.action == "DRAFT"

    router_auto = RiskRouter(auto_publish_enabled=True)
    d_auto = router_auto.route(category="praise", confidence=0.99, comment_text=short_praise)
    assert d_auto.action == "AUTO"

