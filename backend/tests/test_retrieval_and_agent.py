from pathlib import Path
import json
import pytest
from sqlalchemy import select

from backend.app.retrieval.transcript_loader import TranscriptLoader, parse_timestamp_to_seconds
from backend.app.retrieval.chunker import TranscriptChunker
from backend.app.retrieval.embeddings import get_embedding_engine
from backend.app.retrieval.retriever import ScopedRetriever
from backend.app.ingestion.importer import CommentImporter
from backend.app.db.models import Comment, Video, Channel
from backend.app.agent.graph import TriageAgent

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TRANSCRIPT_PATH = ROOT_DIR / "data" / "sample_transcripts" / "vid_101.txt"
CSV_PATH = ROOT_DIR / "data" / "sample_comments.csv"


def test_transcript_parsing():
    loader = TranscriptLoader()
    segments = loader.load_from_file(TRANSCRIPT_PATH)
    assert len(segments) >= 10
    assert segments[0].start_time == 0.0
    assert "Python 3.11" in segments[1].text
    assert parse_timestamp_to_seconds("02:45") == 165.0
    assert parse_timestamp_to_seconds("01:23:45") == 5025.0


def test_chunking_preserves_timestamp():
    loader = TranscriptLoader()
    segments = loader.load_from_file(TRANSCRIPT_PATH)
    chunker = TranscriptChunker(target_chars=300, overlap_chars=50)
    chunks = chunker.chunk_segments(segments)

    assert len(chunks) >= 3
    for ch in chunks:
        assert ch.formatted_timestamp.startswith("[")
        assert len(ch.text) > 20


def test_scoped_retrieval(db_session):
    loader = TranscriptLoader()
    segments = loader.load_from_file(TRANSCRIPT_PATH)
    chunks = TranscriptChunker().chunk_segments(segments)

    # Setup video in db
    video = db_session.scalars(select(Video).where(Video.youtube_video_id == "vid_scoped_test")).first()
    if not video:
        video = Video(youtube_video_id="vid_scoped_test", title="AI Triage Tutorial", transcript_status="processed")
        db_session.add(video)
        db_session.commit()

    retriever = ScopedRetriever(db=db_session)
    indexed = retriever.index_video_chunks(video.id, chunks)
    assert indexed > 0

    # Retrieve relevant query
    results, top_score = retriever.retrieve("What python version is needed?", video.id, top_k=2)
    assert len(results) > 0
    assert any("Python" in r.text for r in results)

    # Scoped check: querying another non-existent video returns 0 chunks
    other_results, other_score = retriever.retrieve("Python version", video_id=9999)
    assert len(other_results) == 0
    assert other_score == 0.0


def test_agent_skips_retrieval_for_praise(db_session, llm_client, mock_llm):
    # Queue classification for praise
    mock_llm.queue_response(json.dumps({
        "category": "praise",
        "confidence": 0.98,
        "rationale": "Viewer is complimenting the video",
        "sensitive": False
    }))

    video = db_session.scalars(select(Video).where(Video.youtube_video_id == "vid_praise_test")).first()
    if not video:
        video = Video(youtube_video_id="vid_praise_test", title="AI Triage Tutorial")
        db_session.add(video)
        db_session.flush()

    comment = Comment(
        youtube_comment_id="c_praise_test",
        video_id=video.id,
        text="Awesome tutorial, thank you!",
        author="Fan",
        status="new"
    )
    db_session.add(comment)
    db_session.commit()

    agent = TriageAgent(db=db_session, llm_client=llm_client)
    final_state = agent.process_comment(comment)

    assert final_state.category == "praise"
    # CRITICAL: Step 2 in specification: skip retrieval and drafting for non-questions!
    assert len(final_state.retrieved_chunks) == 0
    assert final_state.draft_text is None


def test_agent_abstains_on_unanswerable_question(db_session, llm_client, mock_llm):
    # Queue classification as question
    mock_llm.queue_response(json.dumps({
        "category": "question",
        "confidence": 0.95,
        "rationale": "Viewer asks about upcoming mobile release",
        "sensitive": False
    }))
    # Queue drafter returning ABSTAIN
    mock_llm.queue_response("ABSTAIN")

    video = db_session.scalars(select(Video).where(Video.youtube_video_id == "vid_praise_test")).first()
    if not video:
        video = Video(youtube_video_id="vid_praise_test", title="AI Triage Tutorial")
        db_session.add(video)
        db_session.flush()

    comment = Comment(
        youtube_comment_id="c_unanswerable_test",
        video_id=video.id,
        text="Will you release an iOS version next year?",
        author="UserX",
        status="new"
    )
    db_session.add(comment)
    db_session.commit()

    agent = TriageAgent(db=db_session, llm_client=llm_client)
    final_state = agent.process_comment(comment)

    assert final_state.category == "question"
    assert final_state.abstained is True
    assert final_state.draft_text == "ABSTAIN"


def test_all_15_demo_comments_run_end_to_end(db_session, llm_client, mock_llm):
    # Ingest comments and transcript
    importer = CommentImporter(db=db_session)
    importer.import_file(CSV_PATH)

    video = db_session.scalars(select(Video).where(Video.youtube_video_id == "vid_101")).first()
    assert video is not None

    loader = TranscriptLoader()
    segments = loader.load_from_file(TRANSCRIPT_PATH)
    chunks = TranscriptChunker().chunk_segments(segments)

    retriever = ScopedRetriever(db=db_session)
    retriever.index_video_chunks(video.id, chunks)

    demo_ids = [f"c_{i:03d}" for i in range(1, 16)]
    comments = db_session.scalars(
        select(Comment).where(Comment.youtube_comment_id.in_(demo_ids)).order_by(Comment.id)
    ).all()
    assert len(comments) == 15

    agent = TriageAgent(db=db_session, llm_client=llm_client)

    processed_states = []
    for comment in comments:
        state = agent.process_comment(comment)
        processed_states.append(state)

        # Every comment must have a valid category
        assert state.category in [
            "question", "praise", "complaint", "business_collab",
            "technical_correction", "spam", "sensitive"
        ]

        if state.category == "question":
            assert len(state.retrieved_chunks) > 0
            assert state.draft_text is not None
        else:
            assert len(state.retrieved_chunks) == 0
            assert state.draft_text is None

    assert len(processed_states) == 15

