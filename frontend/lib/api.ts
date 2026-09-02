/**
 * Typed client for the RAIL-OPT backend API.
 * All shapes mirror backend/app/api/routers/plan.py + data.py responses.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export const API_V1 = `${API_BASE}/api/v1`;

// ---- Response types ----

export interface DataStats {
  corridors: number;
  stations: number;
  assets: number;
  maintenance_requests: number;
  trains: number;
  train_paths: number;
  block_windows: number;
}

export interface PlanResult {
  plan_id: number;
  status: string;
  objective_value: number;
  solve_time_seconds: number;
  total_requests: number;
  scheduled_blocks: number;
  scheduled_tasks: number;
  unscheduled_tasks: number;
  coordination_count: number;
}

export interface Kpi {
  k1_completion_rate: number;
  k2_asset_availability: number;
  k3_coordination_rate: number;
  k4_compression_ratio: number;
  k5_block_hours: number;
  n_blocks: number;
  n_scheduled_tasks: number;
  n_coordinated_blocks: number;
  total_candidates: number;
}

export interface Improvements {
  k1_delta: number;
  k2_delta: number;
  k3_delta_pp: number;
  k4_improvement: number;
  k5_reduction_pct: number;
  block_hours_saved: number;
}

export interface CompareResult {
  railopt: Kpi;
  baseline: Kpi;
  improvements: Improvements;
  summary: {
    meets_k5_target: boolean;
    meets_k3_target: boolean;
  };
}

export interface BlockTask {
  request_id: number;
  dept: string;
  task_kind: string;
  task_code: string;
  est_duration_min: number;
  km_from: number;
  priority_score: number | null;
}

export interface PlanBlock {
  block_id: number;
  corridor_id: number;
  start_ts: string;
  end_ts: string;
  duration_hours: number;
  block_type: string;
  depts: string[];
  is_coordinated: boolean;
  km_start: number | null;
  km_end: number | null;
  tasks: BlockTask[];
}

export interface PlanDetails {
  plan_id: number;
  division: string;
  horizon: string;
  period_start: string;
  period_end: string;
  status: string;
  planner_kind: string;
  objective_value: number | null;
  solver_status: string | null;
  solve_ms: number | null;
  blocks: PlanBlock[];
}

// ---- What-If (Phase 5) ----

export interface RippleTrain {
  number: string;
  train_class: string;
  handling: string; // "HOLD" | "DIVERT"
  delay_min: number;
  is_goods: boolean;
  is_protected: boolean;
}

export interface RippleResult {
  feasible: boolean;
  infeasibility_reason: string | null;
  mode: string; // "DIVERT" | "HOLD" | "CORRIDOR_BLOCK" | "CLEAR"
  trains_affected: number;
  passenger_trains: number;
  goods_trains: number;
  held_trains: number;
  diverted_trains: number;
  passenger_delay_min: number;
  goods_delay_min: number;
  goods_detention_hours: number;
  total_delay_min: number;
  max_delay_min: number;
  protected_train_hit: boolean;
  n_sections: number;
  headway_min: number;
  top_trains: RippleTrain[];
}

export interface PlanScore {
  score: number;
  components: {
    maint_value_norm: number;
    block_hours_norm: number;
    coord_rate: number;
    cascade_delay_norm: number;
    asset_avail_gain_norm: number;
    block_utilization: number;
    total_cascade_delay_min: number;
  };
}

export interface WhatIfResult {
  feasible: boolean;
  infeasibility_reason: string | null;
  edit: { op: string; block_id: number; delta_min: number; label: string | null };
  block_id: number;
  kpi_before: Kpi;
  kpi_after: Kpi;
  kpi_delta: {
    k5_block_hours: number;
    k4_compression_ratio: number;
    k3_coordination_rate: number;
  };
  ripple_before: RippleResult | null;
  ripple_after: RippleResult;
  ripple_delta: {
    trains_affected: number;
    total_delay_min: number;
    goods_detention_hours: number;
  };
  plan_score_before: PlanScore;
  plan_score_after: PlanScore;
  plan_score_delta: number;
}

export type WhatIfOp = "EXTEND_BLOCK" | "MOVE_BLOCK";

// ---- Explainability (Phase 6) ----

export interface PriorityDriver {
  label: string;
  points: number;
}

export interface WhyTask {
  request_id: number;
  dept: string;
  task_kind: string;
  task_code: string;
  km_from: number;
  est_duration_min: number;
  defect_severity: number | null;
  due_on: string | null;
  priority: number;
  drivers: PriorityDriver[];
}

export interface WhyWindow {
  found: boolean;
  window_kind: string | null;
  start_ts?: string;
  end_ts?: string;
  allowed_block_types?: string[];
  rationale: string;
}

export interface WhyBlock {
  block_id: number;
  plan_id: number;
  planner_kind: string;
  corridor_id: number;
  block_type: string;
  depts: string[];
  is_coordinated: boolean;
  n_tasks: number;
  n_depts: number;
  km_start: number;
  km_end: number;
  km_span: number;
  start_ts: string;
  end_ts: string;
  duration_hours: number;
  coordination: {
    n_tasks: number;
    n_depts: number;
    depts: string[];
    km_span: number;
    radius_km: number;
    headline: string;
    rationale: string;
  };
  value: {
    task_value: number;
    coordination_bonus: number;
    n_extra_depts: number;
    total_value: number;
    bundled_hours: number;
    standalone_hours: number;
    hours_saved: number;
    compression: number;
  };
  tasks: WhyTask[];
  window: WhyWindow;
}

// ---- Fetch helpers ----

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function getStats(): Promise<DataStats> {
  return jsonOrThrow<DataStats>(await fetch(`${API_V1}/data/stats`, { cache: "no-store" }));
}

export async function generatePlan(
  division = "NDLS",
  time_limit_seconds = 60,
): Promise<PlanResult> {
  return jsonOrThrow<PlanResult>(
    await fetch(`${API_V1}/plan/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ division, time_limit_seconds }),
    }),
  );
}

export async function generateBaseline(division = "NDLS"): Promise<PlanResult> {
  return jsonOrThrow<PlanResult>(
    await fetch(`${API_V1}/plan/baseline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ division }),
    }),
  );
}

export async function comparePlans(
  railoptPlanId: number,
  baselinePlanId: number,
): Promise<CompareResult> {
  const q = `railopt_plan_id=${railoptPlanId}&baseline_plan_id=${baselinePlanId}`;
  return jsonOrThrow<CompareResult>(
    await fetch(`${API_V1}/plan/compare?${q}`, { cache: "no-store" }),
  );
}

export async function getPlanDetails(planId: number): Promise<PlanDetails> {
  return jsonOrThrow<PlanDetails>(
    await fetch(`${API_V1}/plan/${planId}/details`, { cache: "no-store" }),
  );
}

export async function simulateWhatIf(
  planId: number,
  op: WhatIfOp,
  blockId: number,
  deltaMin: number,
  label?: string,
): Promise<WhatIfResult> {
  return jsonOrThrow<WhatIfResult>(
    await fetch(`${API_V1}/plan/${planId}/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op, block_id: blockId, delta_min: deltaMin, label }),
    }),
  );
}

export async function explainBlock(planId: number, blockId: number): Promise<WhyBlock> {
  return jsonOrThrow<WhyBlock>(
    await fetch(`${API_V1}/plan/${planId}/block/${blockId}/why`, { cache: "no-store" }),
  );
}

// ---- Domain helpers ----

export const DEPT_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  ENGG: { bg: "#2563eb", text: "#ffffff", label: "Engineering" },
  SNT: { bg: "#16a34a", text: "#ffffff", label: "Signal & Telecom" },
  TRD: { bg: "#ea580c", text: "#ffffff", label: "Traction / OHE" },
};

export function deptColor(dept: string) {
  return DEPT_COLORS[dept] ?? { bg: "#64748b", text: "#ffffff", label: dept };
}
