"""
main.py — FastAPI application for GaiaMed.

Start with:
    uvicorn backend.main:app --reload

All endpoints are prefixed /api.
CORS is open for local development.
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import GEOJSON_PATH
from backend.model import load_model, predict_latest, get_timeseries
from backend.pipeline import build_features, load_place_names, _name_from_cell_id
from backend.schemas import (
    GeoJSONResponse,
    HealthResponse,
    RiskResponse,
    SummaryResponse,
    TimeseriesResponse,
)

app = FastAPI(
    title="GaiaMed API",
    description=(
        "Early-warning system for vegetation and climate stress "
        "in the Doñana / Andalusia region."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup: load model once ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Load (or train) the model at startup so the first request is not slow."""
    load_model()


# ── /api/health ───────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["Status"])
def health():
    """Returns API health and whether the model is loaded."""
    try:
        model, _, _ = load_model()
        model_loaded = model is not None
    except Exception:
        model_loaded = False

    df = build_features()
    latest_month = df["month"].max().strftime("%Y-%m")

    return HealthResponse(
        status="ok",
        model_loaded=model_loaded,
        latest_month=latest_month,
    )


# ── /api/risk ─────────────────────────────────────────────────────────────────

@app.get("/api/risk", response_model=RiskResponse, tags=["Predictions"])
def risk():
    """
    Risk predictions for all grid cells based on the most recent data month.
    Predictions are for 2 months ahead of the latest available data.
    Includes feature importances so the frontend can explain WHY a zone is flagged.
    """
    result = predict_latest()
    return RiskResponse(
        predicted_for=result["predicted_for"],
        generated_at=result["generated_at"],
        model_metrics=result["metrics"],
        feature_importance=result["feature_importance"],
        zones=result["zones"],
    )


# ── /api/geojson ──────────────────────────────────────────────────────────────

@app.get("/api/geojson", tags=["Map"])
def geojson():
    """
    GeoJSON FeatureCollection of the 578 grid polygons enriched with stress
    predictions for the latest month. Used to render the choropleth map.
    """
    if not GEOJSON_PATH.exists():
        raise HTTPException(status_code=500, detail="GeoJSON file not found")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
        geo = json.load(fh)

    # Build a lookup: cell_id -> prediction data from the risk endpoint
    predictions = predict_latest()
    place_names = load_place_names()
    pred_lookup = {z["cell_id"]: z for z in predictions["zones"]}

    # Filter to latest month features only (one polygon per cell)
    latest_month = predictions["generated_at"]  # e.g. "2025-08"
    latest_features = [
        f for f in geo["features"]
        if f.get("properties", {}).get("month") == latest_month
    ]

    # If the GeoJSON has no month property, fall back to all features
    if not latest_features:
        latest_features = geo["features"]

    # Enrich each polygon's properties with prediction data
    enriched = []
    for feature in latest_features:
        cell_id = feature.get("properties", {}).get("cell_id")
        pred = pred_lookup.get(cell_id, {})
        feature["properties"].update(
            {
                "place_name": pred.get(
                    "place_name",
                    place_names.get(cell_id, _name_from_cell_id(cell_id)),
                ),
                "stress_prob": pred.get("stress_prob"),
                "risk_level": pred.get("risk_level"),
                "ndvi_mean": pred.get("ndvi_mean"),
                "precip_mm": pred.get("precip_mm"),
                "temp_c": pred.get("temp_c"),
            }
        )
        # Remove raw month field — not needed by the frontend map layer
        feature["properties"].pop("month", None)
        enriched.append(feature)

    return {"type": "FeatureCollection", "features": enriched}


# ── /api/timeseries ───────────────────────────────────────────────────────────

@app.get("/api/timeseries", response_model=TimeseriesResponse, tags=["Analytics"])
def timeseries():
    """
    Observed vs predicted stress fraction per month for the held-out test period.
    Used to render the time-evolution chart in the dashboard.
    """
    return get_timeseries()


# ── /api/summary ──────────────────────────────────────────────────────────────

@app.get("/api/summary", response_model=SummaryResponse, tags=["Analytics"])
def summary():
    """
    Aggregated stats for the dashboard header cards.
    Counts zones by risk level and identifies the most stressed zone.
    """
    result = predict_latest()
    zones = result["zones"]

    if not zones:
        raise HTTPException(status_code=500, detail="No prediction data available")

    high = sum(1 for z in zones if z["risk_level"] == "high")
    moderate = sum(1 for z in zones if z["risk_level"] == "moderate")
    low = sum(1 for z in zones if z["risk_level"] == "low")
    avg_prob = round(sum(z["stress_prob"] for z in zones) / len(zones), 4)

    most_stressed = max(zones, key=lambda z: z["stress_prob"])

    return SummaryResponse(
        total_zones=len(zones),
        high_risk=high,
        moderate_risk=moderate,
        low_risk=low,
        avg_stress_prob=avg_prob,
        most_stressed_zone=most_stressed["place_name"],
        latest_month=result["generated_at"],
    )
