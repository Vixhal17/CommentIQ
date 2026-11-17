"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Check,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  BookOpen,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  History,
  Loader2,
  CornerDownLeft,
  Copy,
} from "lucide-react";
import { CommentDetailResponse, AskAIResponse } from "@/types";
import { CategoryBadge, ActionBadge, FaithfulnessBadge } from "./Badges";

const API_BASE = "http://127.0.0.1:8000/api";

interface DetailDrawerProps {
  comment: CommentDetailResponse | null;
  onClose: () => void;
  onApprove: (id: number) => Promise<void>;
  onEdit: (id: number, text: string) => Promise<void>;
  onReject: (id: number, reason: string) => Promise<void>;
}

export const DetailDrawer: React.FC<DetailDrawerProps> = ({
  comment,
  onClose,
  onApprove,
  onEdit,
  onReject,
}) => {
  const [draftText, setDraftText] = useState("");
  const [originalDraft, setOriginalDraft] = useState("");
  const [rejectReason, setRejectReason] = useState("Off-topic / rejected by creator");
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Ask AI Assistant state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<AskAIResponse | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [userInstruction, setUserInstruction] = useState("");
  const [showInstruction, setShowInstruction] = useState(false);
  const [copiedChunk, setCopiedChunk] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (comment) {
      let initialText = comment.reply?.final_text || comment.reply?.draft_text || "";
      if (initialText.trim().startsWith("{") && initialText.includes('"category"')) {
        initialText = "";
      }
      setDraftText(initialText);
      setOriginalDraft(initialText);
      setShowRejectInput(false);
      setAiResult(null);
      setAiError(null);
      setUserInstruction("");
      setShowInstruction(false);
    }
  }, [comment]);

  const isModified = draftText.trim() !== originalDraft.trim();

  // Keyboard Shortcuts: A to approve, R to reject, Esc to close
  useEffect(() => {
    if (!comment) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // If user is editing the draft or reject input, ignore hotkeys
      if (
        document.activeElement?.tagName === "TEXTAREA" ||
        document.activeElement?.tagName === "INPUT"
      ) {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        }
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        handleApprove();
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        setShowRejectInput(true);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [comment, draftText, originalDraft, isModified]);

  if (!comment) return null;

  const isSensitive =
    comment.analysis?.category?.toLowerCase() === "sensitive" || aiResult?.is_sensitive;

  const handleAskAI = async () => {
    if (!comment) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetch(`${API_BASE}/comments/${comment.id}/ask-ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_instruction: userInstruction }),
      });
      if (!res.ok) {
        throw new Error(`Failed to generate sample reply (${res.status})`);
      }
      const data: AskAIResponse = await res.json();
      setAiResult(data);
    } catch (err: any) {
      console.error("Ask AI error:", err);
      setAiError(err.message || "Failed to generate AI response.");
    } finally {
      setAiLoading(false);
    }
  };

  const handleApprove = async () => {
    setActionLoading(true);
    try {
      if (isModified) {
        await onEdit(comment.id, draftText);
      } else {
        await onApprove(comment.id);
      }
      onClose();
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    setActionLoading(true);
    try {
      await onReject(comment.id, rejectReason);
      onClose();
    } finally {
      setActionLoading(false);
    }
  };

  const handleInsertCitation = (timestamp: string) => {
    setDraftText((prev) => `${prev.trim()} as covered around ${timestamp}.`);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end">
      <motion.div
        initial={{ x: "100%", opacity: 0.6 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: "100%", opacity: 0 }}
        transition={{ type: "spring", damping: 30, stiffness: 320 }}
        className="w-full max-w-2xl bg-surface border-l border-border shadow-drawer h-full flex flex-col relative"
      >
        {/* Top Header Bar */}
        <div className="h-14 px-5 border-b border-border flex items-center justify-between shrink-0 bg-subtle/60">
          <div className="flex items-center gap-2.5">
            <CategoryBadge category={comment.analysis?.category} />
            <ActionBadge action={comment.analysis?.action} />
            {comment.analysis?.persona_name && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                Voice: {comment.analysis.persona_name}
              </span>
            )}
            <span className="text-[10px] font-mono text-muted">
              #{comment.youtube_comment_id}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <kbd>Esc</kbd>
            <button
              onClick={onClose}
              className="p-1 rounded text-muted hover:text-primary hover:bg-surface-hover transition-colors"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable Split Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* 1. Original Comment Card */}
          <div className="p-4 rounded-lg bg-subtle border border-border space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-primary">
                {comment.author || "Anonymous"}
              </span>
              <span className="text-[10px] font-mono text-muted">
                {comment.video_title}
              </span>
            </div>
            <p className="text-xs text-primary leading-relaxed font-normal select-text">
              "{comment.text}"
            </p>
          </div>

          {/* 2. Routing Decision & Faithfulness Verdict */}
          <div className="p-3.5 rounded-lg bg-subtle/50 border border-border space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
                Risk Router Decision
              </span>
              <FaithfulnessBadge
                score={comment.analysis?.faithfulness}
                independent={comment.analysis?.judge_independent}
              />
            </div>

            <p className="text-xs text-secondary font-mono leading-relaxed bg-surface p-2.5 rounded border border-border">
              {comment.analysis?.reason || "Standard risk routing evaluation"}
            </p>

            <div className="grid grid-cols-3 gap-2 pt-1 text-center font-mono">
              <div className="p-2 rounded bg-surface border border-border">
                <span className="text-[9px] uppercase tracking-wider text-muted block">
                  Confidence
                </span>
                <span className="text-xs font-medium text-primary tabular-nums">
                  {((comment.analysis?.confidence || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="p-2 rounded bg-surface border border-border">
                <span className="text-[9px] uppercase tracking-wider text-muted block">
                  RAG Score
                </span>
                <span className="text-xs font-medium text-primary tabular-nums">
                  {comment.analysis?.retrieval_score
                    ? `${(comment.analysis.retrieval_score * 100).toFixed(0)}%`
                    : "N/A"}
                </span>
              </div>
              <div className="p-2 rounded bg-surface border border-border">
                <span className="text-[9px] uppercase tracking-wider text-muted block">
                  Faithfulness
                </span>
                <span className="text-xs font-medium text-primary tabular-nums">
                  {comment.analysis?.faithfulness
                    ? `${(comment.analysis.faithfulness * 100).toFixed(0)}%`
                    : "N/A"}
                </span>
              </div>
            </div>

            {comment.analysis?.judge_independent === false && (
              <div className="flex items-center gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px]">
                <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                <span>
                  <strong>Non-Independent Judge:</strong> Drafter used fallback provider; judge independence not guaranteed.
                </span>
              </div>
            )}
          </div>

          {/* 3. Draft Reply Area (Human-in-the-Loop) */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
                  Drafted Reply
                </span>
                {isModified && (
                  <span className="text-[9px] font-mono text-amber-300 bg-amber-500/10 border border-amber-500/20 px-1 py-0.2 rounded">
                    Edited
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowInstruction(!showInstruction)}
                  className="text-[11px] text-muted hover:text-primary transition-colors font-mono"
                >
                  {showInstruction ? "Hide Prompt" : "+ Add Prompt"}
                </button>
                <button
                  type="button"
                  onClick={handleAskAI}
                  disabled={aiLoading}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-white bg-accent hover:bg-accent-hover rounded-md transition-all shadow-subtle active:scale-95 disabled:opacity-50"
                >
                  {aiLoading ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Sparkles className="w-3 h-3 text-indigo-200" />
                  )}
                  <span>{aiLoading ? "Generating..." : "Ask AI"}</span>
                </button>
              </div>
            </div>

            {/* Optional Creator Prompt Input */}
            {showInstruction && (
              <div className="flex items-center gap-2 p-2 rounded-md bg-subtle border border-border">
                <input
                  type="text"
                  value={userInstruction}
                  onChange={(e) => setUserInstruction(e.target.value)}
                  placeholder="e.g. 'be concise', 'apologize for the typo', 'de-escalate'..."
                  className="flex-1 text-xs bg-surface border border-border rounded px-2.5 py-1 text-primary placeholder-muted focus:outline-none focus:border-border-focus"
                  onKeyDown={(e) => e.key === "Enter" && handleAskAI()}
                />
                <button
                  type="button"
                  onClick={handleAskAI}
                  disabled={aiLoading}
                  className="text-xs px-2.5 py-1 bg-accent hover:bg-accent-hover text-white rounded transition-colors disabled:opacity-50"
                >
                  Run
                </button>
              </div>
            )}

            {/* Explicit Sensitive Case Notice */}
            {isSensitive && (
              <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/25 text-rose-200 space-y-1.5">
                <div className="flex items-center gap-2 text-rose-300 font-semibold text-xs">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                  <span>Sensitive Case Notice</span>
                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    CRITICAL
                  </span>
                </div>
                <p className="text-xs text-rose-200/90 leading-relaxed font-sans">
                  {aiResult?.sensitive_notice ||
                    "⚠️ Notice: This comment is classified as a sensitive case (safety, legal risk, harassment, or self-harm concern). Standard public replies should be handled with extreme care. Click 'Ask AI' to generate a safe, de-escalating sample response tailored specifically for sensitive cases."}
                </p>
              </div>
            )}

            {/* AI Generated Recommendation */}
            {aiResult && (
              <div className="p-3.5 rounded-lg bg-accent-subtle/40 border border-accent/25 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-accent">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>AI Sample Response</span>
                    <span className="text-[10px] font-mono text-muted">
                      ({aiResult.model_used})
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setDraftText(aiResult.sample_response)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-accent hover:bg-accent-hover rounded transition-colors shadow-subtle"
                  >
                    <Check className="w-3 h-3" />
                    <span>Apply to Draft</span>
                  </button>
                </div>

                <div className="p-2.5 rounded bg-surface border border-border text-xs text-primary leading-relaxed font-sans">
                  "{aiResult.sample_response}"
                </div>

                {aiResult.guidance && (
                  <div className="text-[11px] text-muted leading-relaxed bg-surface/50 p-2 rounded border border-border">
                    <span className="font-semibold text-secondary">Creator Advice: </span>
                    {aiResult.guidance}
                  </div>
                )}
              </div>
            )}

            {aiError && (
              <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {aiError}
              </div>
            )}

            <div className="relative">
              <textarea
                ref={textareaRef}
                rows={4}
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                placeholder="No draft reply generated. Click 'Ask AI' above to generate a sample response."
                className="w-full text-xs font-sans rounded-lg bg-surface border border-border p-3 text-primary placeholder-muted focus:outline-none focus:border-border-focus resize-none leading-relaxed transition-colors"
              />
              <div className="absolute right-3 bottom-3 text-[10px] font-mono text-muted pointer-events-none tabular-nums">
                {draftText.length} chars
              </div>
            </div>
          </div>

          {/* 4. Retrieved Grounding Evidence Chunks */}
          {comment.retrieved_chunks && comment.retrieved_chunks.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
                  Grounding Evidence ({comment.retrieved_chunks.length} chunks)
                </span>
                <span className="text-[10px] font-mono text-muted">
                  Click timestamp to cite
                </span>
              </div>
              <div className="space-y-2">
                {comment.retrieved_chunks.map((ch, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-subtle border border-border text-xs text-secondary space-y-1.5 hover:border-border-strong transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => handleInsertCitation(ch.timestamp)}
                        className="citation-chip"
                        title="Click to insert timestamp into draft"
                      >
                        <Clock className="w-2.5 h-2.5" />
                        <span>{ch.timestamp}</span>
                      </button>
                    </div>
                    <p className="text-secondary leading-relaxed font-sans select-text">
                      {ch.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. Audit History */}
          {comment.audit_history && comment.audit_history.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-border">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-muted">
                <History className="w-3 h-3" />
                <span>Audit History</span>
              </div>
              <div className="space-y-1">
                {comment.audit_history.slice(0, 3).map((a, i) => (
                  <div
                    key={i}
                    className="text-[11px] font-mono text-muted bg-subtle p-2 rounded border border-border flex items-center justify-between"
                  >
                    <span>
                      <strong className="text-primary">{a.event}</strong> by {a.actor}
                    </span>
                    <span className="text-[10px] tabular-nums">
                      {a.timestamp.slice(11, 19)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sticky Footer Actions with Keyboard Chips */}
        <div className="h-16 px-6 border-t border-border bg-subtle flex items-center justify-between gap-3 shrink-0">
          {!showRejectInput ? (
            <>
              <button
                onClick={() => setShowRejectInput(true)}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-300 hover:text-rose-200 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-md transition-colors disabled:opacity-50"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
                <kbd className="ml-1 text-[9px]">R</kbd>
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleApprove}
                  disabled={actionLoading || !draftText.trim()}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-hover active:scale-95 rounded-md transition-all shadow-subtle disabled:opacity-40"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{isModified ? "Save & Approve" : "Approve Draft"}</span>
                  <kbd className="ml-1 text-[9px] text-white/80 bg-white/10 border-white/20">
                    A
                  </kbd>
                </button>
              </div>
            </>
          ) : (
            <div className="w-full flex items-center gap-2">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Rejection reason..."
                className="flex-1 text-xs bg-surface border border-border rounded-md px-3 py-1.5 text-primary placeholder-muted focus:outline-none focus:border-border-focus"
                onKeyDown={(e) => e.key === "Enter" && handleReject()}
              />
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="px-3 py-1.5 text-xs font-medium text-white bg-rose-600 hover:bg-rose-500 rounded-md transition-colors"
              >
                Confirm Reject
              </button>
              <button
                onClick={() => setShowRejectInput(false)}
                className="px-2.5 py-1.5 text-xs text-muted hover:text-primary"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};
