"""
Data loading and feature engineering pipeline for GaiaMed.

Builds the full feature DataFrame from the primary regional CSV exported
from Google Earth Engine. Degrades gracefully when optional columns
(LST_c, soil_moisture) are absent.
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
    """Compute z-score with a small epsilon to avoid division by zero."""
    return (x - x.mean()) / (x.std() + 1e-9)


def load_raw() -> pd.DataFrame:
    """Load the primary CSV and apply minimal type coercions.

    Converts the month column to datetime and temperature from Kelvin to
    Celsius. Prefers LST_c over ERA5 temperature when both are present.

    Returns:
        DataFrame with at least: cell_id, lat, lon, month, NDVI,
        precip_mm, temp_c.
    """
    df = pd.read_csv(PRIMARY_CSV)
    df["month"] = pd.to_datetime(df["month"])
    df["temp_c"] = df["temperature_2m"] - 273.15

    if "LST_c" in df.columns:
        df["temp_c"] = df["LST_c"].where(df["LST_c"].notna(), df["temp_c"])

    return df


def build_features() -> pd.DataFrame:
    """Run the full feature engineering pipeline.

    Steps:
      1. Load raw data and coerce types.
      2. Fill missing soil_moisture values with per-cell mean.
      3. Compute cross-sectional z-score anomalies (per month, across cells).
      4. Add season binary flags (summer, spring, autumn; winter is baseline).
      5. Compute a rule-based stress score and binary stress label.
      6. Add one-month lag features.
      7. Compute the 2-month-ahead stress target (stress_next).
      8. Add a dense month ordinal for time-aware train/test splits.

    Returns:
        DataFrame enriched with anomaly features, lag features, stress
        labels, and a stress_next prediction target.
    """
    df = load_raw()

    has_soil = "soil_moisture" in df.columns
    has_lst = "LST_c" in df.columns

    if has_soil:
        df["soil_moisture"] = df.groupby("cell_id")["soil_moisture"].transform(
            lambda x: x.fillna(x.mean())
        )

    df = df.sort_values(["cell_id", "month"]).reset_index(drop=True)

    # Cross-sectional z-score anomalies: captures which cells are worse than
    # their peers this month, providing spatial variation even in uniformly
    # hot or dry periods.
    df["ndvi_anom"] = df.groupby("month")["NDVI"].transform(_zscore)
    df["rain_anom"] = df.groupby("month")["precip_mm"].transform(_zscore)
    df["temp_anom"] = df.groupby("month")["temp_c"].transform(_zscore)

    if has_lst:
        df["lst_anom"] = df.groupby("month")["LST_c"].transform(_zscore)
    if has_soil:
        df["soil_anom"] = df.groupby("month")["soil_moisture"].transform(_zscore)

    df["month_of_year"] = df["month"].dt.month
    df["is_summer"] = df["month_of_year"].isin([6, 7, 8]).astype(int)
    df["is_spring"] = df["month_of_year"].isin([3, 4, 5]).astype(int)
    df["is_autumn"] = df["month_of_year"].isin([9, 10, 11]).astype(int)

    df["stress_score"] = (
        (df["ndvi_anom"] < NDVI_ANOM_THRESHOLD).astype(int)
        + (df["rain_anom"] < RAIN_ANOM_THRESHOLD).astype(int)
        + (df["temp_anom"] > TEMP_ANOM_THRESHOLD).astype(int)
    )
    if has_soil:
        df["stress_score"] += (df["soil_anom"] < -0.5).astype(int)

    df["stress"] = (df["stress_score"] >= STRESS_SCORE_THRESHOLD).astype(int)

    lag_cols = ["NDVI", "precip_mm", "temp_c", "ndvi_anom", "rain_anom", "temp_anom"]
    if has_lst:
        lag_cols += ["LST_c", "lst_anom"]
    if has_soil:
        lag_cols += ["soil_moisture", "soil_anom"]

    for col in lag_cols:
        df[f"{col}_prev"] = df.groupby("cell_id")[col].shift(1)

    df["stress_next"] = df.groupby("cell_id")["stress"].shift(-2)
    df["month_num"] = df["month"].rank(method="dense").astype(int)

    return df


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return the ordered list of feature columns present in the DataFrame.

    Core features are always included; optional features (LST, soil moisture)
    are appended only when the underlying CSV contains them.

    Args:
        df: The feature DataFrame returned by build_features().

    Returns:
        List of column name strings in the order expected by the model.
    """
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
    """Convert a raw cell_id like 'cell_{lon}_{lat}' to a readable coordinate.

    Args:
        cell_id: Raw identifier string from the GEE export.

    Returns:
        Human-readable coordinate string, e.g. "37.2°N 3.8°W".
        Falls back to the raw cell_id on parse failure.
    """
    try:
        lon_str, lat_str = cell_id.replace("cell_", "").split("_", 1)
        lon, lat = float(lon_str), float(lat_str)
        ns = "N" if lat >= 0 else "S"
        ew = "W" if lon < 0 else "E"
        return f"{abs(lat):.1f}°{ns} {abs(lon):.1f}°{ew}"
    except Exception:
        return cell_id


def load_place_names() -> dict[str, str]:
    """Load the cell_id → place_name mapping from CSV.

    Returns an empty dict if the file does not exist; callers fall back to
    coordinate labels generated by _name_from_cell_id.

    Returns:
        Dict mapping cell_id strings to human-readable place names.
    """
    if not PLACE_NAMES_CSV.exists():
        return {}
    try:
        df = pd.read_csv(PLACE_NAMES_CSV)
        return dict(zip(df["cell_id"], df["place_name"]))
    except Exception:
        return {}
