# GAIA MED — Claude Code Project Brief

Read this file first before touching any code. It contains everything you need to understand the project, the data, the architecture to build, and the constraints that matter.

\---

## What this project is

GaiaMind-Med is an AI-powered early-warning system for vegetation and climate stress targeting smallholder farmers in the Doñana / Andalusia region of Southern Spain. It uses satellite and climate data to predict zones of high stress two months ahead, displayed as a simple green/yellow/red choropleth map.

This is a final academic project for the course "Perspectives on Artificial Intelligence, Business and Sustainability" at ESADE Business School. It needs to be high quality, runnable locally, and have a clean REST API that a React frontend can consume.

\---

## The data

### Primary CSV: `data/gaia\_andalusia\_regional.csv`

* 11,560 rows, 578 unique grid cells, 20 months (2024-01 to 2025-08)
* Geographic scope: lat 36.6–38.0, lon -4.72 to -1.75 (roughly Malaga to Almeria/Murcia)
* Columns: `system:index`, `NDVI`, `cell\_id`, `lat`, `lon`, `month`, `precip\_mm`, `temperature\_2m`, `.geo`
* `.geo` column contains GeoJSON polygon strings for each 10km grid cell
* `temperature\_2m` has \~1,360 missing values (about 12%) — handle gracefully
* Note: this CSV does not have `LST\_c` or `soil\_moisture` — the full notebook used a richer dataset from Google Drive. Build the pipeline to work with what is available and degrade gracefully when columns are missing
* data/gaia\_andalusia\_regional.geojson — pre-built GeoJSON FeatureCollection for the grid. Use this directly for the /api/geojson endpoint instead of parsing the .geo column from the CSV.

### Secondary CSV: `data/cell\_place\_names.csv`

* Maps `cell\_id` to human-readable place names via reverse geocoding (Nominatim)
* This was pre-generated and committed to avoid hitting rate limits at runtime
* Columns: `cell\_id`, `place\_name`

\---

## The original notebook logic (translate this into modules)

The notebook (`gaia\_med.py` in the repo root) has two phases:

### Phase 1 — Mini prototype (ignore, superseded)

Single ROI, basic stress flag, single marker map. This is just the initial exploration. Do not port this.

### Phase 2 — Regional pipeline (port this)

**Loading and parsing:**

* Load the CSV, parse `.geo` polygon column to extract centroid lat/lon
* Keep columns: `cell\_id`, `lat`, `lon`, `month`, `NDVI`, `LST\_c` (if present), `temperature\_2m`, `precip\_mm`, `soil\_moisture` (if present)
* Derive `temp\_c`: use `LST\_c` where available, fall back to `temperature\_2m - 273.15`
* Fill missing `soil\_moisture` with per-cell mean before z-scoring
* Drop rows still missing critical columns

**Feature engineering (per-cell z-score anomalies):**

```python
def zscore(x): return (x - x.mean()) / (x.std() + 1e-9)

df\['ndvi\_anom'] = df.groupby('cell\_id')\['NDVI'].transform(zscore)
df\['rain\_anom'] = df.groupby('cell\_id')\['precip\_mm'].transform(zscore)
df\['temp\_anom'] = df.groupby('cell\_id')\['temp\_c'].transform(zscore)
# lst\_anom and soil\_anom only if those columns exist
```

**Season flags:**

```python
df\['month\_of\_year'] = df\['month'].dt.month
df\['is\_summer'] = df\['month\_of\_year'].isin(\[6,7,8]).astype(int)
df\['is\_spring'] = df\['month\_of\_year'].isin(\[3,4,5]).astype(int)
df\['is\_autumn'] = df\['month\_of\_year'].isin(\[9,10,11]).astype(int)
```

**Stress rule (score-based):**

```python
df\['stress\_score'] = (
    (df\['ndvi\_anom'] < -0.5).astype(int) +
    (df\['rain\_anom'] < -0.5).astype(int) +
    (df\['temp\_anom'] > 0.5).astype(int)
    # + soil\_anom condition if column exists
)
df\['stress'] = (df\['stress\_score'] >= 2).astype(int)
```

**Lag features (previous month):**

```python
lag\_cols = \['NDVI', 'precip\_mm', 'temp\_c', 'ndvi\_anom', 'rain\_anom', 'temp\_anom']
for col in lag\_cols:
    df\[f'{col}\_prev'] = df.groupby('cell\_id')\[col].shift(1)
```

**Target: stress 2 months ahead:**

```python
df\['stress\_next'] = df.groupby('cell\_id')\['stress'].shift(-2)
```

**Train/test split (time-aware, no leakage):**

```python
df\['month\_num'] = df\['month'].rank(method='dense').astype(int)
max\_month = df\['month\_num'].max()
train\_df = df\[df\['month\_num'] <= max\_month - 3]
test\_df  = df\[df\['month\_num'] >  max\_month - 3]
```

**Model:**

```python
model = RandomForestClassifier(n\_estimators=300, random\_state=42,
                               class\_weight='balanced', n\_jobs=-1)
```

**Risk classification:**

```python
def traffic\_light(prob):
    if prob < 0.35:   return 'low'
    elif prob < 0.65: return 'moderate'
    else:             return 'high'
```

**Feature importance:** expose this in the API — it is critical for explainability (farmers need to know WHY a zone is flagged).

\---

## File structure to build

```
gaia-med/
├── BRIEF.md                        ← this file
├── gaia\_med.py                     ← original notebook, do not edit
├── data/
│   ├── gaia\_andalusia\_regional.csv
│   └── cell\_place\_names.csv
├── models/
│   └── rf\_model.pkl                ← generated by train script, gitignored
├── backend/
│   ├── config.py                   ← all paths, thresholds, env vars
│   ├── pipeline.py                 ← feature engineering functions
│   ├── model.py                    ← train, save, load, predict
│   ├── schemas.py                  ← Pydantic response models
│   ├── main.py                     ← FastAPI app and endpoints
│   ├── train.py                    ← standalone script: python train.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       ← React app will go here (Lovable export)
└── docker-compose.yml
```

\---

## API endpoints to build

### `GET /api/health`

Returns `{"status": "ok", "model\_loaded": true, "latest\_month": "2025-08"}`.

### `GET /api/risk`

Returns risk predictions for all 578 cells for the latest available month.

Response shape:

```json
{
  "predicted\_for": "2025-10",
  "generated\_at": "2025-08",
  "model\_metrics": {
    "test\_accuracy": 0.82,
    "test\_roc\_auc": 0.89
  },
  "feature\_importance": {
    "ndvi\_anom": 0.31,
    "rain\_anom": 0.22,
    "temp\_anom": 0.18
  },
  "zones": \[
    {
      "cell\_id": "cell\_-4.71616\_36.60635",
      "place\_name": "Málaga",
      "lat": 36.606,
      "lon": -4.716,
      "stress\_prob": 0.73,
      "risk\_level": "high",
      "ndvi\_mean": 0.21,
      "precip\_mm": 18.4,
      "temp\_c": 32.1
    }
  ]
}
```

### `GET /api/geojson`

Returns a GeoJSON FeatureCollection with the grid polygons colored by stress probability. Used to render the choropleth map in the frontend.

Each feature properties: `cell\_id`, `place\_name`, `stress\_prob`, `risk\_level`, `ndvi\_mean`, `precip\_mm`, `temp\_c`.

### `GET /api/timeseries`

Returns the time evolution data (observed vs predicted stress fraction per month, test months only).

```json
{
  "months": \["2025-06", "2025-07", "2025-08"],
  "observed": \[0.31, 0.44, 0.52],
  "predicted": \[0.29, 0.41, 0.49]
}
```

### `GET /api/summary`

Returns aggregated summary stats for the dashboard header cards:

```json
{
  "total\_zones": 578,
  "high\_risk": 142,
  "moderate\_risk": 203,
  "low\_risk": 233,
  "avg\_stress\_prob": 0.48,
  "most\_stressed\_zone": "Doñana Nacional Park",
  "latest\_month": "2025-08"
}
```

\---

## Important constraints and context

### User research constraints (from farmer interview)

The primary user is Juan Manuel Ortega, a smallholder strawberry farmer in Rociana del Condado (Doñana region), 23 years experience, 4.2 hectare plot. His exact requirements:

* "One color map. Green, yellow, red. No more. If you give us too many numbers, people get lost."
* "If the map is red, I need to know why. Was there less rainfall? Is plant vigor dropping? If you show me the reason, I trust it."
* "WhatsApp is guaranteed. Websites... no. Apps... maybe."
* "We don't fear bad news. We fear late news."
* Monthly updates normally, weekly during heatwaves
* Willing to contribute anonymous local data, but fears inspections if data is shared

This means the API must always include feature importance / reason codes alongside the risk level. The frontend will use these to show plain-language explanations.

### Secondary users

Local cooperatives and environmental offices (e.g., Confederación Hidrográfica del Guadalquivir). They need a summary view, not individual cell details. The `/api/summary` endpoint serves them.

### Technical constraints

* Model must load at API startup, not per request (use a module-level singleton)
* CORS must be open during development (`allow\_origins=\["\*"]`)
* All paths must use `pathlib.Path` relative to the project root, never hardcoded absolute paths or Google Drive mounts
* The `.geo` polygon parsing must be robust — some rows may have malformed JSON, handle with try/except
* `cell\_place\_names.csv` is the source of truth for place names; if a cell is missing, fall back to `f"Zone {cell\_id}"`

### Model persistence

* Train once with `python backend/train.py`, which saves `models/rf\_model.pkl`
* `model.py` exposes a `load\_model()` function and a `predict\_latest()` function
* If the pickle does not exist when the API starts, it should train automatically and save it

### Features to use (adapt based on available columns)

Always include: `NDVI`, `precip\_mm`, `temp\_c`, `ndvi\_anom`, `rain\_anom`, `temp\_anom`, `month\_of\_year`, `is\_summer`, `is\_spring`, `is\_autumn`, and their `\_prev` lag versions.

Include only if column exists in CSV: `LST\_c`, `soil\_moisture`, `lst\_anom`, `soil\_anom`, `LST\_c\_prev`, `soil\_moisture\_prev`.

\---

## Build order

1. `config.py` — paths and thresholds
2. `pipeline.py` — feature engineering, test with `python -c "from backend.pipeline import build\_features; print(build\_features().shape)"`
3. `model.py` — train, save, load, predict
4. `backend/train.py` — run it, confirm `models/rf\_model.pkl` is created, print accuracy and ROC-AUC
5. `schemas.py` — Pydantic models for all responses
6. `main.py` — FastAPI app, wire all endpoints, test at `http://localhost:8000/docs`
7. `Dockerfile` and `docker-compose.yml`

Do not start on the frontend. The frontend will be added separately from a Lovable export.

\---

## What good looks like

* `python backend/train.py` runs without errors and prints accuracy + ROC-AUC
* `uvicorn backend.main:app --reload` starts without errors
* `curl http://localhost:8000/api/risk` returns valid JSON with 578 zones
* `curl http://localhost:8000/api/geojson` returns valid GeoJSON
* `/docs` shows all endpoints with correct schemas
* No hardcoded paths, no Google Drive references, no Colab-specific code

