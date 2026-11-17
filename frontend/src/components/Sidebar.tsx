"use client";

import React, { useState } from "react";
import {
  Inbox,
  Layers,
  Shield,
  ShieldCheck,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Folder,
  Command,
  Sparkles,
} from "lucide-react";
import { VideoListSummary } from "@/types";

interface SidebarProps {
  lists: VideoListSummary[];
  selectedListId: number | null;
  onSelectList: (id: number | null) => void;
  activeFilter: string;
  setActiveFilter: (filter: string) => void;
  onOpenCommandPalette: () => void;
  onOpenAutopilotRules?: () => void;
  onOpenPersonaModal?: () => void;
  shadowMode: boolean;
  totalPending: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  lists,
  selectedListId,
  onSelectList,
  activeFilter,
  setActiveFilter,
  onOpenCommandPalette,
  onOpenAutopilotRules,
  onOpenPersonaModal,
  shadowMode,
  totalPending,
}) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`border-r border-border bg-subtle flex flex-col justify-between transition-all duration-200 select-none ${
        collapsed ? "w-14" : "w-60"
      }`}
    >
      {/* Top Section */}
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="h-14 px-3.5 flex items-center justify-between border-b border-border">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="h-7 w-7 rounded-md bg-surface-active border border-border-strong flex items-center justify-center shrink-0 text-primary font-mono text-xs font-bold tracking-tighter">
              CIQ
            </div>
            {!collapsed && (
              <div className="flex flex-col truncate">
                <span className="text-xs font-medium text-primary tracking-tight truncate">
                  CommentIQ
                </span>
                <span className="text-[10px] font-mono text-muted truncate">
                  v2.0 • Hybrid RAG
                </span>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded text-muted hover:text-primary hover:bg-surface-hover transition-colors"
            title={collapsed ? "Expand sidebar ([)" : "Collapse sidebar ([)"}
          >
            {collapsed ? (
              <ChevronRight className="w-3.5 h-3.5" />
            ) : (
              <ChevronLeft className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {/* Quick Command Trigger */}
        <div className="p-2 border-b border-border">
          <button
            onClick={onOpenCommandPalette}
            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-surface border border-border text-xs text-muted hover:text-primary hover:border-border-strong transition-all ${
              collapsed ? "justify-center px-0" : "justify-between"
            }`}
            title="Open command palette (⌘K)"
          >
            <div className="flex items-center gap-2">
              <Command className="w-3.5 h-3.5 text-secondary" />
              {!collapsed && <span>Search & Jump</span>}
            </div>
            {!collapsed && <kbd className="text-[9px]">⌘K</kbd>}
          </button>
        </div>

        {/* Primary Views */}
        <nav className="p-2 space-y-0.5">
          <button
            onClick={() => {
              onSelectList(null);
              setActiveFilter("all");
            }}
            className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
              selectedListId === null && activeFilter === "all"
                ? "bg-surface-active text-primary font-medium border border-border"
                : "text-secondary hover:text-primary hover:bg-surface-hover"
            } ${collapsed ? "justify-center" : ""}`}
            title="All Queued Comments"
          >
            <Inbox className="w-4 h-4 shrink-0 text-secondary" />
            {!collapsed && (
              <div className="flex-1 flex items-center justify-between text-left">
                <span>All Inbox</span>
                {totalPending > 0 && (
                  <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 tabular-nums">
                    {totalPending}
                  </span>
                )}
              </div>
            )}
          </button>

          <button
            onClick={onOpenAutopilotRules}
            className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs text-secondary hover:text-primary hover:bg-surface-hover transition-colors ${
              collapsed ? "justify-center" : ""
            }`}
            title="Granular Autopilot Rules Engine"
          >
            <ShieldCheck className="w-4 h-4 shrink-0 text-indigo-400" />
            {!collapsed && (
              <div className="flex-1 flex items-center justify-between text-left">
                <span>Autopilot Rules</span>
                <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.2 rounded">
                  Rules
                </span>
              </div>
            )}
          </button>

          <button
            onClick={onOpenPersonaModal}
            className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs text-secondary hover:text-primary hover:bg-surface-hover transition-colors ${
              collapsed ? "justify-center" : ""
            }`}
            title="Creator Persona & Tone Cloner"
          >
            <Sparkles className="w-4 h-4 shrink-0 text-amber-400" />
            {!collapsed && (
              <div className="flex-1 flex items-center justify-between text-left">
                <span>Creator Persona</span>
                <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.2 rounded">
                  Voice
                </span>
              </div>
            )}
          </button>
        </nav>

        {/* Workspaces / Video Lists */}
        {!collapsed ? (
          <div className="px-2 pt-3">
            <div className="px-2.5 pb-1.5 flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
                Workspaces ({lists.length})
              </span>
              <Layers className="w-3 h-3 text-muted" />
            </div>
            <div className="space-y-0.5 max-h-56 overflow-y-auto">
              {lists.map((l) => {
                const isActive = selectedListId === l.id;
                return (
                  <button
                    key={l.id}
                    onClick={() => onSelectList(l.id)}
                    className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors text-left ${
                      isActive
                        ? "bg-surface-active text-primary font-medium border border-border"
                        : "text-secondary hover:text-primary hover:bg-surface-hover"
                    }`}
                  >
                    <Folder className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-accent" : "text-muted"}`} />
                    <span className="truncate flex-1">{l.title}</span>
                    <span className="text-[10px] font-mono text-muted tabular-nums">
                      {l.total_comments}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="p-2 border-t border-border mt-2 flex flex-col items-center gap-1">
            <button
              onClick={() => onSelectList(null)}
              className="p-2 rounded text-muted hover:text-primary hover:bg-surface-hover"
              title="Workspaces"
            >
              <Layers className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Bottom Status & System Info */}
      <div className="p-2 border-t border-border space-y-1">
        {/* Subtle Shadow Mode indicator */}
        <div
          className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[11px] font-mono border ${
            shadowMode
              ? "bg-surface text-secondary border-border"
              : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
          } ${collapsed ? "justify-center" : ""}`}
          title={shadowMode ? "Shadow Mode: Drafts held for approval" : "Live Auto-Publish Enabled"}
        >
          <span className="relative flex h-2 w-2 shrink-0">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                shadowMode ? "bg-amber-400" : "bg-emerald-400"
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                shadowMode ? "bg-amber-500" : "bg-emerald-500"
              }`}
            />
          </span>
          {!collapsed && (
            <span className="truncate">
              {shadowMode ? "Shadow Mode" : "Live Auto-Reply"}
            </span>
          )}
        </div>
      </div>
    </aside>
  );
};
