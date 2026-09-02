"use client";

import { useEffect, useState } from "react";
import { explainBlock, deptColor, type PlanBlock, type WhyBlock } from "@/lib/api";

function fmtHours(h: number): string {
  const H = Math.floor(h);
  const m = Math.round((h - H) * 60);
  if (H === 0) return `${m}m`;
  return m ? `${H}h ${m}m` : `${H}h`;
}

const WINDOW_LABEL: Record<string, string> = {
  TRAFFIC_LEAN: "Traffic-lean",
  CORRIDOR_POLICY: "Corridor policy",
  MAINT_NOTIFIED: "Pre-notified",
};

export default function WhyPanel({
  planId,
  block,
}: {
  planId: number;
  block: PlanBlock;
}) {
  const [why, setWhy] = useState<WhyBlock | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-load the explanation when a block is opened (or changes).
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setWhy(null);
    explainBlock(planId, block.block_id)
      .then((w) => {
        if (!cancelled) setWhy(w);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to explain block");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [planId, block.block_id]);

  return (
    <div className="mt-4 rounded-lg border border-teal-200 bg-teal-50/50 p-4">
      <div className="flex items-center gap-2">
        <span className="rounded bg-teal-600 px-2 py-0.5 text-[10px] font-bold tracking-wide text-white">
          WHY
        </span>
        <h4 className="text-sm font-semibold text-slate-800">Why this block is here</h4>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">
        The optimizer&apos;s own reasoning — coordination, value gained, task urgency and the
        window it had to fit.
      </p>

      {loading && <div className="mt-3 text-xs text-slate-400">Explaining…</div>}
      {error && (
        <div className="mt-3 rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}
      {why && <WhyBody why={why} />}
    </div>
  );
}

function WhyBody({ why }: { why: WhyBlock }) {
  return (
    <div className="mt-3 space-y-3">
      <CoordinationCard why={why} />
      <ValueStats why={why} />
      <TaskPriorities why={why} />
      <TimingCard why={why} />
    </div>
  );
}

/** The headline: N separate closures collapsed into one shared block. */
function CoordinationCard({ why }: { why: WhyBlock }) {
  const c = why.coordination;
  const coordinated = why.n_tasks > 1;

  return (
    <div className="rounded-lg border border-teal-200 bg-white p-3">
      <div className="flex items-center gap-3">
        {coordinated ? (
          <div className="flex items-center gap-2">
            <span className="flex h-9 min-w-9 items-center justify-center rounded-md bg-rose-100 px-2 text-lg font-bold text-rose-600">
              {why.n_tasks}
            </span>
            <span className="text-slate-400">→</span>
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-100 text-lg font-bold text-emerald-600">
              1
            </span>
          </div>
        ) : (
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-100 text-lg font-bold text-slate-500">
            1
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-slate-800">{c.headline}</div>
          {/* department chips */}
          <div className="mt-1 flex flex-wrap gap-1">
            {c.depts.map((d) => {
              const col = deptColor(d);
              return (
                <span
                  key={d}
                  className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                  style={{ background: col.bg, color: col.text }}
                >
                  {d}
                </span>
              );
            })}
          </div>
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-600">{c.rationale}</p>
    </div>
  );
}

/** Objective value + block-hours saved vs separate closures. */
function ValueStats({ why }: { why: WhyBlock }) {
  const v = why.value;
  const saved = v.hours_saved > 0.01;
  return (
    <div className="grid grid-cols-3 gap-2">
      <Stat
        label="Time saved"
        value={saved ? fmtHours(v.hours_saved) : "—"}
        sub={saved ? `${fmtHours(v.standalone_hours)} → ${fmtHours(v.bundled_hours)}` : "standalone"}
        tone={saved ? "emerald" : "slate"}
      />
      <Stat
        label="Compression"
        value={`${v.compression.toFixed(2)}×`}
        sub={saved ? "vs separate blocks" : "single task"}
        tone={v.compression > 1.01 ? "emerald" : "slate"}
      />
      <Stat
        label="Plan value"
        value={v.total_value.toFixed(0)}
        sub={
          v.coordination_bonus > 0
            ? `${v.task_value.toFixed(0)} + ${v.coordination_bonus.toFixed(0)} coord`
            : "task priority"
        }
        tone="teal"
      />
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  tone: "emerald" | "teal" | "slate";
}) {
  const valueTone =
    tone === "emerald"
      ? "text-emerald-600"
      : tone === "teal"
        ? "text-teal-700"
        : "text-slate-700";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2.5 text-center">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-bold ${valueTone}`}>{value}</div>
      <div className="text-[10px] text-slate-400">{sub}</div>
    </div>
  );
}

/** Per-task priority, broken into its drivers. */
function TaskPriorities({ why }: { why: WhyBlock }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold text-slate-500">
        Task priorities — why each task earns its place
      </div>
      <div className="space-y-1.5">
        {why.tasks.map((t) => {
          const col = deptColor(t.dept);
          return (
            <div
              key={t.request_id}
              className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5"
            >
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                style={{ background: col.bg, color: col.text }}
              >
                {t.dept}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium text-slate-700">
                  {t.task_code}{" "}
                  <span className="font-normal text-slate-400">· {t.task_kind.toLowerCase()}</span>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  {t.drivers.map((d, i) => (
                    <span
                      key={i}
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-500"
                    >
                      {d.label} <span className="font-semibold text-slate-700">+{d.points}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-sm font-bold text-teal-700">{t.priority.toFixed(0)}</div>
                <div className="text-[9px] text-slate-400">priority</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The admissible window that pinned the timing (constraint H4). */
function TimingCard({ why }: { why: WhyBlock }) {
  const w = why.window;
  const kindLabel = w.window_kind ? (WINDOW_LABEL[w.window_kind] ?? w.window_kind) : null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold text-slate-500">Timing</span>
        {kindLabel && (
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-white">
            {kindLabel} window
          </span>
        )}
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
          {why.block_type}
        </span>
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-slate-600">{w.rationale}</p>
    </div>
  );
}
