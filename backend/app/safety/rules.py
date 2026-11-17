import re
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.models import AutopilotRule
from backend.app.core.logging import logger

DEFAULT_AUTOPILOT_RULES: List[Dict[str, Any]] = [
    {
        "name": "Negative Keyword Suppression",
        "description": "Escalates comments containing high-risk keywords (refund, scam, legal, hack, urgent, broken) directly to human review.",
        "enabled": True,
        "priority": 1,
        "action": "ESCALATE",
        "categories": [],  # Any category
        "keywords_any": [
            "refund",
            "scam",
            "broken",
            "lawyer",
            "legal",
            "sue",
            "urgent",
            "hack",
            "virus",
            "terrible",
            "worst",
        ],
        "negative_keywords": [],
        "min_confidence": None,
        "min_faithfulness": None,
        "min_retrieval_score": None,
        "require_citations": False,
        "max_comment_words": None,
        "author_match": None,
    },
    {
        "name": "Commercial & Collaboration Inquiries",
        "description": "Escalates business sponsorships, partnerships, bug reports, and viewer complaints directly to the creator.",
        "enabled": True,
        "priority": 2,
        "action": "ESCALATE",
        "categories": ["business_collab", "complaint", "technical_correction"],
        "keywords_any": [],
        "negative_keywords": [],
        "min_confidence": None,
        "min_faithfulness": None,
        "min_retrieval_score": None,
        "require_citations": False,
        "max_comment_words": None,
        "author_match": None,
    },
    {
        "name": "Verified Technical FAQ Drafts",
        "description": "Queues grounded answers for viewer technical questions with verified transcript citations [MM:SS] and faithfulness >= 0.80.",
        "enabled": True,
        "priority": 3,
        "action": "DRAFT",
        "categories": ["question"],
        "keywords_any": [],
        "negative_keywords": ["refund", "scam", "broken", "lawyer", "legal", "urgent"],
        "min_confidence": 0.70,
        "min_faithfulness": 0.80,
        "min_retrieval_score": 0.35,
        "require_citations": True,
        "max_comment_words": None,
        "author_match": None,
    },
    {
        "name": "Safe Short Praise Auto-Reply",
        "description": "Auto-publishes friendly responses to short, genuine compliments (under 25 words with no negative caveats).",
        "enabled": True,
        "priority": 4,
        "action": "AUTO",
        "categories": ["praise"],
        "keywords_any": [],
        "negative_keywords": ["refund", "but", "however", "issue", "why", "broken", "problem"],
        "min_confidence": 0.80,
        "min_faithfulness": None,
        "min_retrieval_score": None,
        "require_citations": False,
        "max_comment_words": 25,
        "author_match": None,
    },
]


def seed_default_autopilot_rules(db: Session) -> int:
    """Seeds default autopilot rules if no rules currently exist in the database."""
    count = db.scalars(select(AutopilotRule)).first()
    if count is not None:
        return 0

    seeded = 0
    for r in DEFAULT_AUTOPILOT_RULES:
        rule = AutopilotRule(
            name=r["name"],
            description=r["description"],
            enabled=r["enabled"],
            priority=r["priority"],
            action=r["action"],
            categories=r["categories"],
            min_confidence=r["min_confidence"],
            min_faithfulness=r["min_faithfulness"],
            min_retrieval_score=r["min_retrieval_score"],
            require_citations=r["require_citations"],
            max_comment_words=r["max_comment_words"],
            keywords_any=r["keywords_any"],
            negative_keywords=r["negative_keywords"],
            author_match=r["author_match"],
        )
        db.add(rule)
        seeded += 1

    db.commit()
    logger.info(f"Seeded {seeded} default autopilot rules.")
    return seeded


def matches_rule(
    rule: AutopilotRule,
    category: str,
    confidence: float,
    retrieval_score: float = 0.0,
    faithfulness: float = 0.0,
    draft_text: Optional[str] = None,
    comment_text: str = "",
    author: str = "",
) -> Tuple[bool, str]:
    """
    Evaluates whether a comment and its analysis satisfy all conditions of an AutopilotRule.
    Returns (matches: bool, explanation: str).
    """
    if not rule.enabled:
        return False, "Rule is disabled"

    cat = (category or "").strip().lower()
    comment_lower = (comment_text or "").lower()

    # 1. Category check (empty list means applies to any category)
    if rule.categories and len(rule.categories) > 0:
        allowed_cats = [c.strip().lower() for c in rule.categories]
        if cat not in allowed_cats:
            return False, f"Category '{cat}' is not in rule categories {allowed_cats}"

    # 2. Classifier Confidence check
    if rule.min_confidence is not None:
        if confidence < rule.min_confidence:
            return False, f"Confidence {confidence:.2f} is below rule minimum {rule.min_confidence:.2f}"

    # 3. Retrieval Score check
    if rule.min_retrieval_score is not None:
        if retrieval_score < rule.min_retrieval_score:
            return False, f"Retrieval similarity {retrieval_score:.2f} is below rule minimum {rule.min_retrieval_score:.2f}"

    # 4. Faithfulness check
    if rule.min_faithfulness is not None:
        if faithfulness < rule.min_faithfulness:
            return False, f"Faithfulness {faithfulness:.2f} is below rule minimum {rule.min_faithfulness:.2f}"

    # 5. Citation requirement check
    if rule.require_citations:
        if not draft_text or not draft_text.strip():
            return False, "Rule requires citations but no draft was generated"
        # Matches [MM:SS] or [Page X] or [Section X]
        has_citations = bool(re.search(r"\[\d{1,2}:\d{2}\]|\[Page \d+\]|\[Section [^\]]+\]", draft_text))
        if not has_citations:
            return False, "Draft does not contain required citation markers [MM:SS] or [Page X]"

    # 6. Max word count check
    if rule.max_comment_words is not None:
        word_count = len((comment_text or "").split())
        if word_count > rule.max_comment_words:
            return False, f"Comment word count ({word_count}) exceeds rule maximum {rule.max_comment_words}"

    # 7. Negative keywords suppression (None can be present in comment)
    if rule.negative_keywords and len(rule.negative_keywords) > 0:
        found_neg = [kw.lower() for kw in rule.negative_keywords if kw.lower() in comment_lower]
        if found_neg:
            return False, f"Found negative keyword(s): {', '.join(found_neg)}"

    # 8. Keywords Any (At least one must be present if list is non-empty)
    if rule.keywords_any and len(rule.keywords_any) > 0:
        found_any = [kw.lower() for kw in rule.keywords_any if kw.lower() in comment_lower]
        if not found_any:
            return False, f"Comment does not contain any of required keywords: {rule.keywords_any}"

    # 9. Author match (regex or substring)
    if rule.author_match and rule.author_match.strip():
        pattern = rule.author_match.strip().lower()
        if pattern not in (author or "").lower():
            return False, f"Author '{author}' does not match pattern '{pattern}'"

    return True, f"Matched rule '{rule.name}'"
