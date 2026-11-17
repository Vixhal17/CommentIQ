import csv
import json
from pathlib import Path
from typing import Union, Sequence
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.logging import logger, current_comment_id
from backend.app.db.models import Comment, Video, AuditLog
from backend.app.ingestion.schemas import CommentImportItem, ImportSummary


class CommentImporter:
    """
    Idempotent importer for YouTube comments from CSV, JSON, or structured dicts.
    Guarantees no duplicate records on repeated runs.
    """

    def __init__(self, db: Session):
        self.db = db

    def load_from_file(self, file_path: Union[str, Path]) -> list[dict]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Import file not found: {path}")

        records = []
        suffix = path.suffix.lower()

        if suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and "comments" in data:
                    records = data["comments"]
                else:
                    raise ValueError("JSON file must be a list of comments or contain a 'comments' array.")
        elif suffix == ".csv":
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(dict(row))
        else:
            raise ValueError(f"Unsupported file format '{suffix}'. Supported: .csv, .json")

        return records

    def get_or_create_video(self, youtube_video_id: str, title: str = "Imported Video") -> Video:
        stmt = select(Video).where(Video.youtube_video_id == youtube_video_id)
        video = self.db.scalars(stmt).first()
        if not video:
            video = Video(
                youtube_video_id=youtube_video_id,
                title=title,
                description="Auto-created during comment import",
                transcript_status="pending",
            )
            self.db.add(video)
            self.db.flush()
        return video

    def import_records(self, raw_records: Sequence[dict]) -> ImportSummary:
        summary = ImportSummary()

        for raw_item in raw_records:
            summary.total_processed += 1
            try:
                item = CommentImportItem(**raw_item)
            except Exception as val_err:
                msg = f"Validation failed for record: {val_err}"
                logger.warning(msg)
                summary.errors.append(msg)
                continue

            # Set correlation ID for logs
            token = current_comment_id.set(item.youtube_comment_id)
            try:
                video = self.get_or_create_video(item.youtube_video_id)

                # Check for existing comment by UNIQUE youtube_comment_id
                stmt = select(Comment).where(Comment.youtube_comment_id == item.youtube_comment_id)
                existing = self.db.scalars(stmt).first()

                if existing:
                    # Idempotency check: update if text changed, otherwise skip
                    if existing.text != item.text or existing.author != item.author:
                        existing.text = item.text
                        existing.author = item.author
                        summary.updated += 1
                        logger.info("Updated existing comment details")
                    else:
                        summary.skipped += 1
                        logger.info("Comment already exists; skipped without duplication")
                else:
                    new_comment = Comment(
                        youtube_comment_id=item.youtube_comment_id,
                        video_id=video.id,
                        text=item.text,
                        author=item.author,
                        status="new",
                        source=item.source,
                        processed_at=None,
                        created_at=datetime.now(timezone.utc),
                    )
                    self.db.add(new_comment)
                    summary.inserted += 1
                    logger.info("Inserted new comment for triage")

            finally:
                current_comment_id.reset(token)

        # Record audit log event
        audit = AuditLog(
            actor="system",
            event="comment_import",
            payload={
                "total": summary.total_processed,
                "inserted": summary.inserted,
                "updated": summary.updated,
                "skipped": summary.skipped,
                "errors_count": len(summary.errors),
            },
        )
        self.db.add(audit)
        self.db.commit()

        logger.info(
            f"Import finished. Inserted: {summary.inserted}, "
            f"Updated: {summary.updated}, Skipped: {summary.skipped}, Errors: {len(summary.errors)}"
        )
        return summary

    def import_file(self, file_path: Union[str, Path]) -> ImportSummary:
        records = self.load_from_file(file_path)
        return self.import_records(records)

