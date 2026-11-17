export interface AnalysisSummary {
  category: string;
  confidence: number;
  retrieval_score?: number | null;
  faithfulness?: number | null;
  action: "AUTO" | "DRAFT" | "ESCALATE";
  reason: string;
  rule_name?: string | null;
  persona_name?: string | null;
  model_used: string;
  fallback_used: boolean;
  judge_independent: boolean;
}

export interface ReplySummary {
  draft_text: string;
  final_text: string;
  source: string;
  published_at?: string | null;
}

export interface CommentQueueItem {
  id: number;
  youtube_comment_id: string;
  video_id?: number | null;
  video_title: string;
  author: string;
  text: string;
  status: "new" | "processing" | "drafted" | "approved" | "published" | "escalated" | "rejected";
  source: string;
  created_at: string;
  analysis?: AnalysisSummary | null;
  reply?: ReplySummary | null;
}

export interface CommentDetailResponse extends CommentQueueItem {
  retrieved_chunks: {
    chunk_id: number;
    timestamp: string;
    text: string;
  }[];
  audit_history: {
    timestamp: string;
    actor: string;
    event: string;
    payload: any;
  }[];
}

export interface StatsResponse {
  total_comments: number;
  pending_drafts: number;
  escalated_count: number;
  auto_count: number;
  approved_count: number;
  rejected_count: number;
  approval_rate: number;
  edit_rate: number;
  shadow_mode: boolean;
  categories: Record<string, number>;
}

export interface CategoryPreference {
  name: string;
  description: string;
  action: "AUTO" | "DRAFT" | "ESCALATE";
}

export interface UserPreferences {
  categories: CategoryPreference[];
  tone: string;
  custom_instructions: string;
}

export interface VideoListSummary {
  id: number;
  title: string;
  description: string;
  youtube_video_id: string;
  transcript_status: string;
  total_comments: number;
  pending_drafts: number;
  escalated_count: number;
  approved_count: number;
  reference_chunks_count: number;
  has_reference_doc: boolean;
  created_at: string;
}

export interface UploadBatchResponse {
  status: string;
  batch_id: string;
  video_id: number;
  list_id?: number;
  list_title?: string;
  filename: string;
  total_parsed: number;
  reference_chunks_indexed: number;
  categories_breakdown: Record<string, number>;
  comments: {
    id: number;
    author: string;
    text: string;
    category: string;
    action: string;
    status: string;
  }[];
}

export interface AskAIResponse {
  comment_id: number;
  category: string;
  is_sensitive: boolean;
  sensitive_notice?: string | null;
  guidance: string;
  sample_response: string;
  model_used: string;
}

export interface TranscribeUrlResponse {
  status: string;
  video_id: string;
  list_id: number;
  list_title: string;
  source: string;
  chunks_indexed: number;
  sample_chunks: string[];
}

export interface AutopilotRule {
  id: number;
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
  action: "AUTO" | "DRAFT" | "ESCALATE";
  categories: string[];
  min_confidence?: number | null;
  min_faithfulness?: number | null;
  min_retrieval_score?: number | null;
  require_citations: boolean;
  max_comment_words?: number | null;
  keywords_any: string[];
  negative_keywords: string[];
  author_match?: string | null;
  created_at: string;
}

export interface TestRuleResponse {
  action: "AUTO" | "DRAFT" | "ESCALATE";
  reason: string;
  matched_rule_id?: number | null;
  matched_rule_name?: string | null;
  can_auto_publish: boolean;
  requires_human_approval: boolean;
}

export interface CreatorPersona {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  greeting_pattern: string;
  sign_off_pattern: string;
  formality: "casual" | "neutral" | "formal";
  emoji_density: "none" | "minimal" | "expressive";
  max_sentences: number;
  custom_voice_notes: string;
  sample_pairs: Array<{ comment: string; reply: string }>;
  created_at: string;
}

export interface ExtractToneResult {
  name: string;
  description: string;
  greeting_pattern: string;
  sign_off_pattern: string;
  formality: "casual" | "neutral" | "formal";
  emoji_density: "none" | "minimal" | "expressive";
  max_sentences: number;
  custom_voice_notes: string;
  sample_count: number;
  metrics: {
    avg_sentence_count: number;
    emoji_ratio: number;
    has_greeting_ratio: number;
    has_sign_off_ratio: number;
  };
}

export interface PreviewDraftResult {
  draft_text: string;
  abstained: boolean;
  persona_name: string;
  greeting_used: string;
  sign_off_used: string;
}






