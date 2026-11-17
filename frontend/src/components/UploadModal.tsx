"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Upload,
  FileText,
  Sliders,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  BookOpen,
  ArrowRight,
  FolderPlus,
  ListFilter,
  Check,
  Youtube,
  Link,
  Loader2,
} from "lucide-react";
import {
  UserPreferences,
  CategoryPreference,
  UploadBatchResponse,
  VideoListSummary,
  TranscribeUrlResponse,
} from "@/types";

const API_BASE = "http://127.0.0.1:8000/api";

const DEFAULT_CATEGORIES: CategoryPreference[] = [
  { name: "question", description: "Technical questions or queries about the topic", action: "DRAFT" },
  { name: "praise", description: "Positive feedback, appreciation, and compliments", action: "AUTO" },
  { name: "complaint", description: "Audio/video issues, bugs, criticisms", action: "ESCALATE" },
  { name: "feature_request", description: "Suggestions, proposals, roadmap ideas", action: "DRAFT" },
  { name: "business_collab", description: "Sponsorships, partnerships, podcast invites", action: "ESCALATE" },
  { name: "refund_billing", description: "Refund or billing inquiries", action: "ESCALATE" },
  { name: "spam", description: "Scams, crypto links, promotional bots", action: "ESCALATE" },
  { name: "sensitive", description: "Crisis triggers, self-harm, legal threats", action: "ESCALATE" },
];

const TONE_OPTIONS = [
  { id: "helpful_concise", label: "Helpful & Concise", desc: "Short, direct, grounded answers" },
  { id: "warm_empathetic", label: "Warm & Empathetic", desc: "Friendly, encouraging, community-focused" },
  { id: "formal_professional", label: "Formal & Professional", desc: "Polite, objective, corporate tone" },
  { id: "technical_direct", label: "Technical & Direct", desc: "Precise code references & error fixes" },
];

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (createdOrUpdatedListId?: number) => void;
  initialListId?: number | null;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  initialListId,
}) => {
  // Lists State
  const [lists, setLists] = useState<VideoListSummary[]>([]);
  const [listMode, setListMode] = useState<"existing" | "new">("existing");
  const [selectedListId, setSelectedListId] = useState<number | "">("");
  const [newListName, setNewListName] = useState("");
  const [newListDesc, setNewListDesc] = useState("");

  // Files & Video Reference State
  const [commentsFile, setCommentsFile] = useState<File | null>(null);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referenceMode, setReferenceMode] = useState<"url" | "file">("url");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [isTranscribingUrl, setIsTranscribingUrl] = useState(false);
  const [urlTranscriptionResult, setUrlTranscriptionResult] = useState<TranscribeUrlResponse | null>(null);

  // Preferences State
  const [categories, setCategories] = useState<CategoryPreference[]>(DEFAULT_CATEGORIES);
  const [tone, setTone] = useState("helpful_concise");
  const [customInstructions, setCustomInstructions] = useState("");

  // New Category Creation State
  const [newCatName, setNewCatName] = useState("");
  const [newCatDesc, setNewCatDesc] = useState("");
  const [newCatAction, setNewCatAction] = useState<"AUTO" | "DRAFT" | "ESCALATE">("DRAFT");
  const [showAddCat, setShowAddCat] = useState(false);

  // Active Tab: "upload" | "preferences"
  const [activeTab, setActiveTab] = useState<"upload" | "preferences">("upload");

  // Processing State
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<UploadBatchResponse | null>(null);

  useEffect(() => {
    const fetchListsAndPrefs = async () => {
      try {
        // Fetch lists
        const listsRes = await fetch(`${API_BASE}/lists`);
        if (listsRes.ok) {
          const listsData: VideoListSummary[] = await listsRes.json();
          setLists(listsData);
          if (initialListId && listsData.some((l) => l.id === initialListId)) {
            setSelectedListId(initialListId);
            setListMode("existing");
          } else if (listsData.length > 0) {
            setSelectedListId(listsData[0].id);
            setListMode("existing");
          } else {
            setListMode("new");
          }
        }

        // Fetch stored preferences
        const prefsRes = await fetch(`${API_BASE}/preferences`);
        if (prefsRes.ok) {
          const prefsData: UserPreferences = await prefsRes.json();
          if (prefsData.categories && prefsData.categories.length > 0) {
            setCategories(prefsData.categories);
          }
          if (prefsData.tone) setTone(prefsData.tone);
          if (prefsData.custom_instructions) setCustomInstructions(prefsData.custom_instructions);
        }
      } catch {
        // Fallback to defaults
      }
    };

    if (isOpen) {
      fetchListsAndPrefs();
      setUploadError(null);
      setBatchResult(null);
      setCommentsFile(null);
      setReferenceFile(null);
      setYoutubeUrl("");
      setReferenceMode("url");
      setIsTranscribingUrl(false);
      setUrlTranscriptionResult(null);
    }
  }, [isOpen, initialListId]);

  if (!isOpen) return null;

  const currentSelectedList = lists.find((l) => l.id === selectedListId);

  const handleAddCategory = () => {
    if (!newCatName.trim()) return;
    const cleanName = newCatName.trim().toLowerCase().replace(/\s+/g, "_");
    if (categories.some((c) => c.name.toLowerCase() === cleanName)) {
      setUploadError(`Category '${cleanName}' already exists.`);
      return;
    }
    const updated = [
      ...categories,
      {
        name: cleanName,
        description: newCatDesc.trim() || `User defined category ${cleanName}`,
        action: newCatAction,
      },
    ];
    setCategories(updated);
    setNewCatName("");
    setNewCatDesc("");
    setNewCatAction("DRAFT");
    setShowAddCat(false);
    setUploadError(null);
  };

  const handleRemoveCategory = (name: string) => {
    setCategories(categories.filter((c) => c.name !== name));
  };

  const handleActionChange = (name: string, action: "AUTO" | "DRAFT" | "ESCALATE") => {
    setCategories(
      categories.map((c) => (c.name === name ? { ...c, action } : c))
    );
  };

  const handleTranscribeUrlOnly = async () => {
    if (!youtubeUrl.trim()) {
      setUploadError("Please provide a valid YouTube video URL or 11-character video ID.");
      return;
    }

    if (listMode === "existing" && !selectedListId) {
      setUploadError("Please select a target workspace list or switch to 'Create New List'.");
      return;
    }

    setIsTranscribingUrl(true);
    setUploadError(null);
    setUrlTranscriptionResult(null);

    try {
      const payload = {
        youtube_url: youtubeUrl.trim(),
        list_id: listMode === "existing" ? Number(selectedListId) : null,
        list_name: listMode === "new" ? (newListName.trim() || undefined) : undefined,
        list_description: listMode === "new" ? (newListDesc.trim() || undefined) : undefined,
      };

      const res = await fetch(`${API_BASE}/videos/transcribe-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Transcription failed with HTTP ${res.status}`);
      }

      const data: TranscribeUrlResponse = await res.json();
      setUrlTranscriptionResult(data);

      // Refresh list selector with the new/updated video list
      const listsRes = await fetch(`${API_BASE}/lists`);
      if (listsRes.ok) {
        const listsData: VideoListSummary[] = await listsRes.json();
        setLists(listsData);
        setSelectedListId(data.list_id);
        setListMode("existing");
      }
      onUploadSuccess(data.list_id);
    } catch (err: any) {
      console.error("URL transcription failed:", err);
      setUploadError(err.message || "Failed to transcribe YouTube video.");
    } finally {
      setIsTranscribingUrl(false);
    }
  };

  const handleSubmit = async () => {
    if (!commentsFile) {
      setUploadError("Please select a comments document (.pdf, .docx, .csv, .json).");
      return;
    }

    if (listMode === "new" && !newListName.trim()) {
      setUploadError("Please provide a name for the new list (e.g. Video 1: Masterclass).");
      return;
    }

    if (listMode === "existing" && !selectedListId) {
      setUploadError("Please choose an existing list or select 'Create New List'.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setBatchResult(null);

    const formData = new FormData();
    formData.append("comments_file", commentsFile);
    if (referenceMode === "file" && referenceFile) {
      formData.append("reference_file", referenceFile);
    } else if (referenceMode === "url" && youtubeUrl.trim()) {
      formData.append("youtube_url", youtubeUrl.trim());
    }

    if (listMode === "existing") {
      formData.append("list_id", String(selectedListId));
    } else {
      formData.append("list_name", newListName.trim());
      if (newListDesc.trim()) {
        formData.append("list_description", newListDesc.trim());
      }
    }

    const prefsPayload: UserPreferences = {
      categories,
      tone,
      custom_instructions: customInstructions,
    };
    formData.append("preferences_json", JSON.stringify(prefsPayload));

    try {
      const res = await fetch(`${API_BASE}/upload/batch`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed with HTTP ${res.status}`);
      }

      const data: UploadBatchResponse = await res.json();
      setBatchResult(data);
      onUploadSuccess(data.list_id || data.video_id);
    } catch (err: any) {
      console.error("Batch upload failed:", err);
      setUploadError(err.message || "An error occurred during upload and triage.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-canvas/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="relative w-full max-w-2xl bg-surface-elevated border border-border-strong rounded-xl shadow-floating overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border bg-subtle/80 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-md bg-surface-active border border-border-strong flex items-center justify-center shrink-0 text-primary">
              <Upload className="w-3.5 h-3.5" strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-primary tracking-tight">
                Document Upload & Real-Time Triage
              </h2>
              <p className="text-xs text-secondary mt-0.5">
                Organize comments into named video lists with Hybrid Search (BM25 + Dense) RAG
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-muted hover:text-primary hover:bg-surface-hover transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border bg-subtle/50 px-6 gap-2">
          <button
            onClick={() => setActiveTab("upload")}
            className={`py-2.5 px-3 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "upload"
                ? "border-primary text-primary font-medium"
                : "border-transparent text-muted hover:text-secondary"
            }`}
          >
            <FileText className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Destination & Files</span>
          </button>
          <button
            onClick={() => setActiveTab("preferences")}
            className={`py-2.5 px-3 text-xs font-medium border-b-2 transition-all flex items-center gap-2 ${
              activeTab === "preferences"
                ? "border-primary text-primary font-medium"
                : "border-transparent text-muted hover:text-secondary"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Triage Preferences ({categories.length} Categories)</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {uploadError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>{uploadError}</span>
            </div>
          )}

          {batchResult && (
            <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs space-y-3 animate-in fade-in">
              <div className="flex items-center gap-2 font-medium text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>
                  Triage Complete: {batchResult.total_parsed} comments ingested into "{batchResult.list_title || 'List'}"
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                {Object.entries(batchResult.categories_breakdown).map(([cat, count]) => (
                  <div key={cat} className="p-2 rounded bg-surface border border-border text-center">
                    <span className="text-[10px] text-muted uppercase block font-mono">{cat}</span>
                    <span className="text-sm font-semibold text-primary tabular-nums">{count}</span>
                  </div>
                ))}
              </div>
              {batchResult.reference_chunks_indexed > 0 && (
                <p className="text-[11px] text-emerald-400/80 font-mono">
                  Indexed {batchResult.reference_chunks_indexed} reference chunks using Hybrid Search (BM25 + Dense).
                </p>
              )}
            </div>
          )}

          {activeTab === "upload" && (
            <div className="space-y-4">
              {/* Destination List Selector */}
              <div className="p-4 rounded-lg bg-surface/40 border border-border space-y-3">
                <label className="text-[10px] font-mono uppercase tracking-widest text-muted flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <ListFilter className="w-3.5 h-3.5 text-secondary" strokeWidth={1.5} />
                    <span>Target List / Video Workspace</span>
                  </div>
                  <span className="normal-case tracking-normal text-[11px] text-muted">
                    Organize files by video or topic
                  </span>
                </label>

                {/* Mode Selector Toggle: Linear Segmented Track */}
                <div className="grid grid-cols-2 gap-1 bg-subtle p-1 rounded-lg border border-border">
                  <button
                    type="button"
                    onClick={() => setListMode("existing")}
                    disabled={lists.length === 0}
                    className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                      listMode === "existing"
                        ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                        : "text-muted hover:text-secondary hover:bg-surface-hover/50 disabled:opacity-30 disabled:cursor-not-allowed"
                    }`}
                  >
                    <Check className={`w-3.5 h-3.5 ${listMode === "existing" ? "opacity-100" : "opacity-0"}`} />
                    <span>Add to Existing List ({lists.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setListMode("new")}
                    className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                      listMode === "new"
                        ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                        : "text-muted hover:text-secondary hover:bg-surface-hover/50"
                    }`}
                  >
                    <FolderPlus className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>Create New List</span>
                  </button>
                </div>

                {/* Existing List Dropdown */}
                {listMode === "existing" && (
                  <div className="space-y-2 pt-1 animate-in fade-in duration-150">
                    <select
                      value={selectedListId}
                      onChange={(e) => setSelectedListId(Number(e.target.value))}
                      className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary focus:outline-none focus:border-border-focus font-sans cursor-pointer transition-colors"
                    >
                      {lists.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.title} ({l.total_comments} comments{l.has_reference_doc ? ", guide active" : ""})
                        </option>
                      ))}
                    </select>

                    {currentSelectedList && currentSelectedList.has_reference_doc && (
                      <p className="text-[11px] text-emerald-400/90 font-mono flex items-center gap-1.5">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>
                          Active reference guide ({currentSelectedList.reference_chunks_count} chunks) available. Leave blank to reuse.
                        </span>
                      </p>
                    )}
                  </div>
                )}

                {/* New List Form Inputs */}
                {listMode === "new" && (
                  <div className="space-y-2.5 pt-1 animate-in fade-in duration-150">
                    <input
                      type="text"
                      value={newListName}
                      onChange={(e) => setNewListName(e.target.value)}
                      placeholder="List / Video Name (e.g. Video 1: Python Masterclass)"
                      className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2.5 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus transition-colors"
                    />
                    <input
                      type="text"
                      value={newListDesc}
                      onChange={(e) => setNewListDesc(e.target.value)}
                      placeholder="Description / notes (optional)..."
                      className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus transition-colors"
                    />
                  </div>
                )}
              </div>

              {/* Primary Comments Document */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase tracking-widest text-muted flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-secondary" strokeWidth={1.5} />
                  <span>Comments Document (Required)</span>
                  <span className="text-[10px] text-faint font-normal lowercase tracking-normal">
                    — .pdf, .docx, .csv, .json, .txt
                  </span>
                </label>
                <div className="relative border border-dashed border-border-strong hover:border-border-focus rounded-lg p-5 text-center bg-surface/30 hover:bg-surface/60 transition-all">
                  <input
                    type="file"
                    accept=".pdf,.docx,.csv,.json,.txt"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setCommentsFile(e.target.files[0]);
                      }
                    }}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  {commentsFile ? (
                    <div className="flex items-center justify-center gap-2 text-primary font-medium text-xs">
                      <FileText className="w-4 h-4 text-accent" strokeWidth={1.5} />
                      <span>{commentsFile.name}</span>
                      <span className="text-[10px] text-muted font-mono tabular-nums">
                        ({(commentsFile.size / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <Upload className="w-5 h-5 mx-auto text-muted" strokeWidth={1.5} />
                      <p className="text-xs text-secondary font-medium">
                        Click or drag comments table document here
                      </p>
                      <p className="text-[11px] text-muted">
                        Supports PDF/DOCX tables with Author & Comment columns, CSV, JSON, or text lines
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Reference Knowledge Base (YouTube URL or Document File) */}
              <div className="space-y-3 p-4 rounded-lg bg-surface/40 border border-border">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-mono uppercase tracking-widest text-muted flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-secondary" strokeWidth={1.5} />
                    <span>Reference Knowledge Base (Optional for Grounded RAG)</span>
                  </label>
                  <span className="text-[11px] text-muted">
                    Auto-transcribe or upload manual
                  </span>
                </div>

                {/* Sub-tab Switcher: Linear Segmented Track */}
                <div className="grid grid-cols-2 gap-1 bg-subtle p-1 rounded-lg border border-border">
                  <button
                    type="button"
                    onClick={() => setReferenceMode("url")}
                    className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                      referenceMode === "url"
                        ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                        : "text-muted hover:text-secondary hover:bg-surface-hover/50"
                    }`}
                  >
                    <Youtube className="w-3.5 h-3.5 text-rose-400" strokeWidth={1.5} />
                    <span>YouTube Video URL (Instant)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setReferenceMode("file")}
                    className={`py-1.5 px-3 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${
                      referenceMode === "file"
                        ? "bg-surface-active text-primary border border-border-strong shadow-subtle"
                        : "text-muted hover:text-secondary hover:bg-surface-hover/50"
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 text-secondary" strokeWidth={1.5} />
                    <span>Upload Document File</span>
                  </button>
                </div>

                {/* Option 1: YouTube URL */}
                {referenceMode === "url" && (
                  <div className="space-y-2.5 pt-1 animate-in fade-in duration-150">
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
                          <Link className="w-3.5 h-3.5" strokeWidth={1.5} />
                        </div>
                        <input
                          type="text"
                          value={youtubeUrl}
                          onChange={(e) => setYoutubeUrl(e.target.value)}
                          placeholder="Paste YouTube Video URL (e.g. https://www.youtube.com/watch?v=... or 11-char ID)"
                          className="w-full text-xs bg-surface border border-border hover:border-border-strong rounded-md pl-8 pr-3 py-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus font-mono transition-colors"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleTranscribeUrlOnly}
                        disabled={isTranscribingUrl || !youtubeUrl.trim()}
                        className="px-3 py-2 bg-surface hover:bg-surface-hover disabled:opacity-40 text-secondary hover:text-primary border border-border rounded-md text-xs font-medium transition-all flex items-center gap-1.5 shrink-0"
                        title="Transcribe and index this video into the workspace immediately without uploading comments"
                      >
                        {isTranscribingUrl ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-muted" />
                            <span>Transcribing...</span>
                          </>
                        ) : (
                          <>
                            <Youtube className="w-3.5 h-3.5 text-rose-400" strokeWidth={1.5} />
                            <span>Transcribe URL Only</span>
                          </>
                        )}
                      </button>
                    </div>

                    <p className="text-[11px] text-muted leading-relaxed">
                      ⚡ <span className="text-secondary font-medium">Tier 1: Instant Captions ($0)</span>. If captions are missing, <span className="text-secondary font-medium">Tier 2: Groq Whisper</span> transcribes audio automatically. Formatted with <span className="font-mono text-secondary">[MM:SS]</span> timestamp citations.
                    </p>

                    {urlTranscriptionResult && (
                      <div className="p-3 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs space-y-1 animate-in fade-in">
                        <div className="flex items-center gap-1.5 font-medium text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Video Indexed: {urlTranscriptionResult.list_title}</span>
                        </div>
                        <p className="text-[11px] text-emerald-400/80 font-mono">
                          Method: {urlTranscriptionResult.source === "groq_whisper" ? "Groq Whisper Large-v3 (Audio Fallback)" : "Official YouTube Captions"} • {urlTranscriptionResult.chunks_indexed} chunks indexed for Hybrid Search.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Option 2: Upload File */}
                {referenceMode === "file" && (
                  <div className="relative border border-dashed border-border-strong hover:border-border-focus rounded-lg p-5 text-center bg-surface/30 hover:bg-surface/60 transition-all animate-in fade-in duration-150">
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt,.srt"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setReferenceFile(e.target.files[0]);
                        }
                      }}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    {referenceFile ? (
                      <div className="flex items-center justify-center gap-2 text-primary font-medium text-xs">
                        <BookOpen className="w-4 h-4 text-accent" strokeWidth={1.5} />
                        <span>{referenceFile.name}</span>
                        <span className="text-[10px] text-muted font-mono tabular-nums">
                          ({(referenceFile.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <BookOpen className="w-5 h-5 mx-auto text-muted" strokeWidth={1.5} />
                        <p className="text-xs text-secondary font-medium">
                          Upload video transcript, FAQ sheet, or documentation manual
                        </p>
                        <p className="text-[11px] text-muted">
                          Enables Hybrid Search (BM25 + Dense) with [Page X] or [Section X] citations
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Quick Summary of Active Tone & Categories */}
              <div className="p-3 rounded-lg bg-surface/30 border border-border text-xs flex items-center justify-between text-muted">
                <div className="flex items-center gap-2">
                  <span>Active Channel Tone:</span>
                  <span className="font-medium text-primary">
                    {TONE_OPTIONS.find((t) => t.id === tone)?.label || tone}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("preferences")}
                  className="text-xs text-secondary hover:text-primary flex items-center gap-1 font-medium transition-colors"
                >
                  <span>Customize Categories & Tone</span>
                  <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.5} />
                </button>
              </div>
            </div>
          )}

          {activeTab === "preferences" && (
            <div className="space-y-5">
              {/* Tone Selection */}
              <div className="space-y-2">
                <label className="text-[10px] font-mono uppercase tracking-widest text-muted block">
                  Channel Response Tone
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {TONE_OPTIONS.map((t) => {
                    const isSelected = tone === t.id;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setTone(t.id)}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          isSelected
                            ? "bg-surface-active border-border-focus text-primary ring-1 ring-border-focus shadow-subtle"
                            : "bg-surface/40 border-border text-secondary hover:border-border-strong"
                        }`}
                      >
                        <div className="text-xs font-medium text-primary">{t.label}</div>
                        <div className="text-[11px] text-muted mt-0.5">{t.desc}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Custom Freeform Instructions */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase tracking-widest text-muted flex items-center justify-between">
                  <span>Custom Freeform Instructions</span>
                  <span className="normal-case tracking-normal text-[11px] text-faint">
                    Injected into LLM classifier & drafter
                  </span>
                </label>
                <textarea
                  rows={2}
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                  placeholder="e.g. If anyone asks about discounts, mention code SAVE20. Keep all technical answers under 2 sentences."
                  className="w-full text-xs font-sans rounded-md bg-surface border border-border hover:border-border-strong focus:border-border-focus p-3 text-primary placeholder:text-muted focus:outline-none resize-none leading-relaxed transition-colors"
                />
              </div>

              {/* Categories & Actions Manager */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-widest text-muted block">
                      Triage Categories & Actions
                    </span>
                    <span className="text-[11px] text-secondary">
                      Choose whether each category triggers auto-publish, human drafting, or escalation.
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAddCat(!showAddCat)}
                    className="flex items-center gap-1 text-xs text-secondary hover:text-primary font-medium px-2.5 py-1 rounded-md bg-surface border border-border hover:border-border-strong transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>Add Category</span>
                  </button>
                </div>

                {showAddCat && (
                  <div className="p-3.5 rounded-lg bg-surface border border-border-strong space-y-2.5 animate-in fade-in">
                    <div className="text-xs font-medium text-primary">New Category Definition</div>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        value={newCatName}
                        onChange={(e) => setNewCatName(e.target.value)}
                        placeholder="Category Name (e.g. partnership)"
                        className="text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus"
                      />
                      <select
                        value={newCatAction}
                        onChange={(e) => setNewCatAction(e.target.value as any)}
                        className="text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary focus:outline-none focus:border-border-focus font-mono"
                      >
                        <option value="DRAFT">Action: DRAFT (Queue for Review)</option>
                        <option value="AUTO">Action: AUTO (Auto-Publish)</option>
                        <option value="ESCALATE">Action: ESCALATE (Flag to Human)</option>
                      </select>
                    </div>
                    <input
                      type="text"
                      value={newCatDesc}
                      onChange={(e) => setNewCatDesc(e.target.value)}
                      placeholder="Description / keywords for classifier..."
                      className="w-full text-xs bg-subtle border border-border hover:border-border-strong rounded-md p-2 text-primary placeholder:text-muted focus:outline-none focus:border-border-focus"
                    />
                    <div className="flex justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setShowAddCat(false)}
                        className="px-2.5 py-1 text-xs text-muted hover:text-secondary"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleAddCategory}
                        className="px-3 py-1 text-xs bg-primary text-canvas hover:bg-white rounded-md font-medium transition-colors"
                      >
                        Save Category
                      </button>
                    </div>
                  </div>
                )}

                <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                  {categories.map((cat) => (
                    <div
                      key={cat.name}
                      className="p-2.5 rounded-md bg-surface/40 border border-border flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-primary font-mono">
                            {cat.name}
                          </span>
                        </div>
                        <p className="text-[11px] text-muted truncate mt-0.5">
                          {cat.description}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <select
                          value={cat.action}
                          onChange={(e) => handleActionChange(cat.name, e.target.value as any)}
                          className={`text-[10px] font-mono px-2 py-0.5 rounded border focus:outline-none ${
                            cat.action === "AUTO"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                              : cat.action === "DRAFT"
                              ? "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                              : "bg-amber-500/10 text-amber-300 border-amber-500/20"
                          }`}
                        >
                          <option value="DRAFT">DRAFT</option>
                          <option value="AUTO">AUTO</option>
                          <option value="ESCALATE">ESCALATE</option>
                        </select>

                        <button
                          type="button"
                          onClick={() => handleRemoveCategory(cat.name)}
                          className="p-1 text-muted hover:text-rose-400 transition-colors"
                          title="Remove category"
                        >
                          <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border bg-subtle/80 flex items-center justify-between sticky bottom-0 z-10">
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-medium text-muted hover:text-primary transition-colors"
          >
            {batchResult ? "Close" : "Cancel"}
          </button>

          <div className="flex items-center gap-3">
            {batchResult ? (
              <button
                type="button"
                onClick={onClose}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-canvas bg-primary hover:bg-white rounded-md transition-all shadow-subtle"
              >
                <span>View Triaged Queue</span>
                <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={isUploading || !commentsFile}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-canvas bg-primary hover:bg-white active:bg-neutral-200 rounded-md transition-all shadow-subtle disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
              >
                {isUploading ? (
                  <>
                    <Sparkles className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                    <span>Real-Time Triaging...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
                    <span>Start Real-Time Triage</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
