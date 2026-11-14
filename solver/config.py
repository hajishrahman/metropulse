"""
MetroPulse configuration.

Tags:
    [EXTERNAL]  from GTFS / Annual Report / news
    [DERIVED]   computed from external source
    [SYNTHETIC] project assumption
    [MODEL LIMITATION] deliberate simplification
"""

# ===========================================================================
# FLEET  [EXTERNAL — Annual Report 2024-25 + News 2026]
# ===========================================================================
SERVICE_RAKES = 18          # [EXTERNAL — News 2026 "18 operating"]
MAINTENANCE_RAKES = 7       # [EXTERNAL — News 2026]
TOTAL_FLEET = 25            # [EXTERNAL — News 2026]

# Initial split (fixed, not solver choice).
# 9 / 9 / 0 verified OPTIMAL under correct R6 and R11 on the 255-trip model
# (objective 900, gap 0.0%, 2026-11-14). The earlier 9 / 7 / 2 split was
# forced by the home-lock pruning rule, which has been removed.
INITIAL_RAKES_AT_ALVA = 9    # [SYNTHETIC]
INITIAL_RAKES_AT_TPHT = 9    # [SYNTHETIC]
INITIAL_RAKES_AT_MUTTOM = 0  # [SYNTHETIC] no MUTT-home service rakes in 255-trip V1

assert (
    INITIAL_RAKES_AT_ALVA + INITIAL_RAKES_AT_TPHT + INITIAL_RAKES_AT_MUTTOM
    == SERVICE_RAKES
), (
    f"Initial rake split {INITIAL_RAKES_AT_ALVA}/{INITIAL_RAKES_AT_TPHT}/"
    f"{INITIAL_RAKES_AT_MUTTOM} does not sum to SERVICE_RAKES={SERVICE_RAKES}"
)

# ===========================================================================
# PHYSICAL PARAMETERS
# ===========================================================================
SECTION_LENGTH_KM = 28.144          # [EXTERNAL — Annual Report]
ONE_WAY_RUNNING_MIN = 50.47         # [DERIVED] GTFS median — summary only, not solver input
TERMINAL_TURNAROUND_MIN = 5         # [SYNTHETIC]

# ===========================================================================
# OPERATING WINDOW  [EXTERNAL — GTFS 2024-25 WK trips; widened from Annual Report
# 06:00-23:00 to include 5 positioning/depot movements: WK_4, WK_256, WK_18,
# WK_12, WK_253. 255 trips total.]
# ===========================================================================
OPERATING_START_SEC = 4 * 3600 + 40 * 60    # 04:40:00
OPERATING_END_SEC = 24 * 3600               # 24:00:00 (exclusive)
OPERATING_START_HOUR = OPERATING_START_SEC // 3600
OPERATING_END_HOUR = OPERATING_END_SEC // 3600

# ===========================================================================
# DEPOT  [SYNTHETIC / MODEL LIMITATION]
# ===========================================================================
INFO_PARK_2_CAPACITY = 2            # [SYNTHETIC]
MUTTOM_CAPACITY = None              # [MODEL LIMITATION] unbounded

# ===========================================================================
# DEADHEAD  [SYNTHETIC — NOT CONFIGURED]
# ===========================================================================
TERMINAL_TO_TERMINAL_DEADHEAD_MIN = 15   # [SYNTHETIC] ALVA <-> TPHT deadhead time
MUTTOM_TO_TERMINAL_DEADHEAD_MIN = 8      # [SYNTHETIC] MUTT <-> ALVA/TPHT deadhead
# Note: deadhead is undefined for non-terminal, non-MUTT stops (e.g., KVTR).
# Such stops can only be reached by a rake ending a previous trip there.

# ===========================================================================
# MAINTENANCE  [SYNTHETIC]
# ===========================================================================
MAINTENANCE_THRESHOLD_KM = 1_000_000

# ===========================================================================
# DATA PATHS
# ===========================================================================
DATA_DIR = "data"
SYNTHETIC_DIR = "data/synthetic"
GENERATED_DIR = "data/processed"

HOURLY_SERVICE_CSV = "data/hourly_service.csv"        # reconciliation only

RAKES_CSV = f"{SYNTHETIC_DIR}/rakes.csv"
TERMINALS_CSV = f"{SYNTHETIC_DIR}/terminals.csv"
MAINTENANCE_CSV = f"{SYNTHETIC_DIR}/maintenance.csv"
DEPOT_CSV = f"{SYNTHETIC_DIR}/depot.csv"

SOLUTION_JSON = f"{GENERATED_DIR}/solution.json"
SCHEDULE_CSV = f"{GENERATED_DIR}/schedule.csv"
VALIDATION_JSON = f"{GENERATED_DIR}/validation.json"

# ===========================================================================
# DIRECTION LABELS
# ===========================================================================
DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"

# ===========================================================================
# OBJECTIVE WEIGHTS  [SYNTHETIC — INITIAL TUNING]
# ===========================================================================
W_WAITING_TIME = 10
W_RAKE_BALANCE = 3
W_RESERVE_ACTIVATION = 1
OBJ_SCALE = 100

# ===========================================================================
# SOLVER  [SYNTHETIC]
# ===========================================================================
CP_SAT_TIME_LIMIT_SEC = 300
CP_SAT_NUM_WORKERS = 4
CP_SAT_RANDOM_SEED = 42

# ===========================================================================
# DELAY DISTRIBUTION  [SYNTHETIC — Phase 2]
# ===========================================================================
DELAY_DISTRIBUTION_TYPE = "clipped_normal"
DELAY_DISTRIBUTION_MEAN_SEC = -48
DELAY_DISTRIBUTION_STD_SEC = 60
DELAY_DISTRIBUTION_MIN_SEC = 0
DELAY_DISTRIBUTION_MAX_SEC = 300