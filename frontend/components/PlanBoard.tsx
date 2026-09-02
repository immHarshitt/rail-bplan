"use client";

import { useMemo, useState } from "react";
import { deptColor, type PlanBlock, type PlanDetails } from "@/lib/api";
import WhatIfPanel from "./WhatIfPanel";
import WhyPanel from "./WhyPanel";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Background fill for a block: solid for one dept, hard-stop gradient for a bundle. */
function blockBackground(depts: string[]): string {
  const colors = depts.map((d) => deptColor(d).bg);
  if (colors.length <= 1) return colors[0] ?? "#64748b";
  const n = colors.length;
  const stops = colors
    .map((c, i) => `${c} ${(i / n) * 100}%, ${c} ${((i + 1) / n) * 100}%`)
    .join(", ");
  return `linear-gradient(135deg, ${stops})`;
}

/** Greedy interval partitioning: pack blocks into as few non-overlapping sub-lanes as possible. */
function packLanes(blocks: PlanBlock[]): PlanBlock[][] {
  const sorted = [...blocks].sort(
    (a, b) => new Date(a.start_ts).getTime() - new Date(b.start_ts).getTime(),
  );
  const lanes: { end: number; blocks: PlanBlock[] }[] = [];
  for (const blk of sorted) {
    const start = new Date(blk.start_ts).getTime();
    const end = new Date(blk.end_ts).getTime();
    const lane = lanes.find((l) => l.end <= start);
    if (lane) {
      lane.blocks.push(blk);
      lane.end = end;
    } else {
      lanes.push({ end, blocks: [blk] });
    }
  }
  return lanes.map((l) => l.blocks);
}

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleString("en-GB", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function PlanBoard({
  details,
  kind,
}: {
  details: PlanDetails;
  kind: "railopt" | "baseline";
}) {
  const [selected, setSelected] = useState<PlanBlock | null>(null);

  const t0 = new Date(details.period_start).getTime();
  const t1 = new Date(details.period_end).getTime();
  const span = Math.max(t1 - t0, DAY_MS);
  const nDays = Math.max(1, Math.round(span / DAY_MS));

  // Group blocks by corridor, then pack each corridor into non-overlapping sub-lanes.
  const corridors = useMemo(() => {
    const byCorridor = new Map<number, PlanBlock[]>();
    for (const b of details.blocks) {
      const arr = byCorridor.get(b.corridor_id) ?? [];
      arr.push(b);
      byCorridor.set(b.corridor_id, arr);
    }
    return [...byCorridor.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([corridor_id, blocks]) => ({
        corridor_id,
        lanes: packLanes(blocks),
        count: blocks.length,
      }));
  }, [details.blocks]);

  const dayLabels = useMemo(
    () =>
      Array.from({ length: nDays }, (_, i) =>
        new Date(t0 + i * DAY_MS).toLocaleDateString("en-GB", {
          weekday: "short",
          day: "numeric",
        }),
      ),
    [t0, nDays],
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Weekly plan board
            <span className="ml-2 text-sm font-normal text-slate-400">
              {kind === "railopt" ? "RAIL-OPT (optimized)" : "Baseline (manual FCFS)"}
            </span>
          </h2>
          <p className="text-xs text-slate-400">
            {details.blocks.length} track closures across {corridors.length} corridors ·
            each bar is one block · click for tasks
          </p>
        </div>
        <Legend />
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[720px]">
          {/* Day header */}
          <div className="flex border-b border-slate-200 pb-1 pl-24">
            {dayLabels.map((lbl, i) => (
              <div
                key={i}
                className="border-l border-slate-100 pl-1 text-[11px] font-medium text-slate-400"
                style={{ width: `${100 / nDays}%` }}
              >
                {lbl}
              </div>
            ))}
          </div>

          {/* Corridor lanes */}
          <div className="divide-y divide-slate-100">
            {corridors.map((c) => (
              <div key={c.corridor_id} className="flex py-2">
                <div className="w-24 shrink-0 pr-2">
                  <div className="text-xs font-semibold text-slate-600">
                    Corridor {c.corridor_id}
                  </div>
                  <div className="text-[10px] text-slate-400">{c.count} blocks</div>
                </div>

                <div className="relative flex-1">
                  {/* Day gridlines */}
                  {Array.from({ length: nDays }, (_, i) => (
                    <div
                      key={i}
                      className="absolute top-0 bottom-0 border-l border-slate-100"
                      style={{ left: `${(i / nDays) * 100}%` }}
                    />
                  ))}

                  {c.lanes.map((lane, li) => (
                    <div key={li} className="relative h-8">
                      {lane.map((blk) => {
                        const s = new Date(blk.start_ts).getTime();
                        const e = new Date(blk.end_ts).getTime();
                        const left = ((s - t0) / span) * 100;
                        const width = ((e - s) / span) * 100;
                        const multi = blk.depts.length >= 2;
                        const isSel = selected?.block_id === blk.block_id;
                        return (
                          <button
                            key={blk.block_id}
                            onClick={() => setSelected(isSel ? null : blk)}
                            title={`${blk.depts.join("+")} · ${blk.duration_hours}h · ${fmtTime(
                              blk.start_ts,
                            )}`}
                            className={`absolute top-0.5 h-7 rounded-md border text-left transition ${
                              isSel
                                ? "z-10 border-slate-900 ring-2 ring-slate-900/30"
                                : "border-black/10 hover:border-black/40"
                            }`}
                            style={{
                              left: `${left}%`,
                              width: `max(${width}%, 10px)`,
                              background: blockBackground(blk.depts),
                            }}
                          >
                            {multi && (
                              <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber-400 text-[9px] font-bold text-amber-950 shadow">
                                {blk.depts.length}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {selected && (
        <BlockDetail
          block={selected}
          planId={details.plan_id}
          whatIfEnabled={kind === "railopt"}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
      {["ENGG", "SNT", "TRD"].map((d) => {
        const c = deptColor(d);
        return (
          <span key={d} className="flex items-center gap-1">
            <span className="h-3 w-3 rounded-sm" style={{ background: c.bg }} />
            {c.label}
          </span>
        );
      })}
      <span className="flex items-center gap-1">
        <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-400 text-[8px] font-bold text-amber-950">
          n
        </span>
        coordinated ({"≥"}2 depts)
      </span>
    </div>
  );
}

function BlockDetail({
  block,
  planId,
  whatIfEnabled,
  onClose,
}: {
  block: PlanBlock;
  planId: number;
  whatIfEnabled: boolean;
  onClose: () => void;
}) {
  const multi = block.depts.length >= 2;
  return (
    <div className="mt-4 rounded-lg border border-slate-300 bg-slate-50 p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-800">
              Block #{block.block_id} · Corridor {block.corridor_id}
            </h3>
            {multi && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                Coordinated · {block.depts.length} departments
              </span>
            )}
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              {block.block_type}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {fmtTime(block.start_ts)} → {fmtTime(block.end_ts)} · {block.duration_hours}h
            {block.km_start != null && block.km_end != null && (
              <> · km {block.km_start}–{block.km_end}</>
            )}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md px-2 py-1 text-xs text-slate-400 hover:bg-slate-200 hover:text-slate-600"
        >
          Close ✕
        </button>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {block.tasks.map((t) => {
          const c = deptColor(t.dept);
          return (
            <div
              key={t.request_id}
              className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2"
            >
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                style={{ background: c.bg, color: c.text }}
              >
                {t.dept}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium text-slate-700">
                  {t.task_kind}{" "}
                  <span className="font-normal text-slate-400">#{t.request_id}</span>
                </div>
                <div className="text-[10px] text-slate-400">
                  km {t.km_from} · {t.est_duration_min} min
                  {t.priority_score != null && <> · priority {t.priority_score.toFixed(0)}</>}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <WhyPanel planId={planId} block={block} />

      {whatIfEnabled && <WhatIfPanel planId={planId} block={block} />}
    </div>
  );
}
