"""
schemas.py — Pydantic response models for all GaiaMed API endpoints.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── /api/health ───────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    latest_month: str


# ── /api/risk ─────────────────────────────────────────────────────────────────

class ZonePrediction(BaseModel):
    cell_id: str
    place_name: str
    lat: float
    lon: float
    stress_prob: float
    risk_level: str
    ndvi_mean: Optional[float] = None
    precip_mm: Optional[float] = None
    temp_c: Optional[float] = None


class ModelMetrics(BaseModel):
    test_accuracy: float
    test_roc_auc: float


class RiskResponse(BaseModel):
    predicted_for: str
    generated_at: str
    model_metrics: ModelMetrics
    feature_importance: Dict[str, float]
    zones: List[ZonePrediction]


# ── /api/geojson ──────────────────────────────────────────────────────────────

class GeoJSONResponse(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]


# ── /api/timeseries ───────────────────────────────────────────────────────────

class TimeseriesResponse(BaseModel):
    months: List[str]
    observed: List[float]
    predicted: List[float]


# ── /api/summary ──────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    total_zones: int
    high_risk: int
    moderate_risk: int
    low_risk: int
    avg_stress_prob: float
    most_stressed_zone: str
    latest_month: str
