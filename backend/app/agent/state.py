from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PipelineState(BaseModel):
    # Input identifiers
    comment_id: int = 0
    youtube_comment_id: str = ""
    video_id: Optional[int] = None
    comment_text: str = ""
    author: str = ""
    channel_tone: str = "helpful_concise"

    # Classification results
    category: Optional[str] = None
    confidence: float = 0.0
    rationale: str = ""
    sensitive: bool = False

    # Retrieval results
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    top_retrieval_score: float = 0.0

    # Drafting results
    draft_text: Optional[str] = None
    abstained: bool = False

    # User Preferences & Custom Instructions
    custom_categories: Optional[List[Dict[str, Any]]] = None
    custom_instructions: str = ""

    # Model and provenance tracking
    persona_name: Optional[str] = None
    persona_instructions: Optional[str] = None
    model_used: str = ""
    fallback_used: bool = False
    judge_independent: bool = True
    error: Optional[str] = None

