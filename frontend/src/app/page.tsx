"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { StatsBar } from "@/components/StatsBar";
import { QueueTable } from "@/components/QueueTable";
import { DetailDrawer } from "@/components/DetailDrawer";
import { CommandPalette } from "@/components/CommandPalette";
import { UploadModal } from "@/components/UploadModal";
import { AutopilotModal } from "@/components/AutopilotModal";
import { PersonaModal } from "@/components/PersonaModal";
import {
  CommentQueueItem,
  CommentDetailResponse,
  StatsResponse,
  VideoListSummary,
} from "@/types";

const API_BASE = "http://127.0.0.1:8000/api";

export default function DashboardPage() {
  const [lists, setLists] = useState<VideoListSummary[]>([]);
  const [selectedListId, setSelectedListId] = useState<number | null>(null);

  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [comments, setComments] = useState<CommentQueueItem[]>([]);
  const [selectedComment, setSelectedComment] = useState<CommentDetailResponse | null>(null);
  const [activeFilter, setActiveFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isAutopilotModalOpen, setIsAutopilotModalOpen] = useState(false);
  const [isPersonaModalOpen, setIsPersonaModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const fetchLists = async () => {
    try {
      const res = await fetch(`${API_BASE}/lists`);
      if (res.ok) {
        const data: VideoListSummary[] = await res.json();
        setLists(data);
      }
    } catch (err) {
      console.error("Error fetching lists:", err);
    }
  };

  const fetchData = async (listIdOverride?: number | null) => {
    setLoading(true);
    const targetListId = listIdOverride !== undefined ? listIdOverride : selectedListId;
    const listQuery = targetListId ? `list_id=${targetListId}` : "";

    try {
      await fetchLists();

      const statsUrl = listQuery ? `${API_BASE}/stats?${listQuery}` : `${API_BASE}/stats`;
      const statsRes = await fetch(statsUrl);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      const queueUrl = listQuery
        ? `${API_BASE}/queue?limit=100&${listQuery}`
        : `${API_BASE}/queue?limit=100`;
      const queueRes = await fetch(queueUrl);
      if (queueRes.ok) {
        const queueData = await queueRes.json();
        setComments(queueData);
      }
    } catch (err) {
      console.error("Error fetching triage data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Global hotkey for Command Palette (Cmd/Ctrl + K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSelectList = (id: number | null) => {
    setSelectedListId(id);
    fetchData(id);
  };

  const handleSelectComment = async (item: CommentQueueItem) => {
    try {
      const res = await fetch(`${API_BASE}/comments/${item.id}`);
      if (res.ok) {
        const detailData = await res.json();
        setSelectedComment(detailData);
      } else {
        setSelectedComment(item as unknown as CommentDetailResponse);
      }
    } catch {
      setSelectedComment(item as unknown as CommentDetailResponse);
    }
  };

  const handleApprove = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/comments/${id}/approve`, {
        method: "POST",
      });
      if (res.ok) {
        showToast("Draft approved and recorded.");
        await fetchData();
      }
    } catch (err) {
      console.error("Approve failed:", err);
    }
  };

  const handleEdit = async (id: number, text: string) => {
    try {
      const res = await fetch(`${API_BASE}/comments/${id}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ final_text: text }),
      });
      if (res.ok) {
        showToast("Edited response saved and approved.");
        await fetchData();
      }
    } catch (err) {
      console.error("Edit failed:", err);
    }
  };

  const handleReject = async (id: number, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/comments/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (res.ok) {
        showToast("Comment rejected and archived.");
        await fetchData();
      }
    } catch (err) {
      console.error("Reject failed:", err);
    }
  };

  const handleBulkApprove = async (ids: number[]) => {
    let count = 0;
    for (const id of ids) {
      try {
        const res = await fetch(`${API_BASE}/comments/${id}/approve`, { method: "POST" });
        if (res.ok) count++;
      } catch (err) {
        console.error("Bulk approve error:", err);
      }
    }
    showToast(`Approved ${count} drafts.`);
    await fetchData();
  };

  const handleBulkReject = async (ids: number[]) => {
    let count = 0;
    for (const id of ids) {
      try {
        const res = await fetch(`${API_BASE}/comments/${id}/reject`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "Bulk rejected by creator" }),
        });
        if (res.ok) count++;
      } catch (err) {
        console.error("Bulk reject error:", err);
      }
    }
    showToast(`Rejected ${count} comments.`);
    await fetchData();
  };

  const handleRunTriage = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/triage/run?limit=50`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`Triage executed: ${data.processed_count} comments processed.`);
        await fetchData();
      }
    } catch (err) {
      console.error("Run triage failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const selectedListObj = lists.find((l) => l.id === selectedListId);

  return (
    <div className="min-h-screen bg-canvas flex text-primary">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-surface border border-border-strong text-primary text-xs px-3.5 py-2.5 rounded-lg shadow-elevated font-mono flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Slim Collapsible Sidebar */}
      <Sidebar
        lists={lists}
        selectedListId={selectedListId}
        onSelectList={handleSelectList}
        activeFilter={activeFilter}
        setActiveFilter={setActiveFilter}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        onOpenAutopilotRules={() => setIsAutopilotModalOpen(true)}
        onOpenPersonaModal={() => setIsPersonaModalOpen(true)}
        shadowMode={stats?.shadow_mode ?? true}
        totalPending={stats?.pending_drafts ?? 0}
      />

      {/* Main App Layout */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <Header
          shadowMode={stats?.shadow_mode ?? true}
          lists={lists}
          selectedListId={selectedListId}
          onSelectList={handleSelectList}
          onRefresh={() => fetchData(selectedListId)}
          onRunTriage={handleRunTriage}
          onOpenUpload={() => setIsUploadModalOpen(true)}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          loading={loading}
        />

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto px-6 py-6 space-y-5 max-w-7xl w-full mx-auto">
          {/* Active List Scope Bar (if filtered) */}
          {selectedListObj && (
            <div className="px-3.5 py-2 rounded-lg bg-surface border border-border flex items-center justify-between text-xs animate-in fade-in">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted">
                  Workspace
                </span>
                <span className="text-muted">•</span>
                <span className="font-medium text-primary">{selectedListObj.title}</span>
                <span className="text-muted">•</span>
                <span className="text-secondary font-mono text-[11px] tabular-nums">
                  {selectedListObj.total_comments} comments
                </span>
                {selectedListObj.has_reference_doc && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.2 rounded">
                    Guide Active
                  </span>
                )}
              </div>
              <button
                onClick={() => handleSelectList(null)}
                className="text-xs font-mono text-muted hover:text-primary transition-colors"
              >
                Show All Workspaces
              </button>
            </div>
          )}

          {/* Compact Editorial Stat Strip */}
          <StatsBar stats={stats} />

          {/* Scannable Queue Table with Bulk Action Bar & Keyboard Navigation */}
          <QueueTable
            comments={comments}
            onSelectComment={handleSelectComment}
            activeFilter={activeFilter}
            setActiveFilter={setActiveFilter}
            onBulkApprove={handleBulkApprove}
            onBulkReject={handleBulkReject}
          />
        </main>
      </div>

      {/* Review Drawer (Spring slide-in) */}
      <DetailDrawer
        comment={selectedComment}
        onClose={() => setSelectedComment(null)}
        onApprove={handleApprove}
        onEdit={handleEdit}
        onReject={handleReject}
      />

      {/* Quick Command Palette (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        comments={comments}
        lists={lists}
        onSelectComment={handleSelectComment}
        onSelectList={handleSelectList}
        onRunTriage={handleRunTriage}
        onOpenUpload={() => setIsUploadModalOpen(true)}
        onOpenAutopilotRules={() => setIsAutopilotModalOpen(true)}
        onOpenPersonaModal={() => setIsPersonaModalOpen(true)}
      />

      {/* Document Upload & Preferences Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        initialListId={selectedListId}
        onUploadSuccess={(createdOrUpdatedListId) => {
          if (createdOrUpdatedListId) {
            setSelectedListId(createdOrUpdatedListId);
            fetchData(createdOrUpdatedListId);
          } else {
            fetchData();
          }
          showToast("Batch uploaded and real-time triage completed.");
        }}
      />

      {/* Granular Autopilot Rules Modal (Batch 2) */}
      <AutopilotModal
        isOpen={isAutopilotModalOpen}
        onClose={() => setIsAutopilotModalOpen(false)}
        shadowMode={stats?.shadow_mode ?? true}
        onRulesChanged={() => fetchData()}
      />

      {/* Creator Persona & Tone Cloner Modal (Phase 3) */}
      <PersonaModal
        isOpen={isPersonaModalOpen}
        onClose={() => setIsPersonaModalOpen(false)}
        onPersonaChanged={() => fetchData()}
      />
    </div>
  );
}
