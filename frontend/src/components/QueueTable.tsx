"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  CheckCircle2,
  XCircle,
  Check,
  ChevronRight,
  Inbox,
  Filter,
} from "lucide-react";
import { CommentQueueItem } from "@/types";
import { CategoryBadge, ActionBadge, StatusPill } from "./Badges";

interface QueueTableProps {
  comments: CommentQueueItem[];
  onSelectComment: (comment: CommentQueueItem) => void;
  activeFilter: string;
  setActiveFilter: (filter: string) => void;
  onBulkApprove?: (ids: number[]) => Promise<void>;
  onBulkReject?: (ids: number[]) => Promise<void>;
}

function getAvatarHue(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 40%, 25%)`;
}

function getInitials(name: string): string {
  if (!name) return "?";
  const parts = name.trim().split(" ");
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return "";
  try {
    const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diffSec < 60) return "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "1d";
    return `${diffDays}d`;
  } catch {
    return "";
  }
}

export const QueueTable: React.FC<QueueTableProps> = ({
  comments,
  onSelectComment,
  activeFilter,
  setActiveFilter,
  onBulkApprove,
  onBulkReject,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);

  // Live Counts for Tabs
  const counts = {
    all: comments.length,
    drafted: comments.filter((c) => c.status === "drafted").length,
    escalated: comments.filter((c) => c.status === "escalated").length,
    approved: comments.filter((c) => c.status === "approved" || c.status === "published").length,
    rejected: comments.filter((c) => c.status === "rejected").length,
  };

  const filterTabs = [
    { id: "all", label: "All Items", count: counts.all },
    { id: "drafted", label: "Needs Review", count: counts.drafted },
    { id: "escalated", label: "Escalated", count: counts.escalated },
    { id: "approved", label: "Approved", count: counts.approved },
    { id: "rejected", label: "Rejected", count: counts.rejected },
  ];

  const filteredComments = comments.filter((c) => {
    if (activeFilter !== "all") {
      if (activeFilter === "approved") {
        if (c.status !== "approved" && c.status !== "published") return false;
      } else if (c.status !== activeFilter) {
        return false;
      }
    }

    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      const textMatch = c.text.toLowerCase().includes(term);
      const authorMatch = c.author.toLowerCase().includes(term);
      const categoryMatch = c.analysis?.category.toLowerCase().includes(term);
      return textMatch || authorMatch || categoryMatch;
    }

    return true;
  });

  // Keyboard navigation: j/k to move, Enter to open, x to select
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in input or textarea
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((prev) => Math.min(prev + 1, Math.max(filteredComments.length - 1, 0)));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const activeComment = filteredComments[focusedIndex];
        if (activeComment) {
          onSelectComment(activeComment);
        }
      } else if (e.key === "x") {
        e.preventDefault();
        const activeComment = filteredComments[focusedIndex];
        if (activeComment) {
          toggleRowSelect(activeComment.id);
        }
      } else if (e.key === "Escape") {
        setSelectedIds(new Set());
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredComments, focusedIndex, onSelectComment]);

  const toggleRowSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredComments.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredComments.map((c) => c.id)));
    }
  };

  const handleBulkApprove = async () => {
    if (!onBulkApprove || selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await onBulkApprove(Array.from(selectedIds));
      setSelectedIds(new Set());
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkReject = async () => {
    if (!onBulkReject || selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await onBulkReject(Array.from(selectedIds));
      setSelectedIds(new Set());
    } finally {
      setBulkLoading(false);
    }
  };

  return (
    <div
      ref={tableRef}
      className="w-full rounded-lg border border-border bg-surface shadow-subtle flex flex-col relative overflow-hidden"
    >
      {/* Segmented Filter Control & Search Bar */}
      <div className="p-3 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-subtle/50">
        {/* Segmented Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          {filterTabs.map((tab) => {
            const isActive = activeFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveFilter(tab.id);
                  setFocusedIndex(0);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                    : "text-secondary hover:text-primary hover:bg-surface-hover"
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] font-mono tabular-nums px-1.5 py-0.2 rounded ${
                    isActive ? "bg-surface-elevated text-primary" : "text-muted"
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Dense Search Input */}
        <div className="relative w-full sm:w-56 shrink-0">
          <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setFocusedIndex(0);
            }}
            placeholder="Filter by keyword..."
            className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md pl-8 pr-3 py-1 text-primary placeholder-muted focus:outline-none focus:border-border-focus transition-colors"
          />
        </div>
      </div>

      {/* Scannable Queue Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          {/* Sticky Header */}
          <thead className="sticky top-0 z-10 bg-subtle/95 backdrop-blur-sm border-b border-border select-none">
            <tr className="text-[10px] font-mono uppercase tracking-widest text-muted">
              <th className="py-2.5 px-3 w-8 text-center">
                <input
                  type="checkbox"
                  checked={
                    filteredComments.length > 0 &&
                    selectedIds.size === filteredComments.length
                  }
                  onChange={toggleSelectAll}
                  className="rounded border-border bg-surface text-accent focus:ring-0 cursor-pointer"
                />
              </th>
              <th className="py-2.5 px-3 w-48 font-medium">Author & Workspace</th>
              <th className="py-2.5 px-3 font-medium">Comment Preview</th>
              <th className="py-2.5 px-3 w-28 font-medium">Category</th>
              <th className="py-2.5 px-3 w-24 font-medium">Routing</th>
              <th className="py-2.5 px-3 w-16 font-medium text-right">RAG</th>
              <th className="py-2.5 px-3 w-20 font-medium text-right">Status</th>
              <th className="py-2.5 px-3 w-14 font-medium text-right">Time</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-border font-sans">
            {filteredComments.length > 0 ? (
              filteredComments.map((comment, index) => {
                const isSelected = selectedIds.has(comment.id);
                const isFocused = index === focusedIndex;

                // Status Rail Color
                const action = comment.analysis?.action || "DRAFT";
                const isSens = comment.analysis?.category?.toLowerCase() === "sensitive";
                const railColor = isSens
                  ? "bg-rose-500"
                  : action === "AUTO"
                  ? "bg-emerald-500"
                  : action === "ESCALATE"
                  ? "bg-amber-500"
                  : "bg-indigo-500";

                return (
                  <tr
                    key={comment.id}
                    onClick={() => onSelectComment(comment)}
                    onMouseEnter={() => setFocusedIndex(index)}
                    className={`group cursor-pointer transition-colors relative ${
                      isFocused ? "bg-surface-hover" : "hover:bg-surface-hover/70"
                    } ${isSelected ? "bg-accent-subtle/30" : ""}`}
                    style={{ height: "46px" }}
                  >
                    {/* Left Status Rail (1px subtle indicator) */}
                    <td className="p-0 relative">
                      <div
                        className={`absolute left-0 top-0 bottom-0 w-[2.5px] ${railColor} opacity-75 group-hover:opacity-100 transition-opacity`}
                      />
                      <div
                        className="py-2.5 px-3 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRowSelect(comment.id)}
                          className="rounded border-border bg-surface text-accent focus:ring-0 cursor-pointer"
                        />
                      </div>
                    </td>

                    {/* Author & Avatar */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono font-medium text-white shrink-0"
                          style={{ backgroundColor: getAvatarHue(comment.author || "Anon") }}
                        >
                          {getInitials(comment.author || "Anon")}
                        </div>
                        <div className="truncate max-w-[150px]">
                          <span className="text-primary font-medium truncate block">
                            {comment.author || "Anonymous"}
                          </span>
                          <span className="text-[10px] text-muted truncate block">
                            {comment.video_title}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Comment Preview */}
                    <td className="py-2 px-3 max-w-md">
                      <div className="text-secondary group-hover:text-primary transition-colors line-clamp-1 text-xs">
                        {comment.text}
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      <CategoryBadge category={comment.analysis?.category} />
                    </td>

                    {/* Routing Decision */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      <ActionBadge action={comment.analysis?.action} />
                    </td>

                    {/* Grounding Score */}
                    <td className="py-2 px-3 whitespace-nowrap text-right font-mono text-[11px] text-muted tabular-nums">
                      {comment.analysis?.confidence
                        ? `${(comment.analysis.confidence * 100).toFixed(0)}%`
                        : "—"}
                    </td>

                    {/* Status */}
                    <td className="py-2 px-3 whitespace-nowrap text-right">
                      <StatusPill status={comment.status} />
                    </td>

                    {/* Time */}
                    <td className="py-2 px-3 whitespace-nowrap text-right font-mono text-[10px] text-muted">
                      {formatRelativeTime(comment.created_at)}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} className="py-16 text-center">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <div className="h-9 w-9 rounded-full bg-surface-active border border-border flex items-center justify-center text-muted">
                      <Inbox className="w-4 h-4" />
                    </div>
                    <div className="text-sm font-medium text-primary">
                      Nothing needs you right now
                    </div>
                    <p className="text-xs text-muted max-w-sm">
                      {searchTerm
                        ? `No comments matched "${searchTerm}". Try clearing your search.`
                        : "All comments in this view have been reviewed or resolved. You're completely caught up."}
                    </p>
                    {searchTerm && (
                      <button
                        onClick={() => setSearchTerm("")}
                        className="mt-2 text-xs font-mono text-accent hover:text-accent-hover"
                      >
                        Clear search filter
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Floating Bulk Action Bar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-surface border border-border-strong rounded-xl shadow-floating px-4 py-2.5 flex items-center gap-3 backdrop-blur-md"
          >
            <div className="text-xs font-mono text-primary flex items-center gap-1.5 pr-2 border-r border-border">
              <span className="font-semibold text-accent tabular-nums">
                {selectedIds.size}
              </span>
              <span>selected</span>
            </div>

            {onBulkApprove && (
              <button
                onClick={handleBulkApprove}
                disabled={bulkLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-accent hover:bg-accent-hover rounded-md transition-colors disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve All</span>
              </button>
            )}

            {onBulkReject && (
              <button
                onClick={handleBulkReject}
                disabled={bulkLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-md transition-colors disabled:opacity-50"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject All</span>
              </button>
            )}

            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-xs text-muted hover:text-primary px-1.5 py-1 transition-colors flex items-center gap-1"
            >
              <kbd>Esc</kbd>
              <span>Clear</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Keyboard Navigation Hint Bar */}
      <div className="px-3.5 py-2 border-t border-border bg-subtle/40 flex items-center justify-between text-[11px] text-muted font-mono select-none">
        <div className="flex items-center gap-3">
          <span>
            <kbd>j</kbd> / <kbd>k</kbd> Navigate
          </span>
          <span>
            <kbd>↵</kbd> Open Drawer
          </span>
          <span>
            <kbd>x</kbd> Select Row
          </span>
        </div>
        <div className="tabular-nums">
          {filteredComments.length} {filteredComments.length === 1 ? "item" : "items"}
        </div>
      </div>
    </div>
  );
};
