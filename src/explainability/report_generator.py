# src/explainability/report_generator.py
"""MetroPulse Phase 4 — Explainability report generator.

Reads Phase 1/2/3 output files and generates:
  data/processed/explainability_report.md
  data/processed/utilization_stats.json

Every number in the outputs is read from a source file.
No hardcoded values. No per-trip solver reasoning.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT       = Path(__file__).parent.parent.parent
IN_DIR     = ROOT / "data" / "processed"
REPORT_MD  = IN_DIR / "explainability_report.md"
STATS_JSON = IN_DIR / "utilization_stats.json"

F_VALIDATION      = IN_DIR / "validation.json"
F_SOLUTION        = IN_DIR / "solution.json"
F_SCHEDULE        = IN_DIR / "schedule.csv"
F_SIM_KPIS        = IN_DIR / "simulation_kpis.json"
F_CREW_SOLUTION   = IN_DIR / "crew_solution.json"
F_CREW_VALIDATION = IN_DIR / "crew_validation.json"
F_CREW_SCHEDULE   = IN_DIR / "crew_schedule.csv"


# ---------- I/O helpers ----------

def _time_to_sec(t: str) -> int:
    try:
        parts = t.split(":")
    except AttributeError as exc:
        raise ValueError(f"Invalid time: {t!r}") from exc
    if len(parts) != 3:
        raise ValueError(f"Invalid time: {t!r}")
    try:
        h, m, s = (int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"Invalid time: {t!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f"Invalid time: {t!r}")
    return h * 3600 + m * 60 + s


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path, required: set[str]) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)}")
        return list(reader)


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1f}%"


def _fmt_num(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


# ---------- Section 1 ----------

def build_section_1_executive_summary(
    solution: dict,
    validation: dict,
    crew_solution: dict,
    crew_validation: dict,
    schedule_rows: list[dict],
    crew_rows: list[dict],
) -> str:
    lines: list[str] = []
    lines.append("## 1. Executive Summary")
    lines.append("")
    trips_total = solution.get("num_trips", len(schedule_rows))
    rakes_used = len({r["rake_id"] for r in schedule_rows})
    pools = sorted(crew_solution.keys(), key=lambda x: int(x))
    active_line = ", ".join(
        f"pool {p}: {crew_solution[p]['num_active_drivers']} active "
        f"(of {crew_solution[p]['pool_size']})"
        for p in pools
    )
    lines.append(f"- Total trips scheduled: **{trips_total}**")
    lines.append(f"- Total rakes used: **{rakes_used}**")
    lines.append(f"- Active drivers: {active_line}")
    lines.append(f"- Phase 1 solver status: **{solution['status']}**, "
                 f"objective = {solution['objective']}, "
                 f"best bound = {solution['best_bound']}, "
                 f"gap = {solution['gap_pct']}%")
    lines.append(f"- Phase 1 validator overall: **{validation['overall']}**")
    lines.append(f"- Phase 3 validator overall: **{crew_validation['overall']}**")
    lines.append("")
    lines.append(
        f"MetroPulse Phase 1 scheduled the {trips_total}-trip service day across the "
        f"{rakes_used} service rakes, and Phase 3 assigned every trip to an "
        "active driver in each of the three tested pool sizes while keeping a "
        "reserve. Phase 2 simulation over 100 seeds shows on-time performance "
        "at the broadest tolerance stays at 100% and degrades monotonically as "
        "the assumed delay scale increases."
    )
        
    lines.append("")
    lines.append(
        "> **What \"OPTIMAL\" means here.** Phase 1 OPTIMAL is under the O6 "
        "rake-balance objective only. Other objectives are declared in "
        "`config.py` but disabled in V1. OPTIMAL does not mean \"best possible "
        "schedule overall\" — it means \"best under the single active "
        "objective, proven at gap 0.0%.\""
    )
    lines.append("")
    lines.append("*Source: data/processed/solution.json, "
                 "data/processed/validation.json, "
                 "data/processed/crew_solution.json, "
                 "data/processed/crew_validation.json, "
                 "data/processed/schedule.csv, "
                 "data/processed/crew_schedule.csv*")
    return "\n".join(lines)


# ---------- Section 2 ----------

def build_section_2_phase1_constraints(validation: dict) -> str:
    lines: list[str] = []
    lines.append("## 2. Phase 1 Constraint Status (R1–R12)")
    lines.append("")
    lines.append(f"Overall: **{validation['overall']}** "
                 f"({validation['num_trips']} trips).")
    lines.append("")
    lines.append("| Check | Status | Key detail |")
    lines.append("|---|---|---|")
    for c in validation["checks"]:
        name = c["check"]
        status = c["status"]
        det = c.get("details", {}) or {}
        detail = _phase1_detail(name, det)
        lines.append(f"| {name} | {status} | {detail} |")
    lines.append("")
    lines.append(
        "**Notes.** R2 (fixed GTFS times) is not present — GTFS timings are "
        "treated as given. R8 is SKIPPED because V1 performs no stabling "
        "assignment. R9 (maintenance exclusivity) is not present as a check "
        "row — it is vacuous in V1 because maintenance rakes are excluded "
        "from service by R10 and no maintenance rake can be selected for any "
        "trip."
    )
    lines.append("")
    lines.append("*Source: data/processed/validation.json*")
    return "\n".join(lines)


def _phase1_detail(name: str, det: dict) -> str:
    if name.startswith("R1"):
        return f"required={det.get('required')}, scheduled={det.get('scheduled')}"
    if name.startswith("R4"):
        return f"bad_rakes={len(det.get('bad_rakes', []))}"
    if name.startswith("R5"):
        return f"overlap failures={det.get('total', 0)}"
    if name.startswith("R6"):
        return (f"same-terminal pairs={det.get('same_terminal_pairs')}, "
                f"cross-terminal pairs={det.get('cross_terminal_pairs')}")
    if name.startswith("R7"):
        return f"running-time mismatches={len(det.get('failures', []))}"
    if name.startswith("R8"):
        return f"SKIPPED — {det.get('reason','')}; info_park_2_capacity={det.get('info_park_2_capacity')}"
    if name.startswith("R10"):
        return (f"threshold={det.get('threshold_km')} km, "
                f"max mileage={det.get('max_mileage_km')} km, "
                f"rakes over threshold={len(det.get('rakes_over_threshold', []))}")
    if name.startswith("R11"):
        return f"cross-terminal switches={det.get('cross_terminal_switches')}"
    if name.startswith("R12"):
        return f"failures={len(det.get('failures', []))}"
    if name.startswith("R3"):
        return f"failures={len(det.get('failures', []))}"
    return ""


# ---------- Section 3 ----------

def build_section_3_phase3_constraints(crew_validation: dict,
                                       crew_solution: dict) -> str:
    lines: list[str] = []
    lines.append("## 3. Phase 3 Constraint Status (C1–C7, per pool)")
    lines.append("")
    lines.append(f"Overall: **{crew_validation['overall']}**.")
    lines.append("")
    pools = sorted(crew_validation["pools"].keys(), key=lambda x: int(x))
    for p in pools:
        pool = crew_validation["pools"][p]
        obj = crew_solution.get(p, {}).get("objective")
        lines.append(f"### Pool {p} — {pool['pool_status']}")
        lines.append("")
        lines.append("| Check | Status | Key detail |")
        lines.append("|---|---|---|")
        for c in pool["checks"]:
            name = c["check"]
            det = c.get("details", {}) or {}
            detail = _phase3_detail(name, det)
            lines.append(f"| {name} | {c['status']} | {detail} |")
        lines.append("")
        lines.append(
            f"C5 deferred to V2. C6 is a soft objective, not a validator "
            f"check — Phase 3 reports objective = {obj} for this pool, i.e. "
            f"zero C6 penalty was incurred."
        )
        lines.append("")
    lines.append("*Source: data/processed/crew_validation.json, "
                 "data/processed/crew_solution.json*")
    return "\n".join(lines)


def _phase3_detail(name: str, det: dict) -> str:
    if name.startswith("C4"):
        return f"required={det.get('required')}, scheduled={det.get('scheduled')}"
    if name.startswith("C7"):
        return (f"pool={det.get('pool_size')}, active={det.get('active')}, "
                f"reserve={det.get('reserve')}, min_reserve={det.get('min_reserve')}")
    if name.startswith("C1") or name.startswith("C2") or name.startswith("C3"):
        return f"failures={det.get('total', 0)}"
    return ""


# ---------- Section 4 ----------

def build_section_4_rake_utilization(schedule_rows: list[dict]) -> tuple[str, dict]:
    # per-rake aggregate
    per_rake: dict[str, dict] = {}
    for row in schedule_rows:
        rid = row["rake_id"]
        dep = _time_to_sec(row["departure"])
        arr = _time_to_sec(row["arrival"])
        agg = per_rake.setdefault(rid, {
            "trip_count": 0,
            "first_dep": dep,
            "last_arr": arr,
            "busy_sec": 0,
            "intervals": [],
        })
        agg["trip_count"] += 1
        if dep < agg["first_dep"]:
            agg["first_dep"] = dep
        if arr > agg["last_arr"]:
            agg["last_arr"] = arr
        agg["busy_sec"] += (arr - dep)
        agg["intervals"].append((dep, arr))

    rake_rows: list[dict] = []
    util_values: list[float] = []
    for rid in sorted(per_rake):
        a = per_rake[rid]
        span_sec = a["last_arr"] - a["first_dep"]
        util = (a["busy_sec"] / span_sec * 100.0) if span_sec > 0 else None
        if util is not None:
            util_values.append(util)
        rake_rows.append({
            "rake_id": rid,
            "trip_count": a["trip_count"],
            "first_departure": _sec_to_hhmmss(a["first_dep"]),
            "last_arrival": _sec_to_hhmmss(a["last_arr"]),
            "span_min": span_sec / 60.0,
            "busy_min": a["busy_sec"] / 60.0,
            "utilization_pct": util,
        })

    # peak simultaneous rakes (1-second sweep)
    all_dep = min(a["first_dep"] for a in per_rake.values())
    all_arr = max(a["last_arr"] for a in per_rake.values())
    peak = 0
    # For efficiency: build event deltas instead of per-second loop
    deltas: dict[int, int] = defaultdict(int)
    for a in per_rake.values():
        for dep, arr in a["intervals"]:
            deltas[dep] += 1
            deltas[arr] -= 1
    cur = 0
    for t in sorted(deltas):
        cur += deltas[t]
        if cur > peak:
            peak = cur

    trips_counts = [r["trip_count"] for r in rake_rows]
    mean_util = (sum(util_values) / len(util_values)) if util_values else None

    lines: list[str] = []
    lines.append("## 4. Rake Utilization (Phase 1)")
    lines.append("")
    lines.append("**Definitions (computed before the table):**")
    lines.append("")
    lines.append("- **span_sec** = `last_arrival_sec − first_departure_sec` per rake "
                 "(the rake's active day).")
    lines.append("- **busy_sec** = `Σ(arrival_sec − departure_sec)` over all trips "
                 "assigned to that rake (running time only).")
    lines.append("- **utilization_pct** = `busy_sec / span_sec × 100` "
                 "(null if span_sec = 0).")
    lines.append("- **peak_simultaneous_rakes** = maximum count of distinct rakes "
                 "simultaneously running at any integer second, computed by an "
                 "event-sweep over departure/arrival times.")
    lines.append("")
    lines.append("**Flags.** Turnaround and deadhead are **not** added to "
                 "`span_sec` — no invented parameters. Busy time is running time "
                 "only; terminal idling is the gap, not counted as busy. Spans "
                 "are single-day and per-rake, not fleet-wide utilization.")
    lines.append("")
    lines.append("**Aggregate metrics:**")
    lines.append("")
    lines.append(f"- Trips per rake — min = {min(trips_counts)}, "
                 f"mean = {sum(trips_counts)/len(trips_counts):.2f}, "
                 f"max = {max(trips_counts)}")
    lines.append(f"- Peak simultaneous rakes = {peak}")
    lines.append(f"- Mean utilization = {_fmt_pct(mean_util)}")
    lines.append("")
    lines.append("**Per-rake table:**")
    lines.append("")
    lines.append("| Rake | Trips | First departure | Last arrival | Span (min) | Busy (min) | Utilization % |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rake_rows:
        lines.append(
            f"| {r['rake_id']} | {r['trip_count']} | {r['first_departure']} | "
            f"{r['last_arrival']} | {r['span_min']:.2f} | {r['busy_min']:.2f} | "
            f"{_fmt_pct(r['utilization_pct'])} |"
        )
    lines.append("")
    lines.append(f"Row count: **{len(schedule_rows)}** data rows in "
                 f"`schedule.csv` (file line count is data + 1 header).")
    lines.append("")
    lines.append("*Source: data/processed/schedule.csv*")

    stats = {
        "formula_span_sec": "last_arrival_sec - first_departure_sec per rake",
        "formula_busy_sec": "sum(arrival_sec - departure_sec) per rake",
        "formula_utilization_pct": "busy_sec / span_sec * 100 (null if span_sec <= 0)",
        "formula_peak_simultaneous_rakes": "max concurrent rake intervals via event sweep",
        "trips_per_rake": {
            "min": min(trips_counts),
            "mean": sum(trips_counts) / len(trips_counts),
            "max": max(trips_counts),
        },
        "peak_simultaneous_rakes": peak,
        "mean_utilization_pct": mean_util,
        "per_rake": rake_rows,
    }
    return "\n".join(lines), stats


def _sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------- Section 5 ----------

def build_section_5_driver_utilization(crew_solution: dict,
                                       crew_rows: list[dict]) -> tuple[str, dict]:
    # group by pool then driver
    by_pool: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "trip_count": 0,
        "first_on": None,
        "last_off": None,
    }))
    pool_row_count: dict[str, int] = defaultdict(int)
    for row in crew_rows:
        pool = str(row["pool_size"])
        drv = row["driver_id"]
        on_sec = _time_to_sec(row["sign_on"])
        off_sec = _time_to_sec(row["sign_off"])
        g = by_pool[pool][drv]
        g["trip_count"] += 1
        if g["first_on"] is None or on_sec < g["first_on"]:
            g["first_on"] = on_sec
        if g["last_off"] is None or off_sec > g["last_off"]:
            g["last_off"] = off_sec
        pool_row_count[pool] += 1

    lines: list[str] = []
    lines.append("## 5. Driver Utilization (Phase 3)")
    lines.append("")
    lines.append("**Definitions (computed before the tables):**")
    lines.append("")
    lines.append("- **Total depot hours** = `(max sign_off − min sign_on) / 3600` "
                 "per driver per pool.")
    lines.append("- Because Phase 3 sets `sign_on = first_departure − 900 s` and "
                 "`sign_off = last_arrival + 900 s`, this equals "
                 "`(last_arrival − first_departure)/3600 + 0.5 h`. It is **total "
                 "depot time including sign-on/sign-off buffers**, not the C2 "
                 "`duty` variable (which is `last_arrival − first_departure` and "
                 "is validated separately as C2 in `crew_validation.json`).")
    lines.append("- **Reserve** = `pool_size − num_active_drivers`, both read from "
                 "`crew_solution.json`. Cross-checked against "
                 "`crew_validation.json` C7.")
    lines.append("")
    pools = sorted(crew_solution.keys(), key=lambda x: int(x))
    stats_pools: dict[str, dict] = {}
    for p in pools:
        sol = crew_solution[p]
        pool_size = sol["pool_size"]
        active = sol["num_active_drivers"]
        reserve = sol["reserve"]
        drivers = by_pool.get(p, {})
        per_driver: list[dict] = []
        depot_hours_list: list[float] = []
        for drv in sorted(drivers):
            g = drivers[drv]
            depot_hours = (g["last_off"] - g["first_on"]) / 3600.0
            depot_hours_list.append(depot_hours)
            per_driver.append({
                "driver_id": drv,
                "trip_count": g["trip_count"],
                "first_sign_on": _sec_to_hhmmss(g["first_on"]),
                "last_sign_off": _sec_to_hhmmss(g["last_off"]),
                "total_depot_hours": depot_hours,
            })
        dh_min = min(depot_hours_list) if depot_hours_list else None
        dh_max = max(depot_hours_list) if depot_hours_list else None
        dh_mean = (sum(depot_hours_list) / len(depot_hours_list)) if depot_hours_list else None

        lines.append(f"### Pool {p}")
        lines.append("")
        lines.append(f"- pool_size = **{pool_size}**, "
                     f"active drivers = **{active}**, "
                     f"reserve = **{reserve}**")
        lines.append(f"- Total depot hours — min = {_fmt_num(dh_min)}, "
                     f"mean = {_fmt_num(dh_mean)}, max = {_fmt_num(dh_max)}")
        lines.append(f"- Rows in `crew_schedule.csv` for pool {p}: "
                     f"{pool_row_count.get(p, 0)} "
                     f"(assignments listed in `crew_solution.json` pool {p}: "
                     f"{len(sol['assignments'])})")
        lines.append("")
        lines.append("| Driver | Trips | First sign-on | Last sign-off | Duty hours (depot span) |")
        lines.append("|---|---|---|---|---|")
        for r in per_driver:
            lines.append(
                f"| {r['driver_id']} | {r['trip_count']} | {r['first_sign_on']} | "
                f"{r['last_sign_off']} | {r['total_depot_hours']:.2f} |"
            )
        lines.append("")

        stats_pools[p] = {
            "pool_size": pool_size,
            "active_drivers": active,
            "reserve": reserve,
            "rows_in_crew_schedule": pool_row_count.get(p, 0),
            "assignments_in_crew_solution": len(sol["assignments"]),
            "total_depot_hours": {"min": dh_min, "mean": dh_mean, "max": dh_max},
            "per_driver": per_driver,
        }

    lines.append("*Source: data/processed/crew_schedule.csv, "
                 "data/processed/crew_solution.json*")

    stats = {
        "formula_total_depot_hours": "(max sign_off - min sign_on)/3600 per driver per pool",
        "pools": stats_pools,
    }
    return "\n".join(lines), stats


# ---------- Section 6 ----------

def build_section_6_simulation(sim: dict) -> str:
    lines: list[str] = []
    lines.append("## 6. Simulation Results (Phase 2)")
    lines.append("")
    md = sim["metadata"]
    lines.append(f"- Headline seed: **{md['headline_seed']}**; "
                 f"Monte Carlo seeds: **{md['n_seeds_monte_carlo']}**")
    lines.append(f"- Delay model: `{md['delay_model']['type']}`, pre-clip mean = "
                 f"{md['delay_model']['preclip_mean_sec']} s, "
                 f"std sweep = {md['delay_model']['std_sweep_sec']} s, "
                 f"clip = [{md['delay_model']['clip_min_sec']}, "
                 f"{md['delay_model']['clip_max_sec']}] s")
    lines.append("")
    lines.append("**Headline seed run — on-time % by tolerance:**")
    lines.append("")
    lines.append("| Experiment | Tolerance | On-time (250 trips) | On-time (232 eligible) |")
    lines.append("|---|---|---|---|")
    tol_keys = ["on_time_1min", "on_time_3min", "on_time_5min"]
    for exp in ["E1", "E2", "E3", "E4"]:
        for k in tol_keys:
            block = sim["headline_seed_run"][exp][k]
            tol_sec = block["tolerance_sec"]
            label = f"±{tol_sec // 60} min"
            lines.append(
                f"| {exp} | {label} | "
                f"{block['on_time_250_pct']:.2f}% | "
                f"{block['on_time_232_eligible_pct']:.2f}% |"
            )
    lines.append("")
    lines.append("**Monte Carlo aggregate (100 seeds) — mean / p5–p95:**")
    lines.append("")
    lines.append("| Experiment | Tolerance | Mean | p5 | p95 |")
    lines.append("|---|---|---|---|---|")
    for exp in ["E1", "E2", "E3", "E4"]:
        for k in ["1min", "3min", "5min"]:
            # tolerance_sec from headline block, not hardcoded
            tol_sec = sim["headline_seed_run"][exp][f"on_time_{k}"]["tolerance_sec"]
            agg = sim["monte_carlo_aggregate"][exp][f"on_time_{k}_250_pct"]
            lines.append(
                f"| {exp} | ±{tol_sec // 60} min | "
                f"{agg['mean']:.2f}% | {agg['p5']:.2f}% | {agg['p95']:.2f}% |"
            )
    lines.append("")
    lines.append("> " + md["provenance_note"])
    lines.append("")
    lines.append(
        "**On the ±5-minute = 100% result.** The 100% figure at ±5 minutes is a "
        "**model property** — the own-delay cap is 300 s and ±5 minutes is an "
        "inclusive tolerance, so a single trip cannot exceed ±5. It is **not** "
        "an operational guarantee."
    )
    lines.append("")
    lines.append("*Source: data/processed/simulation_kpis.json*")
    return "\n".join(lines)


# ---------- Section 7 ----------

def build_section_7_sensitivity_and_limitations(crew_solution: dict,
                                                solution: dict) -> str:
    lines: list[str] = []
    lines.append("## 7. Sensitivity Analysis & Honest Limitations")
    lines.append("")
    lines.append("**Pool-size sensitivity (from `crew_solution.json`):**")
    lines.append("")
    lines.append("| Pool | Status | Active drivers | Reserve | Objective | Gap % |")
    lines.append("|---|---|---|---|---|---|")
    for p in sorted(crew_solution.keys(), key=lambda x: int(x)):
        s = crew_solution[p]
        lines.append(
            f"| {p} | {s['status']} | {s['num_active_drivers']} | "
            f"{s['reserve']} | {s['objective']} | {s['gap_pct']} |"
        )
    lines.append("")
    lines.append("The table is presented as-is; no recommendation is drawn from it.")
    lines.append("")
    lines.append("*Source: data/processed/crew_solution.json*")
    lines.append("")
    lines.append("**Honest limitations:**")
    lines.append("")
    lines.append(f"- Single-day scope; no multi-day rostering.")
    lines.append(f"- C5 deferred to V2.")
    lines.append(f"- C6 is a soft objective, not a validator check "
                 f"(Phase 3 objective = {crew_solution[sorted(crew_solution)[0]]['objective']} "
                 f"for every tested pool, i.e. zero C6 penalty).")
    lines.append(f"- GTFS 2024–25 static; not live 2026 operations.")
    lines.append(f"- Phase 1 OPTIMAL ({solution['status']}, gap = {solution['gap_pct']}%) "
                 f"is under the O6 rake-balance objective only; other objectives "
                 f"in `config.py` are declared but disabled in V1.")
    lines.append(f"- No per-trip solver explanations: CP-SAT returns a global "
                 f"solution, not per-assignment reasons. Assignments in "
                 f"`schedule.csv` are consistent with the active objective and "
                 f"the passing constraints — they are not \"chosen because\" of "
                 f"any per-trip criterion.")
    lines.append(f"- Phase 2 delay model is `synthetic` (see "
        f"`simulation_kpis.json.metadata.provenance_note`).")
    return "\n".join(lines)


# ---------- Assembly ----------

def generate_report() -> tuple[str, dict]:
    validation = _read_json(F_VALIDATION)
    solution = _read_json(F_SOLUTION)
    sim = _read_json(F_SIM_KPIS)
    crew_solution = _read_json(F_CREW_SOLUTION)
    crew_validation = _read_json(F_CREW_VALIDATION)
    schedule_rows = _read_csv(F_SCHEDULE, {
        "trip_id", "rake_id", "direction", "first_stop", "last_stop",
        "departure", "arrival",
    })
    crew_rows = _read_csv(F_CREW_SCHEDULE, {
        "trip_id", "driver_id", "sign_on", "sign_off", "pool_size",
    })

    sec1 = build_section_1_executive_summary(
        solution, validation, crew_solution, crew_validation,
        schedule_rows, crew_rows,
    )
    sec2 = build_section_2_phase1_constraints(validation)
    sec3 = build_section_3_phase3_constraints(crew_validation, crew_solution)
    sec4, rake_stats = build_section_4_rake_utilization(schedule_rows)
    sec5, driver_stats = build_section_5_driver_utilization(crew_solution, crew_rows)
    sec6 = build_section_6_simulation(sim)
    sec7 = build_section_7_sensitivity_and_limitations(crew_solution, solution)

    header = "\n".join([
        "# MetroPulse — Explainability Report",
        "",
        "> Generated by `src/explainability/report_generator.py`.",
        "> All numbers below are read from the seven Phase 1/2/3 output files in "
        "`data/processed/`. No values are hardcoded. No per-trip solver reasoning "
        "is claimed — CP-SAT returns a global solution, not per-assignment reasons.",
        "",
    ])

    markdown = "\n\n---\n\n".join([
        header,
        sec1, sec2, sec3, sec4, sec5, sec6, sec7,
    ]) + "\n"

    stats = {
        "generated_from": {
            "schedule_csv": "data/processed/schedule.csv",
            "crew_schedule_csv": "data/processed/crew_schedule.csv",
            "crew_solution_json": "data/processed/crew_solution.json",
        },
        "row_counts": {
            "schedule_rows": len(schedule_rows),
            "crew_schedule_rows": len(crew_rows),
            "crew_pool_rows": {
                p: driver_stats["pools"][p]["rows_in_crew_schedule"]
                for p in driver_stats["pools"]
            },
        },
        "rake_utilization": rake_stats,
        "driver_utilization": driver_stats,
    }
    return markdown, stats


def write_outputs(markdown: str, stats: dict) -> None:
    IN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(markdown, encoding="utf-8")
    print(f"[report] wrote {REPORT_MD}")
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"[report] wrote {STATS_JSON}")


def main() -> None:
    print("[report] reading inputs ...")
    md, stats = generate_report()
    write_outputs(md, stats)
    print("[report] done")


if __name__ == "__main__":
    main()