"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

interface Place {
  id: string;
  name: string;
  category: string;
  area: string;
  avg_rating: number;
  review_count: number;
  is_featured: boolean;
}

function PlacesContent() {
  const [places, setPlaces] = useState<Place[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.places()
      .then((d) => setPlaces(d.items))
      .finally(() => setLoading(false));
  }, []);

  const toggleFeature = async (p: Place) => {
    if (p.is_featured) {
      await adminApi.unfeaturePlace(p.id);
    } else {
      await adminApi.featurePlace(p.id);
    }
    setPlaces((prev) =>
      prev.map((pl) => pl.id === p.id ? { ...pl, is_featured: !pl.is_featured } : pl)
    );
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-bold mb-6">Places</h1>

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Category</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Area</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Rating</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Reviews</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Featured</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {places.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{p.name}</td>
                    <td className="px-4 py-3 text-gray-500 capitalize">{p.category}</td>
                    <td className="px-4 py-3 text-gray-500">{p.area}</td>
                    <td className="px-4 py-3">
                      {p.avg_rating > 0
                        ? <span className="text-yellow-600 font-medium">★ {p.avg_rating.toFixed(1)}</span>
                        : <span className="text-gray-300">–</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-gray-500">{p.review_count}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleFeature(p)}
                        className={`text-xs px-3 py-1 rounded-full font-medium transition-colors ${
                          p.is_featured
                            ? "bg-pink-100 text-pink-700 hover:bg-pink-200"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {p.is_featured ? "Featured" : "Feature"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

export default function PlacesPage() {
  return (
    <AuthGuard>
      <PlacesContent />
    </AuthGuard>
  );
}
