"""
Centralised configuration for GaiaMed backend.

All file paths, model hyperparameters, and thresholds live here.
No other module should define a hardcoded path or magic number.
"""
from pathlib import Path

# Project root is one level above this file (backend/)
ROOT = Path(__file__).parent.parent

DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"

# ── Data files ────────────────────────────────────────────────────────────────
PRIMARY_CSV = DATA_DIR / "gaia_andalusia_regional.csv"
PLACE_NAMES_CSV = DATA_DIR / "cell_place_names.csv"
GEOJSON_PATH = DATA_DIR / "gaia_andalusia_regional.geojson"
MODEL_PATH = MODELS_DIR / "rf_model.pkl"

# ── Stress-flag thresholds (z-score based) ───────────────────────────────────
NDVI_ANOM_THRESHOLD = -0.5    # below this z-score → low vegetation signal
RAIN_ANOM_THRESHOLD = -0.5    # below this z-score → dry anomaly
TEMP_ANOM_THRESHOLD = 0.5     # above this z-score → heat anomaly
STRESS_SCORE_THRESHOLD = 2    # need ≥ 2 conditions to flag a cell as stressed

# ── Risk-level probability thresholds ────────────────────────────────────────
RISK_LOW_MAX = 0.35       # prob < 0.35  → low
RISK_MODERATE_MAX = 0.65  # prob < 0.65  → moderate, else high

# ── RandomForest hyperparameters ─────────────────────────────────────────────
RF_N_ESTIMATORS = 300
RF_RANDOM_STATE = 42

# ── Time-aware train/test split ───────────────────────────────────────────────
TEST_MONTHS = 3  # hold out the last N months for evaluation
