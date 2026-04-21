"""
config.py — all paths, thresholds, and constants for GaiaMed backend.
All paths are relative to the project root using pathlib. No hardcoded absolute paths.
"""
from pathlib import Path

# Project root is one level above this file (backend/)
ROOT = Path(__file__).parent.parent

DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"

# Data files
PRIMARY_CSV = DATA_DIR / "gaia_andalusia_regional.csv"
PLACE_NAMES_CSV = DATA_DIR / "cell_place_names.csv"
GEOJSON_PATH = DATA_DIR / "gaia_andalusia_regional.geojson"
MODEL_PATH = MODELS_DIR / "rf_model.pkl"

# Feature engineering thresholds
NDVI_ANOM_THRESHOLD = -0.5
RAIN_ANOM_THRESHOLD = -0.5
TEMP_ANOM_THRESHOLD = 0.5
STRESS_SCORE_THRESHOLD = 2  # need >= 2 conditions to flag stress

# Traffic-light risk thresholds
RISK_LOW_MAX = 0.35      # prob < 0.35 -> low
RISK_MODERATE_MAX = 0.65  # prob < 0.65 -> moderate, else high

# Model hyperparameters
RF_N_ESTIMATORS = 300
RF_RANDOM_STATE = 42

# Time-aware train/test split: hold out last N months for testing
TEST_MONTHS = 3
