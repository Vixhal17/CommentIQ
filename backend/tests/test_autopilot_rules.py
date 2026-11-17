import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.models import AutopilotRule
from backend.app.safety.router import RiskRouter
from backend.app.safety.rules import matches_rule, DEFAULT_AUTOPILOT_RULES, seed_default_autopilot_rules


@pytest.fixture(scope="function")
def api_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_rule_matching_logic():
    # 1. Test citation requirement rule
    faq_rule = AutopilotRule(
        id=1,
        name="Verified FAQ",
        enabled=True,
        priority=1,
        action="AUTO",
        categories=["question"],
        min_confidence=0.80,
        min_faithfulness=0.85,
        require_citations=True,
        keywords_any=[],
        negative_keywords=["refund"],
        max_comment_words=None,
        author_match=None,
    )

    # Fails citation check
    matched, reason = matches_rule(
        faq_rule,
        category="question",
        confidence=0.90,
        faithfulness=0.90,
        draft_text="Here is the solution.",
        comment_text="How does this work?",
    )
    assert not matched
    assert "citation" in reason.lower()

    # Passes citation check
    matched_ok, reason_ok = matches_rule(
        faq_rule,
        category="question",
        confidence=0.90,
        faithfulness=0.90,
        draft_text="Here is the solution as explained at [04:15].",
        comment_text="How does this work?",
    )
    assert matched_ok

    # Fails negative keyword
    matched_neg, reason_neg = matches_rule(
        faq_rule,
        category="question",
        confidence=0.90,
        faithfulness=0.90,
        draft_text="Here is the solution as explained at [04:15].",
        comment_text="How do I get a refund for this course?",
    )
    assert not matched_neg
    assert "negative keyword" in reason_neg.lower()


def test_rule_max_words_and_author_match():
    short_praise_rule = AutopilotRule(
        id=2,
        name="Short Praise",
        enabled=True,
        priority=2,
        action="AUTO",
        categories=["praise"],
        min_confidence=0.80,
        require_citations=False,
        keywords_any=[],
        negative_keywords=[],
        max_comment_words=10,
        author_match="vip_",
    )

    # Too many words
    matched_long, _ = matches_rule(
        short_praise_rule,
        category="praise",
        confidence=0.95,
        comment_text="This was an amazingly well structured and extraordinarily deep tutorial on building agents thank you so much!",
        author="vip_john",
    )
    assert not matched_long

    # Author mismatch
    matched_author, _ = matches_rule(
        short_praise_rule,
        category="praise",
        confidence=0.95,
        comment_text="Great job!",
        author="regular_user",
    )
    assert not matched_author

    # Passes all conditions
    matched_ok, _ = matches_rule(
        short_praise_rule,
        category="praise",
        confidence=0.95,
        comment_text="Great tutorial!",
        author="vip_alice",
    )
    assert matched_ok


def test_hard_safety_invariants_override_custom_rules():
    router = RiskRouter(auto_publish_enabled=True)

    # Permissive rule that wants to auto-publish everything
    wildcard_rule = AutopilotRule(
        id=99,
        name="Wildcard",
        enabled=True,
        priority=1,
        action="AUTO",
        categories=[],
        keywords_any=[],
        negative_keywords=[],
    )

    # Invariant 1: Sensitive MUST escalate
    d1 = router.route(
        category="sensitive",
        confidence=0.99,
        sensitive=True,
        comment_text="Crisis alert",
        rules=[wildcard_rule],
    )
    assert d1.action == "ESCALATE"
    assert "sensitive" in d1.reason.lower()

    # Invariant 2: Spam MUST escalate
    d2 = router.route(
        category="spam",
        confidence=0.99,
        comment_text="Free crypto coins at telegram.me/fake",
        rules=[wildcard_rule],
    )
    assert d2.action == "ESCALATE"
    assert "spam" in d2.reason.lower()

    # Invariant 3: Abstain draft CANNOT be AUTO
    d3 = router.route(
        category="question",
        confidence=0.95,
        draft_text="ABSTAIN",
        abstained=True,
        comment_text="Where is feature X?",
        rules=[wildcard_rule],
    )
    assert d3.action == "DRAFT"
    assert "insufficient evidence" in d3.reason.lower()

    # Invariant 4: Shadow Mode safely downgrades AUTO to DRAFT
    shadow_router = RiskRouter(auto_publish_enabled=False)
    d4 = shadow_router.route(
        category="praise",
        confidence=0.95,
        comment_text="Love this video!",
        rules=[wildcard_rule],
    )
    assert d4.action == "DRAFT"
    assert "shadow mode" in d4.reason.lower()


def test_api_autopilot_rules_crud_and_simulation(api_client):
    client = api_client

    # 1. Reset / Seed rules
    reset_res = client.post("/api/autopilot/rules/reset")
    assert reset_res.status_code == 200
    rules = reset_res.json()
    assert len(rules) >= 4

    # 2. Get rules list
    list_res = client.get("/api/autopilot/rules")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 4

    # 3. Create custom rule
    create_payload = {
        "name": "VIP Sponsor Alert",
        "description": "Escalates comments from VIP sponsor partners",
        "enabled": True,
        "priority": 1,
        "action": "ESCALATE",
        "categories": ["business_collab"],
        "keywords_any": ["sponsor", "partnership"],
        "negative_keywords": [],
        "require_citations": False,
    }
    create_res = client.post("/api/autopilot/rules", json=create_payload)
    assert create_res.status_code == 200
    created_rule = create_res.json()
    rule_id = created_rule["id"]
    assert created_rule["name"] == "VIP Sponsor Alert"

    # 4. Test dry-run simulation
    test_payload = {
        "comment_text": "We would love to discuss a sponsor partnership for your next video series.",
        "category": "business_collab",
        "confidence": 0.95,
        "author": "Acme Marketing",
    }
    test_res = client.post("/api/autopilot/test", json=test_payload)
    assert test_res.status_code == 200
    test_data = test_res.json()
    assert test_data["action"] == "ESCALATE"
    assert test_data["matched_rule_id"] == rule_id

    # 5. Update rule (disable it)
    update_res = client.put(f"/api/autopilot/rules/{rule_id}", json={"enabled": False})
    assert update_res.status_code == 200
    assert update_res.json()["enabled"] is False

    # 6. Delete rule
    del_res = client.delete(f"/api/autopilot/rules/{rule_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_rule_id"] == rule_id
