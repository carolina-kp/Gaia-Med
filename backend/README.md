---
title: GaiaMed Backend
emoji: 🌿
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---

# GaiaMed Backend

FastAPI backend for the GaiaMed vegetation stress early-warning system.

Serves predictions from a RandomForest model trained on Google Earth Engine satellite data (NDVI, precipitation, land surface temperature, soil moisture) covering ~578 municipality-level grid cells across Andalusia, Spain.

## Endpoints

- `GET /health` — liveness check
- `GET /api/geojson` — enriched GeoJSON with risk predictions per cell
- `GET /api/risk` — latest risk summary with ML model output
- `GET /api/timeseries/{cell_id}` — historical time series for a single cell

## Notes

- Runs on port 7860 (Hugging Face Spaces requirement)
- Model is pre-trained at Docker build time — cold start is instant
- Non-root user (`appuser`, UID 1000) per HF Spaces security policy
