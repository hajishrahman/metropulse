"""
MetroPulse Phase 3 crew configuration.

Mirrors solver/config.py style:
    UPPER_SNAKE_CASE constants, grouped under # ==== section headers,
    every assumption tagged.

Tags:
    [EXTERNAL]  from KMRL rules / Metro Railways General Rules
    [DERIVED]   computed from external source
    [SYNTHETIC] project assumption
    [MODEL LIMITATION] deliberate simplification
"""

# ===========================================================================
# POOL SIZES  [SYNTHETIC — daily availability assumption]
# ===========================================================================
POOL_SIZES = [45, 50, 55]        # [SYNTHETIC] daily-active pool sizes to test
DRIVERS_CSV_TOTAL = 55           # [SYNTHETIC] total rows in drivers.csv

# ===========================================================================
# DUTY LIMITS  [EXTERNAL — Metro Railways General Rules / KMRL]
# ===========================================================================
MAX_DUTY_SEC = 28_800            # [EXTERNAL] 8 h active duty (C2)
SIGN_ON_BUFFER_SEC = 900         # [EXTERNAL] 15 min before first departure (C3)
SIGN_OFF_BUFFER_SEC = 900        # [EXTERNAL] 15 min after last arrival (C3)
TOTAL_DEPOT_CEILING_SEC = 30_600 # [DERIVED]  8h30m = 8h active + 15m + 15m

# ===========================================================================
# TURNAROUND  [SYNTHETIC]
# ===========================================================================
MIN_TURNAROUND_SEC = 300         # [SYNTHETIC] 5 min between arrival and next departure (C1)

# ===========================================================================
# CONTINUOUS DRIVING  [SYNTHETIC — typical Indian metro practice]
# ===========================================================================
MAX_CONTINUOUS_PREFERRED_SEC = 18_000   # [SYNTHETIC] 5 h preferred (C6 soft)
MAX_CONTINUOUS_RELAXED_SEC   = 21_600   # [SYNTHETIC] 6 h relax cap  (C6 fallback)


# ===========================================================================
# RESERVE  [SYNTHETIC — operational resilience]
# ============================================================================
MIN_RESERVE_DRIVERS = 5          # [SYNTHETIC] keep >= 5 drivers unused (C7)

# ===========================================================================
# REST (DEFERRED)  [EXTERNAL — fatigue rules]
# ===========================================================================
# C5 (min rest 12h between shifts) is DEFINED but NOT ENFORCED in single-day V1.
# No solver constraint and no validator check. Enforced in V2 multi-day model.
MIN_REST_BETWEEN_SHIFTS_SEC = 43_200     # [EXTERNAL] 12 h — NOT USED IN V1

# ===========================================================================
# OBJECTIVE WEIGHTS  [SYNTHETIC — initial tuning]
# ===========================================================================
W_CONTINUOUS_DRIVING = 10        # [SYNTHETIC] penalty weight for C6
W_RESERVE_BUFFER     = 15        # [SYNTHETIC] penalty weight for C7
OBJ_SCALE            = 100       # [SYNTHETIC] scales weights up like Phase 1

# ===========================================================================
# SOLVER  [SYNTHETIC]
# ===========================================================================
CP_SAT_TIME_LIMIT_SEC = 300      # [SYNTHETIC]
CP_SAT_NUM_WORKERS    = 4        # [SYNTHETIC]
CP_SAT_RANDOM_SEED    = 42       # [SYNTHETIC]

# ===========================================================================
# OUTPUT FILE NAMES
# ===========================================================================
CREW_SCHEDULE_CSV   = "crew_schedule.csv"
CREW_SOLUTION_JSON  = "crew_solution.json"
CREW_VALIDATION_JSON = "crew_validation.json"

CREW_SCHEDULE_FIELDS = ["trip_id", "driver_id", "sign_on", "sign_off", "pool_size"]