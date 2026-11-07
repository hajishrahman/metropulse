"""
MetroPulse configuration constants.

Every parameter is tagged with its source:
    [EXTERNAL]         External authoritative source
    [DERIVED FROM GTFS] Computed from GTFS data
    [SYNTHETIC]        Project assumption
    [DPR reference — removed]  Old DPR values, no longer used

Spec: docs/constraints-v2.md
"""

# ===========================================================================
# FLEET  [EXTERNAL — Annual Report 2024-25 + News 2026]
# ===========================================================================
# Total: 25 rakes
#   18 in service   [EXTERNAL — Annual Report for accomaditing peak hours
#    0 standby      [EXTERNAL — News 2026 had 3 but now 0]
#    7 maintenance  [EXTERNAL — News 2026]
SERVICE_RAKES       = 18      # [EXTERNAL — News 2026: "18 operating"]
STANDBY_RAKES       = 0       # (folded into 18 service)
MAINTENANCE_RAKES   = 7       # [EXTERNAL — News 2026]
TOTAL_FLEET         = 25      # [EXTERNAL — News 2026]

# ===========================================================================
# PHYSICAL PARAMETERS  [EXTERNAL — Annual Report + GTFS]
# ===========================================================================
SECTION_LENGTH_KM        = 28.144      # [EXTERNAL — Annual Report 2024-25]
ONE_WAY_RUNNING_MIN      = 50.47       # [EXTERNAL — GTFS median (412 trips)]
TERMINAL_TURNAROUND_MIN  = 5           # [SYNTHETIC — no verified source]
MIN_HEADWAY_DESIGN_SEC   = 90          # [SYNTHETIC]

# Derived
ROUND_TRIP_CYCLE_MIN = (2 * ONE_WAY_RUNNING_MIN
                        + 2 * TERMINAL_TURNAROUND_MIN)
                                       # ≈ 110.94 min

# ===========================================================================
# OPERATING WINDOW  [EXTERNAL — Annual Report]
# ===========================================================================
OPERATING_START_HOUR = 6               # [EXTERNAL] 06:00
OPERATING_END_HOUR   = 23              # [EXTERNAL] 23:00
NON_SERVICE_START_HOUR = 0
NON_SERVICE_END_HOUR   = 6

# ===========================================================================
# DEPOT / STABLING
# ===========================================================================
INFO_PARK_2_CAPACITY = 2               # [SYNTHETIC]
MUTTOM_CAPACITY      = None            # [MODEL LIMITATION] unbounded in V1

# ===========================================================================
# DEADHEAD  [SYNTHETIC — NOT CONFIGURED]
# ===========================================================================
MUTTOM_TO_JLN_DEADHEAD_MIN = None

# ===========================================================================
# MAINTENANCE  [SYNTHETIC]
# ===========================================================================
MAINTENANCE_THRESHOLD_KM = 1_000_000

# ===========================================================================
# HOURLY SERVICE PLAN
# ===========================================================================
# Loaded from data/hourly_service.csv (generated from GTFS)
# See data/extract_gtfs_hourly.py
# Expected: 250 weekday passenger trips, 06:00-23:00
HOURLY_SERVICE_CSV = "data/hourly_service.csv"

# ===========================================================================
# DIRECTION LABELS
# ===========================================================================
DIRECTION_UP   = "UP"
DIRECTION_DOWN = "DOWN"

# ===========================================================================
# OBJECTIVE WEIGHTS  [SYNTHETIC — INITIAL TUNING PARAMETERS]
# ===========================================================================
W_WAITING_TIME        = 10
W_HEADWAY_DEVIATION   = 5
W_OPERATIONAL_DELAY   = 5
W_EMPTY_RUNNING       = 2
W_DEPOT_MOVEMENTS     = 2
W_RAKE_BALANCE        = 3
W_RESERVE_ACTIVATION  = 1

OBJ_SCALE = 100

# ===========================================================================
# SOLVER  [SYNTHETIC]
# ===========================================================================
CP_SAT_TIME_LIMIT_SEC = 300
CP_SAT_NUM_WORKERS    = 8
CP_SAT_RANDOM_SEED    = 42

# ===========================================================================
# DELAY DISTRIBUTION  [SYNTHETIC — for Phase 2]
# ===========================================================================
DELAY_DISTRIBUTION_TYPE       = "clipped_normal"
DELAY_DISTRIBUTION_MEAN_SEC   = -48
DELAY_DISTRIBUTION_STD_SEC    = 60
DELAY_DISTRIBUTION_MIN_SEC    = 0
DELAY_DISTRIBUTION_MAX_SEC    = 300

# ===========================================================================
# PATHS  [SYNTHETIC]
# ===========================================================================
DATA_DIR          = "data"
SYNTHETIC_DIR     = "data/synthetic"
GENERATED_DIR     = "data/processed"

HOURLY_SERVICE_CSV_PATH = "data/hourly_service.csv"
RAKES_CSV               = f"{SYNTHETIC_DIR}/rakes.csv"
TERMINALS_CSV           = f"{SYNTHETIC_DIR}/terminals.csv"
MAINTENANCE_CSV         = f"{SYNTHETIC_DIR}/maintenance.csv"
DEPOT_CSV               = f"{SYNTHETIC_DIR}/depot.csv"

SOLUTION_JSON           = f"{GENERATED_DIR}/solution.json"
SCHEDULE_CSV            = f"{GENERATED_DIR}/schedule.csv"
VALIDATION_JSON         = f"{GENERATED_DIR}/validation.json"