"use client";

import React from "react";
import { StatsResponse } from "@/types";

interface StatsBarProps {
  stats: StatsResponse | null;
}

export const StatsBar: React.FC<StatsBarProps> = ({ stats }) => {
  if (!stats) return null;

  return (
    <div className="w-full rounded-lg border border-border bg-surface shadow-subtle overflow-hidden">
      <div className="grid grid-cols-2 md:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border">
        {/* Metric 1: Total Triage */}
        <div className="px-5 py-3.5 flex flex-col justify-between group hover:bg-surface-hover/50 transition-colors">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
              Total Triaged
            </span>
            {/* Micro Sparkline */}
            <svg className="w-12 h-3.5 text-muted/60" viewBox="0 0 48 14" fill="none">
              <path
                d="M1 12L10 9L18 11L28 5L38 7L47 2"
                stroke="currentColor"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-semibold font-mono tracking-tight text-primary tabular-nums">
              {stats.total_comments}
            </span>
            <span className="text-[11px] font-mono text-secondary tabular-nums">
              {stats.auto_count} auto
            </span>
          </div>
        </div>

        {/* Metric 2: Needs Review (Held in Draft) */}
        <div className="px-5 py-3.5 flex flex-col justify-between group hover:bg-surface-hover/50 transition-colors">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
              Needs Review
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-semibold font-mono tracking-tight text-primary tabular-nums">
              {stats.pending_drafts}
            </span>
            <span className="text-[11px] font-mono text-indigo-300/80">
              {stats.pending_drafts === 0 ? "queue clear" : "held in draft"}
            </span>
          </div>
        </div>

        {/* Metric 3: Escalated */}
        <div className="px-5 py-3.5 flex flex-col justify-between group hover:bg-surface-hover/50 transition-colors">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
              Escalated
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-semibold font-mono tracking-tight text-primary tabular-nums">
              {stats.escalated_count}
            </span>
            <span className="text-[11px] font-mono text-amber-300/80">
              creator action
            </span>
          </div>
        </div>

        {/* Metric 4: Human Alignment Rate */}
        <div className="px-5 py-3.5 flex flex-col justify-between group hover:bg-surface-hover/50 transition-colors">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
              Human Alignment
            </span>
            <span className="text-[10px] font-mono text-emerald-400/90">
              ✓ Grounded
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-semibold font-mono tracking-tight text-primary tabular-nums">
              {(stats.approval_rate * 100).toFixed(0)}%
            </span>
            <span className="text-[11px] font-mono text-secondary tabular-nums">
              {(stats.edit_rate * 100).toFixed(0)}% edited
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};


