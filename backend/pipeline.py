"""
pipeline.py — data loading and feature engineering for GaiaMed.

Builds the full feature DataFrame from the primary regional CSV.
Degrades gracefully when optional columns (LST_c, soil_moisture) are absent.
"""
import pandas as pd
import numpy as np

from backend.config import (
    PRIMARY_CSV,
    PLACE_NAMES_CSV,
    NDVI_ANOM_THRESHOLD,
    RAIN_ANOM_THRESHOLD,
    TEMP_ANOM_THRESHOLD,
    STRESS_SCORE_THRESHOLD,
)


def _zscore(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / (x.std() + 1e-9)


def load_raw() -> pd.DataFrame:
    """Load primary CSV and do minimal type coercion."""
    df = pd.read_csv(PRIMARY_CSV)
    df["month"] = pd.to_datetime(df["month"])

    # temperature_2m is in Kelvin — convert to Celsius
    df["temp_c"] = df["temperature_2m"] - 273.15

    # If LST_c present, prefer it (already Celsius in V2; regional CSV lacks it)
    if "LST_c" in df.columns:
        df["temp_c"] = df["LST_c"].where(df["LST_c"].notna(), df["temp_c"])

    return df


def build_features() -> pd.DataFrame:
    """
    Full feature engineering pipeline.

    Returns a DataFrame with anomaly features, season flags, lag features,
    stress label, and stress_next target (2 months ahead).
    """
    df = load_raw()

    has_soil = "soil_moisture" in df.columns
    has_lst = "LST_c" in df.columns

    # --- Fill soil_moisture with per-cell mean before z-scoring ---
    if has_soil:
        df["soil_moisture"] = df.groupby("cell_id")["soil_moisture"].transform(
            lambda x: x.fillna(x.mean())
        )

    # Sort so lag operations work correctly
    df = df.sort_values(["cell_id", "month"]).reset_index(drop=True)

    # --- Cross-sectional z-score anomalies (per month, across cells) ---
    # Captures which cells are relatively worse than peers this month, giving
    # spatial variation even in uniformly hot/dry summer months.
    df["ndvi_anom"] = df.groupby("month")["NDVI"].transform(_zscore)
    df["rain_anom"] = df.groupby("month")["precip_mm"].transform(_zscore)
    df["temp_anom"] = df.groupby("month")["temp_c"].transform(_zscore)

    if has_lst:
        df["lst_anom"] = df.groupby("month")["LST_c"].transform(_zscore)
    if has_soil:
        df["soil_anom"] = df.groupby("month")["soil_moisture"].transform(_zscore)

    # --- Season flags ---
    df["month_of_year"] = df["month"].dt.month
    df["is_summer"] = df["month_of_year"].isin([6, 7, 8]).astype(int)
    df["is_spring"] = df["month_of_year"].isin([3, 4, 5]).astype(int)
    df["is_autumn"] = df["month_of_year"].isin([9, 10, 11]).astype(int)

    # --- Stress score (rule-based label) ---
    df["stress_score"] = (
        (df["ndvi_anom"] < NDVI_ANOM_THRESHOLD).astype(int)
        + (df["rain_anom"] < RAIN_ANOM_THRESHOLD).astype(int)
        + (df["temp_anom"] > TEMP_ANOM_THRESHOLD).astype(int)
    )
    if has_soil:
        df["stress_score"] += (df["soil_anom"] < -0.5).astype(int)

    df["stress"] = (df["stress_score"] >= STRESS_SCORE_THRESHOLD).astype(int)

    # --- Lag features (previous month) ---
    lag_cols = ["NDVI", "precip_mm", "temp_c", "ndvi_anom", "rain_anom", "temp_anom"]
    if has_lst:
        lag_cols += ["LST_c", "lst_anom"]
    if has_soil:
        lag_cols += ["soil_moisture", "soil_anom"]

    for col in lag_cols:
        df[f"{col}_prev"] = df.groupby("cell_id")[col].shift(1)

    # --- Target: stress 2 months ahead ---
    df["stress_next"] = df.groupby("cell_id")["stress"].shift(-2)

    # --- Month ordinal (for time-aware split) ---
    df["month_num"] = df["month"].rank(method="dense").astype(int)

    return df


def get_feature_cols(df: pd.DataFrame) -> list:
    """Return ordered list of feature columns present in df."""
    base = [
        "NDVI", "precip_mm", "temp_c",
        "ndvi_anom", "rain_anom", "temp_anom",
        "month_of_year", "is_summer", "is_spring", "is_autumn",
        "NDVI_prev", "precip_mm_prev", "temp_c_prev",
        "ndvi_anom_prev", "rain_anom_prev", "temp_anom_prev",
    ]
    optional = [
        "LST_c", "lst_anom", "LST_c_prev", "lst_anom_prev",
        "soil_moisture", "soil_anom", "soil_moisture_prev", "soil_anom_prev",
    ]
    return base + [c for c in optional if c in df.columns]


def _name_from_cell_id(cell_id: str) -> str:
    """Parse 'cell_{lon}_{lat}' into a readable coordinate label."""
    try:
        lon_str, lat_str = cell_id.replace("cell_", "").split("_", 1)
        lon, lat = float(lon_str), float(lat_str)
        ns = "N" if lat >= 0 else "S"
        ew = "W" if lon < 0 else "E"
        return f"{abs(lat):.1f}°{ns} {abs(lon):.1f}°{ew}"
    except Exception:
        return cell_id


def load_place_names() -> dict:
    """
    Load cell_id -> place_name mapping.
    Returns an empty dict if the file doesn't exist — callers fall back to 'Zone {cell_id}'.
    """
    if not PLACE_NAMES_CSV.exists():
        return {}
    try:
        df = pd.read_csv(PLACE_NAMES_CSV)
        return dict(zip(df["cell_id"], df["place_name"]))
    except Exception:
        return {}
