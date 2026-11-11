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

# Initial split (fixed, not solver choice)
INITIAL_RAKES_AT_ALVA = 9    # [SYNTHETIC]
INITIAL_RAKES_AT_TPHT = 7    # [SYNTHETIC]
INITIAL_RAKES_AT_MUTTOM = 2  # [SYNTHETIC] Muttom depot has operating rakes

# ===========================================================================
# PHYSICAL PARAMETERS
# ===========================================================================
SECTION_LENGTH_KM = 28.144          # [EXTERNAL — Annual Report]
ONE_WAY_RUNNING_MIN = 50.47         # [DERIVED] GTFS median
TERMINAL_TURNAROUND_MIN = 5         # [SYNTHETIC]
MIN_HEADWAY_SEC = 120               # [SYNTHETIC] 2 minutes
MIN_HEADWAY_DESIGN_SEC = 90         # [SYNTHETIC] design minimum

# ===========================================================================
# OPERATING WINDOW  [EXTERNAL — Annual Report]
# ===========================================================================
OPERATING_START_SEC = 6 * 3600      # 06:00:00
OPERATING_END_SEC = 23 * 3600       # 23:00:00 (exclusive)
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
MUTTOM_TO_JLN_DEADHEAD_MIN = None
TERMINAL_TO_TERMINAL_DEADHEAD_MIN = 15   # [SYNTHETIC] ALVA <-> TPHT deadhead time
MUTTOM_TO_TERMINAL_DEADHEAD_MIN = 8      # [SYNTHETIC] MUTTOM <-> ALVA/TPHT deadhead (half of terminal-to-terminal)

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

TRIPS_FULL_ROUTE_CSV = "data/trips_all.csv"   # solver input (232 full + 18 partial)
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
