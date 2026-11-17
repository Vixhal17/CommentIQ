"use client";

import React from "react";
import { Play, RefreshCw, Upload, Search, ChevronDown } from "lucide-react";
import { VideoListSummary } from "@/types";

interface HeaderProps {
  shadowMode: boolean;
  lists: VideoListSummary[];
  selectedListId: number | null;
  onSelectList: (id: number | null) => void;
  onRefresh: () => void;
  onRunTriage: () => void;
  onOpenUpload: () => void;
  onOpenCommandPalette: () => void;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  shadowMode,
  lists,
  selectedListId,
  onSelectList,
  onRefresh,
  onRunTriage,
  onOpenUpload,
  onOpenCommandPalette,
  loading,
}) => {
  const currentList = lists.find((l) => l.id === selectedListId);

  return (
    <header className="h-14 border-b border-border bg-subtle/80 backdrop-blur-md sticky top-0 z-30 px-5 flex items-center justify-between gap-4">
      {/* Left: Breadcrumbs & Workspace Switcher */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-muted font-mono uppercase tracking-wider text-[10px]">
            Queue
          </span>
          <span className="text-muted">/</span>
          <div className="relative flex items-center">
            <select
              value={selectedListId ?? ""}
              onChange={(e) => onSelectList(e.target.value ? Number(e.target.value) : null)}
              className="appearance-none bg-surface border border-border hover:border-border-strong text-primary text-xs font-medium rounded-md pl-2.5 pr-7 py-1 focus:outline-none focus:border-border-focus cursor-pointer truncate max-w-[240px] transition-colors"
            >
              <option value="">All Lists (Overview)</option>
              {lists.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title} ({l.total_comments})
                </option>
              ))}
            </select>
            <ChevronDown className="w-3 h-3 text-muted absolute right-2 pointer-events-none" />
          </div>
        </div>

        {currentList?.has_reference_doc && (
          <span className="hidden md:inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-[4px]">
            <span>✓ Guide Active</span>
          </span>
        )}
      </div>

      {/* Center: Command Palette Trigger */}
      <div className="hidden lg:flex items-center">
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface border border-border hover:border-border-strong text-xs text-muted hover:text-secondary transition-all w-64 justify-between"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5" />
            <span>Search or jump to...</span>
          </div>
          <kbd className="text-[9px]">⌘K</kbd>
        </button>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Refresh */}
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 rounded-md text-muted hover:text-primary hover:bg-surface border border-transparent hover:border-border transition-colors disabled:opacity-50"
          title="Refresh queue"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>

        {/* Run Pending Triage */}
        <button
          onClick={onRunTriage}
          disabled={loading}
          className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-md bg-surface hover:bg-surface-hover text-secondary hover:text-primary border border-border transition-colors disabled:opacity-50"
          title="Run background classification on pending items"
        >
          <Play className="w-3 h-3 fill-current text-muted" />
          <span>Run Queue</span>
        </button>

        {/* Primary Upload & Triage */}
        <button
          onClick={onOpenUpload}
          className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md bg-accent hover:bg-accent-hover text-white transition-all shadow-subtle active:scale-95"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>Upload</span>
        </button>
      </div>
    </header>
  );
};
