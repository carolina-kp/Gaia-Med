"""
Model lifecycle management for GaiaMed.

Handles training, persisting, loading, and inference for the RandomForest
classifier that predicts vegetation stress 2 months ahead.

Module-level singletons ensure the model is loaded once at startup, not
once per request.
"""
import pickle
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

from backend.config import (
    MODEL_PATH,
    MODELS_DIR,
    RF_N_ESTIMATORS,
    RF_RANDOM_STATE,
    RISK_LOW_MAX,
    RISK_MODERATE_MAX,
    TEST_MONTHS,
)
from backend.pipeline import build_features, get_feature_cols, load_place_names, _name_from_cell_id

# Module-level singletons — populated on the first load_model() call.
_model: Optional[RandomForestClassifier] = None
_feature_cols: Optional[list[str]] = None
_model_meta: Optional[dict] = None
_predictions: Optional[dict] = None


def _traffic_light(prob: float) -> str:
    """Map a stress probability to a risk label.

    Args:
        prob: Predicted stress probability in [0, 1].

    Returns:
        "low", "moderate", or "high".
    """
    if prob < RISK_LOW_MAX:
        return "low"
    if prob < RISK_MODERATE_MAX:
        return "moderate"
    return "high"


def train_and_save() -> dict:
    """Train the RandomForest on all available data and persist it to disk.

    Uses a time-aware train/test split: the last TEST_MONTHS months are held
    out for evaluation so no future data leaks into training.

    Returns:
        Dict with "metrics" (accuracy, ROC-AUC) and "feature_importance".
    """
    df = build_features()
    feature_cols = get_feature_cols(df)

    model_df = df.dropna(subset=["stress_next"] + feature_cols).copy()

    max_month = model_df["month_num"].max()
    train_df = model_df[model_df["month_num"] <= max_month - TEST_MONTHS]
    test_df = model_df[model_df["month_num"] > max_month - TEST_MONTHS]

    X_train, y_train = train_df[feature_cols], train_df["stress_next"]
    X_test, y_test = test_df[feature_cols], test_df["stress_next"]

    model = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS,
        random_state=RF_RANDOM_STATE,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "test_roc_auc": round(float(roc_auc_score(y_test, y_prob)), 4),
    }
    feature_importance = {
        col: round(float(imp), 6)
        for col, imp in sorted(
            zip(feature_cols, model.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(
            {
                "model": model,
                "feature_cols": feature_cols,
                "metrics": metrics,
                "feature_importance": feature_importance,
            },
            fh,
        )

    return {"metrics": metrics, "feature_importance": feature_importance}


def load_model() -> tuple[RandomForestClassifier, list[str], dict]:
    """Return the trained model from the singleton cache.

    Loads from rf_model.pkl on the first call. If the pickle does not exist,
    trains the model from scratch and saves it first.

    Returns:
        Tuple of (model, feature_cols, meta) where meta contains metrics and
        feature_importance dicts.
    """
    global _model, _feature_cols, _model_meta

    if _model is not None:
        return _model, _feature_cols, _model_meta  # type: ignore[return-value]

    if not MODEL_PATH.exists():
        _model_meta = train_and_save()

    with open(MODEL_PATH, "rb") as fh:
        data = pickle.load(fh)

    _model = data["model"]
    _feature_cols = data["feature_cols"]
    _model_meta = {
        "metrics": data["metrics"],
        "feature_importance": data["feature_importance"],
    }

    return _model, _feature_cols, _model_meta  # type: ignore[return-value]


def predict_latest() -> dict:
    """Predict vegetation stress for every cell using the most recent month's data.

    The result is cached in-process after the first call — subsequent requests
    return the same dict without re-running inference.

    Returns:
        Dict with keys: predicted_for, generated_at, metrics,
        feature_importance, zones (list of per-cell dicts).
    """
    global _predictions
    if _predictions is not None:
        return _predictions

    model, feature_cols, meta = load_model()
    df = build_features()
    place_names = load_place_names()

    latest_month = df["month"].max()
    latest_df = df[df["month"] == latest_month].copy()
    valid = latest_df.dropna(subset=feature_cols).copy()

    probs = model.predict_proba(valid[feature_cols])[:, 1]
    valid = valid.copy()
    valid["stress_prob"] = probs
    valid["risk_level"] = valid["stress_prob"].apply(_traffic_light)

    predicted_for = (latest_month + pd.DateOffset(months=2)).strftime("%Y-%m")

    zones = [
        {
            "cell_id": row["cell_id"],
            "place_name": place_names.get(row["cell_id"], _name_from_cell_id(row["cell_id"])),
            "lat": round(float(row["lat"]), 6),
            "lon": round(float(row["lon"]), 6),
            "stress_prob": round(float(row["stress_prob"]), 4),
            "risk_level": row["risk_level"],
            "ndvi_mean": round(float(row["NDVI"]), 4) if pd.notna(row["NDVI"]) else None,
            "precip_mm": round(float(row["precip_mm"]), 2) if pd.notna(row["precip_mm"]) else None,
            "temp_c": round(float(row["temp_c"]), 2) if pd.notna(row["temp_c"]) else None,
        }
        for _, row in valid.iterrows()
    ]

    _predictions = {
        "predicted_for": predicted_for,
        "generated_at": latest_month.strftime("%Y-%m"),
        "metrics": meta["metrics"],
        "feature_importance": meta["feature_importance"],
        "zones": zones,
    }
    return _predictions


def get_timeseries() -> dict:
    """Compute observed vs predicted stress fraction across all labeled months.

    Each data point corresponds to a target month (feature_month + 2):
      - "observed": fraction of cells actually stressed in that month.
      - "predicted": mean model-predicted probability from feature_month data.

    Covers all months where ground-truth labels exist, giving the Analytics
    page a meaningful view of how well the 2-month-ahead forecast tracks reality.

    Returns:
        Dict with parallel lists: months (str), observed (float), predicted (float).
    """
    model, feature_cols, _ = load_model()
    df = build_features()
    valid_df = df.dropna(subset=feature_cols + ["stress_next"]).copy()

    months_out: list[str] = []
    observed: list[float] = []
    predicted: list[float] = []

    for month, grp in valid_df.groupby("month"):
        probs = model.predict_proba(grp[feature_cols])[:, 1]
        target_month = (month + pd.DateOffset(months=2)).strftime("%Y-%m")
        months_out.append(target_month)
        observed.append(round(float(grp["stress_next"].mean()), 4))
        predicted.append(round(float(probs.mean()), 4))

    return {"months": months_out, "observed": observed, "predicted": predicted}
