# MetroPulse — Disruption Response Summary

## Scenario A: Single Rake Breakdown
- **Disruption:** R008 fails at 18:00:00. R008: WK_181 in-progress (departed 17:45:55, arrives 18:36:42) — completes normally. Withdrawn for any future trip departing ≥ 18:00:00; trips already departed complete normally.
- **Response:** R022 activated (R022 (2,100 km); lowest km_since_last_maintenance among scheduled).
- **Result:** 18 rakes active. 4 trips withdrawn from downed rakes; 4 recovered by reassignment (100.0%); 0 dropped.
  - 255 of 255 trips served (5 unchanged on original rake, 250 reassigned to a different rake).
- **Solver status:** OPTIMAL, objective 900.0, gap 0.0%.
- **Solve time:** 184.992 seconds.

## Scenario B: Multiple Rake Breakdowns (Capacity-Constrained)
- **Disruption:** R008, R013, R015, R002 fail at 07:00:00. R008: WK_8 in-progress (departed 06:30:00, arrives 07:23:38) — completes normally; R013: no in-progress trip (between trips) at 07:00:00; R015: no in-progress trip (between trips) at 07:00:00; R002: no in-progress trip (between trips) at 07:00:00. Withdrawn for any future trip departing ≥ 07:00:00; trips already departed complete normally.
- **Response:** R022, R024 activated (R022 (2,100 km), R024 (3,500 km)).
- **Result:** 16 rakes active. 53 trips withdrawn from downed rakes; 45 recovered by reassignment (84.9%); 8 dropped.
  - 247 of 255 trips served (5 unchanged on original rake, 242 reassigned to a different rake).
- **Solver status:** FEASIBLE, objective 802100.0, gap 31.62947263433487%.
- **Solve time:** 300.19 seconds.
- **Capacity floor:** 8 drops at 16 active rakes under R5/R6/R11. The remaining 247 trips are served.
- **Capacity warning:** 8 trips cannot be covered.

**DROPPED** = trip scheduled but cannot operate due to insufficient rakes.

## D3 Correction Note
The original D3 table in the Phase 5 handoff listed R019, R020, R021, R022, R023 as
"scheduled" maintenance rakes. Per D2's rule (the 2 maintenance rakes with the
**highest** initial_mileage_km become `unscheduled_repair`), the actual split on
this fleet is:

- **Unscheduled repair (blocked):** R020 (176,838 km), R023 (199,479 km) — the two
  highest-mileage maintenance rakes.
- **Scheduled (reactivatable):** R019 (4,200 km-since), R021 (6,800), R022 (2,100),
  R024 (3,500), R025 (7,200).

Therefore Scenario A activates **R022**, and Scenario B activates
**R022, R024** — the lowest-km scheduled rakes, not R020/R023.

**D4 defense (corrected):** R022 recently serviced (2,100 km), R024 next (3,500 km),
R019 near-service-due (4,200 km), R025 overdue (7,200 km). The heuristic picks R022
first — most recently serviced, safest for short-term rescue.

## Passenger Impact & Operational Recommendation

**Scenario B — dropped trips:**
- 8 trips cannot operate due to insufficient rakes at 16 active. Of the 53 trips withdrawn from downed rakes, 45 were recovered by reassignment and 8 remained dropped.
- Estimated passenger impact: approximately 800 passenger journeys affected (assuming 100 passengers/trip).
- Passenger experience: affected passengers will wait 45–90 minutes for alternative service. If no alternative is available, trips should be announced as **cancelled** via PA system and app notification.
- **Operational recommendation:** Prioritize peak-hour trips for coverage. Drop off-peak trips where alternative service is available within 15 minutes. For dropped peak trips, issue delay notification first (30 min), then cancellation if no recovery.

## Honest Limitations
1. Full re-solve (~12–30s), not warm-start. Warm-start optimization is future work.
2. Rake completes current trip before withdrawal. Mid-trip abort (passenger deboarding) is out of scope.
3. No cascading delay modeling. Phase 2 integration is future work.
4. Not real-time. This is planned disruption response, not sub-second control.
5. Synthetic km data. `km_since_last_maintenance` is a SYNTHETIC proxy for reliability.
6. "Dropped" means the trip does not operate (cancelled). Passenger-impact framing ("45–90 min delay") describes the passenger *experience* of a dropped trip, not a rescheduled delay.
