# GaiaMed — Vegetation Stress Early-Warning System

GaiaMed is an AI-powered early-warning dashboard for vegetation and climate stress across the Doñana / Andalusia region of Spain. It combines satellite remote-sensing data (NDVI, land surface temperature, precipitation, soil moisture) with a machine-learning model to forecast vegetation stress **2 months ahead** at municipality level.

Built as a university project at ESADE, 2025–2026.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                │
│  React + Vite + Leaflet  (Vercel, always-on)            │
└────────────────────┬────────────────────────────────────┘
                     │  /api/* (Vercel rewrite proxy)
┌────────────────────▼────────────────────────────────────┐
│  FastAPI + Uvicorn  (Fly.io, always-on, Paris region)   │
│                                                         │
│  Startup sequence:                                      │
│    1. Load rf_model.pkl into memory                     │
│    2. Run inference on latest CSV month                 │
│    3. Build enriched GeoJSON and cache in memory        │
│    4. Mark _ready = True → data endpoints unblocked     │
└────────────────────┬────────────────────────────────────┘
                     │  reads from disk once at startup
┌────────────────────▼────────────────────────────────────┐
│  data/   gaia_andalusia_regional.csv  (GEE export)      │
│          gaia_andalusia_regional.geojson                │
│          cell_place_names.csv                           │
│  models/ rf_model.pkl   (pre-trained, committed to git) │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Map | React-Leaflet, Leaflet.js |
| Charts | Recharts |
| Backend | Python 3.11, FastAPI, Uvicorn |
| ML model | scikit-learn RandomForestClassifier (300 trees) |
| Data | Google Earth Engine exports (CSV + GeoJSON) |
| Backend hosting | Fly.io (shared-cpu-1x, 512 MB, always-on) |
| Frontend hosting | Vercel |

---

## Folder Structure

```
Gaia_Med/
├── backend/
│   ├── __init__.py
│   ├── config.py        # All paths, thresholds, hyperparameters
│   ├── main.py          # FastAPI app, endpoints, startup loading
│   ├── model.py         # Train, load, predict (RandomForest)
│   ├── pipeline.py      # Feature engineering pipeline
│   ├── schemas.py       # Pydantic response models
│   ├── train.py         # Standalone training script
│   ├── Dockerfile       # Docker image (builds model at image build time)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/  # RiskMap, ZoneDetailPanel, TopNav, …
│   │   ├── data/        # useZones hook, zone type definitions
│   │   ├── pages/       # Index (map), Analytics, About, NotFound
│   │   └── lib/         # Shared utilities
│   ├── .env.example     # Environment variable template
│   ├── vercel.json      # Vercel rewrite: /api/* → Fly.io backend
│   └── vite.config.ts
├── data/                # Satellite data exports (not committed if large)
├── models/              # Trained model weights (rf_model.pkl)
├── notebooks/
│   └── gaia_med_prototype.py  # Original Colab exploration notebook
├── docker-compose.yml   # Local full-stack development
├── fly.toml             # Fly.io backend deployment config
├── render.yaml          # Legacy Render config (superseded by Fly.io)
└── README.md
```

---

## How to Run Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- The data files in `data/` (CSV + GeoJSON)

### Backend

```bash
# From the project root
pip install -r backend/requirements.txt

# Train the model (only needed once, or when data changes)
python backend/train.py

# Start the API server
uvicorn backend.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (interactive API docs)
```

### Frontend

```bash
cd frontend

# Copy the environment template
cp .env.example .env.local
# VITE_API_TARGET is already set to http://localhost:8000 — no changes needed for local dev

npm install
npm run dev
# → http://localhost:5173
```

### Docker (full stack)

```bash
docker-compose up --build
# Backend:  http://localhost:8000
# Frontend: http://localhost:5173
```

---

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|---|---|---|
| `VITE_API_TARGET` | URL of the FastAPI backend | `http://localhost:8000` |

In production on Vercel, this variable is not needed — `frontend/vercel.json` rewrites `/api/*` directly to the Fly.io backend URL.

### Backend

The backend uses no environment variables. All configuration is in `backend/config.py`.

---

## How the ML Model Works

1. **Data source**: Monthly satellite composites exported from Google Earth Engine covering ~578 municipality-level grid cells across Andalusia (March 2024 – present).

2. **Features per cell per month**:
   - NDVI (vegetation greenness), precipitation, land surface temperature
   - Cross-sectional z-score anomalies (how much worse than peer cells this month)
   - Season flags (summer / spring / autumn)
   - One-month lag of all of the above

3. **Stress label**: A cell is labelled "stressed" if ≥ 2 of these anomaly conditions fire: low NDVI, low rainfall, high temperature, low soil moisture.

4. **Target**: `stress_next` — whether the cell will be stressed **2 months from now**. This is the 2-month forecast horizon.

5. **Model**: `RandomForestClassifier` with 300 trees, balanced class weights, trained on all months except the last 3 (held out for evaluation).

6. **Metrics**: ~84% accuracy, 0.89 ROC-AUC on the held-out test set.

7. **Risk levels**: Predicted probability is mapped to Low (<35%), Moderate (35–65%), High (>65%).

8. **Inference**: At server startup, the model runs inference on the latest available month. Results are cached in memory and served instantly on every subsequent request.

---

## Deployment

### Backend (Fly.io)

```bash
# Install Fly CLI, then:
fly auth login
fly deploy
fly status
```

The Dockerfile pre-trains the model at image build time (`python backend/train.py`), so the container starts with `rf_model.pkl` already present and cold-start time is minimal.

### Frontend (Vercel)

Push to `main` — Vercel auto-deploys. The `/api/*` rewrite in `frontend/vercel.json` proxies all API calls to the Fly.io backend.
