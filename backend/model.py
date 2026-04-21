"""
model.py — train, save, load, and predict with the GaiaMed RandomForest.

Module-level singletons ensure the model is loaded once at startup,
not per request.
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

# ── Module-level singletons (populated on first load_model() call) ──────────
_model: Optional[RandomForestClassifier] = None
_feature_cols: Optional[list] = None
_model_meta: Optional[dict] = None  # {"metrics": {...}, "feature_importance": {...}}
_predictions: Optional[dict] = None  # cached output of predict_latest()


# ── Helpers ──────────────────────────────────────────────────────────────────

def traffic_light(prob: float) -> str:
    if prob < RISK_LOW_MAX:
        return "low"
    elif prob < RISK_MODERATE_MAX:
        return "moderate"
    return "high"


# ── Training ─────────────────────────────────────────────────────────────────

def train_and_save() -> dict:
    """
    Run the full training pipeline, persist the model to disk, and
    return metrics + feature importance.
    """
    df = build_features()
    feature_cols = get_feature_cols(df)

    # Drop rows where target or any feature is NaN
    model_df = df.dropna(subset=["stress_next"] + feature_cols).copy()

    # Time-aware split — last TEST_MONTHS held out for evaluation
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


# ── Loading ───────────────────────────────────────────────────────────────────

def load_model() -> tuple:
    """
    Return (model, feature_cols, meta) from the singleton cache.
    Trains and saves automatically if the pickle doesn't exist yet.
    """
    global _model, _feature_cols, _model_meta

    if _model is not None:
        return _model, _feature_cols, _model_meta

    if not MODEL_PATH.exists():
        print("Model not found — training now...")
        _model_meta = train_and_save()
    else:
        with open(MODEL_PATH, "rb") as fh:
            data = pickle.load(fh)
        _model_meta = {
            "metrics": data["metrics"],
            "feature_importance": data["feature_importance"],
        }

    with open(MODEL_PATH, "rb") as fh:
        data = pickle.load(fh)

    _model = data["model"]
    _feature_cols = data["feature_cols"]
    _model_meta = {
        "metrics": data["metrics"],
        "feature_importance": data["feature_importance"],
    }

    return _model, _feature_cols, _model_meta


# ── Prediction ────────────────────────────────────────────────────────────────

def predict_latest() -> dict:
    """
    Predict stress probability for all cells using the most recent month's data.
    Result is cached in-process after the first call.
    """
    global _predictions
    if _predictions is not None:
        return _predictions

    model, feature_cols, meta = load_model()
    df = build_features()
    place_names = load_place_names()

    latest_month = df["month"].max()
    latest_df = df[df["month"] == latest_month].copy()

    # Only predict rows that have all required features
    valid = latest_df.dropna(subset=feature_cols).copy()
    probs = model.predict_proba(valid[feature_cols])[:, 1]
    valid["stress_prob"] = probs
    valid["risk_level"] = valid["stress_prob"].apply(traffic_light)

    # Prediction horizon: 2 months ahead of latest
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
    """
    Return observed vs model-predicted stress fraction across all months
    that have valid stress_next labels.

    Each data point corresponds to a TARGET month (feature_month + 2):
      'observed'  = fraction of cells actually stressed in the target month
      'predicted' = mean model-predicted probability (made from feature_month data)

    This covers all 18 months where ground truth exists, giving the frontend
    a meaningful chart of how well the 2-month-ahead forecast tracks reality.
    """
    model, feature_cols, _ = load_model()
    df = build_features()

    # Only rows where we have both features and a ground-truth label
    valid_df = df.dropna(subset=feature_cols + ["stress_next"]).copy()

    months_out, observed, predicted = [], [], []
    for month, grp in valid_df.groupby("month"):
        probs = model.predict_proba(grp[feature_cols])[:, 1]
        target_month = (month + pd.DateOffset(months=2)).strftime("%Y-%m")
        months_out.append(target_month)
        observed.append(round(float(grp["stress_next"].mean()), 4))
        predicted.append(round(float(probs.mean()), 4))

    return {"months": months_out, "observed": observed, "predicted": predicted}
