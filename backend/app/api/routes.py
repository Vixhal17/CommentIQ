from datetime import datetime, timezone
import json
import uuid
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from backend.app.db.session import get_db
from backend.app.db.models import Comment, Video, Analysis, Reply, AuditLog, TranscriptChunk, AutopilotRule, CreatorPersona
from backend.app.api.schemas import (
    CommentQueueItem,
    CommentDetailResponse,
    EditReplyRequest,
    RejectCommentRequest,
    StatsResponse,
    AnalysisSummary,
    ReplySummary,
    CreateListRequest,
    ListSummaryResponse,
    AskAIRequest,
    AskAIResponse,
    AskAIOutput,
    TranscribeUrlRequest,
    TranscribeUrlResponse,
    AutopilotRuleCreate,
    AutopilotRuleUpdate,
    AutopilotRuleResponse,
    TestRuleRequest,
    TestRuleResponse,
    CreatorPersonaCreate,
    CreatorPersonaUpdate,
    CreatorPersonaResponse,
    ExtractToneRequest,
    ExtractToneResponse,
    PreviewDraftRequest,
    PreviewDraftResponse,
)
from backend.app.llm.client import LLMClient
from backend.app.safety.service import TriageService
from backend.app.safety.router import RiskRouter
from backend.app.safety.rules import seed_default_autopilot_rules, DEFAULT_AUTOPILOT_RULES
from backend.app.persona.service import (
    seed_default_personas,
    get_active_persona,
    set_active_persona,
    extract_tone_from_texts,
    extract_tone_from_approved_db,
    build_persona_prompt_block,
)
from backend.app.agent.preferences import UserPreferences, get_default_preferences
from backend.app.ingestion.doc_parser import DocumentCommentsParser, ReferenceDocumentParser
from backend.app.ingestion.youtube_transcriber import YouTubeTranscriber
from backend.app.retrieval.retriever import ScopedRetriever
from backend.config.settings import settings
from backend.app.core.logging import logger

router = APIRouter(prefix="/api", tags=["Triage API"])

# In-memory active preference cache
ACTIVE_PREFERENCES: UserPreferences = get_default_preferences()


@router.get("/queue", response_model=List[CommentQueueItem])
def get_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    action_filter: Optional[str] = Query(None, alias="action"),
    list_id: Optional[int] = Query(None, alias="list_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve comments queue with filtering by status, category, action, or list/video."""
    query = select(Comment).order_by(Comment.id.desc())

    if list_id:
        query = query.where(Comment.video_id == list_id)

    if status_filter:
        query = query.where(Comment.status == status_filter)

    if category_filter or action_filter:
        query = query.join(Comment.analysis)
        if category_filter:
            query = query.where(Analysis.category == category_filter)
        if action_filter:
            query = query.where(Analysis.action == action_filter)

    query = query.offset(offset).limit(limit)
    comments = db.scalars(query).all()

    items = []
    for c in comments:
        video_title = c.video.title if c.video else "Unknown Video"
        analysis_data = None
        if c.analysis:
            analysis_data = AnalysisSummary(
                category=c.analysis.category,
                confidence=c.analysis.confidence,
                retrieval_score=c.analysis.retrieval_score,
                faithfulness=c.analysis.faithfulness,
                action=c.analysis.action,
                reason=c.analysis.reason,
                rule_name=getattr(c.analysis, "rule_name", None),
                persona_name=getattr(c.analysis, "persona_name", None),
                model_used=c.analysis.model_used,
                fallback_used=c.analysis.fallback_used,
                judge_independent=c.analysis.judge_independent,
            )

        reply_data = None
        if c.reply:
            reply_data = ReplySummary(
                draft_text=c.reply.draft_text,
                final_text=c.reply.final_text,
                source=c.reply.source,
                published_at=c.reply.published_at,
            )

        items.append(
            CommentQueueItem(
                id=c.id,
                youtube_comment_id=c.youtube_comment_id,
                video_id=c.video_id,
                video_title=video_title,
                author=c.author,
                text=c.text,
                status=c.status,
                source=c.source,
                created_at=c.created_at,
                analysis=analysis_data,
                reply=reply_data,
            )
        )
    return items


@router.get("/comments/{comment_id}", response_model=CommentDetailResponse)
def get_comment_detail(comment_id: int, db: Session = Depends(get_db)):
    """Fetch complete detail view for a comment including grounding chunks and audit trail."""
    comment = db.scalars(select(Comment).where(Comment.id == comment_id)).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    video_title = comment.video.title if comment.video else "Unknown Video"

    analysis_data = None
    if comment.analysis:
        analysis_data = AnalysisSummary(
            category=comment.analysis.category,
            confidence=comment.analysis.confidence,
            retrieval_score=comment.analysis.retrieval_score,
            faithfulness=comment.analysis.faithfulness,
            action=comment.analysis.action,
            reason=comment.analysis.reason,
            rule_name=getattr(comment.analysis, "rule_name", None),
            persona_name=getattr(comment.analysis, "persona_name", None),
            model_used=comment.analysis.model_used,
            fallback_used=comment.analysis.fallback_used,
            judge_independent=comment.analysis.judge_independent,
        )

    reply_data = None
    if comment.reply:
        reply_data = ReplySummary(
            draft_text=comment.reply.draft_text,
            final_text=comment.reply.final_text,
            source=comment.reply.source,
            published_at=comment.reply.published_at,
        )

    # Fetch scoped chunks if video exists
    retrieved_chunks = []
    if comment.video_id:
        chunks = db.scalars(
            select(TranscriptChunk).where(TranscriptChunk.video_id == comment.video_id).limit(5)
        ).all()
        for ch in chunks:
            sec = int(ch.start_time)
            mins = sec // 60
            s = sec % 60
            retrieved_chunks.append({
                "chunk_id": ch.id,
                "timestamp": f"[{mins:02d}:{s:02d}]",
                "text": ch.text,
            })

    # Fetch audit history related to this comment
    audit_records = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(20)
    ).all()
    history = []
    for a in audit_records:
        if a.payload.get("comment_id") == comment.id or a.payload.get("youtube_comment_id") == comment.youtube_comment_id:
            history.append({
                "timestamp": a.timestamp.isoformat(),
                "actor": a.actor,
                "event": a.event,
                "payload": a.payload,
            })

    return CommentDetailResponse(
        id=comment.id,
        youtube_comment_id=comment.youtube_comment_id,
        video_id=comment.video_id,
        video_title=video_title,
        author=comment.author,
        text=comment.text,
        status=comment.status,
        source=comment.source,
        created_at=comment.created_at,
        analysis=analysis_data,
        reply=reply_data,
        retrieved_chunks=retrieved_chunks,
        audit_history=history,
    )


@router.post("/comments/{comment_id}/approve")
def approve_comment(comment_id: int, db: Session = Depends(get_db)):
    """Approve a draft reply with row-level locking and audit logging."""
    stmt = select(Comment).where(Comment.id == comment_id)
    if "postgresql" in str(db.bind.url):
        stmt = stmt.with_for_update()

    comment = db.scalars(stmt).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    old_status = comment.status
    new_status = "published" if settings.AUTO_PUBLISH_ENABLED else "approved"
    comment.status = new_status

    if comment.reply:
        comment.reply.published_at = datetime.now(timezone.utc)

    # Record audit log
    audit = AuditLog(
        actor="user",
        event="approve_draft",
        payload={
            "comment_id": comment.id,
            "youtube_comment_id": comment.youtube_comment_id,
            "old_status": old_status,
            "new_status": new_status,
            "approved_text": comment.reply.final_text if comment.reply else "",
        },
    )
    db.add(audit)
    db.commit()

    logger.info(f"Comment #{comment.id} approved by user (status: {old_status} -> {new_status})")
    return {"status": "success", "new_status": new_status, "comment_id": comment.id}


@router.post("/comments/{comment_id}/edit")
def edit_comment(
    comment_id: int,
    payload: EditReplyRequest,
    db: Session = Depends(get_db),
):
    """Edit draft response, update source to 'edited', and record in audit log."""
    stmt = select(Comment).where(Comment.id == comment_id)
    if "postgresql" in str(db.bind.url):
        stmt = stmt.with_for_update()

    comment = db.scalars(stmt).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    previous_draft = ""
    if comment.reply:
        previous_draft = comment.reply.final_text
        comment.reply.final_text = payload.final_text
        comment.reply.source = "edited"
        comment.reply.published_at = datetime.now(timezone.utc)
    else:
        reply = Reply(
            comment_id=comment.id,
            draft_text=payload.final_text,
            final_text=payload.final_text,
            source="edited",
            published_at=datetime.now(timezone.utc),
        )
        db.add(reply)

    old_status = comment.status
    comment.status = "approved"

    audit = AuditLog(
        actor="user",
        event="edit_draft",
        payload={
            "comment_id": comment.id,
            "youtube_comment_id": comment.youtube_comment_id,
            "old_status": old_status,
            "new_status": "approved",
            "previous_text": previous_draft,
            "new_text": payload.final_text,
        },
    )
    db.add(audit)
    db.commit()

    logger.info(f"Comment #{comment.id} draft edited and approved by user")
    return {"status": "success", "new_status": "approved", "comment_id": comment.id}


@router.post("/comments/{comment_id}/reject")
def reject_comment(
    comment_id: int,
    payload: RejectCommentRequest,
    db: Session = Depends(get_db),
):
    """Reject a drafted reply and record rejection reason in audit log."""
    stmt = select(Comment).where(Comment.id == comment_id)
    if "postgresql" in str(db.bind.url):
        stmt = stmt.with_for_update()

    comment = db.scalars(stmt).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    old_status = comment.status
    comment.status = "rejected"

    audit = AuditLog(
        actor="user",
        event="reject_draft",
        payload={
            "comment_id": comment.id,
            "youtube_comment_id": comment.youtube_comment_id,
            "old_status": old_status,
            "new_status": "rejected",
            "rejection_reason": payload.reason,
        },
    )
    db.add(audit)
    db.commit()

    logger.info(f"Comment #{comment.id} rejected by user (reason: {payload.reason})")
    return {"status": "success", "new_status": "rejected", "comment_id": comment.id}


@router.post("/comments/{comment_id}/ask-ai", response_model=AskAIResponse)
def ask_ai_for_sample_response(
    comment_id: int,
    payload: Optional[AskAIRequest] = None,
    db: Session = Depends(get_db),
):
    """
    On-demand AI assistant for the creator in the review drawer.
    Provides a tailored sample response and explicit sensitive case guidance
    when category is 'sensitive'.
    """
    comment = db.scalars(select(Comment).where(Comment.id == comment_id)).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    category = (comment.analysis.category if comment.analysis else "question").strip().lower()
    is_category_sensitive = category == "sensitive"

    # Fetch reference chunks if available
    reference_chunks_context = ""
    if comment.video_id:
        chunks = db.scalars(
            select(TranscriptChunk)
            .where(TranscriptChunk.video_id == comment.video_id)
            .limit(3)
        ).all()
        if chunks:
            chunk_texts = [f"- {c.text}" for c in chunks]
            reference_chunks_context = "REFERENCE KNOWLEDGE CHUNKS:\n" + "\n".join(chunk_texts)

    user_instruction = (payload.user_instruction or "").strip() if payload else ""
    channel_tone = ACTIVE_PREFERENCES.tone or "helpful_concise"

    prompt_content = f"""You are an expert AI Creator Assistant helping a content creator draft an appropriate, professional, and empathetic reply to a YouTube viewer's comment.

COMMENT INFORMATION:
- Author: {comment.author or "Viewer"}
- Comment: "{comment.text}"
- Detected Category: {category}
- Channel Tone: {channel_tone}
- Additional Creator Instruction: {user_instruction or "None provided"}

{reference_chunks_context}

CRITICAL RULES:
1. IF CATEGORY IS "sensitive" OR IF THE COMMENT TOUCHES ON SENSITIVE TOPICS (e.g. self-harm, legal threats, severe harassment, privacy, or safety violations):
   - You MUST set "is_sensitive" to true.
   - In "sensitive_notice", you MUST explicitly mention that this is a sensitive case and explain the risk (e.g., "⚠️ SENSITIVE CASE NOTICE: This comment has been identified as a sensitive case involving safety, legal dispute, or harassment.").
   - In "guidance", clearly explain how the creator should handle it (e.g., avoid public argument, protect user privacy, direct to private email/support, or de-escalate calmly).
   - In "sample_response", provide a carefully worded, calm, neutral, and de-escalating reply that provides a private contact method or support resource without admitting liability or inflaming tension.

2. FOR ALL OTHER CATEGORIES (question, praise, complaint, technical_correction, business_collab, etc.):
   - Set "is_sensitive" to false and "sensitive_notice" to null.
   - If reference documents / transcript chunks are provided, ground answers accurately on them.
   - For praise: warm, authentic appreciation.
   - For complaints: empathetic, constructive, solution-oriented response.
   - For technical corrections: appreciative acknowledgment and validation.
   - For business collabs: professional response directing to official business email.
   - In "guidance", provide brief strategic advice on why this response is effective.

OUTPUT SCHEMA:
Return ONLY valid JSON matching this schema:
{{
  "is_sensitive": <true or false>,
  "sensitive_notice": <string if sensitive, else null>,
  "guidance": "<brief creator advice/rationale>",
  "sample_response": "<the actual text the creator can post as their reply>"
}}
- Do not output any markdown code fence or thinking tags. Output raw JSON only.
"""
    llm_client = LLMClient(db=db)
    messages = [{"role": "user", "content": prompt_content}]

    result = llm_client.call_role(
        role="drafter",
        messages=messages,
        schema=AskAIOutput,
        estimated_tokens=400,
    )

    parsed: Optional[AskAIOutput] = result.parsed
    if not parsed:
        if is_category_sensitive:
            parsed = AskAIOutput(
                is_sensitive=True,
                sensitive_notice="⚠️ SENSITIVE CASE NOTICE: This comment has been classified as a sensitive case (safety, legal dispute, harassment, or self-harm risk). Handle with caution and avoid public escalation.",
                guidance="Explicit sensitive case handling: maintain calm, de-escalate without admitting liability, and direct to private support.",
                sample_response="Thank you for reaching out. Please contact our dedicated support team directly at support@channel.com so we can address your concerns privately and safely.",
            )
        else:
            parsed = AskAIOutput(
                is_sensitive=False,
                sensitive_notice=None,
                guidance="Helpful and friendly reply aligned with channel tone.",
                sample_response=f"Thank you for your feedback, {comment.author or 'friend'}! We appreciate your support.",
            )

    # Deterministic safety guarantee: If category is sensitive, enforce sensitive notice
    if is_category_sensitive:
        parsed.is_sensitive = True
        if not parsed.sensitive_notice:
            parsed.sensitive_notice = (
                "⚠️ SENSITIVE CASE NOTICE: This comment has been classified as a sensitive case "
                "(safety, legal concern, harassment, or self-harm risk). Exercise caution and avoid public disputes."
            )

    # Record in audit log
    audit = AuditLog(
        actor="creator",
        event="ask_ai",
        payload={
            "comment_id": comment.id,
            "category": category,
            "is_sensitive": parsed.is_sensitive,
            "model_used": result.model_used,
        },
    )
    db.add(audit)
    db.commit()

    return AskAIResponse(
        comment_id=comment.id,
        category=category,
        is_sensitive=parsed.is_sensitive,
        sensitive_notice=parsed.sensitive_notice,
        guidance=parsed.guidance,
        sample_response=parsed.sample_response,
        model_used=result.model_used,
    )



@router.post("/triage/run")
def trigger_batch_triage(limit: int = 50, db: Session = Depends(get_db)):
    """Triggers pipeline processing for all pending comments."""
    llm_client = LLMClient(db=db)
    service = TriageService(db=db, llm_client=llm_client)
    processed = service.process_all_pending(limit=limit)
    return {"status": "success", "processed_count": processed}


@router.get("/stats", response_model=StatsResponse)
def get_stats(list_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """Returns dashboard operational statistics and metrics, optionally filtered by list_id."""
    base_comment = select(func.count(Comment.id))
    if list_id:
        base_comment = base_comment.where(Comment.video_id == list_id)
    total_comments = db.scalar(base_comment) or 0

    pending_stmt = select(func.count(Comment.id)).where(Comment.status == "drafted")
    if list_id:
        pending_stmt = pending_stmt.where(Comment.video_id == list_id)
    pending_drafts = db.scalar(pending_stmt) or 0

    escalated_stmt = select(func.count(Comment.id)).where(Comment.status == "escalated")
    if list_id:
        escalated_stmt = escalated_stmt.where(Comment.video_id == list_id)
    escalated_count = db.scalar(escalated_stmt) or 0

    approved_stmt = select(func.count(Comment.id)).where(Comment.status.in_(["approved", "published"]))
    if list_id:
        approved_stmt = approved_stmt.where(Comment.video_id == list_id)
    approved_count = db.scalar(approved_stmt) or 0

    rejected_stmt = select(func.count(Comment.id)).where(Comment.status == "rejected")
    if list_id:
        rejected_stmt = rejected_stmt.where(Comment.video_id == list_id)
    rejected_count = db.scalar(rejected_stmt) or 0

    if list_id:
        auto_count = db.scalar(
            select(func.count(Analysis.comment_id))
            .join(Comment, Analysis.comment_id == Comment.id)
            .where(Analysis.action == "AUTO", Comment.video_id == list_id)
        ) or 0
    else:
        auto_count = db.scalar(
            select(func.count(Analysis.comment_id)).where(Analysis.action == "AUTO")
        ) or 0

    # Calculate Approval and Edit rates
    reviewed_total = approved_count + rejected_count
    approval_rate = round(approved_count / reviewed_total, 4) if reviewed_total > 0 else 0.0

    if list_id:
        total_replies = db.scalar(
            select(func.count(Reply.id))
            .join(Comment, Reply.comment_id == Comment.id)
            .where(Comment.video_id == list_id)
        ) or 0
        edited_replies = db.scalar(
            select(func.count(Reply.id))
            .join(Comment, Reply.comment_id == Comment.id)
            .where(Reply.source == "edited", Comment.video_id == list_id)
        ) or 0
    else:
        total_replies = db.scalar(select(func.count(Reply.id))) or 0
        edited_replies = db.scalar(select(func.count(Reply.id)).where(Reply.source == "edited")) or 0
    edit_rate = round(edited_replies / total_replies, 4) if total_replies > 0 else 0.0

    # Category breakdown
    cat_counts = {}
    if list_id:
        categories_query = db.execute(
            select(Analysis.category, func.count(Analysis.comment_id))
            .join(Comment, Analysis.comment_id == Comment.id)
            .where(Comment.video_id == list_id)
            .group_by(Analysis.category)
        ).all()
    else:
        categories_query = db.execute(
            select(Analysis.category, func.count(Analysis.comment_id)).group_by(Analysis.category)
        ).all()

    for cat, count in categories_query:
        if cat:
            cat_counts[cat] = count

    return StatsResponse(
        total_comments=total_comments,
        pending_drafts=pending_drafts,
        escalated_count=escalated_count,
        auto_count=auto_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        approval_rate=approval_rate,
        edit_rate=edit_rate,
        shadow_mode=settings.SHADOW_MODE,
        categories=cat_counts,
    )


@router.get("/audit-log")
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    """Fetch latest audit log entries."""
    logs = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "actor": l.actor,
            "event": l.event,
            "payload": l.payload,
        }
        for l in logs
    ]


# --- YouTube OAuth 2.0 (Testing Mode) ---

@router.get("/auth/youtube/status")
def get_oauth_status(db: Session = Depends(get_db)):
    """Check whether Google OAuth is configured and if any channel is connected."""
    from backend.app.ingestion.youtube_oauth import YouTubeOAuthManager
    from backend.app.db.models import Channel
    oauth_mgr = YouTubeOAuthManager()
    is_configured = oauth_mgr.is_configured()
    channels = db.scalars(select(Channel)).all()
    return {
        "configured": is_configured,
        "redirect_uri": oauth_mgr.redirect_uri,
        "connected_channels": [
            {
                "id": ch.id,
                "google_id": ch.google_id,
                "tone_setting": ch.tone_setting,
                "has_refresh_token": bool(ch.encrypted_refresh_token),
            }
            for ch in channels
        ],
    }


@router.get("/auth/youtube/login")
def get_oauth_login_url():
    """Returns Google OAuth 2.0 authorization URL for YouTube channel connection."""
    from backend.app.ingestion.youtube_oauth import YouTubeOAuthManager
    oauth_mgr = YouTubeOAuthManager()
    if not oauth_mgr.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )
    auth_url = oauth_mgr.get_authorization_url()
    return {"authorization_url": auth_url}


@router.get("/auth/youtube/callback")
def handle_oauth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    OAuth 2.0 callback endpoint. Exchanges authorization code for tokens,
    fetches YouTube channel info, and saves channel with encrypted refresh token.
    """
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth authorization rejected: {error}",
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'code' query parameter in OAuth callback.",
        )

    from backend.app.ingestion.youtube_oauth import YouTubeOAuthManager
    oauth_mgr = YouTubeOAuthManager()
    try:
        token_payload = oauth_mgr.exchange_code_for_tokens(code)
        access_token = token_payload.get("access_token")
        refresh_token = token_payload.get("refresh_token")

        channel_info = oauth_mgr.fetch_channel_info(access_token)
        channel = oauth_mgr.register_or_update_channel(
            db=db,
            channel_id=channel_info["channel_id"],
            refresh_token=refresh_token,
        )

        return {
            "status": "success",
            "message": f"Successfully connected channel {channel_info['title']}",
            "channel": {
                "id": channel.id,
                "google_id": channel.google_id,
                "title": channel_info["title"],
                "custom_url": channel_info["custom_url"],
            },
        }
    except Exception as e:
        logger.error(f"OAuth callback handling failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete OAuth authorization: {str(e)}",
        )


# --- User Preferences & Document-Based Real-Time Triage ---

@router.get("/preferences")
def get_user_preferences():
    """Retrieve active user triage preferences (categories, tone, custom instructions)."""
    global ACTIVE_PREFERENCES
    return ACTIVE_PREFERENCES.model_dump()


@router.post("/preferences")
def update_user_preferences(prefs: UserPreferences):
    """Update active user triage preferences."""
    global ACTIVE_PREFERENCES
    ACTIVE_PREFERENCES = prefs
    return {"status": "success", "preferences": ACTIVE_PREFERENCES.model_dump()}


# --- Lists & Video Workspaces ---

@router.get("/lists", response_model=List[ListSummaryResponse])
def get_lists(db: Session = Depends(get_db)):
    """Fetch all lists / video workspaces with summary metrics."""
    videos = db.scalars(select(Video).order_by(Video.id.desc())).all()
    results = []
    for v in videos:
        total_comments = db.scalar(select(func.count(Comment.id)).where(Comment.video_id == v.id)) or 0
        pending_drafts = db.scalar(
            select(func.count(Comment.id)).where(Comment.video_id == v.id, Comment.status == "drafted")
        ) or 0
        escalated_count = db.scalar(
            select(func.count(Comment.id)).where(Comment.video_id == v.id, Comment.status == "escalated")
        ) or 0
        approved_count = db.scalar(
            select(func.count(Comment.id)).where(Comment.video_id == v.id, Comment.status.in_(["approved", "published"]))
        ) or 0
        chunks_count = db.scalar(
            select(func.count(TranscriptChunk.id)).where(TranscriptChunk.video_id == v.id)
        ) or 0

        created_str = (
            v.created_at.isoformat()
            if hasattr(v, "created_at") and v.created_at
            else datetime.now(timezone.utc).isoformat()
        )

        results.append(
            ListSummaryResponse(
                id=v.id,
                title=v.title,
                description=v.description or "",
                youtube_video_id=v.youtube_video_id,
                transcript_status=v.transcript_status,
                total_comments=total_comments,
                pending_drafts=pending_drafts,
                escalated_count=escalated_count,
                approved_count=approved_count,
                reference_chunks_count=chunks_count,
                has_reference_doc=chunks_count > 0,
                created_at=created_str,
            )
        )
    return results


@router.post("/lists")
def create_list(payload: CreateListRequest, db: Session = Depends(get_db)):
    """Create a new named list / video workspace."""
    clean_title = payload.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="List title cannot be empty.")

    batch_uid = f"list_{uuid.uuid4().hex[:8]}"
    video = Video(
        youtube_video_id=batch_uid,
        title=clean_title,
        description=payload.description or "",
        transcript_status="pending",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    created_str = (
        video.created_at.isoformat()
        if hasattr(video, "created_at") and video.created_at
        else datetime.now(timezone.utc).isoformat()
    )

    return {
        "status": "success",
        "list": {
            "id": video.id,
            "title": video.title,
            "description": video.description,
            "youtube_video_id": video.youtube_video_id,
            "transcript_status": video.transcript_status,
            "total_comments": 0,
            "pending_drafts": 0,
            "escalated_count": 0,
            "approved_count": 0,
            "reference_chunks_count": 0,
            "has_reference_doc": False,
            "created_at": created_str,
        },
    }


@router.post("/videos/transcribe-url", response_model=TranscribeUrlResponse)
def transcribe_youtube_video_url(
    payload: TranscribeUrlRequest,
    db: Session = Depends(get_db),
):
    """
    Ingests and transcribes a YouTube video from its URL (Tier 1 Captions, Tier 2 Groq Whisper).
    Chunks with [MM:SS] timestamp preservation and indexes into the workspace with hybrid search.
    """
    clean_url = payload.youtube_url.strip()
    if not clean_url:
        raise HTTPException(status_code=400, detail="YouTube URL or video ID is required.")

    try:
        trans_res = YouTubeTranscriber.transcribe(clean_url)
    except Exception as e:
        logger.error(f"Failed to transcribe YouTube URL '{clean_url}': {e}")
        raise HTTPException(status_code=400, detail=f"Transcription failed: {str(e)}")

    # Resolve or create target list / video
    if payload.list_id:
        video = db.scalars(select(Video).where(Video.id == payload.list_id)).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"List with ID {payload.list_id} not found.")
        if payload.list_name and payload.list_name.strip():
            video.title = payload.list_name.strip()
    else:
        title = (payload.list_name or trans_res.title or f"Video: {trans_res.video_id}").strip()
        batch_uid = f"yt_{trans_res.video_id}_{uuid.uuid4().hex[:4]}"
        video = Video(
            youtube_video_id=batch_uid,
            title=title,
            description=payload.list_description or f"Auto-transcribed from YouTube: {clean_url}",
            transcript_status="pending",
        )
        db.add(video)
        db.flush()

    # Index chunks via ScopedRetriever
    retriever = ScopedRetriever(db=db)
    indexed_count = retriever.index_video_chunks(video.id, trans_res.chunks)
    video.transcript_status = "processed"

    # Audit log
    audit = AuditLog(
        actor="creator",
        event="transcribe_youtube_url",
        payload={
            "video_id": video.id,
            "youtube_video_id": trans_res.video_id,
            "title": video.title,
            "source": trans_res.source,
            "chunk_count": indexed_count,
        },
    )
    db.add(audit)
    db.commit()

    sample_chunks = [c.text[:120] + "..." for c in trans_res.chunks[:3]]

    return TranscribeUrlResponse(
        status="success",
        video_id=trans_res.video_id,
        list_id=video.id,
        list_title=video.title,
        source=trans_res.source,
        chunks_indexed=indexed_count,
        sample_chunks=sample_chunks,
    )


@router.post("/upload/batch")
async def upload_and_triage_batch(
    comments_file: UploadFile = File(...),
    reference_file: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
    preferences_json: Optional[str] = Form(None),
    list_id: Optional[int] = Form(None),
    list_name: Optional[str] = Form(None),
    list_description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Uploads comments (PDF, DOCX, CSV, JSON) + optional reference document or YouTube URL.
    Can target an existing list (list_id) or create a new named list (list_name).
    Indexes reference doc or YouTube transcript with Hybrid Search (Dense + BM25) and
    performs real-time triage based on the user's custom preferences.
    """

    global ACTIVE_PREFERENCES
    user_prefs = ACTIVE_PREFERENCES

    if preferences_json:
        try:
            parsed_prefs = json.loads(preferences_json)
            user_prefs = UserPreferences(**parsed_prefs)
            ACTIVE_PREFERENCES = user_prefs
        except Exception as pe:
            logger.warning(f"Could not parse custom preferences JSON: {pe}")

    # Read and parse comments file
    comments_bytes = await comments_file.read()
    try:
        parsed_comments = DocumentCommentsParser.parse(comments_bytes, comments_file.filename)
    except Exception as doc_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse comments document: {str(doc_err)}",
        )

    if not parsed_comments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid comment rows found in the uploaded file.",
        )

    # Resolve or create target List (Video record)
    if list_id:
        video = db.scalars(select(Video).where(Video.id == list_id)).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"List with ID {list_id} not found.")
        batch_uid = video.youtube_video_id
    elif list_name and list_name.strip():
        batch_uid = f"list_{uuid.uuid4().hex[:8]}"
        video = Video(
            youtube_video_id=batch_uid,
            title=list_name.strip(),
            description=list_description or f"Created via upload: {comments_file.filename}",
            transcript_status="pending",
        )
        db.add(video)
        db.flush()
    else:
        batch_uid = f"doc_{uuid.uuid4().hex[:8]}"
        video = Video(
            youtube_video_id=batch_uid,
            title=f"Batch: {comments_file.filename}",
            description=f"Uploaded {comments_file.filename} ({len(parsed_comments)} items)",
            transcript_status="pending",
        )
        db.add(video)
        db.flush()

    # Index Reference Knowledge Document or YouTube URL if provided (Hybrid Search: Dense + BM25)
    indexed_chunks_count = 0
    if reference_file and reference_file.filename:
        try:
            ref_bytes = await reference_file.read()
            chunks = ReferenceDocumentParser.parse_to_chunks(ref_bytes, reference_file.filename)
            if chunks:
                retriever = ScopedRetriever(db=db)
                indexed_chunks_count = retriever.index_video_chunks(video.id, chunks)
                video.transcript_status = "processed"
                db.commit()
                logger.info(f"Hybrid indexed {indexed_chunks_count} chunks from {reference_file.filename} for list {video.id}")
        except Exception as ref_err:
            logger.error(f"Failed to index reference document: {ref_err}")
    elif youtube_url and youtube_url.strip():
        try:
            trans_res = YouTubeTranscriber.transcribe(youtube_url.strip())
            if trans_res.chunks:
                retriever = ScopedRetriever(db=db)
                indexed_chunks_count = retriever.index_video_chunks(video.id, trans_res.chunks)
                video.transcript_status = "processed"
                db.commit()
                logger.info(f"Auto-transcribed & indexed {indexed_chunks_count} chunks from YouTube URL '{youtube_url}' (source: {trans_res.source})")
        except Exception as yt_err:
            logger.error(f"Failed to transcribe YouTube URL during batch upload: {yt_err}")
    else:
        # If adding to an existing list that already has indexed chunks, count them
        existing_chunks = db.scalar(
            select(func.count(TranscriptChunk.id)).where(TranscriptChunk.video_id == video.id)
        ) or 0
        indexed_chunks_count = existing_chunks


    # Ingest comments and run real-time LangGraph triage
    llm_client = LLMClient(db=db)
    service = TriageService(db=db, llm_client=llm_client)

    triaged_comments = []
    category_counts = {}

    for idx, c_data in enumerate(parsed_comments, 1):
        comment_uid = f"{batch_uid}_{uuid.uuid4().hex[:6]}_{idx:03d}"
        c = Comment(
            youtube_comment_id=comment_uid,
            video_id=video.id,
            author=c_data["author"],
            text=c_data["text"],
            status="new",
            source=c_data.get("source", "doc_upload"),
            created_at=datetime.now(timezone.utc),
        )
        db.add(c)
        db.flush()

        triaged = service.process_and_persist_comment(
            comment_id=c.id,
            force=True,
            user_preferences=user_prefs,
        )
        if triaged and triaged.analysis:
            cat = triaged.analysis.category
            category_counts[cat] = category_counts.get(cat, 0) + 1
            triaged_comments.append({
                "id": triaged.id,
                "author": triaged.author,
                "text": triaged.text,
                "category": cat,
                "action": triaged.analysis.action,
                "status": triaged.status,
            })

    db.commit()

    return {
        "status": "success",
        "batch_id": batch_uid,
        "video_id": video.id,
        "list_id": video.id,
        "list_title": video.title,
        "filename": comments_file.filename,
        "total_parsed": len(parsed_comments),
        "reference_chunks_indexed": indexed_chunks_count,
        "categories_breakdown": category_counts,
        "comments": triaged_comments,
    }


# ============================================================================
# Granular Autopilot Rules Engine Endpoints (Batch 2)
# ============================================================================

def _serialize_rule(rule: AutopilotRule) -> AutopilotRuleResponse:
    created_str = (
        rule.created_at.isoformat()
        if hasattr(rule, "created_at") and rule.created_at
        else datetime.now(timezone.utc).isoformat()
    )
    return AutopilotRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description or "",
        enabled=rule.enabled,
        priority=rule.priority,
        action=rule.action,
        categories=rule.categories or [],
        min_confidence=rule.min_confidence,
        min_faithfulness=rule.min_faithfulness,
        min_retrieval_score=rule.min_retrieval_score,
        require_citations=rule.require_citations,
        max_comment_words=rule.max_comment_words,
        keywords_any=rule.keywords_any or [],
        negative_keywords=rule.negative_keywords or [],
        author_match=rule.author_match,
        created_at=created_str,
    )


@router.get("/autopilot/rules", response_model=List[AutopilotRuleResponse])
def get_autopilot_rules(db: Session = Depends(get_db)):
    """Fetches all autopilot triage rules ordered by priority."""
    # Ensure default rules exist
    seed_default_autopilot_rules(db)
    rules = db.scalars(
        select(AutopilotRule).order_by(AutopilotRule.priority.asc(), AutopilotRule.id.asc())
    ).all()
    return [_serialize_rule(r) for r in rules]


@router.post("/autopilot/rules", response_model=AutopilotRuleResponse)
def create_autopilot_rule(payload: AutopilotRuleCreate, db: Session = Depends(get_db)):
    """Creates a new granular autopilot rule."""
    if payload.action not in ("AUTO", "DRAFT", "ESCALATE"):
        raise HTTPException(status_code=400, detail="Action must be AUTO, DRAFT, or ESCALATE")

    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Rule name cannot be empty")

    rule = AutopilotRule(
        name=clean_name,
        description=payload.description or "",
        enabled=payload.enabled,
        priority=payload.priority,
        action=payload.action,
        categories=payload.categories or [],
        min_confidence=payload.min_confidence,
        min_faithfulness=payload.min_faithfulness,
        min_retrieval_score=payload.min_retrieval_score,
        require_citations=payload.require_citations,
        max_comment_words=payload.max_comment_words,
        keywords_any=payload.keywords_any or [],
        negative_keywords=payload.negative_keywords or [],
        author_match=payload.author_match,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    # Log audit
    audit = AuditLog(
        actor="creator",
        event="create_autopilot_rule",
        payload={"rule_id": rule.id, "name": rule.name, "action": rule.action, "priority": rule.priority},
    )
    db.add(audit)
    db.commit()

    return _serialize_rule(rule)


@router.put("/autopilot/rules/{rule_id}", response_model=AutopilotRuleResponse)
def update_autopilot_rule(
    rule_id: int,
    payload: AutopilotRuleUpdate,
    db: Session = Depends(get_db),
):
    """Updates an existing autopilot rule."""
    rule = db.scalars(select(AutopilotRule).where(AutopilotRule.id == rule_id)).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Autopilot rule with ID {rule_id} not found")

    if payload.name is not None:
        clean_name = payload.name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Rule name cannot be empty")
        rule.name = clean_name

    if payload.description is not None:
        rule.description = payload.description
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.action is not None:
        if payload.action not in ("AUTO", "DRAFT", "ESCALATE"):
            raise HTTPException(status_code=400, detail="Action must be AUTO, DRAFT, or ESCALATE")
        rule.action = payload.action
    if payload.categories is not None:
        rule.categories = payload.categories
    if payload.min_confidence is not None:
        rule.min_confidence = payload.min_confidence
    if payload.min_faithfulness is not None:
        rule.min_faithfulness = payload.min_faithfulness
    if payload.min_retrieval_score is not None:
        rule.min_retrieval_score = payload.min_retrieval_score
    if payload.require_citations is not None:
        rule.require_citations = payload.require_citations
    if payload.max_comment_words is not None:
        rule.max_comment_words = payload.max_comment_words
    if payload.keywords_any is not None:
        rule.keywords_any = payload.keywords_any
    if payload.negative_keywords is not None:
        rule.negative_keywords = payload.negative_keywords
    if payload.author_match is not None:
        rule.author_match = payload.author_match

    db.commit()
    db.refresh(rule)

    # Log audit
    audit = AuditLog(
        actor="creator",
        event="update_autopilot_rule",
        payload={"rule_id": rule.id, "name": rule.name, "action": rule.action, "enabled": rule.enabled},
    )
    db.add(audit)
    db.commit()

    return _serialize_rule(rule)


@router.delete("/autopilot/rules/{rule_id}")
def delete_autopilot_rule(rule_id: int, db: Session = Depends(get_db)):
    """Deletes an autopilot rule."""
    rule = db.scalars(select(AutopilotRule).where(AutopilotRule.id == rule_id)).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Autopilot rule with ID {rule_id} not found")

    rule_name = rule.name
    db.delete(rule)
    db.commit()

    audit = AuditLog(
        actor="creator",
        event="delete_autopilot_rule",
        payload={"rule_id": rule_id, "name": rule_name},
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "deleted_rule_id": rule_id, "name": rule_name}


@router.post("/autopilot/rules/reset", response_model=List[AutopilotRuleResponse])
def reset_autopilot_rules_to_defaults(db: Session = Depends(get_db)):
    """Resets all autopilot rules back to recommended factory defaults."""
    rules = db.scalars(select(AutopilotRule)).all()
    for r in rules:
        db.delete(r)
    db.commit()

    seed_default_autopilot_rules(db)
    new_rules = db.scalars(
        select(AutopilotRule).order_by(AutopilotRule.priority.asc(), AutopilotRule.id.asc())
    ).all()

    audit = AuditLog(
        actor="creator",
        event="reset_autopilot_rules",
        payload={"rules_count": len(new_rules)},
    )
    db.add(audit)
    db.commit()

    return [_serialize_rule(r) for r in new_rules]


@router.post("/autopilot/test", response_model=TestRuleResponse)
def test_autopilot_decision(payload: TestRuleRequest, db: Session = Depends(get_db)):
    """
    Dry-run simulation: Evaluates which rule matches a test comment and returns the resulting action.
    """
    rules = db.scalars(
        select(AutopilotRule)
        .where(AutopilotRule.enabled == True)
        .order_by(AutopilotRule.priority.asc(), AutopilotRule.id.asc())
    ).all()

    router = RiskRouter()
    decision = router.route(
        category=payload.category,
        confidence=payload.confidence,
        sensitive=(payload.category.lower() == "sensitive"),
        retrieval_score=payload.retrieval_score,
        faithfulness=payload.faithfulness,
        draft_text=payload.draft_text,
        abstained=("ABSTAIN" in (payload.draft_text or "").upper()),
        comment_text=payload.comment_text,
        author=payload.author or "",
        rules=rules,
    )

    return TestRuleResponse(
        action=decision.action,
        reason=decision.reason,
        matched_rule_id=decision.matched_rule_id,
        matched_rule_name=decision.matched_rule_name,
        can_auto_publish=decision.can_auto_publish,
        requires_human_approval=decision.requires_human_approval,
    )


# ---------------------------------------------------------------------------
# Creator Persona Tone Cloner & Few-Shot Dynamic Drafter Endpoints (Phase 3)
# ---------------------------------------------------------------------------

def _serialize_persona(p: CreatorPersona) -> CreatorPersonaResponse:
    return CreatorPersonaResponse(
        id=p.id,
        name=p.name,
        description=p.description or "",
        is_active=bool(p.is_active),
        greeting_pattern=p.greeting_pattern or "None",
        sign_off_pattern=p.sign_off_pattern or "None",
        formality=p.formality or "neutral",
        emoji_density=p.emoji_density or "minimal",
        max_sentences=int(p.max_sentences or 2),
        custom_voice_notes=p.custom_voice_notes or "",
        sample_pairs=list(p.sample_pairs or []),
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


@router.get("/personas", response_model=List[CreatorPersonaResponse])
def get_all_personas(db: Session = Depends(get_db)):
    """Retrieve all creator personas, auto-seeding defaults if empty."""
    personas = db.scalars(
        select(CreatorPersona).order_by(CreatorPersona.id.asc())
    ).all()

    if not personas:
        personas = seed_default_personas(db)

    return [_serialize_persona(p) for p in personas]


@router.post("/personas", response_model=CreatorPersonaResponse, status_code=status.HTTP_201_CREATED)
def create_persona(payload: CreatorPersonaCreate, db: Session = Depends(get_db)):
    """Create a new creator tone persona."""
    if payload.is_active:
        db.query(CreatorPersona).update({CreatorPersona.is_active: False})

    persona = CreatorPersona(
        name=payload.name,
        description=payload.description or "",
        is_active=payload.is_active,
        greeting_pattern=payload.greeting_pattern,
        sign_off_pattern=payload.sign_off_pattern,
        formality=payload.formality,
        emoji_density=payload.emoji_density,
        max_sentences=payload.max_sentences,
        custom_voice_notes=payload.custom_voice_notes or "",
        sample_pairs=payload.sample_pairs or [],
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)

    audit = AuditLog(
        actor="creator",
        event="creator_persona_created",
        payload={"persona_id": persona.id, "name": persona.name},
    )
    db.add(audit)
    db.commit()

    return _serialize_persona(persona)


@router.put("/personas/{persona_id}", response_model=CreatorPersonaResponse)
def update_persona(persona_id: int, payload: CreatorPersonaUpdate, db: Session = Depends(get_db)):
    """Update attributes of an existing persona."""
    persona = db.scalars(select(CreatorPersona).where(CreatorPersona.id == persona_id)).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Creator persona not found")

    if payload.name is not None:
        persona.name = payload.name
    if payload.description is not None:
        persona.description = payload.description
    if payload.greeting_pattern is not None:
        persona.greeting_pattern = payload.greeting_pattern
    if payload.sign_off_pattern is not None:
        persona.sign_off_pattern = payload.sign_off_pattern
    if payload.formality is not None:
        persona.formality = payload.formality
    if payload.emoji_density is not None:
        persona.emoji_density = payload.emoji_density
    if payload.max_sentences is not None:
        persona.max_sentences = payload.max_sentences
    if payload.custom_voice_notes is not None:
        persona.custom_voice_notes = payload.custom_voice_notes
    if payload.sample_pairs is not None:
        persona.sample_pairs = payload.sample_pairs
    if payload.is_active is True:
        db.query(CreatorPersona).update({CreatorPersona.is_active: False})
        persona.is_active = True

    db.commit()
    db.refresh(persona)
    return _serialize_persona(persona)


@router.put("/personas/{persona_id}/activate", response_model=CreatorPersonaResponse)
def activate_persona_endpoint(persona_id: int, db: Session = Depends(get_db)):
    """Activate a persona as the primary voice used by the grounded drafter."""
    persona = set_active_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Creator persona not found")

    audit = AuditLog(
        actor="creator",
        event="creator_persona_activated",
        payload={"persona_id": persona.id, "name": persona.name},
    )
    db.add(audit)
    db.commit()
    return _serialize_persona(persona)


@router.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(persona_id: int, db: Session = Depends(get_db)):
    """Delete a creator persona. If deleting the active one, fallback to the first available."""
    persona = db.scalars(select(CreatorPersona).where(CreatorPersona.id == persona_id)).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Creator persona not found")

    was_active = persona.is_active
    db.delete(persona)
    db.commit()

    if was_active:
        remaining = db.scalars(select(CreatorPersona).order_by(CreatorPersona.id.asc())).first()
        if remaining:
            remaining.is_active = True
            db.commit()

    return None


@router.post("/personas/extract", response_model=ExtractToneResponse)
def extract_tone_from_samples(payload: ExtractToneRequest):
    """
    Analyzes raw pasted sample replies and returns extracted tone metrics
    (formality, sentence length, greeting style, sign-off, emoji density).
    """
    result = extract_tone_from_texts(payload.sample_replies)
    return ExtractToneResponse(**result)


@router.post("/personas/extract-from-db", response_model=ExtractToneResponse)
def extract_tone_from_database(db: Session = Depends(get_db)):
    """
    One-click tone cloning: Auto-extracts creator persona metrics from all
    comments with approved/finalized replies in the database.
    """
    result = extract_tone_from_approved_db(db)
    return ExtractToneResponse(**result)


@router.post("/personas/preview-draft", response_model=PreviewDraftResponse)
def preview_draft_persona(payload: PreviewDraftRequest, db: Session = Depends(get_db)):
    """
    Interactive Persona Sandbox: Test how the persona drafts a response for a test question
    with grounded timestamp citations.
    """
    # 1. Resolve persona
    persona = None
    if payload.persona_id:
        persona = db.scalars(select(CreatorPersona).where(CreatorPersona.id == payload.persona_id)).first()
    if not persona:
        persona = get_active_persona(db)

    persona_name = persona.name if persona else "Default"

    # 2. Resolve transcript context
    context_str = payload.mock_context or ""
    if not context_str and payload.video_id:
        chunks = db.scalars(
            select(TranscriptChunk)
            .where(TranscriptChunk.video_id == payload.video_id)
            .limit(3)
        ).all()
        if chunks:
            context_str = "\n\n".join([f"{c.formatted_timestamp} {c.text}" for c in chunks])

    if not context_str:
        # Default mock context if none provided
        context_str = (
            "[01:10] In this video we demonstrate building the full-stack agent with FastAPI and Next.js 14.\n"
            "[02:15] To install Docker Desktop on Windows, download the installer directly from docker.com.\n"
            "[04:40] Python 3.10 through 3.14 are supported out of the box."
        )

    # 3. Format persona prompt
    prompt_persona = build_persona_prompt_block(persona, author_name=payload.author or "there") if persona else ""

    from backend.app.agent.nodes import DRAFT_PROMPT
    prompt_content = (
        DRAFT_PROMPT.replace("{tone_setting}", "helpful_concise")
        .replace("{transcript_context}", context_str)
        .replace("{comment_text}", payload.comment_text)
    )
    if prompt_persona:
        prompt_content += f"\n\n{prompt_persona}"

    llm_client = LLMClient()
    result = llm_client.call_role(
        role="drafter",
        messages=[{"role": "user", "content": prompt_content}],
        estimated_tokens=500,
    )

    raw_reply = result.content.strip()
    is_abstain = "ABSTAIN" in raw_reply.upper() or len(raw_reply) == 0

    return PreviewDraftResponse(
        draft_text=raw_reply if not is_abstain else "ABSTAIN",
        abstained=is_abstain,
        persona_name=persona_name,
        greeting_used=persona.greeting_pattern if persona else "None",
        sign_off_used=persona.sign_off_pattern if persona else "None",
    )





