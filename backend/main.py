"""
main.py — FastAPI application for GaiaMed.

Start with:
    uvicorn backend.main:app --reload

All endpoints are prefixed /api.
CORS is open for local development.
"""
import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

logger = logging.getLogger("gaiamed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── In-memory caches (populated once at startup) ──────────────────────────────
_geojson_cache: dict | None = None

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

# ── Readiness flag ────────────────────────────────────────────────────────────
# Set to True once load_model() completes. Endpoints gate on this so they
# return a clean 503+Retry-After instead of hanging or crashing.
_ready = False


@app.middleware("http")
async def readiness_gate(request: Request, call_next):
    """Return 503 immediately for data endpoints while model is loading."""
    data_paths = {"/api/risk", "/api/geojson", "/api/summary", "/api/timeseries"}
    if not _ready and request.url.path in data_paths:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "5"},
            content={"detail": "Model loading, please retry shortly."},
        )
    return await call_next(request)


# ── Startup: load model once in a background thread ──────────────────────────

@app.on_event("startup")
async def startup_event():
    """Load the model and all data files off the event loop so HTTP handling starts immediately."""
    global _ready, _geojson_cache

    async def _load():
        global _ready, _geojson_cache
        try:
            logger.info("Loading model…")
            await asyncio.to_thread(load_model)
            logger.info("Model ready.")

            logger.info("Pre-loading GeoJSON into memory…")
            _geojson_cache = await asyncio.to_thread(_build_geojson)
            logger.info("GeoJSON cached (%d features).", len(_geojson_cache.get("features", [])))

            _ready = True
        except Exception:
            logger.exception("Startup load failed — check that rf_model.pkl and data files are present.")

    asyncio.create_task(_load())


def _build_geojson() -> dict:
    """Build the enriched GeoJSON FeatureCollection (runs in a thread at startup)."""
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {GEOJSON_PATH}")

    with open(GEOJSON_PATH, "r", encoding="utf-8") as fh:
        geo = json.load(fh)

    predictions = predict_latest()
    place_names = load_place_names()
    pred_lookup = {z["cell_id"]: z for z in predictions["zones"]}
    latest_month = predictions["generated_at"]

    latest_features = [
        f for f in geo["features"]
        if f.get("properties", {}).get("month") == latest_month
    ]
    if not latest_features:
        latest_features = geo["features"]

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
        feature["properties"].pop("month", None)
        enriched.append(feature)

    return {"type": "FeatureCollection", "features": enriched}


# ── /api/health ───────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["Status"])
def health():
    """Returns API health immediately — no model or file I/O. Used by frontend warm-up ping."""
    return HealthResponse(
        status="ok",
        model_loaded=_ready,
        latest_month=None,
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
    predictions for the latest month. Served from the in-memory cache built at startup.
    """
    if _geojson_cache is None:
        raise HTTPException(status_code=503, detail="GeoJSON not yet loaded — retry shortly.")
    return _geojson_cache


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
