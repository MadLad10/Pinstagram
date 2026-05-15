"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Report {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  reason: string;
  notes: string | null;
  status: string;
  created_at: string;
}

function ReportsContent() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ id: string; action: string } | null>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    adminApi.reports()
      .then((d) => setReports(d.items))
      .finally(() => setLoading(false));
  }, []);

  const resolve = async () => {
    if (!modal) return;
    await adminApi.resolveReport(modal.id, modal.action, notes);
    setReports((prev) => prev.filter((r) => r.id !== modal.id));
    setModal(null);
    setNotes("");
  };

  const ACTION_LABELS: Record<string, string> = {
    dismiss: "Dismiss",
    warn: "Warn user",
    remove_content: "Remove content",
    ban_user: "Ban user",
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Reports</h1>

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : reports.length === 0 ? (
          <p className="text-gray-400">No open reports 🎉</p>
        ) : (
          <div className="space-y-4">
            {reports.map((r) => (
              <div key={r.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                        {r.target_type}
                      </span>
                      <span className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-sm font-medium text-gray-800">{r.reason}</p>
                    {r.notes && <p className="text-xs text-gray-500 mt-1">{r.notes}</p>}
                    <p className="text-xs text-gray-400 mt-2">
                      Reporter: {r.reporter_id.slice(0, 8)} · Target: {r.target_id.slice(0, 8)}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5 shrink-0">
                    {Object.entries(ACTION_LABELS).map(([action, label]) => (
                      <button
                        key={action}
                        onClick={() => setModal({ id: r.id, action })}
                        className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-700"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {modal && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
              <h2 className="font-semibold text-lg mb-1">{ACTION_LABELS[modal.action]}</h2>
              <p className="text-sm text-gray-500 mb-3">Resolving report {modal.id.slice(0, 8)}</p>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Internal notes (optional)"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 h-20 resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setModal(null)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={resolve}
                  className="px-4 py-2 text-sm bg-pink-600 text-white rounded-lg hover:bg-pink-700"
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <AuthGuard>
      <ReportsContent />
    </AuthGuard>
  );
}
