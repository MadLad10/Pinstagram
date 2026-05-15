"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Review {
  id: string;
  user_id: string;
  place_id: string;
  rating: number;
  body: string;
  created_at: string;
}

function ReviewsContent() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const load = () => {
    setLoading(true);
    adminApi.pendingReviews()
      .then((d) => setReviews(d.items))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const approve = async (id: string) => {
    await adminApi.approveReview(id);
    setReviews((prev) => prev.filter((r) => r.id !== id));
  };

  const reject = async () => {
    if (!rejectId) return;
    await adminApi.rejectReview(rejectId, rejectReason);
    setReviews((prev) => prev.filter((r) => r.id !== rejectId));
    setRejectId(null);
    setRejectReason("");
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Pending Reviews</h1>

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : reviews.length === 0 ? (
          <p className="text-gray-400">No pending reviews 🎉</p>
        ) : (
          <div className="space-y-4">
            {reviews.map((r) => (
              <div key={r.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-yellow-500 font-semibold">{"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}</span>
                      <span className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-sm text-gray-700">{r.body}</p>
                    <p className="text-xs text-gray-400 mt-2">User {r.user_id.slice(0, 8)} · Place {r.place_id.slice(0, 8)}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => approve(r.id)}
                      className="bg-green-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-green-700"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setRejectId(r.id)}
                      className="bg-red-100 text-red-600 text-sm px-3 py-1.5 rounded-lg hover:bg-red-200"
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
              <h2 className="font-semibold text-lg mb-3">Reject review</h2>
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

export default function ReviewsPage() {
  return (
    <AuthGuard>
      <ReviewsContent />
    </AuthGuard>
  );
}
