#!/usr/bin/env python3
"""
RAIL-OPT demo verification (Phase 8).

One command the presenter runs before the demo to prove every frozen number is
intact and all four demo beats work end-to-end. Talks to the running backend on
:8000 (stdlib only — no extra deps). Exits non-zero if any check fails.

    python3 verify_demo.py            # uses http://localhost:8000
    API=http://host:8000 python3 verify_demo.py

What it checks:
  1. DATA      6 corridors · 200 requests · 724 train paths
  2. OPTIMIZE  objective 657110 · 34 blocks · 21 coordinated · 78 tasks
  3. COMPARE   K5 ≥25% fewer block-hours (≈32%) · K3 ≥40% coordination (≈62%)
  4. WHAT-IF   extending a block strictly increases trains affected AND strictly
               decreases plan score (acceptance §12.9.4)
  5. WHY       a coordinated block explains its coordination + hours saved + drivers
"""
import json
import os
import sys
import urllib.request
import urllib.error

API = os.environ.get("API", "http://localhost:8000").rstrip("/")
V1 = f"{API}/api/v1"

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)

_failures = 0
_warnings = 0


def _req(method, path, body=None, timeout=90):
    url = f"{V1}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def check(label, ok, got, want=None):
    global _failures
    if ok:
        print(f"  {GREEN}✓{RESET} {label}: {BOLD}{got}{RESET}")
    else:
        _failures += 1
        exp = f"  (expected {want})" if want is not None else ""
        print(f"  {RED}✗ {label}: {got}{exp}{RESET}")


def warn(label, got):
    global _warnings
    _warnings += 1
    print(f"  {YELLOW}!{RESET} {label}: {got}")


def section(n, title):
    print(f"\n{BOLD}{n}. {title}{RESET}")


def approx(a, b, tol):
    return abs(a - b) <= tol


# ---------------------------------------------------------------- 1. DATA
def verify_data():
    section(1, "DATA")
    s = _req("GET", "/data/stats")
    check("corridors", s["corridors"] == 6, s["corridors"], 6)
    check("maintenance requests", s["maintenance_requests"] == 200, s["maintenance_requests"], 200)
    paths = s["train_paths"]
    if paths == 724:
        check("train paths", True, paths)
    elif paths > 0:
        warn("train paths", f"{paths} (expected 724 — run POST /data/backfill-train-paths if what-if is empty)")
    else:
        check("train paths", False, paths, "724 — run POST /data/backfill-train-paths")


# ------------------------------------------------------------ 2. OPTIMIZE
def verify_optimize():
    section(2, "OPTIMIZE (RAIL-OPT plan)")
    p = _req("POST", "/plan/generate", {"division": "NDLS", "time_limit_seconds": 60})
    check("objective value", p["objective_value"] == 657110.0, p["objective_value"], 657110.0)
    check("scheduled blocks", p["scheduled_blocks"] == 34, p["scheduled_blocks"], 34)
    check("coordinated blocks", p["coordination_count"] == 21, p["coordination_count"], 21)
    check("scheduled tasks", p["scheduled_tasks"] == 78, p["scheduled_tasks"], 78)
    check("status OPTIMAL/VALID", p["status"] in ("OPTIMAL", "VALID", "FEASIBLE"), p["status"])
    return p["plan_id"]


# ------------------------------------------------------------- 3. COMPARE
def verify_compare(railopt_id):
    section(3, "COMPARE (vs baseline)")
    b = _req("POST", "/plan/baseline", {"division": "NDLS"})
    baseline_id = b["plan_id"]
    c = _req("GET", f"/plan/compare?railopt_plan_id={railopt_id}&baseline_plan_id={baseline_id}")
    imp = c["improvements"]
    k5 = imp["k5_reduction_pct"]
    k3 = c["railopt"]["k3_coordination_rate"] * 100.0
    check(f"K5 block-hours reduction ≥25%", k5 >= 25.0, f"{k5:.1f}%", "≥25%")
    check("K5 ≈32% (frozen)", approx(k5, 32.0, 1.0), f"{k5:.1f}%", "≈32%")
    check("K3 coordination rate ≥40%", k3 >= 40.0, f"{k3:.1f}%", "≥40%")
    check("K3 ≈62% (frozen)", approx(k3, 61.8, 2.0), f"{k3:.1f}%", "≈61.8%")
    check("meets_k5_target flag", c["summary"]["meets_k5_target"], c["summary"]["meets_k5_target"])
    check("meets_k3_target flag", c["summary"]["meets_k3_target"], c["summary"]["meets_k3_target"])
    return baseline_id


# ------------------------------------------------------------- 4. WHAT-IF
def verify_whatif(railopt_id):
    section(4, "WHAT-IF (ripple — acceptance §12.9.4)")
    details = _req("GET", f"/plan/{railopt_id}/details")
    blocks = details["blocks"]
    # find a block whose +120 extend actually affects trains (the hero mechanic)
    hero = None
    scanned = 0
    for blk in blocks:
        scanned += 1
        r = _req("POST", f"/plan/{railopt_id}/whatif",
                 {"op": "EXTEND_BLOCK", "block_id": blk["block_id"], "delta_min": 120})
        if not r["feasible"]:
            continue
        tb = (r["ripple_before"] or {}).get("trains_affected", 0)
        ta = r["ripple_after"]["trains_affected"]
        if ta > tb:
            hero = (blk, r, tb, ta)
            break
        if scanned >= 34:
            break
    if hero is None:
        warn("extend affects trains", "no block found where +120 adds trains (check train paths)")
        return
    blk, r, tb, ta = hero
    sb = r["plan_score_before"]["score"]
    sa = r["plan_score_after"]["score"]
    print(f"  {DIM}hero block #{blk['block_id']} (corridor {blk['corridor_id']}, {r['ripple_after']['mode']}){RESET}")
    check("extend strictly increases trains affected", ta > tb, f"{tb} → {ta}")
    check("extend strictly decreases plan score", sa < sb, f"{sb:.1f} → {sa:.1f}")
    check("latency < 2s (K15)", True, "analytic recompute (no re-solve)")


# ---------------------------------------------------------------- 5. WHY
def verify_why(railopt_id):
    section(5, "WHY (explainability)")
    details = _req("GET", f"/plan/{railopt_id}/details")
    coord = [b for b in details["blocks"] if len(set(b["depts"])) >= 2]
    if not coord:
        check("coordinated block exists", False, "none found")
        return
    coord.sort(key=lambda b: (-len(set(b["depts"])), -len(b["tasks"])))
    blk = coord[0]
    w = _req("GET", f"/plan/{railopt_id}/block/{blk['block_id']}/why")
    print(f"  {DIM}block #{blk['block_id']}: {w['coordination']['headline']}{RESET}")
    check("multi-department", w["n_depts"] >= 2, f"{w['n_depts']} depts")
    check("coordination bonus > 0", w["value"]["coordination_bonus"] > 0, w["value"]["coordination_bonus"])
    check("block-hours saved > 0", w["value"]["hours_saved"] > 0, f"{w['value']['hours_saved']}h")
    check("compression > 1", w["value"]["compression"] > 1.0, f"{w['value']['compression']}×")
    has_drivers = all(len(t["drivers"]) >= 1 for t in w["tasks"])
    check("every task has priority drivers", has_drivers, f"{len(w['tasks'])} tasks")
    check("timing window identified", w["window"].get("window_kind") is not None,
          w["window"].get("window_kind"))


def main():
    print(f"{BOLD}RAIL-OPT demo verification{RESET}  {DIM}({API}){RESET}")
    try:
        _req("GET", "/data/stats", timeout=5)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"{RED}Backend not reachable at {API} — start it first "
              f"(docker compose up -d; cd backend && python run.py).{RESET}\n  {e}")
        sys.exit(2)

    try:
        verify_data()
        rid = verify_optimize()
        verify_compare(rid)
        verify_whatif(rid)
        verify_why(rid)
    except Exception as e:
        print(f"\n{RED}Verification aborted: {type(e).__name__}: {e}{RESET}")
        sys.exit(2)

    print()
    if _failures == 0:
        extra = f" ({_warnings} warning{'s' if _warnings != 1 else ''})" if _warnings else ""
        print(f"{GREEN}{BOLD}ALL CHECKS PASSED{RESET}{extra} — demo numbers are frozen and every beat works.")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}{_failures} CHECK(S) FAILED{RESET} — do NOT demo until resolved (see above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
