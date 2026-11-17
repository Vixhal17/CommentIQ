from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel


class AnalysisSummary(BaseModel):
    category: str
    confidence: float
    retrieval_score: Optional[float] = None
    faithfulness: Optional[float] = None
    action: str
    reason: str
    rule_name: Optional[str] = None
    persona_name: Optional[str] = None
    model_used: str
    fallback_used: bool = False
    judge_independent: bool = True


class ReplySummary(BaseModel):
    draft_text: str
    final_text: str
    source: str
    published_at: Optional[datetime] = None


class CommentQueueItem(BaseModel):
    id: int
    youtube_comment_id: str
    video_id: Optional[int] = None
    video_title: str
    author: str
    text: str
    status: str
    source: str
    created_at: datetime
    analysis: Optional[AnalysisSummary] = None
    reply: Optional[ReplySummary] = None


class CommentDetailResponse(BaseModel):
    id: int
    youtube_comment_id: str
    video_id: Optional[int] = None
    video_title: str
    author: str
    text: str
    status: str
    source: str
    created_at: datetime
    analysis: Optional[AnalysisSummary] = None
    reply: Optional[ReplySummary] = None
    retrieved_chunks: List[dict] = []
    audit_history: List[dict] = []


class EditReplyRequest(BaseModel):
    final_text: str


class RejectCommentRequest(BaseModel):
    reason: Optional[str] = "Rejected by creator"


class StatsResponse(BaseModel):
    total_comments: int
    pending_drafts: int
    escalated_count: int
    auto_count: int
    approved_count: int
    rejected_count: int
    approval_rate: float
    edit_rate: float
    shadow_mode: bool
    categories: dict[str, int]


class CreateListRequest(BaseModel):
    title: str
    description: Optional[str] = ""


class ListSummaryResponse(BaseModel):
    id: int
    title: str
    description: str
    youtube_video_id: str
    transcript_status: str
    total_comments: int
    pending_drafts: int
    escalated_count: int
    approved_count: int
    reference_chunks_count: int
    has_reference_doc: bool
    created_at: str


class AskAIRequest(BaseModel):
    user_instruction: Optional[str] = ""


class AskAIOutput(BaseModel):
    is_sensitive: bool = False
    sensitive_notice: Optional[str] = None
    guidance: str = ""
    sample_response: str = ""


class AskAIResponse(BaseModel):
    comment_id: int
    category: str
    is_sensitive: bool
    sensitive_notice: Optional[str] = None
    guidance: str
    sample_response: str
    model_used: str


class TranscribeUrlRequest(BaseModel):
    youtube_url: str
    list_id: Optional[int] = None
    list_name: Optional[str] = None
    list_description: Optional[str] = None


class TranscribeUrlResponse(BaseModel):
    status: str
    video_id: str
    list_id: int
    list_title: str
    source: str
    chunks_indexed: int
    sample_chunks: List[str]


class AutopilotRuleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    enabled: bool = True
    priority: int = 10
    action: Literal["AUTO", "DRAFT", "ESCALATE"]
    categories: List[str] = []
    min_confidence: Optional[float] = None
    min_faithfulness: Optional[float] = None
    min_retrieval_score: Optional[float] = None
    require_citations: bool = False
    max_comment_words: Optional[int] = None
    keywords_any: List[str] = []
    negative_keywords: List[str] = []
    author_match: Optional[str] = None


class AutopilotRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    action: Optional[Literal["AUTO", "DRAFT", "ESCALATE"]] = None
    categories: Optional[List[str]] = None
    min_confidence: Optional[float] = None
    min_faithfulness: Optional[float] = None
    min_retrieval_score: Optional[float] = None
    require_citations: Optional[bool] = None
    max_comment_words: Optional[int] = None
    keywords_any: Optional[List[str]] = None
    negative_keywords: Optional[List[str]] = None
    author_match: Optional[str] = None


class AutopilotRuleResponse(BaseModel):
    id: int
    name: str
    description: str
    enabled: bool
    priority: int
    action: str
    categories: List[str]
    min_confidence: Optional[float] = None
    min_faithfulness: Optional[float] = None
    min_retrieval_score: Optional[float] = None
    require_citations: bool = False
    max_comment_words: Optional[int] = None
    keywords_any: List[str] = []
    negative_keywords: List[str] = []
    author_match: Optional[str] = None
    created_at: str


class TestRuleRequest(BaseModel):
    comment_text: str
    category: str = "question"
    confidence: float = 0.85
    retrieval_score: float = 0.50
    faithfulness: float = 0.85
    draft_text: Optional[str] = None
    author: Optional[str] = "Viewer"


class TestRuleResponse(BaseModel):
    action: str
    reason: str
    matched_rule_id: Optional[int] = None
    matched_rule_name: Optional[str] = None
    can_auto_publish: bool
    requires_human_approval: bool


class CreatorPersonaCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    greeting_pattern: str = "Hey @author!"
    sign_off_pattern: str = "None"
    formality: Literal["casual", "neutral", "formal"] = "neutral"
    emoji_density: Literal["none", "minimal", "expressive"] = "minimal"
    max_sentences: int = 2
    custom_voice_notes: Optional[str] = ""
    sample_pairs: List[dict] = []
    is_active: bool = False


class CreatorPersonaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    greeting_pattern: Optional[str] = None
    sign_off_pattern: Optional[str] = None
    formality: Optional[Literal["casual", "neutral", "formal"]] = None
    emoji_density: Optional[Literal["none", "minimal", "expressive"]] = None
    max_sentences: Optional[int] = None
    custom_voice_notes: Optional[str] = None
    sample_pairs: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class CreatorPersonaResponse(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    greeting_pattern: str
    sign_off_pattern: str
    formality: str
    emoji_density: str
    max_sentences: int
    custom_voice_notes: str
    sample_pairs: List[dict]
    created_at: str


class ExtractToneRequest(BaseModel):
    sample_replies: List[str]


class ExtractToneResponse(BaseModel):
    name: str
    description: str
    greeting_pattern: str
    sign_off_pattern: str
    formality: str
    emoji_density: str
    max_sentences: int
    custom_voice_notes: str
    sample_count: int
    metrics: dict


class PreviewDraftRequest(BaseModel):
    comment_text: str
    author: Optional[str] = "Viewer"
    persona_id: Optional[int] = None
    video_id: Optional[int] = None
    mock_context: Optional[str] = None


class PreviewDraftResponse(BaseModel):
    draft_text: str
    abstained: bool
    persona_name: str
    greeting_used: str
    sign_off_used: str





