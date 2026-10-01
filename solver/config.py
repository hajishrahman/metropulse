"""
Configuration constants for the MetroPulse CP-SAT solver.

Sources:
  - KMRL published policy (driver shifts, rest rules, fleet size, depot info)
  - Industry norms (overhaul intervals, cleaning cycles)
  - Documented assumptions (marked below)

Do NOT put per-row data here. This file holds values that are the same
for every entity in a category (all drivers, all rakes, etc.).
"""

# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------
TOTAL_RAKES = 25
SERVICE_RAKES = 18
MAINTENANCE_RAKES = 7

# ---------------------------------------------------------------------------
# Driver rules (KMRL policy)
# ---------------------------------------------------------------------------
MAX_NET_DUTY_HOURS = 8                  # net driving/on-duty time
MAX_TOTAL_DUTY_HOURS = 9                # including sign-on/sign-off briefings
MAX_CONTINUOUS_DRIVING_HOURS = 4        # must take break before this
MIN_INTER_SHIFT_REST_HOURS = 12         # lower bound of KMRL 12-16h band
WEEKLY_REST_HOURS = 30                  # >=30 continuous hours per week
ROSTER_PATTERN = "6_on_1_off"
RELIEF_POINT = "Muttom_Yard"

# ---------------------------------------------------------------------------
# Maintenance thresholds (KMRL + industry norms)
# ---------------------------------------------------------------------------
MINOR_CHECK_KM = 10_000                 # A-check interval
INTERMEDIATE_OVERHAUL_KM = 420_000      # IOH (KMRL: 420k-500k, use lower)
PERIODIC_OVERHAUL_KM = 840_000          # POH (KMRL: 840k-1M, use lower)
CLEANING_INTERVAL_HOURS = 24

# ---------------------------------------------------------------------------
# Depot geometry (assumptions - KMRL does not publish exact numbers)
# ---------------------------------------------------------------------------
DEPOT_STABLING_LINES = 6                # assumption
RAKES_PER_LINE = 4                      # assumption
STACK_DEPTH = 4                         # assumption
FRACTIONAL_MAINTENANCE_CYCLE_DAYS = 3   # KMRL "one-third" rule
TERMINAL_STABLING_SHARE = 0.67          # ~2/3 at terminals

# ---------------------------------------------------------------------------
# Costs (assumptions for objective function)
# ---------------------------------------------------------------------------
COST_PER_KM_INR = 50
COST_PER_SHUNT_INR = 500
COST_PER_DELAY_MINUTE_INR = 100
PENALTY_PER_CANCELLED_TRIP_INR = 5_000

# ---------------------------------------------------------------------------
# Objective weights (alpha, beta, gamma, delta)
# ---------------------------------------------------------------------------
W_MILEAGE_BALANCE = 1.0     # O1 - minimize mileage variance
W_SHUNTING = 1.0            # O2 - minimize depot movements
W_SHIFT_FAIRNESS = 1.0      # O3 - minimize shift variance
W_STANDBY_POSITION = 1.0    # O4 - minimize depot depth for readiness