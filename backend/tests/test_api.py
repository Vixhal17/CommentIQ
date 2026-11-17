import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.models import Comment, Video, Analysis, Reply, AuditLog


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


def test_api_approve_flow(api_client, db_session):
    # Setup video and drafted comment
    video = Video(youtube_video_id="vid_api_1", title="API Test Video")
    db_session.add(video)
    db_session.flush()

    comment = Comment(
        youtube_comment_id="c_api_001",
        video_id=video.id,
        text="Can I use Podman?",
        author="Tester",
        status="drafted"
    )
    db_session.add(comment)
    db_session.flush()

    reply = Reply(
        comment_id=comment.id,
        draft_text="Yes, as covered at [02:45] you can alias podman-compose.",
        final_text="Yes, as covered at [02:45] you can alias podman-compose.",
        source="ai"
    )
    db_session.add(reply)
    db_session.commit()

    # Call approve endpoint
    resp = api_client.post(f"/api/comments/{comment.id}/approve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["new_status"] in ("approved", "published")

    # Verify database state
    db_session.refresh(comment)
    assert comment.status in ("approved", "published")

    # Verify audit log entry
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.event == "approve_draft").order_by(AuditLog.id.desc())
    ).first()
    assert audit is not None
    assert audit.payload["comment_id"] == comment.id
    assert audit.actor == "user"


def test_api_edit_flow(api_client, db_session):
    video = Video(youtube_video_id="vid_api_2", title="API Edit Video")
    db_session.add(video)
    db_session.flush()

    comment = Comment(
        youtube_comment_id="c_api_002",
        video_id=video.id,
        text="What Python version?",
        author="DevUser",
        status="drafted"
    )
    db_session.add(comment)
    db_session.flush()

    reply = Reply(
        comment_id=comment.id,
        draft_text="Original AI draft",
        final_text="Original AI draft",
        source="ai"
    )
    db_session.add(reply)
    db_session.commit()

    # User edits the draft
    edited_text = "You need Python 3.11 or 3.12, as mentioned around [00:45]."
    resp = api_client.post(f"/api/comments/{comment.id}/edit", json={"final_text": edited_text})
    assert resp.status_code == 200

    db_session.refresh(comment)
    assert comment.status == "approved"
    assert comment.reply.final_text == edited_text
    assert comment.reply.source == "edited"  # Marks source as edited

    # Verify audit log
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.event == "edit_draft").order_by(AuditLog.id.desc())
    ).first()
    assert audit is not None
    assert audit.payload["new_text"] == edited_text
    assert audit.payload["previous_text"] == "Original AI draft"


def test_api_reject_flow(api_client, db_session):
    video = Video(youtube_video_id="vid_api_3", title="API Reject Video")
    db_session.add(video)
    db_session.flush()

    comment = Comment(
        youtube_comment_id="c_api_003",
        video_id=video.id,
        text="Spam comment link bit.ly/spam",
        author="Bot",
        status="escalated"
    )
    db_session.add(comment)
    db_session.commit()

    resp = api_client.post(
        f"/api/comments/{comment.id}/reject",
        json={"reason": "Spam bot link"}
    )
    assert resp.status_code == 200

    db_session.refresh(comment)
    assert comment.status == "rejected"

    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.event == "reject_draft").order_by(AuditLog.id.desc())
    ).first()
    assert audit is not None
    assert audit.payload["rejection_reason"] == "Spam bot link"


def test_api_stats_endpoint(api_client):
    resp = api_client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_comments" in data
    assert "approval_rate" in data
    assert "edit_rate" in data
    assert "shadow_mode" in data


def test_api_ask_ai_sensitive(api_client, db_session):
    video = Video(youtube_video_id="vid_api_sens", title="Sensitive Test Video")
    db_session.add(video)
    db_session.flush()

    comment = Comment(
        youtube_comment_id="c_api_sens_001",
        video_id=video.id,
        text="I am feeling hopeless and thinking of self-harm after this.",
        author="StrugglingViewer",
        status="escalated",
    )
    db_session.add(comment)
    db_session.flush()

    analysis = Analysis(
        comment_id=comment.id,
        category="sensitive",
        confidence=0.99,
        action="ESCALATE",
        reason="Safety alert: viewer distress / self-harm mention",
        model_used="mock-model",
    )
    db_session.add(analysis)
    db_session.commit()

    resp = api_client.post(f"/api/comments/{comment.id}/ask-ai", json={"user_instruction": "be supportive"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["comment_id"] == comment.id
    assert data["category"] == "sensitive"
    assert data["is_sensitive"] is True
    assert data["sensitive_notice"] is not None
    assert "sensitive" in data["sensitive_notice"].lower()
    assert len(data["sample_response"]) > 0

    # Verify audit log
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.event == "ask_ai").order_by(AuditLog.id.desc())
    ).first()
    assert audit is not None
    assert audit.payload["comment_id"] == comment.id
    assert audit.payload["is_sensitive"] is True


def test_api_ask_ai_standard(api_client, db_session):
    video = Video(youtube_video_id="vid_api_std", title="Standard Test Video")
    db_session.add(video)
    db_session.flush()

    comment = Comment(
        youtube_comment_id="c_api_std_001",
        video_id=video.id,
        text="This video helped me so much, thank you!",
        author="HappyLearner",
        status="drafted",
    )
    db_session.add(comment)
    db_session.flush()

    analysis = Analysis(
        comment_id=comment.id,
        category="praise",
        confidence=0.98,
        action="DRAFT",
        reason="High confidence positive feedback",
        model_used="mock-model",
    )
    db_session.add(analysis)
    db_session.commit()

    resp = api_client.post(f"/api/comments/{comment.id}/ask-ai")
    assert resp.status_code == 200
    data = resp.json()

    assert data["comment_id"] == comment.id
    assert data["category"] == "praise"
    assert data["is_sensitive"] is False
    assert len(data["sample_response"]) > 0


