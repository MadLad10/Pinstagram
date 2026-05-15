"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  is_banned: boolean;
  created_at: string;
  post_count: number;
  follower_count: number;
}

function UsersContent() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [banModal, setBanModal] = useState<{ id: string; name: string } | null>(null);
  const [banReason, setBanReason] = useState("");

  const load = (q?: string) => {
    setLoading(true);
    adminApi.users(undefined, q)
      .then((d) => setUsers(d.items))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleBan = async () => {
    if (!banModal) return;
    await adminApi.banUser(banModal.id, banReason);
    setUsers((prev) => prev.map((u) => u.id === banModal.id ? { ...u, is_banned: true } : u));
    setBanModal(null);
    setBanReason("");
  };

  const handleUnban = async (id: string) => {
    await adminApi.unbanUser(id);
    setUsers((prev) => prev.map((u) => u.id === id ? { ...u, is_banned: false } : u));
  };

  const handlePromote = async (id: string) => {
    await adminApi.promoteAdmin(id);
    setUsers((prev) => prev.map((u) => u.id === id ? { ...u, role: "admin" } : u));
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Users</h1>

        <div className="flex gap-3 mb-6">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(search)}
            placeholder="Search by name or email…"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm max-w-sm"
          />
          <button
            onClick={() => load(search)}
            className="bg-pink-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-pink-700"
          >
            Search
          </button>
        </div>

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Email</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Role</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Posts</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{u.name}</td>
                    <td className="px-4 py-3 text-gray-500">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${
                        u.role === "admin" ? "bg-purple-100 text-purple-700"
                        : u.role === "moderator" ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-600"
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{u.post_count}</td>
                    <td className="px-4 py-3">
                      {u.is_banned
                        ? <span className="text-xs text-red-600 font-medium">Banned</span>
                        : <span className="text-xs text-green-600 font-medium">Active</span>
                      }
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {u.is_banned ? (
                          <button
                            onClick={() => handleUnban(u.id)}
                            className="text-xs text-green-600 hover:underline"
                          >
                            Unban
                          </button>
                        ) : (
                          <button
                            onClick={() => setBanModal({ id: u.id, name: u.name })}
                            className="text-xs text-red-500 hover:underline"
                          >
                            Ban
                          </button>
                        )}
                        {u.role === "user" && (
                          <button
                            onClick={() => handlePromote(u.id)}
                            className="text-xs text-purple-600 hover:underline"
                          >
                            Promote
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {banModal && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
              <h2 className="font-semibold text-lg mb-1">Ban {banModal.name}?</h2>
              <p className="text-sm text-gray-500 mb-3">This will immediately block all access.</p>
              <input
                value={banReason}
                onChange={(e) => setBanReason(e.target.value)}
                placeholder="Reason"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setBanModal(null)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBan}
                  className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
                >
                  Ban user
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function UsersPage() {
  return (
    <AuthGuard>
      <UsersContent />
    </AuthGuard>
  );
}
