import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.db.models import CreatorPersona, Reply, Comment, Video
from backend.app.persona.service import (
    seed_default_personas,
    get_active_persona,
    set_active_persona,
    extract_tone_from_texts,
    extract_tone_from_approved_db,
    build_persona_prompt_block,
)


def test_seed_and_activate_personas(db_session: Session):
    """Test seeding default personas and switching active status."""
    personas = seed_default_personas(db_session)
    assert len(personas) >= 3

    default_persona = get_active_persona(db_session)
    assert default_persona is not None
    assert default_persona.is_active is True

    # Activate a different persona
    target = personas[1]
    activated = set_active_persona(db_session, target.id)
    assert activated.id == target.id
    assert activated.is_active is True

    # Verify previous is now deactivated
    db_session.refresh(default_persona)
    assert default_persona.is_active is False


def test_tone_extraction_from_samples():
    """Test algorithmic extraction of greeting, sign-off, emoji density, and brevity."""
    sample_replies = [
        "Hey @author! Thanks for asking, you can download the code directly at [02:15]! Hope this helps! 🚀",
        "Hey @author! Check out [04:30] for the exact database setup command. Hope this helps! 🚀",
        "Hey @author! Python 3.12 works without issues as shown at [08:00]. Hope this helps! 🚀",
    ]

    profile = extract_tone_from_texts(sample_replies)
    assert profile["greeting_pattern"] == "Hey @author!"
    assert "Hope this helps" in profile["sign_off_pattern"]
    assert profile["emoji_density"] in ("minimal", "expressive")
    assert profile["max_sentences"] <= 3
    assert profile["formality"] in ("casual", "neutral")


def test_tone_extraction_formal_and_empty():
    """Test extraction on zero-emoji technical responses and empty fallback."""
    # Formal with no greetings or sign-offs
    formal_replies = [
        "The server listens on port 8000. Refer to [01:10].",
        "MiniLM embeddings run locally on CPU without external API keys ([03:25]).",
    ]
    formal_profile = extract_tone_from_texts(formal_replies)
    assert formal_profile["greeting_pattern"] == "None"
    assert formal_profile["sign_off_pattern"] == "None"
    assert formal_profile["emoji_density"] == "none"

    # Empty list fallback
    empty_profile = extract_tone_from_texts([])
    assert empty_profile["sample_count"] == 0
    assert empty_profile["name"] == "Cloned Voice"


def test_build_persona_prompt_block():
    """Verify prompt formatting includes rules and few-shot examples."""
    persona = CreatorPersona(
        name="Test Mentor",
        greeting_pattern="Hi @author!",
        sign_off_pattern="Best, Alex",
        formality="casual",
        emoji_density="minimal",
        max_sentences=2,
        custom_voice_notes="Keep it friendly and warm.",
        sample_pairs=[
            {"comment": "Where is the repo?", "reply": "Hi @author! Check the video description link at [00:45]. Best, Alex"}
        ],
    )

    block = build_persona_prompt_block(persona, author_name="DevUser")
    assert "Active Persona: Test Mentor" in block
    assert "Hi @DevUser!" in block
    assert "Best, Alex" in block
    assert "Keep it friendly and warm." in block
    assert "User: \"Where is the repo?\"" in block
    assert "Creator Reply: \"Hi @author!" in block


def test_persona_api_crud_and_preview(db_session: Session):
    """Test full REST API lifecycle for creator personas and preview drafting."""
    from backend.app.main import app
    from backend.app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    api_client = TestClient(app)

    try:
        # 1. GET /api/personas
        res = api_client.get("/api/personas")
        assert res.status_code == 200
        personas = res.json()
        assert len(personas) >= 3

        # 2. POST /api/personas (create custom)
        new_persona_payload = {
            "name": "Super Casual Creator",
            "description": "Ultra relaxed YouTube creator vibe",
            "greeting_pattern": "Yo @author!",
            "sign_off_pattern": "- Vishal",
            "formality": "casual",
            "emoji_density": "expressive",
            "max_sentences": 2,
            "custom_voice_notes": "Use cheerful exclamation marks.",
            "sample_pairs": [
                {"comment": "Is this free?", "reply": "Yo @author! 100% free, everything is open source at [01:20]! - Vishal"}
            ],
            "is_active": False,
        }
        create_res = api_client.post("/api/personas", json=new_persona_payload)
        assert create_res.status_code == 201
        created = create_res.json()
        assert created["name"] == "Super Casual Creator"
        persona_id = created["id"]

        # 3. PUT /api/personas/{id}/activate
        act_res = api_client.put(f"/api/personas/{persona_id}/activate")
        assert act_res.status_code == 200
        assert act_res.json()["is_active"] is True

        # 4. POST /api/personas/extract
        ext_res = api_client.post(
            "/api/personas/extract",
            json={"sample_replies": ["Hey @author! Glad you enjoyed the tutorial! Cheers!"]}
        )
        assert ext_res.status_code == 200
        assert ext_res.json()["sample_count"] == 1

        # 5. POST /api/personas/extract-from-db
        db_ext_res = api_client.post("/api/personas/extract-from-db")
        assert db_ext_res.status_code == 200

        # 6. POST /api/personas/preview-draft
        prev_res = api_client.post(
            "/api/personas/preview-draft",
            json={
                "comment_text": "Where can I find the Docker setup instructions?",
                "author": "Alice",
                "persona_id": persona_id,
                "mock_context": "[02:15] Download Docker Desktop from docker.com for Windows and macOS.",
            }
        )
        assert prev_res.status_code == 200
        data = prev_res.json()
        assert "draft_text" in data
        assert data["persona_name"] == "Super Casual Creator"

        # 7. DELETE /api/personas/{id}
        del_res = api_client.delete(f"/api/personas/{persona_id}")
        assert del_res.status_code == 204
    finally:
        app.dependency_overrides.clear()
