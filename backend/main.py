"""
FastAPI application entry point for GaiaMed.

Start with:
    uvicorn backend.main:app --reload

All endpoints are prefixed /api. The model, CSV data, and GeoJSON are loaded
once at startup into module-level caches so every subsequent request is O(1).
"""
import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import GEOJSON_PATH
from backend.model import load_model, predict_latest, get_timeseries
from backend.pipeline import load_place_names, _name_from_cell_id
from backend.schemas import (
    HealthResponse,
    RiskResponse,
    SummaryResponse,
    TimeseriesResponse,
)

logger = logging.getLogger("gaiamed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Populated once at startup; None means loading is still in progress.
_geojson_cache: dict | None = None

# Flipped to True only after both the model and GeoJSON finish loading.
# Data endpoints return 503 until this is True.
_ready = False

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


@app.middleware("http")
async def readiness_gate(request: Request, call_next):
    """Block data endpoints with 503 while the model is still loading.

    /api/health is intentionally excluded so the frontend can poll it
    immediately without waiting for the model to be ready.
    """
    data_paths = {"/api/risk", "/api/geojson", "/api/summary", "/api/timeseries"}
    if not _ready and request.url.path in data_paths:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "5"},
            content={"detail": "Model loading — please retry in a few seconds."},
        )
    return await call_next(request)


@app.on_event("startup")
async def startup_event() -> None:
    """Kick off background loading so the server accepts HTTP immediately.

    Sequence:
      1. Load rf_model.pkl (RandomForest + metadata) into memory.
      2. Build the enriched GeoJSON FeatureCollection and cache it.
      3. Set _ready = True — data endpoints become available.
    """
    asyncio.create_task(_load_all())


async def _load_all() -> None:
    """Background task: load model then GeoJSON, then mark the app ready."""
    global _ready, _geojson_cache
    try:
        logger.info("Loading model…")
        await asyncio.to_thread(load_model)
        logger.info("Model ready.")

        logger.info("Pre-loading GeoJSON into memory…")
        _geojson_cache = await asyncio.to_thread(_build_geojson)
        logger.info("GeoJSON cached (%d features).", len(_geojson_cache.get("features", [])))

        _ready = True
        logger.info("GaiaMed API ready.")
    except Exception:
        logger.exception("Startup failed — verify rf_model.pkl and data files are present.")


def _build_geojson() -> dict:
    """Build the enriched GeoJSON FeatureCollection from disk + model predictions.

    Reads the raw polygon geometries, merges in the latest stress predictions
    from the model, and returns a GeoJSON FeatureCollection dict ready to be
    served directly to the frontend map layer.

    Returns:
        A GeoJSON FeatureCollection dict with enriched polygon properties.

    Raises:
        FileNotFoundError: If the GeoJSON source file is missing.
    """
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {GEOJSON_PATH}")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
        geo = json.load(fh)

    predictions = predict_latest()
    place_names = load_place_names()
    pred_lookup = {z["cell_id"]: z for z in predictions["zones"]}
    latest_month = predictions["generated_at"]

    # Keep only the features for the most recent month (one polygon per cell).
    # Fall back to all features if the GeoJSON lacks a month property.
    latest_features = [
        f for f in geo["features"]
        if f.get("properties", {}).get("month") == latest_month
    ] or geo["features"]

    enriched = []
    for feature in latest_features:
        cell_id = feature.get("properties", {}).get("cell_id")
        pred = pred_lookup.get(cell_id, {})
        feature["properties"].update({
            "place_name": pred.get("place_name", place_names.get(cell_id, _name_from_cell_id(cell_id))),
            "stress_prob": pred.get("stress_prob"),
            "risk_level": pred.get("risk_level"),
            "ndvi_mean": pred.get("ndvi_mean"),
            "precip_mm": pred.get("precip_mm"),
            "temp_c": pred.get("temp_c"),
        })
        feature["properties"].pop("month", None)
        enriched.append(feature)

    return {"type": "FeatureCollection", "features": enriched}


@app.get("/api/health", response_model=HealthResponse, tags=["Status"])
def health() -> HealthResponse:
    """Return API liveness status immediately — no I/O, no model access.

    Used by the frontend warm-up ping loop to detect when the server has
    finished loading after a cold start.

    Returns:
        HealthResponse with status "ok" and model_loaded flag.
    """
    return HealthResponse(status="ok", model_loaded=_ready)


@app.get("/api/risk", response_model=RiskResponse, tags=["Predictions"])
def risk() -> RiskResponse:
    """Return stress-risk predictions for every grid cell.

    Predictions cover 2 months ahead of the latest available satellite data.
    Includes per-feature importance scores so the frontend can explain each
    zone's risk level.

    Returns:
        RiskResponse with predicted_for date, metrics, feature importances,
        and a list of per-zone predictions.
    """
    result = predict_latest()
    return RiskResponse(
        predicted_for=result["predicted_for"],
        generated_at=result["generated_at"],
        model_metrics=result["metrics"],
        feature_importance=result["feature_importance"],
        zones=result["zones"],
    )


@app.get("/api/geojson", tags=["Map"])
def geojson() -> dict:
    """Return the enriched GeoJSON FeatureCollection for the choropleth map.

    Serves 578 Andalusian municipality polygons enriched with stress_prob,
    risk_level, ndvi_mean, precip_mm, and temp_c from the latest model run.
    Served from the in-memory cache built at startup — no disk I/O per request.

    Returns:
        GeoJSON FeatureCollection dict.

    Raises:
        HTTPException 503: If the cache has not been populated yet.
    """
    if _geojson_cache is None:
        raise HTTPException(status_code=503, detail="GeoJSON not yet loaded — retry shortly.")
    return _geojson_cache


@app.get("/api/timeseries", response_model=TimeseriesResponse, tags=["Analytics"])
def timeseries() -> TimeseriesResponse:
    """Return observed vs predicted stress fraction per month over the test period.

    Each data point represents one calendar month. "Observed" is the fraction
    of cells that were actually stressed; "predicted" is the mean model
    probability emitted 2 months earlier. Used to render the time-evolution
    chart on the Analytics page.

    Returns:
        TimeseriesResponse with parallel lists: months, observed, predicted.
    """
    return get_timeseries()


@app.get("/api/summary", response_model=SummaryResponse, tags=["Analytics"])
def summary() -> SummaryResponse:
    """Return aggregated statistics for the dashboard header cards.

    Counts zones by risk level (high / moderate / low), computes the average
    stress probability, and identifies the single most-stressed zone.

    Returns:
        SummaryResponse with zone counts and most-stressed zone name.

    Raises:
        HTTPException 500: If no prediction data is available.
    """
    result = predict_latest()
    zones = result["zones"]

    if not zones:
        raise HTTPException(status_code=500, detail="No prediction data available.")

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
