"use client";

import { useCallback, useEffect, useState } from "react";
import {
  comparePlans,
  generateBaseline,
  generatePlan,
  getPlanDetails,
  getStats,
  type CompareResult,
  type DataStats,
  type PlanDetails,
} from "@/lib/api";
import KpiStrip from "@/components/KpiStrip";
import PlanBoard from "@/components/PlanBoard";

type View = "railopt" | "baseline";

export default function Home() {
  const [stats, setStats] = useState<DataStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [railoptDetails, setRailoptDetails] = useState<PlanDetails | null>(null);
  const [baselineDetails, setBaselineDetails] = useState<PlanDetails | null>(null);
  const [view, setView] = useState<View>("railopt");

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((e) => setStatsError(e.message));
  }, []);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      // Both plans schedule the same task set; run them in parallel.
      const [railopt, baseline] = await Promise.all([
        generatePlan("NDLS", 60),
        generateBaseline("NDLS"),
      ]);
      const [cmp, rDetails, bDetails] = await Promise.all([
        comparePlans(railopt.plan_id, baseline.plan_id),
        getPlanDetails(railopt.plan_id),
        getPlanDetails(baseline.plan_id),
      ]);
      setCompare(cmp);
      setRailoptDetails(rDetails);
      setBaselineDetails(bDetails);
      setView("railopt");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }, []);

  const activeDetails = view === "railopt" ? railoptDetails : baselineDetails;
  const hasPlan = compare && railoptDetails && baselineDetails;

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
      {/* Header */}
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-slate-900 px-2 py-1 font-mono text-sm font-bold text-white">
              RAIL-OPT
            </span>
            <h1 className="text-xl font-semibold text-slate-800">
              Maintenance Block Optimizer
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            One coordinated plan across Engineering, S&amp;T and Traction — Northern
            Railway, NDLS division, weekly horizon.
          </p>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generating ? "Optimizing…" : hasPlan ? "Re-generate plan" : "Generate weekly plan"}
        </button>
      </header>

      {/* Data source bar */}
      <DataBar stats={stats} error={statsError} />

      {error && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <span className="font-semibold">Could not generate plan:</span> {error}
          <div className="mt-1 text-xs text-rose-500">
            Is the backend running on <code>http://localhost:8000</code>?
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasPlan && !generating && (
        <div className="mt-10 rounded-xl border border-dashed border-slate-300 bg-white/60 p-12 text-center">
          <p className="text-lg font-medium text-slate-600">
            Ready to plan this week&rsquo;s maintenance.
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
            RAIL-OPT bundles nearby jobs from different departments into shared track
            closures, then compares the result against today&rsquo;s manual first-come
            approach.
          </p>
        </div>
      )}

      {generating && (
        <div className="mt-10 flex flex-col items-center gap-3 py-12 text-slate-500">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800" />
          <p className="text-sm">Solving constraint model &amp; building baseline…</p>
        </div>
      )}

      {/* Results */}
      {hasPlan && !generating && (
        <div className="mt-6 space-y-6">
          <KpiStrip compare={compare} />

          <div>
            <div className="mb-3 flex items-center justify-between">
              <ViewToggle
                view={view}
                onChange={setView}
                railoptBlocks={railoptDetails.blocks.length}
                baselineBlocks={baselineDetails.blocks.length}
              />
            </div>
            {activeDetails && <PlanBoard details={activeDetails} kind={view} />}
          </div>
        </div>
      )}
    </div>
  );
}

function DataBar({ stats, error }: { stats: DataStats | null; error: string | null }) {
  if (error) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-700">
        Backend not reachable ({error}). Start it on port 8000, then reload.
      </div>
    );
  }
  if (!stats) {
    return (
      <div className="h-9 animate-pulse rounded-lg border border-slate-200 bg-white" />
    );
  }
  const items: [string, number][] = [
    ["Corridors", stats.corridors],
    ["Stations", stats.stations],
    ["Assets", stats.assets],
    ["Maintenance requests", stats.maintenance_requests],
    ["Train paths", stats.train_paths],
    ["Block windows", stats.block_windows],
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs text-slate-500">
      <span className="font-semibold text-slate-400">DATA</span>
      {items.map(([label, n]) => (
        <span key={label}>
          <span className="font-mono font-semibold text-slate-700">{n}</span> {label}
        </span>
      ))}
    </div>
  );
}

function ViewToggle({
  view,
  onChange,
  railoptBlocks,
  baselineBlocks,
}: {
  view: View;
  onChange: (v: View) => void;
  railoptBlocks: number;
  baselineBlocks: number;
}) {
  return (
    <div className="inline-flex items-center rounded-lg border border-slate-300 bg-white p-1 text-sm shadow-sm">
      <button
        onClick={() => onChange("railopt")}
        className={`rounded-md px-3 py-1.5 font-medium transition ${
          view === "railopt"
            ? "bg-slate-900 text-white"
            : "text-slate-500 hover:text-slate-800"
        }`}
      >
        RAIL-OPT{" "}
        <span className={view === "railopt" ? "text-slate-300" : "text-slate-400"}>
          {railoptBlocks} blocks
        </span>
      </button>
      <button
        onClick={() => onChange("baseline")}
        className={`rounded-md px-3 py-1.5 font-medium transition ${
          view === "baseline"
            ? "bg-slate-900 text-white"
            : "text-slate-500 hover:text-slate-800"
        }`}
      >
        Baseline{" "}
        <span className={view === "baseline" ? "text-slate-300" : "text-slate-400"}>
          {baselineBlocks} blocks
        </span>
      </button>
    </div>
  );
}
