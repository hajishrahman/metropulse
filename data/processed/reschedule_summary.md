# MetroPulse — Disruption Response Summary

## Scenario A: Single Rake Breakdown
- **Disruption:** R008 fails at 18:00:00. R008: WK_189 in-progress (departed 17:14:30, arrives 18:04:55) — completes normally. Withdrawn for any future trip departing ≥ 18:00:00; trips already departed complete normally.
- **Response:** R022 activated (R022 (2,100 km); lowest km_since_last_maintenance among scheduled).
- **Result:** 18 rakes active. 4 trips withdrawn from downed rakes; 4 recovered by reassignment (100.0%); 0 dropped.
  - 250 of 250 trips served (7 unchanged on original rake, 243 reassigned to a different rake).
- **Solver status:** OPTIMAL, objective 4800.0, gap 0.0%.
- **Solve time:** 91.615 seconds.

## Scenario B: Multiple Rake Breakdowns (Capacity-Constrained)
- **Disruption:** R008, R013, R015, R002, R007 fail at 07:00:00. R008: no in-progress trip (between trips) at 07:00:00; R013: no in-progress trip (between trips) at 07:00:00; R015: no in-progress trip (between trips) at 07:00:00; R002: WK_15 in-progress (departed 06:15:00, arrives 07:07:28) — completes normally; R007: WK_6 in-progress (departed 06:15:00, arrives 07:05:28) — completes normally. Withdrawn for any future trip departing ≥ 07:00:00; trips already departed complete normally.
- **Response:** R022, R024 activated (R022 (2,100 km), R024 (3,500 km)).
- **Result:** 15 rakes active. 69 trips withdrawn from downed rakes; 55 recovered by reassignment (79.7%); 14 dropped.
  - 236 of 250 trips served (14 unchanged on original rake, 222 reassigned to a different rake).
- **Solver status:** OPTIMAL, objective 1401200.0, gap 0.0%.
- **Solve time:** 113.669 seconds.
- **Capacity floor:** 14 drops is the irreducible gap at 15 active rakes under R5/R6/R11. The remaining 236 trips are served.
- **Capacity warning:** 14 trips cannot be covered.

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
- 14 trips cannot operate due to insufficient rakes at 15 active. Of the 69 trips withdrawn from downed rakes, 55 were recovered by reassignment and 14 remained dropped.
- Estimated passenger impact: approximately 1,400 passenger journeys affected (assuming 100 passengers/trip).
- Passenger experience: affected passengers will wait 45–90 minutes for alternative service. If no alternative is available, trips should be announced as **cancelled** via PA system and app notification.
- **Operational recommendation:** Prioritize peak-hour trips for coverage. Drop off-peak trips where alternative service is available within 15 minutes. For dropped peak trips, issue delay notification first (30 min), then cancellation if no recovery.

## Honest Limitations
1. Full re-solve (~12–30s), not warm-start. Warm-start optimization is future work.
2. Rake completes current trip before withdrawal. Mid-trip abort (passenger deboarding) is out of scope.
3. No cascading delay modeling. Phase 2 integration is future work.
4. Not real-time. This is planned disruption response, not sub-second control.
5. Synthetic km data. `km_since_last_maintenance` is a SYNTHETIC proxy for reliability.
6. "Dropped" means the trip does not operate (cancelled). Passenger-impact framing ("45–90 min delay") describes the passenger *experience* of a dropped trip, not a rescheduled delay.
