import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.db.models import Video, TranscriptChunk, AuditLog
from backend.app.ingestion.youtube_transcriber import YouTubeTranscriber, TranscriptResult
from backend.app.retrieval.transcript_loader import TranscriptSegment
from backend.app.retrieval.chunker import Chunk


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


def test_extract_video_id_patterns():
    valid_cases = [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ&feature=share", "dQw4w9WgXcQ"),
    ]
    for url, expected_id in valid_cases:
        assert YouTubeTranscriber.extract_video_id(url) == expected_id

    invalid_cases = ["", "invalid", "not_11_chars", "https://vimeo.com/12345"]
    for url in invalid_cases:
        assert YouTubeTranscriber.extract_video_id(url) is None


def test_youtube_transcriber_chunking():
    # Mock segments
    mock_segments = [
        TranscriptSegment(start_time=0.0, text="Welcome to this tutorial on Docker and PostgreSQL containers."),
        TranscriptSegment(start_time=15.5, text="In this section, we will configure the docker-compose file."),
        TranscriptSegment(start_time=45.0, text="Make sure you have Docker Desktop running on port 5432."),
        TranscriptSegment(start_time=95.0, text="Next we create the pgvector extension with CREATE EXTENSION vector."),
    ]

    with patch.object(YouTubeTranscriber, "fetch_video_metadata", return_value={"title": "Docker Tutorial", "author": "TechPro"}):
        with patch.object(YouTubeTranscriber, "fetch_youtube_captions", return_value=mock_segments):
            res = YouTubeTranscriber.transcribe("dQw4w9WgXcQ", chunk_target_chars=120, chunk_overlap_chars=20)
            assert res.video_id == "dQw4w9WgXcQ"
            assert res.title == "Docker Tutorial"
            assert res.author == "TechPro"
            assert res.source == "youtube_captions"
            assert len(res.chunks) >= 1
            assert res.chunks[0].text.startswith("[00:00]")


def test_api_transcribe_url_endpoint(api_client, db_session):
    mock_chunks = [
        Chunk(text="[00:00] First knowledge chunk from video.", start_time=0.0),
        Chunk(text="[01:15] Second chunk explaining Python 3.11 requirements.", start_time=75.0),
    ]
    mock_result = TranscriptResult(
        video_id="test_vid_999",
        title="Automated Test Video",
        author="DevChannel",
        source="youtube_captions",
        raw_snippet_count=20,
        chunks=mock_chunks,
    )

    with patch.object(YouTubeTranscriber, "transcribe", return_value=mock_result):
        resp = api_client.post(
            "/api/videos/transcribe-url",
            json={
                "youtube_url": "https://www.youtube.com/watch?v=test_vid_999",
                "list_name": "Docker & Vector Workspace",
                "list_description": "Auto-transcribed from test_vid_999",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "success"
        assert data["video_id"] == "test_vid_999"
        assert data["list_title"] == "Docker & Vector Workspace"
        assert data["chunks_indexed"] == 2
        assert len(data["sample_chunks"]) == 2

        # Verify DB Video record
        video = db_session.scalars(select(Video).where(Video.id == data["list_id"])).first()
        assert video is not None
        assert video.transcript_status == "processed"

        # Verify DB TranscriptChunk records
        chunks = db_session.scalars(select(TranscriptChunk).where(TranscriptChunk.video_id == video.id)).all()
        assert len(chunks) == 2

        # Verify Audit Log
        audit = db_session.scalars(
            select(AuditLog).where(AuditLog.event == "transcribe_youtube_url").order_by(AuditLog.id.desc())
        ).first()
        assert audit is not None
        assert audit.payload["youtube_video_id"] == "test_vid_999"
