import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ingestion.youtube_oauth import YouTubeOAuthManager
from backend.app.core.security import decrypt_token, encrypt_token
from backend.app.workers.celery_app import get_celery_status, sync_channel_comments_task
from backend.app.db.models import Channel


def test_oauth_manager_unconfigured():
    mgr = YouTubeOAuthManager(client_id=None, client_secret=None)
    assert mgr.is_configured() is False
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID is not configured"):
        mgr.get_authorization_url()


def test_oauth_manager_generates_correct_url():
    mgr = YouTubeOAuthManager(
        client_id="test_client_id_123",
        client_secret="test_client_secret_abc",
        redirect_uri="http://localhost:8000/api/auth/youtube/callback",
    )
    assert mgr.is_configured() is True
    url = mgr.get_authorization_url(state="test_state_val")
    assert "accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=test_client_id_123" in url
    assert "youtube.readonly" in url
    assert "youtube.force-ssl" in url
    assert "state=test_state_val" in url


def test_channel_registration_and_token_encryption(db_session: Session):
    mgr = YouTubeOAuthManager(client_id="dummy", client_secret="dummy")
    plain_refresh = "1//mock_refresh_token_very_secret_xyz"

    channel = mgr.register_or_update_channel(
        db=db_session,
        channel_id="UC_test_channel_001",
        refresh_token=plain_refresh,
        tone_setting="friendly_technical",
    )

    assert channel.id is not None
    assert channel.google_id == "UC_test_channel_001"
    assert channel.encrypted_refresh_token != plain_refresh

    # Decrypt and verify round-trip integrity
    decrypted = decrypt_token(channel.encrypted_refresh_token)
    assert decrypted == plain_refresh


def test_oauth_status_api(db_session: Session):
    from backend.app.db.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        resp = client.get("/api/auth/youtube/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "connected_channels" in data
        assert isinstance(data["connected_channels"], list)
    finally:
        app.dependency_overrides.clear()


def test_celery_worker_graceful_status():
    status_info = get_celery_status()
    assert "celery_installed" in status_info
    assert "status" in status_info

    # Test fallback task execution
    res = sync_channel_comments_task(channel_id=1)
    assert res["channel_id"] == 1
    assert "synced_comments" in res

