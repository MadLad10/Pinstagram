"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import { adminApi } from "@/lib/api";

type Kind = "bus-stops" | "bus-routes";

interface Summary {
  bus_stops: number;
  bus_routes: number;
  train_stations: number;
  train_schedules: number;
  fares: number;
}

interface ImportError {
  line: number;
  error: string;
}

const FORMATS: Record<Kind, { title: string; header: string; example: string }> = {
  "bus-stops": {
    title: "Bus stops",
    header: "name,lat,lng,district",
    example: "Farmgate,23.7577,90.3897,Dhaka",
  },
  "bus-routes": {
    title: "Bus routes",
    header: "name,operator,typical_fare,typical_duration_min,stops",
    example: "Airport Road Express,BRTC,60,95,Abdullahpur|Airport|Banani|Mohakhali",
  },
};

function ImportCard({ kind, onDone }: { kind: Kind; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [errors, setErrors] = useState<ImportError[]>([]);
  const fmt = FORMATS[kind];

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    setErrors([]);
    try {
      const r = await adminApi.importTransport(kind, file);
      setResult(`Imported: ${r.created} created, ${r.updated} updated`);
      onDone();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (detail?.errors) setErrors(detail.errors);
      else setResult(typeof detail === "string" ? detail : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="font-semibold mb-1">{fmt.title}</h2>
      <p className="text-xs text-gray-500 mb-3">
        CSV with header <code className="bg-gray-100 px-1 rounded">{fmt.header}</code>
        <br />
        e.g. <code className="bg-gray-100 px-1 rounded">{fmt.example}</code>
      </p>
      <div className="flex gap-2 items-center">
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm flex-1"
        />
        <button
          onClick={upload}
          disabled={!file || busy}
          className="bg-pink-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-pink-700 disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import"}
        </button>
      </div>
      {result && <p className="text-sm mt-3 text-gray-700">{result}</p>}
      {errors.length > 0 && (
        <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm font-medium text-red-700 mb-1">
            Nothing was imported. Fix these rows and try again:
          </p>
          <ul className="text-xs text-red-700 space-y-0.5">
            {errors.map((e) => (
              <li key={e.line}>
                Line {e.line}: {e.error}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TransportContent() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const refresh = () => adminApi.transportSummary().then(setSummary);
  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-4xl">
        <h1 className="text-2xl font-bold mb-2">Transport data</h1>
        <p className="text-sm text-gray-500 mb-6">
          Powers “How to Get There”. Imports upsert by name and are all-or-nothing. Import
          stops before the routes that reference them.
        </p>
        {summary && (
          <div className="grid grid-cols-5 gap-3 mb-6">
            {Object.entries(summary).map(([k, v]) => (
              <div key={k} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 capitalize">{k.replace("_", " ")}</p>
                <p className="text-2xl font-bold">{v}</p>
              </div>
            ))}
          </div>
        )}
        <div className="space-y-4">
          <ImportCard kind="bus-stops" onDone={refresh} />
          <ImportCard kind="bus-routes" onDone={refresh} />
        </div>
      </main>
    </div>
  );
}

export default function TransportPage() {
  return (
    <AuthGuard>
      <TransportContent />
    </AuthGuard>
  );
}
