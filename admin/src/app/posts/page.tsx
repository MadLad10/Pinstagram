"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Post {
  id: string;
  author_name: string;
  place_name: string;
  media_url: string;
  caption: string | null;
  created_at: string;
}

function PostsContent() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    adminApi.pendingPosts()
      .then((d) => setPosts(d.items))
      .finally(() => setLoading(false));
  }, []);

  const approve = async (id: string) => {
    await adminApi.approvePost(id);
    setPosts((prev) => prev.filter((p) => p.id !== id));
  };

  const reject = async () => {
    if (!rejectId) return;
    await adminApi.rejectPost(rejectId, rejectReason);
    setPosts((prev) => prev.filter((p) => p.id !== rejectId));
    setRejectId(null);
    setRejectReason("");
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Pending Posts</h1>

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : posts.length === 0 ? (
          <p className="text-gray-400">No pending posts 🎉</p>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {posts.map((p) => (
              <div key={p.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={p.media_url}
                  alt=""
                  className="w-full h-48 object-cover bg-gray-100"
                />
                <div className="p-4">
                  <p className="font-medium text-sm mb-0.5">{p.author_name}</p>
                  <p className="text-xs text-gray-400 mb-2">{p.place_name} · {new Date(p.created_at).toLocaleDateString()}</p>
                  {p.caption && <p className="text-sm text-gray-600 mb-3 line-clamp-2">{p.caption}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={() => approve(p.id)}
                      className="flex-1 bg-green-600 text-white text-sm py-1.5 rounded-lg hover:bg-green-700"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setRejectId(p.id)}
                      className="flex-1 bg-red-100 text-red-600 text-sm py-1.5 rounded-lg hover:bg-red-200"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {rejectId && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
              <h2 className="font-semibold text-lg mb-3">Reject post</h2>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason (optional)"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 h-24 resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setRejectId(null)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={reject}
                  className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function PostsPage() {
  return (
    <AuthGuard>
      <PostsContent />
    </AuthGuard>
  );
}
