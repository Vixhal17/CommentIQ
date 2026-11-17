"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Folder, MessageSquare, Play, Upload, X, ShieldCheck, Sparkles } from "lucide-react";
import { CommentQueueItem, VideoListSummary } from "@/types";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  comments: CommentQueueItem[];
  lists: VideoListSummary[];
  onSelectComment: (comment: CommentQueueItem) => void;
  onSelectList: (listId: number | null) => void;
  onRunTriage: () => void;
  onOpenUpload: () => void;
  onOpenAutopilotRules?: () => void;
  onOpenPersonaModal?: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  comments,
  lists,
  onSelectComment,
  onSelectList,
  onRunTriage,
  onOpenUpload,
  onOpenAutopilotRules,
  onOpenPersonaModal,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (isOpen) onClose();
      }
      if (!isOpen) return;

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter items
  const cleanQ = query.trim().toLowerCase();

  const filteredLists = lists.filter(
    (l) => !cleanQ || l.title.toLowerCase().includes(cleanQ)
  );

  const filteredComments = comments
    .filter(
      (c) =>
        !cleanQ ||
        c.text.toLowerCase().includes(cleanQ) ||
        c.author.toLowerCase().includes(cleanQ) ||
        c.analysis?.category?.toLowerCase().includes(cleanQ)
    )
    .slice(0, 6);

  type ActionItem = {
    id: string;
    type: "action" | "list" | "comment";
    label: string;
    sublabel?: string;
    icon: any;
    run: () => void;
  };

  const actionItems: ActionItem[] = [
    {
      id: "run-queue",
      type: "action",
      label: "Run Queue — Process Pending Comments",
      sublabel: "Trigger background classification & RAG grounding",
      icon: Play,
      run: () => {
        onRunTriage();
        onClose();
      },
    },
    {
      id: "upload-doc",
      type: "action",
      label: "Upload Comments & Guide (.docx/.pdf)",
      sublabel: "Ingest new YouTube comments or knowledge guide",
      icon: Upload,
      run: () => {
        onOpenUpload();
        onClose();
      },
    },
    {
      id: "autopilot-rules",
      type: "action",
      label: "Autopilot Rules Engine — Safety & Thresholds",
      sublabel: "Configure deterministic AUTO, DRAFT, and ESCALATE conditions",
      icon: ShieldCheck,
      run: () => {
        onOpenAutopilotRules?.();
        onClose();
      },
    },
    {
      id: "creator-persona",
      type: "action",
      label: "Creator Persona & Tone Cloner",
      sublabel: "Customize greetings, sign-offs, emoji density, and clone your voice",
      icon: Sparkles,
      run: () => {
        onOpenPersonaModal?.();
        onClose();
      },
    },
  ];

  const matchedActions = actionItems.filter(
    (a) => !cleanQ || a.label.toLowerCase().includes(cleanQ)
  );

  const allItems: ActionItem[] = [
    ...matchedActions,
    ...filteredLists.map((l) => ({
      id: `list-${l.id}`,
      type: "list" as const,
      label: `Switch to List: ${l.title}`,
      sublabel: `${l.total_comments} comments triaged`,
      icon: Folder,
      run: () => {
        onSelectList(l.id);
        onClose();
      },
    })),
    ...filteredComments.map((c) => ({
      id: `comment-${c.id}`,
      type: "comment" as const,
      label: `Comment by ${c.author}: "${c.text.slice(0, 60)}..."`,
      sublabel: `Category: ${c.analysis?.category || "question"} • Status: ${c.status}`,
      icon: MessageSquare,
      run: () => {
        onSelectComment(c);
        onClose();
      },
    })),
  ];

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(allItems.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + allItems.length) % Math.max(allItems.length, 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (allItems[selectedIndex]) {
        allItems[selectedIndex].run();
      }
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-100">
        <motion.div
          initial={{ opacity: 0, scale: 0.98, y: -6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.98, y: -6 }}
          transition={{ duration: 0.14, ease: "easeOut" }}
          className="w-full max-w-xl rounded-xl border border-border-strong bg-surface shadow-floating overflow-hidden flex flex-col"
        >
          {/* Input Bar */}
          <div className="flex items-center gap-2.5 px-3.5 py-3 border-b border-border">
            <Search className="w-4 h-4 text-muted shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search comments, lists, or run actions..."
              className="flex-1 bg-transparent text-sm text-primary placeholder-muted focus:outline-none"
            />
            <div className="flex items-center gap-1.5">
              <kbd>Esc</kbd>
              <button
                onClick={onClose}
                className="p-1 rounded text-muted hover:text-primary transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Results List */}
          <div className="max-h-80 overflow-y-auto p-1.5 space-y-0.5">
            {allItems.length > 0 ? (
              allItems.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                const Icon = item.icon;
                return (
                  <div
                    key={item.id}
                    onClick={() => item.run()}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-surface-active text-primary"
                        : "text-secondary hover:bg-surface-hover"
                    }`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${isSelected ? "text-accent" : "text-muted"}`} />
                    <div className="flex-1 min-w-0">
                      <div className="truncate font-medium text-primary">
                        {item.label}
                      </div>
                      {item.sublabel && (
                        <div className="truncate text-[11px] text-muted">
                          {item.sublabel}
                        </div>
                      )}
                    </div>
                    {isSelected && (
                      <kbd className="text-[9px] shrink-0">↵ Enter</kbd>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="py-8 text-center text-xs text-muted">
                No matching comments, lists, or actions found.
              </div>
            )}
          </div>

          {/* Palette Footer */}
          <div className="px-3.5 py-2 border-t border-border bg-subtle/60 flex items-center justify-between text-[11px] text-muted font-mono">
            <span>Navigation: ↑ ↓ to navigate</span>
            <span>Select: ↵ Enter</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
