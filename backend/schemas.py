"""
Pydantic response models for all GaiaMed API endpoints.

Each model is the single source of truth for what a given endpoint returns,
and also drives the auto-generated OpenAPI docs at /docs.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str
    model_loaded: bool
    latest_month: Optional[str] = None


class ZonePrediction(BaseModel):
    """Per-cell stress prediction included in RiskResponse."""

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
    """Hold-out test-set evaluation metrics."""

    test_accuracy: float
    test_roc_auc: float


class RiskResponse(BaseModel):
    """Response for GET /api/risk."""

    predicted_for: str
    generated_at: str
    model_metrics: ModelMetrics
    feature_importance: Dict[str, float]
    zones: List[ZonePrediction]


class GeoJSONResponse(BaseModel):
    """Response for GET /api/geojson (schema reference only; endpoint returns raw dict)."""

    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]


class TimeseriesResponse(BaseModel):
    """Response for GET /api/timeseries."""

    months: List[str]
    observed: List[float]
    predicted: List[float]


class SummaryResponse(BaseModel):
    """Response for GET /api/summary."""

    total_zones: int
    high_risk: int
    moderate_risk: int
    low_risk: int
    avg_stress_prob: float
    most_stressed_zone: str
    latest_month: str
