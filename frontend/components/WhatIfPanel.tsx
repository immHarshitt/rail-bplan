"use client";

import { useCallback, useEffect, useState } from "react";
import {
  simulateWhatIf,
  type PlanBlock,
  type WhatIfResult,
  type WhatIfOp,
} from "@/lib/api";

type EditSpec = { op: WhatIfOp; delta: number; label: string };

const EXTEND_STEPS: EditSpec[] = [
  { op: "EXTEND_BLOCK", delta: 15, label: "+15" },
  { op: "EXTEND_BLOCK", delta: 30, label: "+30" },
  { op: "EXTEND_BLOCK", delta: 60, label: "+60" },
  { op: "EXTEND_BLOCK", delta: 120, label: "+120" },
];

const MOVE_STEPS: EditSpec[] = [
  { op: "MOVE_BLOCK", delta: -60, label: "◀ 60" },
  { op: "MOVE_BLOCK", delta: -30, label: "◀ 30" },
  { op: "MOVE_BLOCK", delta: 30, label: "30 ▶" },
  { op: "MOVE_BLOCK", delta: 60, label: "60 ▶" },
];

function fmtDelay(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** Colour a delta: more disruption (positive) = red, less = green. */
function deltaTone(v: number, goodWhenNegative = true): string {
  if (v === 0) return "text-slate-400";
  const bad = goodWhenNegative ? v > 0 : v < 0;
  return bad ? "text-rose-600" : "text-emerald-600";
}

export default function WhatIfPanel({
  planId,
  block,
}: {
  planId: number;
  block: PlanBlock;
}) {
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when the selected block changes.
  useEffect(() => {
    setResult(null);
    setActive(null);
    setError(null);
  }, [block.block_id]);

  const run = useCallback(
    async (spec: EditSpec) => {
      const key = `${spec.op}:${spec.delta}`;
      setLoading(true);
      setError(null);
      setActive(key);
      try {
        const r = await simulateWhatIf(planId, spec.op, block.block_id, spec.delta, spec.label);
        setResult(r);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Simulation failed");
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    [planId, block.block_id],
  );

  return (
    <div className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50/50 p-4">
      <div className="flex items-center gap-2">
        <span className="rounded bg-indigo-600 px-2 py-0.5 text-[10px] font-bold tracking-wide text-white">
          WHAT-IF
        </span>
        <h4 className="text-sm font-semibold text-slate-800">
          Simulate a change to this block
        </h4>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">
        Each button re-runs the ripple model against live train paths — see the traffic impact
        before you commit.
      </p>

      {/* Controls */}
      <div className="mt-3 space-y-2">
        <StepRow
          title="Extend block"
          hint="hold the section longer"
          steps={EXTEND_STEPS}
          active={active}
          loading={loading}
          onPick={run}
        />
        <StepRow
          title="Move block"
          hint="shift earlier / later"
          steps={MOVE_STEPS}
          active={active}
          loading={loading}
          onPick={run}
        />
      </div>

      {error && (
        <div className="mt-3 rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}

      {result && <ImpactReadout result={result} />}
    </div>
  );
}

function StepRow({
  title,
  hint,
  steps,
  active,
  loading,
  onPick,
}: {
  title: string;
  hint: string;
  steps: EditSpec[];
  active: string | null;
  loading: boolean;
  onPick: (s: EditSpec) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-28 shrink-0">
        <div className="text-xs font-semibold text-slate-700">{title}</div>
        <div className="text-[10px] text-slate-400">{hint}</div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {steps.map((s) => {
          const key = `${s.op}:${s.delta}`;
          const isActive = active === key;
          return (
            <button
              key={key}
              disabled={loading}
              onClick={() => onPick(s)}
              className={`min-w-[52px] rounded-md border px-2.5 py-1 text-xs font-semibold transition disabled:opacity-50 ${
                isActive
                  ? "border-indigo-600 bg-indigo-600 text-white shadow"
                  : "border-slate-300 bg-white text-slate-600 hover:border-indigo-400 hover:text-indigo-700"
              }`}
            >
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ImpactReadout({ result }: { result: WhatIfResult }) {
  const rb = result.ripple_before;
  const ra = result.ripple_after;

  if (!result.feasible) {
    return (
      <div className="mt-3 rounded-lg border-2 border-rose-400 bg-rose-50 p-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">⛔</span>
          <span className="text-sm font-bold text-rose-800">INFEASIBLE — edit rejected</span>
        </div>
        <p className="mt-1 text-xs text-rose-700">{result.infeasibility_reason}</p>
      </div>
    );
  }

  const trainsBefore = rb?.trains_affected ?? 0;
  const delayBefore = rb?.total_delay_min ?? 0;
  const scoreBefore = result.plan_score_before.score;
  const scoreAfter = result.plan_score_after.score;

  return (
    <div className="mt-3 space-y-3">
      {/* Headline metrics */}
      <div className="grid grid-cols-3 gap-2">
        <Metric
          label="Trains affected"
          before={trainsBefore}
          after={ra.trains_affected}
          delta={result.ripple_delta.trains_affected}
        />
        <Metric
          label="Cascade delay"
          before={fmtDelay(delayBefore)}
          after={fmtDelay(ra.total_delay_min)}
          delta={result.ripple_delta.total_delay_min}
          deltaFmt={(v) => (v > 0 ? `+${fmtDelay(v)}` : v < 0 ? `−${fmtDelay(-v)}` : "0")}
        />
        <Metric
          label="Plan score"
          before={scoreBefore.toFixed(1)}
          after={scoreAfter.toFixed(1)}
          delta={result.plan_score_delta}
          goodWhenNegative={false}
          deltaFmt={(v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1))}
        />
      </div>

      {/* Mode + secondary */}
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <ModeBadge mode={ra.mode} />
        <span className="text-slate-500">
          {ra.held_trains > 0 && <>{ra.held_trains} held · </>}
          {ra.diverted_trains > 0 && <>{ra.diverted_trains} diverted · </>}
          {ra.passenger_delay_min > 0 && (
            <>passenger delay {fmtDelay(ra.passenger_delay_min)} · </>
          )}
          {ra.goods_detention_hours > 0 && (
            <>goods detention {ra.goods_detention_hours.toFixed(1)}h · </>
          )}
          K5 {result.kpi_before.k5_block_hours}h → {result.kpi_after.k5_block_hours}h
        </span>
        {ra.protected_train_hit && (
          <span className="rounded-full bg-rose-100 px-2 py-0.5 font-semibold text-rose-700">
            ⚠ protected train delayed
          </span>
        )}
      </div>

      {/* Top affected trains */}
      {ra.top_trains.length > 0 && (
        <div>
          <div className="mb-1 text-[11px] font-semibold text-slate-500">
            Most-delayed trains
          </div>
          <div className="flex flex-wrap gap-1.5">
            {ra.top_trains.map((t) => (
              <span
                key={t.number}
                className={`flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] ${
                  t.is_goods
                    ? "border-orange-200 bg-orange-50 text-orange-800"
                    : "border-blue-200 bg-blue-50 text-blue-800"
                }`}
                title={`${t.train_class} · ${t.handling}`}
              >
                <span className="font-semibold">{t.number}</span>
                <span className="opacity-60">{t.is_goods ? "goods" : "pax"}</span>
                <span className="font-mono font-semibold">{fmtDelay(t.delay_min)}</span>
                {t.is_protected && <span title="protected">🛡</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  before,
  after,
  delta,
  goodWhenNegative = true,
  deltaFmt,
}: {
  label: string;
  before: string | number;
  after: string | number;
  delta: number;
  goodWhenNegative?: boolean;
  deltaFmt?: (v: number) => string;
}) {
  const tone = deltaTone(delta, goodWhenNegative);
  const fmt = deltaFmt ?? ((v: number) => (v > 0 ? `+${v}` : `${v}`));
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2.5 text-center">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className="mt-1 flex items-baseline justify-center gap-1">
        <span className="text-sm text-slate-400">{before}</span>
        <span className="text-slate-300">→</span>
        <span className="text-xl font-bold text-slate-800">{after}</span>
      </div>
      <div className={`text-[11px] font-semibold ${tone}`}>{delta === 0 ? "no change" : fmt(delta)}</div>
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    HOLD: { bg: "bg-rose-100", text: "text-rose-700", label: "HOLD — trains queued at loop" },
    DIVERT: { bg: "bg-amber-100", text: "text-amber-800", label: "DIVERT — single-line working" },
    CORRIDOR_BLOCK: { bg: "bg-rose-100", text: "text-rose-700", label: "CORRIDOR BLOCK" },
    CLEAR: { bg: "bg-emerald-100", text: "text-emerald-700", label: "CLEAR — no traffic" },
  };
  const m = map[mode] ?? { bg: "bg-slate-100", text: "text-slate-600", label: mode };
  return (
    <span className={`rounded-full px-2 py-0.5 font-semibold ${m.bg} ${m.text}`}>{m.label}</span>
  );
}
