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
│  FastAPI + Uvicorn  (Hugging Face Spaces, Docker SDK)   │
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
| Backend hosting | Hugging Face Spaces (Docker SDK, port 7860) |
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
│   ├── public/          # favicon.svg, manifest.json
│   ├── .env.example     # Environment variable template
│   └── vite.config.ts
├── legacy/              # Archived deployment configs (fly.toml, render.yaml, railway.json)
├── data/                # Satellite data exports (not committed if large)
├── models/              # Trained model weights (rf_model.pkl)
├── notebooks/
│   └── gaia_med_prototype.py  # Original Colab exploration notebook
└── docker-compose.yml   # Local full-stack development
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

In production on Vercel, this variable is not needed — `frontend/vercel.json` rewrites `/api/*` directly to the Hugging Face Spaces backend URL.

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

### Frontend (Vercel)

Push to `main` — Vercel auto-deploys. The `/api/*` rewrite in `frontend/vercel.json` proxies all API calls to the Hugging Face Spaces backend. No environment variables are needed in the Vercel dashboard.

### Backend (Hugging Face Spaces — Docker SDK)

The backend runs as a Docker Space on [Hugging Face Spaces](https://huggingface.co/spaces). The image is built from `backend/Dockerfile`, which pre-trains the RandomForest model at build time so the container starts instantly. The app listens on port 7860 (required by HF Spaces) and runs as a non-root user.

**One-time setup — deploy from scratch:**

1. **Create a Hugging Face account**
   - Go to [huggingface.co](https://huggingface.co) → click **Sign Up**
   - Verify your email and choose a username (this becomes part of your Space URL)

2. **Create a new Space**
   - Go to [huggingface.co/new-space](https://huggingface.co/new-space)
   - Space name: `gaiamed-backend`
   - SDK: **Docker** (not Gradio or Streamlit)
   - Visibility: Public (free tier requirement for always-on)
   - Click **Create Space**

3. **Clone the Space repo locally**
   ```bash
   git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/gaiamed-backend
   cd gaiamed-backend
   ```

4. **Copy the backend files into the Space repo**
   ```bash
   # From the cloned Space repo directory:
   cp -r /path/to/Gaia_Med/backend/* .
   cp -r /path/to/Gaia_Med/data ./data
   # The README.md inside backend/ already has the required HF YAML frontmatter
   cp /path/to/Gaia_Med/backend/README.md ./README.md
   ```

5. **Push to Hugging Face**
   ```bash
   git add .
   git commit -m "Initial deploy"
   git push
   ```
   HF Spaces will automatically build the Docker image and start the container. Build logs are visible in the Space's **Logs** tab. First build takes ~5 minutes (model training included).

6. **Wire the URL into the frontend**
   - Your Space URL will be: `https://YOUR_HF_USERNAME-gaiamed-backend.hf.space`
   - Open `frontend/vercel.json` and replace `YOUR_HF_USERNAME` with your actual HF username
   - Push the change to `main` — Vercel redeploys the frontend automatically

**Subsequent deploys:** push updated files to the HF Space repo — it rebuilds automatically.

> **Note:** Free-tier Spaces sleep after ~15 minutes of inactivity and take ~30 seconds to wake. Upgrade to a paid hardware tier (CPU Basic, $0.05/hr) for always-on behavior.
