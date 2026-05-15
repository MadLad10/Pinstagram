"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Stats {
  pending_reviews: number;
  pending_posts: number;
  open_reports: number;
  total_users: number;
  total_places: number;
  total_posts: number;
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-900">{value.toLocaleString()}</p>
    </div>
  );
}

function DashboardContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi.stats()
      .then(setStats)
      .catch(() => setError("Failed to load stats"));
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

        {error && <p className="text-red-500 mb-4">{error}</p>}

        {stats ? (
          <>
            <div className="mb-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Needs attention
              </h2>
              <div className="grid grid-cols-3 gap-4">
                <StatCard label="Pending reviews" value={stats.pending_reviews} />
                <StatCard label="Pending posts" value={stats.pending_posts} />
                <StatCard label="Open reports" value={stats.open_reports} />
              </div>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Totals
              </h2>
              <div className="grid grid-cols-3 gap-4">
                <StatCard label="Users" value={stats.total_users} />
                <StatCard label="Places" value={stats.total_places} />
                <StatCard label="Posts" value={stats.total_posts} />
              </div>
            </div>
          </>
        ) : (
          !error && (
            <div className="grid grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
                  <div className="h-3 bg-gray-200 rounded w-2/3 mb-3" />
                  <div className="h-8 bg-gray-200 rounded w-1/3" />
                </div>
              ))}
            </div>
          )
        )}
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}
