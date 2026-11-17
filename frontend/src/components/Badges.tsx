import React from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle } from "lucide-react";

export const CategoryBadge: React.FC<{ category?: string }> = ({ category = "question" }) => {
  const cat = category.toLowerCase();

  // Linear-style quiet, desaturated category tags
  const styles: Record<string, string> = {
    question: "bg-surface-elevated text-secondary border-border hover:border-border-strong",
    praise: "bg-emerald-500/10 text-emerald-400/90 border-emerald-500/20",
    complaint: "bg-amber-500/10 text-amber-400/90 border-amber-500/20",
    business_collab: "bg-indigo-500/10 text-indigo-300 border-indigo-500/20",
    technical_correction: "bg-sky-500/10 text-sky-400/90 border-sky-500/20",
    spam: "bg-neutral-800/60 text-muted border-border",
    sensitive: "bg-rose-500/15 text-rose-300 border-rose-500/30 font-medium",
  };

  const labelMap: Record<string, string> = {
    question: "Question",
    praise: "Praise",
    complaint: "Complaint",
    business_collab: "Partnership",
    technical_correction: "Correction",
    spam: "Spam",
    sensitive: "Sensitive",
  };

  const badgeStyle = styles[cat] || "bg-surface text-secondary border-border";
  const label = labelMap[cat] || category;

  return (
    <span
      className={`inline-flex items-center text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded-[4px] border ${badgeStyle} transition-colors`}
    >
      {label}
    </span>
  );
};

export const ActionBadge: React.FC<{ action?: string }> = ({ action = "DRAFT" }) => {
  const act = action.toUpperCase();

  const styles: Record<string, { bg: string; dot: string; label: string }> = {
    AUTO: {
      bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      dot: "bg-emerald-400",
      label: "AUTO",
    },
    DRAFT: {
      bg: "bg-indigo-500/10 text-indigo-300 border-indigo-500/20",
      dot: "bg-indigo-400",
      label: "DRAFT",
    },
    ESCALATE: {
      bg: "bg-amber-500/10 text-amber-300 border-amber-500/20",
      dot: "bg-amber-400",
      label: "ESCALATE",
    },
  };

  const current = styles[act] || styles.DRAFT;

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[10px] font-mono uppercase font-semibold tracking-widest px-2 py-0.5 rounded-[4px] border ${current.bg}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${current.dot}`} />
      {current.label}
    </span>
  );
};

export const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const s = status.toLowerCase();

  const styles: Record<string, { text: string; bg: string; border: string; label: string }> = {
    drafted: {
      text: "text-indigo-300",
      bg: "bg-indigo-500/10",
      border: "border-indigo-500/20",
      label: "Needs Review",
    },
    approved: {
      text: "text-emerald-400",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
      label: "Approved",
    },
    published: {
      text: "text-emerald-400",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
      label: "Published",
    },
    escalated: {
      text: "text-amber-300",
      bg: "bg-amber-500/10",
      border: "border-amber-500/20",
      label: "Escalated",
    },
    rejected: {
      text: "text-muted",
      bg: "bg-surface-active",
      border: "border-border",
      label: "Rejected",
    },
    new: {
      text: "text-secondary",
      bg: "bg-surface",
      border: "border-border",
      label: "Queued",
    },
  };

  const current = styles[s] || {
    text: "text-secondary",
    bg: "bg-surface",
    border: "border-border",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center text-[10px] font-mono tracking-wider uppercase px-2 py-0.5 rounded-[4px] border ${current.bg} ${current.border} ${current.text}`}
    >
      {current.label}
    </span>
  );
};

export const FaithfulnessBadge: React.FC<{
  score?: number | null;
  independent?: boolean;
}> = ({ score, independent = true }) => {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-mono text-muted">
        <span>N/A</span>
      </span>
    );
  }

  const pct = Math.round(score * 100);
  const isHigh = pct >= 80;
  const isMid = pct >= 50 && pct < 80;

  return (
    <div
      className="group relative inline-flex items-center gap-1.5"
      title={
        !independent
          ? "Fallback evaluation was not independent from generator"
          : `Verified grounded by judge: ${pct}% faithful`
      }
    >
      <span
        className={`inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded-[4px] border tabular-nums ${
          !independent
            ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
            : isHigh
            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
            : isMid
            ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
            : "bg-rose-500/10 text-rose-300 border-rose-500/20"
        }`}
      >
        {!independent ? (
          <ShieldAlert className="w-2.5 h-2.5" />
        ) : (
          <ShieldCheck className="w-2.5 h-2.5" />
        )}
        <span>{pct}%</span>
      </span>
    </div>
  );
};


