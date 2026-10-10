"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Entry {
  id: string;
  admin_name: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

function AuditContent() {
  const [items, setItems] = useState<Entry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = (after?: string) => {
    setLoading(true);
    adminApi
      .auditLog(after)
      .then((d) => {
        setItems((prev) => (after ? [...prev, ...d.items] : d.items));
        setCursor(d.next_cursor);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Audit log</h1>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["When", "Admin", "Action", "Target", "Details"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium text-gray-600">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{e.admin_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{e.action}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {e.target_type ?? "—"}{" "}
                    {e.target_id && <code className="text-xs">{e.target_id.slice(0, 8)}</code>}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {e.metadata ? JSON.stringify(e.metadata) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && items.length === 0 && (
            <p className="text-gray-400 p-6">No admin actions yet.</p>
          )}
        </div>
        {cursor && (
          <button
            onClick={() => load(cursor)}
            disabled={loading}
            className="mt-4 text-sm text-pink-600 hover:underline"
          >
            Load more
          </button>
        )}
      </main>
    </div>
  );
}

export default function AuditPage() {
  return (
    <AuthGuard>
      <AuditContent />
    </AuthGuard>
  );
}
