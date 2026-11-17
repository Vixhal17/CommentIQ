"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  ShieldCheck,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Sliders,
  RotateCcw,
  Play,
  Check,
  AlertTriangle,
} from "lucide-react";
import { AutopilotRule, TestRuleResponse } from "@/types";

const API_BASE = "http://127.0.0.1:8000/api";

const CATEGORY_CHOICES = [
  "question",
  "praise",
  "complaint",
  "feature_request",
  "business_collab",
  "refund_billing",
  "technical_correction",
  "spam",
  "sensitive",
];

interface AutopilotModalProps {
  isOpen: boolean;
  onClose: () => void;
  shadowMode: boolean;
  onRulesChanged?: () => void;
}

export const AutopilotModal: React.FC<AutopilotModalProps> = ({
  isOpen,
  onClose,
  shadowMode,
  onRulesChanged,
}) => {
  const [rules, setRules] = useState<AutopilotRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Active view: "rules" | "simulator"
  const [activeTab, setActiveTab] = useState<"rules" | "simulator">("rules");

  // Create / Edit rule state
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [ruleDesc, setRuleDesc] = useState("");
  const [ruleAction, setRuleAction] = useState<"AUTO" | "DRAFT" | "ESCALATE">("DRAFT");
  const [rulePriority, setRulePriority] = useState<number>(5);
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [minConfidence, setMinConfidence] = useState<number | "">("");
  const [minFaithfulness, setMinFaithfulness] = useState<number | "">("");
  const [minRetrieval, setMinRetrieval] = useState<number | "">("");
  const [requireCitations, setRequireCitations] = useState(false);
  const [maxWords, setMaxWords] = useState<number | "">("");
  const [keywordsAny, setKeywordsAny] = useState("");
  const [negativeKeywords, setNegativeKeywords] = useState("");
  const [authorMatch, setAuthorMatch] = useState("");

  // Simulator state
  const [simComment, setSimComment] = useState(
    "How do I install the required packages? Does this work with Python 3.12?"
  );
  const [simCategory, setSimCategory] = useState("question");
  const [simConfidence, setSimConfidence] = useState(0.92);
  const [simFaithfulness, setSimFaithfulness] = useState(0.88);
  const [simCitations, setSimCitations] = useState(true);
  const [simAuthor, setSimAuthor] = useState("TechViewer");
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<TestRuleResponse | null>(null);

  const showNotification = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/autopilot/rules`);
      if (res.ok) {
        const data: AutopilotRule[] = await res.json();
        setRules(data);
      } else {
        throw new Error(`Failed to load rules (HTTP ${res.status})`);
      }
    } catch (err: any) {
      console.error("Fetch rules failed:", err);
      setError(err.message || "Failed to load autopilot rules");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchRules();
      setShowRuleForm(false);
      setEditingRuleId(null);
      setSimResult(null);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleToggleRule = async (rule: AutopilotRule) => {
    const updatedState = !rule.enabled;
    setRules((prev) =>
      prev.map((r) => (r.id === rule.id ? { ...r, enabled: updatedState } : r))
    );

    try {
      const res = await fetch(`${API_BASE}/autopilot/rules/${rule.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: updatedState }),
      });
      if (!res.ok) throw new Error("Failed to update rule state");
      showNotification(`Rule "${rule.name}" ${updatedState ? "enabled" : "disabled"}`);
      onRulesChanged?.();
    } catch (err: any) {
      console.error("Toggle rule failed:", err);
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, enabled: rule.enabled } : r))
      );
      setError(err.message || "Failed to toggle rule");
    }
  };

  const handleDeleteRule = async (ruleId: number, ruleName: string) => {
    if (!window.confirm(`Delete autopilot rule "${ruleName}"?`)) return;

    try {
      const res = await fetch(`${API_BASE}/autopilot/rules/${ruleId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete rule");
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
      showNotification(`Deleted rule "${ruleName}"`);
      onRulesChanged?.();
    } catch (err: any) {
      console.error("Delete rule failed:", err);
      setError(err.message || "Failed to delete rule");
    }
  };

  const handleResetDefaults = async () => {
    if (
      !window.confirm(
        "Reset all autopilot rules back to recommended factory defaults? Any custom rules will be removed."
      )
    ) {
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/autopilot/rules/reset`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to reset rules");
      const defaultRules: AutopilotRule[] = await res.json();
      setRules(defaultRules);
      showNotification("Autopilot rules reset to recommended defaults");
      onRulesChanged?.();
    } catch (err: any) {
      console.error("Reset failed:", err);
      setError(err.message || "Failed to reset rules");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateForm = () => {
    setEditingRuleId(null);
    setRuleName("");
    setRuleDesc("");
    setRuleAction("DRAFT");
    setRulePriority(rules.length + 1);
    setSelectedCats([]);
    setMinConfidence("");
    setMinFaithfulness("");
    setMinRetrieval("");
    setRequireCitations(false);
    setMaxWords("");
    setKeywordsAny("");
    setNegativeKeywords("");
    setAuthorMatch("");
    setShowRuleForm(true);
  };

  const handleSaveRule = async () => {
    if (!ruleName.trim()) {
      setError("Please provide a name for the rule");
      return;
    }

    const payload = {
      name: ruleName.trim(),
      description: ruleDesc.trim(),
      enabled: true,
      priority: Number(rulePriority) || 10,
      action: ruleAction,
      categories: selectedCats,
      min_confidence: minConfidence === "" ? null : Number(minConfidence),
      min_faithfulness: minFaithfulness === "" ? null : Number(minFaithfulness),
      min_retrieval_score: minRetrieval === "" ? null : Number(minRetrieval),
      require_citations: requireCitations,
      max_comment_words: maxWords === "" ? null : Number(maxWords),
      keywords_any: keywordsAny
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      negative_keywords: negativeKeywords
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      author_match: authorMatch.trim() || null,
    };

    setLoading(true);
    setError(null);

    try {
      const url = editingRuleId
        ? `${API_BASE}/autopilot/rules/${editingRuleId}`
        : `${API_BASE}/autopilot/rules`;
      const method = editingRuleId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to save rule");
      }

      const saved: AutopilotRule = await res.json();
      if (editingRuleId) {
        setRules((prev) => prev.map((r) => (r.id === saved.id ? saved : r)));
        showNotification(`Updated rule "${saved.name}"`);
      } else {
        setRules((prev) => [...prev, saved].sort((a, b) => a.priority - b.priority));
        showNotification(`Created rule "${saved.name}"`);
      }
      setShowRuleForm(false);
      onRulesChanged?.();
    } catch (err: any) {
      console.error("Save rule error:", err);
      setError(err.message || "Failed to save rule");
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulator = async () => {
    if (!simComment.trim()) {
      setError("Please enter sample comment text to simulate");
      return;
    }

    setSimulating(true);
    setError(null);
    setSimResult(null);

    try {
      const draftText = simCitations
        ? "Yes! As shown at [03:20], Python 3.10+ is fully supported."
        : "Yes, Python 3.10+ is fully supported.";

      const payload = {
        comment_text: simComment.trim(),
        category: simCategory,
        confidence: simConfidence,
        retrieval_score: 0.55,
        faithfulness: simFaithfulness,
        draft_text: draftText,
        author: simAuthor.trim() || "Viewer",
      };

      const res = await fetch(`${API_BASE}/autopilot/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Simulation request failed");
      const data: TestRuleResponse = await res.json();
      setSimResult(data);
    } catch (err: any) {
      console.error("Simulator error:", err);
      setError(err.message || "Simulator execution failed");
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-canvas/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="relative w-full max-w-4xl bg-surface-elevated border border-border-strong rounded-xl shadow-floating overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-subtle/80 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-md bg-surface-active border border-border-strong flex items-center justify-center shrink-0 text-primary">
              <ShieldCheck className="w-4 h-4 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-primary tracking-tight">
                  Granular Autopilot Rules Engine
                </h2>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  Batch 2 Active
                </span>
              </div>
              <p className="text-xs text-secondary mt-0.5">
                Deterministic multi-condition safety guardrails: AUTO, DRAFT, and ESCALATE routing
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Shadow Mode Persistent Pill */}
            <div
              className={`px-2.5 py-1 rounded-full text-[11px] font-mono border flex items-center gap-1.5 ${
                shadowMode
                  ? "bg-surface text-secondary border-border"
                  : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  shadowMode ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
                }`}
              />
              <span>{shadowMode ? "Shadow Mode: AUTO Held" : "Live Auto-Publish Enabled"}</span>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-muted hover:text-primary hover:bg-surface-hover transition-colors"
            >
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border bg-subtle/50 px-6 gap-2">
          <button
            onClick={() => setActiveTab("rules")}
            className={`py-2.5 px-3 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "rules"
                ? "border-primary text-primary font-medium"
                : "border-transparent text-muted hover:text-secondary"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Active Triage Rules ({rules.length})</span>
          </button>
          <button
            onClick={() => setActiveTab("simulator")}
            className={`py-2.5 px-3 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "simulator"
                ? "border-primary text-primary font-medium"
                : "border-transparent text-muted hover:text-secondary"
            }`}
          >
            <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Dry-Run Simulator</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          {activeTab === "rules" && (
            <div className="space-y-4">
              {/* Actions Bar */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">
                  Rules evaluate in priority order (#1 = highest). First matching rule decides routing.
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleResetDefaults}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-secondary hover:text-primary bg-surface border border-border hover:border-border-strong rounded-md transition-colors"
                    title="Restore default factory safety rules"
                  >
                    <RotateCcw className="w-3 h-3" strokeWidth={1.5} />
                    <span>Reset Defaults</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenCreateForm}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all shadow-subtle"
                  >
                    <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>Add Rule</span>
                  </button>
                </div>
              </div>

              {/* Rule Builder / Form */}
              {showRuleForm && (
                <div className="p-5 rounded-lg bg-surface/50 border border-border-strong space-y-4 animate-in fade-in">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <span className="text-xs font-semibold text-primary">
                      {editingRuleId ? "Edit Autopilot Rule" : "Create New Autopilot Rule"}
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowRuleForm(false)}
                      className="text-muted hover:text-secondary text-xs"
                    >
                      Cancel
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="sm:col-span-2 space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Rule Name</label>
                      <input
                        type="text"
                        value={ruleName}
                        onChange={(e) => setRuleName(e.target.value)}
                        placeholder="e.g. Verified Technical FAQ Auto-Publish"
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus transition-colors"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Target Action</label>
                      <select
                        value={ruleAction}
                        onChange={(e) => setRuleAction(e.target.value as any)}
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary focus:outline-none focus:border-border-focus font-mono"
                      >
                        <option value="AUTO">AUTO (Auto-Publish)</option>
                        <option value="DRAFT">DRAFT (Review Queue)</option>
                        <option value="ESCALATE">ESCALATE (Flag to Creator)</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Description / Rationale</label>
                    <input
                      type="text"
                      value={ruleDesc}
                      onChange={(e) => setRuleDesc(e.target.value)}
                      placeholder="Why this rule fires and what safety condition it enforces..."
                      className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus transition-colors"
                    />
                  </div>

                  {/* Category Filter Chips */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">
                      Target Categories (Leave empty to apply to all categories)
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {CATEGORY_CHOICES.map((cat) => {
                        const isSelected = selectedCats.includes(cat);
                        return (
                          <button
                            key={cat}
                            type="button"
                            onClick={() => {
                              setSelectedCats((prev) =>
                                isSelected ? prev.filter((c) => c !== cat) : [...prev, cat]
                              );
                            }}
                            className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all border ${
                              isSelected
                                ? "bg-primary text-canvas border-primary font-medium"
                                : "bg-surface text-secondary border-border hover:border-border-strong"
                            }`}
                          >
                            {cat}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Thresholds Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Min Confidence (0-1)</label>
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="1"
                        value={minConfidence}
                        onChange={(e) => setMinConfidence(e.target.value === "" ? "" : Number(e.target.value))}
                        placeholder="e.g. 0.85"
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Min Faithfulness (0-1)</label>
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="1"
                        value={minFaithfulness}
                        onChange={(e) => setMinFaithfulness(e.target.value === "" ? "" : Number(e.target.value))}
                        placeholder="e.g. 0.80"
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Max Words Limit</label>
                      <input
                        type="number"
                        min="1"
                        value={maxWords}
                        onChange={(e) => setMaxWords(e.target.value === "" ? "" : Number(e.target.value))}
                        placeholder="e.g. 20"
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Evaluation Priority</label>
                      <input
                        type="number"
                        min="1"
                        value={rulePriority}
                        onChange={(e) => setRulePriority(Number(e.target.value))}
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary focus:outline-none focus:border-border-focus font-mono"
                      />
                    </div>
                  </div>

                  {/* Keywords Filters */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-rose-400">
                        Negative Keywords Suppression (Comma-separated)
                      </label>
                      <input
                        type="text"
                        value={negativeKeywords}
                        onChange={(e) => setNegativeKeywords(e.target.value)}
                        placeholder="refund, scam, broken, lawyer, urgent..."
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-rose-500 font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-mono uppercase tracking-widest text-secondary">
                        Trigger Keywords (Must contain at least one)
                      </label>
                      <input
                        type="text"
                        value={keywordsAny}
                        onChange={(e) => setKeywordsAny(e.target.value)}
                        placeholder="sponsor, podcast, collab, invite..."
                        className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus font-mono"
                      />
                    </div>
                  </div>

                  {/* Citations Required Checkbox */}
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="reqCitations"
                      checked={requireCitations}
                      onChange={(e) => setRequireCitations(e.target.checked)}
                      className="rounded border-border-strong bg-surface text-primary focus:ring-0"
                    />
                    <label htmlFor="reqCitations" className="text-xs text-secondary font-medium cursor-pointer">
                      Require grounded citation markers <span className="font-mono text-primary">[MM:SS]</span> in drafted reply
                    </label>
                  </div>

                  <div className="flex justify-end gap-2 pt-2 border-t border-border">
                    <button
                      type="button"
                      onClick={() => setShowRuleForm(false)}
                      className="px-3 py-1.5 text-xs text-muted hover:text-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveRule}
                      className="px-4 py-1.5 text-xs bg-primary text-canvas hover:bg-white rounded-md font-medium transition-colors shadow-subtle"
                    >
                      Save Autopilot Rule
                    </button>
                  </div>
                </div>
              )}

              {/* Rules List */}
              <div className="space-y-2">
                {rules.map((rule) => {
                  const actionStyle =
                    rule.action === "AUTO"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : rule.action === "DRAFT"
                      ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                      : "bg-amber-500/10 text-amber-300 border-amber-500/20";

                  return (
                    <div
                      key={rule.id}
                      className={`p-3.5 rounded-lg border transition-all ${
                        rule.enabled
                          ? "bg-surface/40 border-border"
                          : "bg-surface/15 border-border/40 opacity-60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface border border-border text-secondary">
                              #{rule.priority}
                            </span>
                            <span className="font-medium text-xs text-primary">{rule.name}</span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${actionStyle}`}>
                              {rule.action}
                            </span>
                            {!rule.enabled && (
                              <span className="text-[10px] font-mono text-muted italic">
                                (Disabled)
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-muted leading-relaxed">
                            {rule.description || "Custom creator autopilot safety rule"}
                          </p>

                          {/* Rule Criteria Breakdown Tags */}
                          <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[10px] font-mono">
                            {rule.categories && rule.categories.length > 0 ? (
                              <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-secondary">
                                {rule.categories.join(", ")}
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-muted">
                                All Categories
                              </span>
                            )}

                            {rule.min_confidence != null && (
                              <span className="px-1.5 py-0.2 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                                Conf ≥ {(rule.min_confidence * 100).toFixed(0)}%
                              </span>
                            )}

                            {rule.min_faithfulness != null && (
                              <span className="px-1.5 py-0.2 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                                Faithfulness ≥ {(rule.min_faithfulness * 100).toFixed(0)}%
                              </span>
                            )}

                            {rule.require_citations && (
                              <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-primary">
                                [MM:SS] Required
                              </span>
                            )}

                            {rule.max_comment_words != null && (
                              <span className="px-1.5 py-0.2 rounded bg-surface border border-border text-secondary">
                                ≤ {rule.max_comment_words} words
                              </span>
                            )}

                            {rule.negative_keywords && rule.negative_keywords.length > 0 && (
                              <span className="px-1.5 py-0.2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300">
                                Suppress: {rule.negative_keywords.slice(0, 3).join(", ")}
                                {rule.negative_keywords.length > 3 ? "..." : ""}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleToggleRule(rule)}
                            className={`px-2 py-0.5 text-[10px] font-mono rounded border transition-colors ${
                              rule.enabled
                                ? "bg-surface border-border text-primary hover:border-border-strong"
                                : "bg-surface/30 border-border text-muted hover:text-secondary"
                            }`}
                          >
                            {rule.enabled ? "Enabled" : "Disabled"}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteRule(rule.id, rule.name)}
                            className="p-1 text-muted hover:text-rose-400 transition-colors rounded hover:bg-surface"
                            title="Delete rule"
                          >
                            <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === "simulator" && (
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-surface/40 border border-border space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-primary">
                    Live Autopilot Rule Simulator
                  </span>
                  <span className="text-[10px] font-mono text-muted">
                    Deterministic zero-cost dry-run
                  </span>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Sample Viewer Comment</label>
                  <textarea
                    rows={2}
                    value={simComment}
                    onChange={(e) => setSimComment(e.target.value)}
                    className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus resize-none font-sans"
                  />
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Classified Category</label>
                    <select
                      value={simCategory}
                      onChange={(e) => setSimCategory(e.target.value)}
                      className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary focus:outline-none focus:border-border-focus font-mono"
                    >
                      {CATEGORY_CHOICES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">
                      Classifier Conf: {(simConfidence * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.30"
                      max="1.0"
                      step="0.05"
                      value={simConfidence}
                      onChange={(e) => setSimConfidence(Number(e.target.value))}
                      className="w-full accent-primary"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">
                      Faithfulness: {(simFaithfulness * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.40"
                      max="1.0"
                      step="0.05"
                      value={simFaithfulness}
                      onChange={(e) => setSimFaithfulness(Number(e.target.value))}
                      className="w-full accent-primary"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-muted">Transcript Citation</label>
                    <button
                      type="button"
                      onClick={() => setSimCitations(!simCitations)}
                      className={`w-full py-2 px-2.5 rounded-md text-xs font-mono border transition-all text-center ${
                        simCitations
                          ? "bg-surface-active text-primary border-border-strong font-medium"
                          : "bg-surface text-muted border-border"
                      }`}
                    >
                      {simCitations ? "[03:20] Present" : "Missing Citation"}
                    </button>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={handleRunSimulator}
                    disabled={simulating}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all shadow-subtle disabled:opacity-50"
                  >
                    <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>{simulating ? "Simulating..." : "Evaluate Active Rules"}</span>
                  </button>
                </div>
              </div>

              {/* Simulator Output Result */}
              {simResult && (
                <div className="p-4 rounded-lg bg-surface/50 border border-border space-y-3 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-muted font-mono">Routing Decision:</span>
                      <span
                        className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                          simResult.action === "AUTO"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : simResult.action === "DRAFT"
                            ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                            : "bg-amber-500/10 text-amber-300 border-amber-500/20"
                        }`}
                      >
                        {simResult.action}
                      </span>
                    </div>

                    <div className="text-[11px] font-mono text-muted">
                      Matched Rule:{" "}
                      <span className="text-primary font-medium">
                        {simResult.matched_rule_name || "Baseline Safety Fallback"}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-secondary leading-relaxed font-sans bg-surface p-3 rounded-md border border-border">
                    <span className="text-[10px] font-mono uppercase tracking-widest text-muted block mb-1">
                      Reasoning Trace
                    </span>
                    {simResult.reason}
                  </p>

                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1 text-muted">
                    <div className="flex items-center gap-1.5">
                      <Check className={`w-3.5 h-3.5 ${simResult.can_auto_publish ? "text-emerald-400" : "text-muted"}`} />
                      <span>Can Auto-Publish: {simResult.can_auto_publish ? "Yes" : "No"}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className={`w-3.5 h-3.5 ${simResult.requires_human_approval ? "text-amber-400" : "text-muted"}`} />
                      <span>Requires Human Approval: {simResult.requires_human_approval ? "Yes" : "No"}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-border bg-subtle/80 flex items-center justify-between sticky bottom-0 z-10">
          <span className="text-xs text-muted">
            Rules execute deterministically in Python prior to human queue ingestion
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs text-secondary hover:text-primary bg-surface hover:bg-surface-hover border border-border rounded-md transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
