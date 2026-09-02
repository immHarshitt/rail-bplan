"use client";

import type { CompareResult } from "@/lib/api";

function pct(x: number): string {
  return `${(x * 100).toFixed(0)}%`;
}

/** A single KPI comparison card. */
function KpiCard({
  label,
  sub,
  baseline,
  railopt,
  delta,
  deltaGood,
  hero,
  target,
  targetMet,
}: {
  label: string;
  sub: string;
  baseline: string;
  railopt: string;
  delta?: string;
  deltaGood?: boolean;
  hero?: boolean;
  target?: string;
  targetMet?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border bg-white p-5 shadow-sm ${
        hero ? "border-slate-300 ring-1 ring-slate-200" : "border-slate-200"
      }`}
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
        {target && (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              targetMet
                ? "bg-emerald-100 text-emerald-700"
                : "bg-rose-100 text-rose-700"
            }`}
          >
            {targetMet ? "✓" : "✗"} {target}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs text-slate-400">{sub}</p>

      <div className="mt-4 flex items-end gap-3">
        <div>
          <div
            className={`font-mono font-bold tracking-tight text-slate-900 ${
              hero ? "text-4xl" : "text-2xl"
            }`}
          >
            {railopt}
          </div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            RAIL-OPT
          </div>
        </div>
        {delta && (
          <div
            className={`mb-1 rounded-md px-2 py-1 text-sm font-bold ${
              deltaGood ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
            }`}
          >
            {delta}
          </div>
        )}
      </div>

      <div className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500">
        Baseline (manual): <span className="font-mono font-semibold text-slate-700">{baseline}</span>
      </div>
    </div>
  );
}

export default function KpiStrip({ compare }: { compare: CompareResult }) {
  const { railopt, baseline, improvements, summary } = compare;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">
          Impact vs. today&rsquo;s manual process
        </h2>
        <span className="text-sm text-slate-500">
          Same {railopt.n_scheduled_tasks} tasks completed · lower is better on block-hours
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Hero 1: block-hours (K5) */}
        <KpiCard
          hero
          label="Block-hours"
          sub="K5 · total track-closure time"
          baseline={`${baseline.k5_block_hours} h`}
          railopt={`${railopt.k5_block_hours} h`}
          delta={`−${improvements.k5_reduction_pct}%`}
          deltaGood={improvements.k5_reduction_pct > 0}
          target="≥25%"
          targetMet={summary.meets_k5_target}
        />

        {/* Hero 2: coordination (K3) */}
        <KpiCard
          hero
          label="Coordination rate"
          sub="K3 · blocks with ≥2 departments"
          baseline={pct(baseline.k3_coordination_rate)}
          railopt={pct(railopt.k3_coordination_rate)}
          delta={`+${improvements.k3_delta_pp}pp`}
          deltaGood={improvements.k3_delta_pp > 0}
          target="≥40%"
          targetMet={summary.meets_k3_target}
        />

        {/* Blocks / closures */}
        <KpiCard
          label="Track closures"
          sub="Separate maintenance blocks"
          baseline={`${baseline.n_blocks}`}
          railopt={`${railopt.n_blocks}`}
          delta={`−${baseline.n_blocks - railopt.n_blocks}`}
          deltaGood={railopt.n_blocks < baseline.n_blocks}
        />

        {/* Compression (K4) */}
        <KpiCard
          label="Compression"
          sub="K4 · standalone ÷ actual hours"
          baseline={`${baseline.k4_compression_ratio.toFixed(2)}×`}
          railopt={`${railopt.k4_compression_ratio.toFixed(2)}×`}
          delta={`+${improvements.k4_improvement.toFixed(2)}`}
          deltaGood={improvements.k4_improvement > 0}
        />
      </div>

      <p className="mt-3 text-sm text-slate-500">
        <span className="font-semibold text-slate-700">
          {improvements.block_hours_saved} block-hours saved
        </span>{" "}
        this week — same work, {baseline.n_blocks - railopt.n_blocks} fewer track closures,
        completion held at {pct(railopt.k1_completion_rate)}.
      </p>
    </section>
  );
}
