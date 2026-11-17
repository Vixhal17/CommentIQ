from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

class CommentImportItem(BaseModel):
    youtube_comment_id: str = Field(..., description="Unique YouTube comment ID")
    youtube_video_id: str = Field(..., description="Target YouTube video ID")
    text: str = Field(..., min_length=1, description="Comment text body")
    author: str = Field(default="Anonymous", description="Author display name")
    source: Literal["real", "synthetic"] = "real"
    published_at: Optional[datetime] = None

    @field_validator("youtube_comment_id", "youtube_video_id")
    @classmethod
    def clean_ids(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("ID cannot be empty")
        return s

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Comment text cannot be empty")
        return s


class ImportSummary(BaseModel):
    total_processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)

