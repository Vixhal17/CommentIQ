from pathlib import Path
from sqlalchemy import select, func
from backend.app.db.models import Comment, Video, AuditLog
from backend.app.ingestion.importer import CommentImporter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT_DIR / "data" / "sample_comments.csv"
JSON_PATH = ROOT_DIR / "data" / "sample_comments.json"


def test_csv_import_and_idempotency(db_session):
    importer = CommentImporter(db=db_session)

    # Initial Run
    summary1 = importer.import_file(CSV_PATH)
    assert summary1.total_processed == 15
    assert summary1.inserted == 15
    assert summary1.skipped == 0
    assert len(summary1.errors) == 0

    # Verify rows in DB
    total_comments = db_session.scalar(select(func.count(Comment.id)))
    assert total_comments == 15

    # Second Run (Idempotency verification)
    summary2 = importer.import_file(CSV_PATH)
    assert summary2.total_processed == 15
    assert summary2.inserted == 0  # CRITICAL: zero duplicates created
    assert summary2.skipped == 15
    assert len(summary2.errors) == 0

    # Count must remain exactly 15
    total_after = db_session.scalar(select(func.count(Comment.id)))
    assert total_after == 15


def test_json_import(db_session):
    importer = CommentImporter(db=db_session)
    summary = importer.import_file(JSON_PATH)

    assert summary.total_processed == 3
    assert summary.inserted == 3
    assert summary.skipped == 0


def test_audit_log_recorded(db_session):
    importer = CommentImporter(db=db_session)
    importer.import_file(JSON_PATH)

    stmt = select(AuditLog).where(AuditLog.event == "comment_import")
    logs = db_session.scalars(stmt).all()
    assert len(logs) >= 1
    assert "inserted" in logs[0].payload

