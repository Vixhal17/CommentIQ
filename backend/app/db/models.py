from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    TypeDecorator,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

Base = declarative_base()


class CompatibleVector(TypeDecorator):
    """
    Transparent vector type: compiles to pgvector's native Vector on PostgreSQL,
    and falls back to JSON on other dialects (such as SQLite for unit testing).
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(100), unique=True, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=True)
    tone_setting = Column(String(50), default="helpful_concise", nullable=False)

    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    youtube_video_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    transcript_status = Column(String(50), default="pending", nullable=False)  # pending, processed, missing
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    channel = relationship("Channel", back_populates="videos")
    chunks = relationship("TranscriptChunk", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="video")


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True, nullable=False)
    text = Column(Text, nullable=False)
    start_time = Column(Float, default=0.0, nullable=False)
    embedding = Column(CompatibleVector(384), nullable=True)

    video = relationship("Video", back_populates="chunks")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_comment_id = Column(String(100), unique=True, index=True, nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), index=True, nullable=True)
    text = Column(Text, nullable=False)
    author = Column(String(255), default="", nullable=False)
    status = Column(String(50), default="new", index=True, nullable=False)  # new, processing, drafted, approved, published, escalated
    source = Column(String(50), default="real", nullable=False)  # real, synthetic
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    video = relationship("Video", back_populates="comments")
    analysis = relationship("Analysis", back_populates="comment", uselist=False, cascade="all, delete-orphan")
    reply = relationship("Reply", back_populates="comment", uselist=False, cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True)
    category = Column(String(50), nullable=False)  # question, praise, complaint, business_collab, technical_correction, spam, sensitive
    confidence = Column(Float, default=0.0, nullable=False)
    retrieval_score = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    action = Column(String(50), nullable=False)  # AUTO, DRAFT, ESCALATE
    reason = Column(Text, default="", nullable=False)
    rule_name = Column(String(100), nullable=True)
    persona_name = Column(String(100), nullable=True)
    model_used = Column(String(100), default="", nullable=False)
    fallback_used = Column(Boolean, default=False, nullable=False)
    judge_independent = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    comment = relationship("Comment", back_populates="analysis")


class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    draft_text = Column(Text, default="", nullable=False)
    final_text = Column(Text, default="", nullable=False)
    source = Column(String(50), default="ai", nullable=False)  # ai, edited, manual
    published_at = Column(DateTime(timezone=True), nullable=True)
    youtube_reply_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    comment = relationship("Comment", back_populates="reply")


class LLMCache(Base):
    __tablename__ = "llm_cache"

    key_hash = Column(String(64), primary_key=True)  # SHA-256
    response = Column(JSON, nullable=False)
    tokens = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    actor = Column(String(50), default="system", nullable=False)  # system, user, llm
    event = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)


class AutopilotRule(Base):
    __tablename__ = "autopilot_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=10, nullable=False)  # lower number = higher priority
    action = Column(String(20), nullable=False)  # "AUTO", "DRAFT", "ESCALATE"

    # Conditions
    categories = Column(JSON, default=list, nullable=False)  # e.g. ["praise"], empty means any category
    min_confidence = Column(Float, nullable=True)  # e.g. 0.85
    min_faithfulness = Column(Float, nullable=True)  # e.g. 0.80
    min_retrieval_score = Column(Float, nullable=True)  # e.g. 0.35
    require_citations = Column(Boolean, default=False, nullable=False)  # must contain [MM:SS] or citation markers
    max_comment_words = Column(Integer, nullable=True)  # e.g. 25 words
    keywords_any = Column(JSON, default=list, nullable=False)  # comment must contain at least one of these
    negative_keywords = Column(JSON, default=list, nullable=False)  # comment must NOT contain any of these
    author_match = Column(String(100), nullable=True)  # author pattern/substring
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CreatorPersona(Base):
    __tablename__ = "creator_personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="", nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)

    # Stylistic attributes
    greeting_pattern = Column(String(100), default="Hey @author!", nullable=False)  # "Hey @author!", "Hi there,", "None"
    sign_off_pattern = Column(String(100), default="None", nullable=False)           # "- Creator", "Hope this helps!", "Cheers", "None"
    formality = Column(String(20), default="neutral", nullable=False)               # "casual", "neutral", "formal"
    emoji_density = Column(String(20), default="minimal", nullable=False)           # "none", "minimal", "expressive"
    max_sentences = Column(Integer, default=2, nullable=False)                      # 1 to 4
    custom_voice_notes = Column(Text, default="", nullable=False)                   # Specific creator notes

    # Dynamic few-shot comment-reply pairs (list of {"comment": "...", "reply": "..."})
    sample_pairs = Column(JSON, default=list, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)



