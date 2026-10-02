"""
MetroPulse configuration constants.

Every parameter is tagged with its source:
    [DPR]              Directly stated in KMRL Phase-II DPR
    [DERIVED FROM DPR] Mathematically computed from DPR values
    [EXTERNAL]         External authoritative source (Railway Board, law)
    [SYNTHETIC]        Project assumption for experimentation
    [ML]               ML prediction layer (not used in V1)

Spec: docs/constraints-v2.md
Do NOT modify values without updating the spec first.
"""

# ===========================================================================
# FLEET  [DPR]
# ===========================================================================
BARE_RAKE_REQUIREMENT        = 15          # [DPR]
TRAFFIC_SPARE                = 1           # [DPR]
MAINTENANCE_SPARE            = 2           # [DPR]
RAKE_REQUIREMENT_2043_2048   = 18          # [DPR]  = 15 + 1 + 2

# Phase I fleet count — [EXTERNAL, UNVERIFIED], not used in V1
ACTUAL_FLEET_PHASE_I_II      = 25          # [EXTERNAL — UNVERIFIED]

# ===========================================================================
# PHYSICAL PARAMETERS
# ===========================================================================
SECTION_LENGTH_KM            = 10.715      # [DPR]
SCHEDULE_SPEED_KMH           = 34.0        # [DPR]
TERMINAL_TURNAROUND_MIN      = 3           # [DPR]
MIN_HEADWAY_DESIGN_SEC       = 90          # [DPR] signalling design headway
SUSTAINED_HEADWAY_MIN        = 2.0         # [DPR] sustained operation up to 2 min

# Derived
ONE_WAY_RUNNING_MIN          = (SECTION_LENGTH_KM / SCHEDULE_SPEED_KMH) * 60
                                             # ≈ 18.9  [DERIVED FROM DPR]
ROUND_TRIP_CYCLE_MIN         = (2 * ONE_WAY_RUNNING_MIN
                                + 2 * TERMINAL_TURNAROUND_MIN)
                                             # ≈ 43.8  [DERIVED FROM DPR]

# ===========================================================================
# OPERATING WINDOW  [DPR]
# ===========================================================================
OPERATING_START_HOUR         = 5           # [DPR] 05:00
OPERATING_END_HOUR           = 24          # [DPR] 24:00
NON_SERVICE_START_HOUR       = 0           # [DPR] 00:00
NON_SERVICE_END_HOUR         = 5           # [DPR] 05:00

# ===========================================================================
# DEPOT / STABLING
# ===========================================================================
INFO_PARK_2_CAPACITY         = 2           # [DPR]
MUTTOM_CAPACITY              = None        # [MODEL LIMITATION] unbounded in V1

# ===========================================================================
# DEADHEAD  [SYNTHETIC — NOT CONFIGURED]
# ===========================================================================
MUTTOM_TO_JLN_DEADHEAD_MIN   = None        # [SYNTHETIC] must be set to enable

# ===========================================================================
# MAINTENANCE
# ===========================================================================
MAINTENANCE_THRESHOLD_KM     = 1_000_000   # [DPR reference — bogie overhaul]
                                            # Configurable; not statutory
# NOTE: IOH = 420,000 km was [SYNTHETIC], removed.

# ===========================================================================
# DPR HOURLY SERVICE PLAN — 2043/2048
# Source: DPR hourly train operation table
# Use train-count as authoritative; keep published headway for objective.
# ===========================================================================
# Format: (hour_start, hour_end, target_headway_min, up_departures, down_departures)
# 19:00–20:00 row preserved as-is per data-quality note (5 min target but 15 count).

DPR_HOURLY_PLAN_2043_2048 = [
    (5,  6,  10.0, 6,  6),
    (6,  7,   7.5, 8,  8),
    (7,  8,   5.0, 12, 12),
    (8,  9,   3.0, 20, 20),
    (9,  10,  3.0, 20, 20),
    (10, 11,  5.0, 12, 12),
    (11, 12,  7.5, 8,  8),
    (12, 13, 10.0, 6,  6),
    (13, 14, 12.0, 5,  5),
    (14, 15, 12.0, 5,  5),
    (15, 16, 10.0, 6,  6),
    (16, 17,  5.0, 12, 12),
    (17, 18,  3.0, 20, 20),
    (18, 19,  3.0, 20, 20),
    (19, 20,  5.0, 15, 15),   # DPR inconsistency — see spec §4.1
    (20, 21,  6.0, 10, 10),
    (21, 22,  7.5, 8,  8),
    (22, 23, 10.0, 6,  6),
    (23, 24, 12.0, 5,  5),
]
# Total: 204 UP + 204 DOWN = 408 [DPR]

# ===========================================================================
# DIRECTION LABELS
# ===========================================================================
DIRECTION_UP   = "UP"      # [DPR label]
DIRECTION_DOWN = "DOWN"    # [DPR label]

# Interpretation (subject to verification against DPR route section):
#   UP   = increasing station sequence
#   DOWN = decreasing station sequence

# ===========================================================================
# OBJECTIVE WEIGHTS  [SYNTHETIC — INITIAL TUNING PARAMETERS]
# ===========================================================================
W_WAITING_TIME        = 10   # O1  [SYNTHETIC]
W_HEADWAY_DEVIATION   = 5    # O2  [SYNTHETIC]
W_OPERATIONAL_DELAY   = 5    # O3  [SYNTHETIC]
W_EMPTY_RUNNING       = 2    # O4  [SYNTHETIC] — inactive in V1
W_DEPOT_MOVEMENTS     = 2    # O5  [SYNTHETIC] — inactive in V1
W_RAKE_BALANCE        = 3    # O6  [SYNTHETIC]
W_RESERVE_ACTIVATION  = 1    # O7  [SYNTHETIC]

# Objective scaling (CP-SAT uses integer coefficients)
OBJ_SCALE             = 100

# ===========================================================================
# SOLVER  [SYNTHETIC]
# ===========================================================================
CP_SAT_TIME_LIMIT_SEC = 300   # [SYNTHETIC] V1 single-day scenario
CP_SAT_NUM_WORKERS    = 8    # [SYNTHETIC]
CP_SAT_RANDOM_SEED    = 42   # [SYNTHETIC]

# ===========================================================================
# SCENARIO SELECTOR  [SYNTHETIC]
# ===========================================================================
SCENARIO_BASELINE_DPR = "DPR_2043_2048"
ACTIVE_SCENARIO       = SCENARIO_BASELINE_DPR

# ===========================================================================
# DELAY DISTRIBUTION  [SYNTHETIC — for future SimPy robustness scenario]
# ===========================================================================
DELAY_DISTRIBUTION_TYPE       = "truncated_normal"   # [SYNTHETIC]
DELAY_DISTRIBUTION_MEAN_SEC   = 0                    # [SYNTHETIC]
DELAY_DISTRIBUTION_STD_SEC    = 0                    # [SYNTHETIC]
DELAY_DISTRIBUTION_MIN_SEC    = 0                    # [SYNTHETIC]
DELAY_DISTRIBUTION_MAX_SEC    = 0                    # [SYNTHETIC]
# Not used in V1; populated for Scenario F later.

# ===========================================================================
# PATHS  [SYNTHETIC]
# ===========================================================================
DATA_DIR          = "data"
DPR_DATA_DIR      = "data/dpr"
SYNTHETIC_DIR     = "data/synthetic"
GENERATED_DIR     = "data/processed"

HOURLY_SERVICE_CSV = f"{DPR_DATA_DIR}/hourly_service.csv"
RAKES_CSV          = f"{SYNTHETIC_DIR}/rakes.csv"
TERMINALS_CSV      = f"{SYNTHETIC_DIR}/terminals.csv"
MAINTENANCE_CSV    = f"{SYNTHETIC_DIR}/maintenance.csv"
DEPOT_CSV          = f"{SYNTHETIC_DIR}/depot.csv"

SOLUTION_JSON      = f"{GENERATED_DIR}/solution.json"
SCHEDULE_CSV       = f"{GENERATED_DIR}/schedule.csv"
VALIDATION_JSON    = f"{GENERATED_DIR}/validation.json"