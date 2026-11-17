"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Sparkles,
  Check,
  Plus,
  Trash2,
  Edit2,
  RefreshCw,
  Loader2,
  Bot,
  User,
  Quote,
  Sliders,
  Play,
  ArrowRight,
  Database,
  CheckCircle2,
  MessageSquare,
  Wand2,
} from "lucide-react";
import { CreatorPersona, ExtractToneResult, PreviewDraftResult } from "@/types";

const API_BASE = "http://127.0.0.1:8000/api";

interface PersonaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPersonaChanged?: () => void;
}

export const PersonaModal: React.FC<PersonaModalProps> = ({
  isOpen,
  onClose,
  onPersonaChanged,
}) => {
  const [personas, setPersonas] = useState<CreatorPersona[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"presets" | "clone" | "sandbox">("presets");

  // Form State (New or Edit Persona)
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [greeting, setGreeting] = useState("Hey @author!");
  const [signOff, setSignOff] = useState("None");
  const [formality, setFormality] = useState<"casual" | "neutral" | "formal">("neutral");
  const [emojiDensity, setEmojiDensity] = useState<"none" | "minimal" | "expressive">("minimal");
  const [maxSentences, setMaxSentences] = useState(2);
  const [customNotes, setCustomNotes] = useState("");

  // Tone Extraction State
  const [sampleRepliesText, setSampleRepliesText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionResult, setExtractionResult] = useState<ExtractToneResult | null>(null);

  // Sandbox State
  const [testComment, setTestComment] = useState("Where do we download Docker for Windows?");
  const [testAuthor, setTestAuthor] = useState("Alex");
  const [selectedPersonaId, setSelectedPersonaId] = useState<number | null>(null);
  const [isDraftingPreview, setIsDraftingPreview] = useState(false);
  const [previewResult, setPreviewResult] = useState<PreviewDraftResult | null>(null);

  const fetchPersonas = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/personas`);
      if (res.ok) {
        const data: CreatorPersona[] = await res.json();
        setPersonas(data);
        const active = data.find((p) => p.is_active);
        if (active && selectedPersonaId === null) {
          setSelectedPersonaId(active.id);
        }
      }
    } catch (err) {
      console.error("Failed to load creator personas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchPersonas();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleActivate = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/personas/${id}/activate`, { method: "PUT" });
      if (res.ok) {
        await fetchPersonas();
        if (onPersonaChanged) onPersonaChanged();
      }
    } catch (err) {
      console.error("Failed to activate persona:", err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this persona?")) return;
    try {
      const res = await fetch(`${API_BASE}/personas/${id}`, { method: "DELETE" });
      if (res.ok) {
        await fetchPersonas();
        if (onPersonaChanged) onPersonaChanged();
      }
    } catch (err) {
      console.error("Failed to delete persona:", err);
    }
  };

  const handleSavePersona = async () => {
    if (!name.trim()) return;

    const payload = {
      name,
      description,
      greeting_pattern: greeting,
      sign_off_pattern: signOff,
      formality,
      emoji_density: emojiDensity,
      max_sentences: maxSentences,
      custom_voice_notes: customNotes,
      sample_pairs: [],
      is_active: false,
    };

    try {
      let res;
      if (editingId) {
        res = await fetch(`${API_BASE}/personas/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(`${API_BASE}/personas`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      if (res.ok) {
        setIsCreating(false);
        setEditingId(null);
        resetForm();
        await fetchPersonas();
        if (onPersonaChanged) onPersonaChanged();
      }
    } catch (err) {
      console.error("Failed to save persona:", err);
    }
  };

  const handleStartEdit = (p: CreatorPersona) => {
    setEditingId(p.id);
    setName(p.name);
    setDescription(p.description);
    setGreeting(p.greeting_pattern);
    setSignOff(p.sign_off_pattern);
    setFormality(p.formality);
    setEmojiDensity(p.emoji_density);
    setMaxSentences(p.max_sentences);
    setCustomNotes(p.custom_voice_notes);
    setIsCreating(true);
  };

  const resetForm = () => {
    setName("");
    setDescription("");
    setGreeting("Hey @author!");
    setSignOff("None");
    setFormality("neutral");
    setEmojiDensity("minimal");
    setMaxSentences(2);
    setCustomNotes("");
  };

  const handleExtractFromText = async () => {
    if (!sampleRepliesText.trim()) return;
    const lines = sampleRepliesText.split("\n").filter((l) => l.trim().length > 0);
    setIsExtracting(true);
    try {
      const res = await fetch(`${API_BASE}/personas/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_replies: lines }),
      });
      if (res.ok) {
        const data: ExtractToneResult = await res.json();
        setExtractionResult(data);
      }
    } catch (err) {
      console.error("Failed to extract tone:", err);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExtractFromDB = async () => {
    setIsExtracting(true);
    try {
      const res = await fetch(`${API_BASE}/personas/extract-from-db`, {
        method: "POST",
      });
      if (res.ok) {
        const data: ExtractToneResult = await res.json();
        setExtractionResult(data);
      }
    } catch (err) {
      console.error("Failed to extract tone from database:", err);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleAdoptExtractedPersona = async () => {
    if (!extractionResult) return;
    setName(extractionResult.name);
    setDescription(extractionResult.description);
    setGreeting(extractionResult.greeting_pattern);
    setSignOff(extractionResult.sign_off_pattern);
    setFormality(extractionResult.formality);
    setEmojiDensity(extractionResult.emoji_density);
    setMaxSentences(extractionResult.max_sentences);
    setCustomNotes(extractionResult.custom_voice_notes);
    setIsCreating(true);
    setActiveTab("presets");
  };

  const handleRunPreviewDraft = async () => {
    if (!testComment.trim()) return;
    setIsDraftingPreview(true);
    try {
      const res = await fetch(`${API_BASE}/personas/preview-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comment_text: testComment,
          author: testAuthor,
          persona_id: selectedPersonaId,
        }),
      });
      if (res.ok) {
        const data: PreviewDraftResult = await res.json();
        setPreviewResult(data);
      }
    } catch (err) {
      console.error("Failed to run preview draft:", err);
    } finally {
      setIsDraftingPreview(false);
    }
  };

  const activePersona = personas.find((p) => p.is_active);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-surface-elevated border border-border-strong rounded-xl shadow-2xl flex flex-col overflow-hidden text-primary">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0 bg-subtle/50">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Sparkles className="w-4 h-4" strokeWidth={1.5} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold tracking-tight text-primary">
                  Creator Persona & Tone Cloner
                </h2>
                {activePersona && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Active: {activePersona.name}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted">
                Clone your authentic creator voice, greeting patterns, and style for grounded drafts.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted hover:text-primary hover:bg-surface-hover transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Tab Switcher: Linear Segmented Track */}
        <div className="px-6 pt-3 pb-2 border-b border-border bg-subtle/20 shrink-0">
          <div className="grid grid-cols-3 gap-1 bg-subtle p-1 rounded-lg border border-border">
            <button
              onClick={() => setActiveTab("presets")}
              className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeTab === "presets"
                  ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                  : "text-muted hover:text-secondary hover:bg-surface-hover/50"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span>Persona Presets ({personas.length})</span>
            </button>

            <button
              onClick={() => setActiveTab("clone")}
              className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeTab === "clone"
                  ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                  : "text-muted hover:text-secondary hover:bg-surface-hover/50"
              }`}
            >
              <Wand2 className="w-3.5 h-3.5 text-indigo-400" strokeWidth={1.5} />
              <span>Clone Tone from Past Replies</span>
            </button>

            <button
              onClick={() => setActiveTab("sandbox")}
              className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeTab === "sandbox"
                  ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                  : "text-muted hover:text-secondary hover:bg-surface-hover/50"
              }`}
            >
              <Play className="w-3.5 h-3.5 text-emerald-400" strokeWidth={1.5} />
              <span>Interactive Voice Sandbox</span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: Presets & Custom Configuration */}
          {activeTab === "presets" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-mono uppercase tracking-widest text-muted">
                    Channel Voice Presets
                  </h3>
                  <p className="text-[11px] text-secondary mt-0.5">
                    Click "Activate" to select which voice persona shapes drafted replies.
                  </p>
                </div>
                {!isCreating && (
                  <button
                    onClick={() => {
                      resetForm();
                      setEditingId(null);
                      setIsCreating(true);
                    }}
                    className="flex items-center gap-1 text-xs text-primary font-medium px-3 py-1.5 rounded-md bg-surface border border-border hover:border-border-strong transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>Create Custom Persona</span>
                  </button>
                )}
              </div>

              {/* Form Drawer / Accordion */}
              {isCreating && (
                <div className="p-4 rounded-lg bg-surface border border-border-strong space-y-4 animate-in fade-in duration-150">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <span className="text-xs font-medium text-primary">
                      {editingId ? "Edit Persona" : "Create New Persona"}
                    </span>
                    <button
                      onClick={() => setIsCreating(false)}
                      className="text-xs text-muted hover:text-primary"
                    >
                      Cancel
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Persona Name
                      </label>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Crisp Technical & Direct"
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary focus:outline-none focus:border-border-focus"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Description / Channel Vibe
                      </label>
                      <input
                        type="text"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="e.g. Friendly mentor tone for beginners"
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary focus:outline-none focus:border-border-focus"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Greeting Format
                      </label>
                      <input
                        type="text"
                        value={greeting}
                        onChange={(e) => setGreeting(e.target.value)}
                        placeholder="e.g. Hey @author! or None"
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary font-mono focus:outline-none focus:border-border-focus"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Sign-off Signature
                      </label>
                      <input
                        type="text"
                        value={signOff}
                        onChange={(e) => setSignOff(e.target.value)}
                        placeholder="e.g. Hope this helps! 🚀 or None"
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary font-mono focus:outline-none focus:border-border-focus"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Max Sentences ({maxSentences})
                      </label>
                      <input
                        type="range"
                        min="1"
                        max="4"
                        value={maxSentences}
                        onChange={(e) => setMaxSentences(Number(e.target.value))}
                        className="w-full mt-2"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Formality Level
                      </label>
                      <select
                        value={formality}
                        onChange={(e) => setFormality(e.target.value as any)}
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary font-mono focus:outline-none focus:border-border-focus"
                      >
                        <option value="casual">Casual (Relaxed, conversational)</option>
                        <option value="neutral">Neutral (Balanced, professional)</option>
                        <option value="formal">Formal (Direct engineering manual)</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                        Emoji Density
                      </label>
                      <select
                        value={emojiDensity}
                        onChange={(e) => setEmojiDensity(e.target.value as any)}
                        className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary font-mono focus:outline-none focus:border-border-focus"
                      >
                        <option value="none">None (0 emojis strictly)</option>
                        <option value="minimal">Minimal (Max 1 subtle emoji)</option>
                        <option value="expressive">Expressive (1-2 friendly emojis 🚀)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] font-mono uppercase text-muted block mb-1">
                      Custom Voice Notes & Guardrails
                    </label>
                    <textarea
                      rows={2}
                      value={customNotes}
                      onChange={(e) => setCustomNotes(e.target.value)}
                      placeholder="e.g. Always thank viewers for subscribing. If they hit a bug, reassure them that it is easy to fix."
                      className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus resize-none"
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      onClick={() => setIsCreating(false)}
                      className="px-3 py-1.5 text-xs text-muted hover:text-primary transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSavePersona}
                      disabled={!name.trim()}
                      className="px-4 py-1.5 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all disabled:opacity-40"
                    >
                      Save Persona
                    </button>
                  </div>
                </div>
              )}

              {/* Persona Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {personas.map((p) => {
                  return (
                    <div
                      key={p.id}
                      className={`p-4 rounded-lg border transition-all text-left flex flex-col justify-between ${
                        p.is_active
                          ? "bg-surface-active border-border-focus ring-1 ring-border-focus shadow-subtle"
                          : "bg-surface/40 border-border hover:border-border-strong"
                      }`}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-xs text-primary">{p.name}</span>
                            {p.is_active && (
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                Active Voice
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => handleStartEdit(p)}
                              className="p-1 text-muted hover:text-primary transition-colors"
                              title="Edit persona"
                            >
                              <Edit2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                            </button>
                            {personas.length > 1 && (
                              <button
                                onClick={() => handleDelete(p.id)}
                                className="p-1 text-muted hover:text-rose-400 transition-colors"
                                title="Delete persona"
                              >
                                <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                              </button>
                            )}
                          </div>
                        </div>

                        <p className="text-[11px] text-muted line-clamp-2 leading-relaxed">
                          {p.description || "Custom creator persona."}
                        </p>

                        {/* Chips */}
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border text-secondary">
                            Greeting: {p.greeting_pattern}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border text-secondary">
                            Sign-off: {p.sign_off_pattern}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border text-secondary">
                            Formality: {p.formality}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border text-secondary">
                            Emojis: {p.emoji_density}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border text-secondary">
                            Max {p.max_sentences} sent.
                          </span>
                        </div>
                      </div>

                      <div className="pt-4 border-t border-border mt-3 flex items-center justify-between">
                        <span className="text-[10px] text-muted font-mono">
                          {p.sample_pairs?.length || 0} few-shot pairs
                        </span>
                        {!p.is_active && (
                          <button
                            onClick={() => handleActivate(p.id)}
                            className="text-xs px-2.5 py-1 rounded bg-surface hover:bg-surface-hover text-secondary hover:text-primary border border-border font-medium transition-colors"
                          >
                            Activate This Voice
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: Tone Cloner from Past Replies */}
          {activeTab === "clone" && (
            <div className="space-y-6 animate-in fade-in duration-150">
              <div className="p-4 rounded-lg bg-surface/30 border border-border space-y-1.5">
                <h3 className="text-xs font-semibold text-primary flex items-center gap-2">
                  <Wand2 className="w-4 h-4 text-indigo-400" strokeWidth={1.5} />
                  <span>Automatic Persona Tone Cloner</span>
                </h3>
                <p className="text-[11px] text-muted leading-relaxed">
                  Provide samples of your real responses to YouTube comments. CommentIQ will mathematically extract your sentence brevity, greeting format, sign-off signature, emoji frequency, and formality level to create a matching digital clone.
                </p>
              </div>

              {/* Source Option A: Auto-extract from Database */}
              <div className="p-4 rounded-lg bg-surface/50 border border-border flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-primary block">
                    Extract Tone from Historical Approved Replies
                  </span>
                  <span className="text-[11px] text-muted">
                    Scans your approved and finalized replies in the CommnetIQ database.
                  </span>
                </div>
                <button
                  onClick={handleExtractFromDB}
                  disabled={isExtracting}
                  className="px-3.5 py-2 text-xs font-medium text-secondary hover:text-primary bg-surface hover:bg-surface-hover border border-border rounded-md transition-all flex items-center gap-1.5 shrink-0"
                >
                  {isExtracting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Database className="w-3.5 h-3.5 text-indigo-400" strokeWidth={1.5} />
                  )}
                  <span>Auto-Clone from Database</span>
                </button>
              </div>

              {/* Source Option B: Manual Pastes */}
              <div className="space-y-2">
                <label className="text-[10px] font-mono uppercase tracking-widest text-muted block">
                  Or Paste 3 to 10 Past Comment Replies (One per line)
                </label>
                <textarea
                  rows={5}
                  value={sampleRepliesText}
                  onChange={(e) => setSampleRepliesText(e.target.value)}
                  placeholder="Hey @user! Thanks for watching, check [02:15] for the code! Hope this helps! 🚀&#10;Hey @user! Glad you liked the explanation, drop any questions below!&#10;Hey @user! Python 3.12 works great as shown at [05:40]."
                  className="w-full text-xs font-mono rounded-md bg-surface border border-border hover:border-border-strong focus:border-border-focus p-3 text-primary placeholder:text-muted focus:outline-none resize-none leading-relaxed"
                />
                <div className="flex justify-end">
                  <button
                    onClick={handleExtractFromText}
                    disabled={isExtracting || !sampleRepliesText.trim()}
                    className="px-4 py-2 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {isExtracting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
                    )}
                    <span>Analyze & Extract Voice DNA</span>
                  </button>
                </div>
              </div>

              {/* Extraction Results Preview */}
              {extractionResult && (
                <div className="p-4 rounded-lg bg-surface border border-border-focus space-y-4 animate-in fade-in">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span className="text-xs font-medium text-primary">
                        Extracted Tone Fingerprint ({extractionResult.sample_count} samples analyzed)
                      </span>
                    </div>
                    <button
                      onClick={handleAdoptExtractedPersona}
                      className="px-3 py-1.5 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all flex items-center gap-1.5"
                    >
                      <span>Adopt as New Persona</span>
                      <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                  </div>

                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="p-2.5 rounded-md bg-subtle border border-border">
                      <span className="text-[10px] font-mono uppercase text-muted block">Greeting</span>
                      <span className="text-xs font-mono font-medium text-primary mt-1 block">
                        {extractionResult.greeting_pattern}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-md bg-subtle border border-border">
                      <span className="text-[10px] font-mono uppercase text-muted block">Sign-off</span>
                      <span className="text-xs font-mono font-medium text-primary mt-1 block truncate">
                        {extractionResult.sign_off_pattern}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-md bg-subtle border border-border">
                      <span className="text-[10px] font-mono uppercase text-muted block">Formality</span>
                      <span className="text-xs font-mono font-medium text-primary mt-1 block capitalize">
                        {extractionResult.formality}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-md bg-subtle border border-border">
                      <span className="text-[10px] font-mono uppercase text-muted block">Emoji Usage</span>
                      <span className="text-xs font-mono font-medium text-primary mt-1 block capitalize">
                        {extractionResult.emoji_density}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-secondary leading-relaxed bg-subtle/50 p-2.5 rounded border border-border">
                    {extractionResult.description}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Interactive Sandbox */}
          {activeTab === "sandbox" && (
            <div className="space-y-6 animate-in fade-in duration-150">
              <div className="p-4 rounded-lg bg-surface/30 border border-border space-y-1.5">
                <h3 className="text-xs font-semibold text-primary flex items-center gap-2">
                  <Play className="w-4 h-4 text-emerald-400" strokeWidth={1.5} />
                  <span>Test-Drive Persona Grounded Drafting</span>
                </h3>
                <p className="text-[11px] text-muted leading-relaxed">
                  Type a sample viewer question to preview how the active or selected persona phrases a grounded answer using citations ([MM:SS]).
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 space-y-2">
                  <label className="text-[10px] font-mono uppercase tracking-widest text-muted block">
                    Sample Viewer Question
                  </label>
                  <input
                    type="text"
                    value={testComment}
                    onChange={(e) => setTestComment(e.target.value)}
                    placeholder="e.g. How do I install Docker on Windows?"
                    className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary focus:outline-none focus:border-border-focus"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-mono uppercase tracking-widest text-muted block">
                    Viewer Author Name
                  </label>
                  <input
                    type="text"
                    value={testAuthor}
                    onChange={(e) => setTestAuthor(e.target.value)}
                    placeholder="e.g. Alex"
                    className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary focus:outline-none focus:border-border-focus font-mono"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted">Test with Persona:</span>
                  <select
                    value={selectedPersonaId || ""}
                    onChange={(e) => setSelectedPersonaId(Number(e.target.value))}
                    className="text-xs bg-surface border border-border hover:border-border-strong rounded-md px-2.5 py-1.5 text-primary font-medium focus:outline-none cursor-pointer"
                  >
                    {personas.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} {p.is_active ? "(Active)" : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleRunPreviewDraft}
                  disabled={isDraftingPreview || !testComment.trim()}
                  className="px-4 py-2 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all flex items-center gap-1.5 disabled:opacity-40"
                >
                  {isDraftingPreview ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 text-canvas fill-canvas" />
                  )}
                  <span>Generate Test Draft</span>
                </button>
              </div>

              {/* Preview Result Card */}
              {previewResult && (
                <div className="p-4 rounded-lg bg-surface border border-border-strong space-y-3 animate-in fade-in">
                  <div className="flex items-center justify-between border-b border-border pb-2.5">
                    <span className="text-xs font-mono uppercase tracking-widest text-secondary flex items-center gap-1.5">
                      <Bot className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Draft Output ({previewResult.persona_name})</span>
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                      Grounded [MM:SS] Citation Active
                    </span>
                  </div>

                  <div className="p-3.5 rounded-md bg-subtle border border-border text-xs leading-relaxed text-primary font-sans">
                    {previewResult.draft_text}
                  </div>

                  <div className="flex items-center gap-3 text-[11px] text-muted font-mono">
                    <span>Greeting: {previewResult.greeting_used}</span>
                    <span>•</span>
                    <span>Sign-off: {previewResult.sign_off_used}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border bg-subtle/80 flex items-center justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-secondary hover:text-primary transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
