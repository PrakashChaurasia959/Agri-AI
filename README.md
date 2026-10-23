# AgriVision AI

**A smart-agriculture platform that classifies crop diseases from leaf photographs,
recommends the best crop for a field, estimates the expected harvest, and layers live
weather on top of the results.**

AgriVision AI is a full-stack final-year B.Tech project. It combines a FastAPI backend
with a React/TypeScript frontend, three genuinely-trained machine-learning models, and a
MongoDB-backed persistence layer with JWT authentication and an administrative console.

Every number reported in this repository was measured on the machine that produced it.
Nothing is simulated: if a model artifact is missing the API says so honestly with a
`503` instead of inventing a prediction.

---

## Table of contents

1. [Feature overview](#feature-overview)
2. [Architecture](#architecture)
3. [Technology stack](#technology-stack)
4. [Repository layout](#repository-layout)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
7. [Environment configuration](#environment-configuration)
8. [Datasets and model training](#datasets-and-model-training)
9. [Running the application](#running-the-application)
10. [API reference](#api-reference)
11. [Measured model performance](#measured-model-performance)
12. [Testing](#testing)
13. [Docker and cloud deployment](#docker-and-cloud-deployment)
14. [Security model](#security-model)
15. [Troubleshooting](#troubleshooting)

---

## Feature overview

| Area | What it does |
| --- | --- |
| **Disease detection** | Uploads a leaf photograph (JPEG/PNG/WebP, ≤ 10 MB), classifies it into one of 38 PlantVillage classes with a calibrated confidence, top-5 alternatives, and a knowledge-base entry covering symptoms, prevention and treatment. |
| **Crop recommendation** | Takes seven soil and climate readings (N, P, K, temperature, humidity, rainfall, pH) and returns a ranked list of the 22 supported crops with a match score and a plain-English rationale. |
| **Yield estimation** | Estimates the expected harvest in tonnes per hectare for a crop, area and agronomic conditions, together with a 95 % planning interval derived from the model's own residual spread. |
| **Weather** | Geocoding plus current conditions and a 7-day forecast from Open-Meteo, proxied through the backend so no provider key reaches the browser. |
| **Dashboard** | Aggregated counters, daily activity, prediction-type mix, crop distribution and confidence buckets - computed from the signed-in user's own documents. |
| **History** | Paginated, filterable, searchable record of every prediction, with per-record deletion. |
| **Profile** | Farm details (name, location, farm size, primary crops) and password change. |
| **Admin console** | User directory with role management, platform statistics, per-model status and measured metrics, and an audit trail of administrative actions. |
| **Authentication** | Argon2id password hashing, JWT access/refresh tokens, HTTP-only cookies with double-submit CSRF protection, and role-based authorisation. |

---

## Architecture

```
┌──────────────────────────── Browser ────────────────────────────┐
│  React 18 + TypeScript + Vite + Tailwind + React Router         │
│  React Hook Form + Zod · Recharts · Lucide                       │
└───────────────────────────┬──────────────────────────────────────┘
                            │  same-origin /api/v1  (Vite proxy or Vercel rewrite)
                            │  cookies: agrivision_token (HttpOnly), agrivision_csrf
┌───────────────────────────▼──────────────────────────────────────┐
│  FastAPI  (app/api/v1, 32 operations)                            │
│  ├─ auth      Argon2id · JWT · CSRF · rate limiting               │
│  ├─ disease   multipart upload → PIL → CNN → MongoDB              │
│  ├─ crops     RandomForest classifier → MongoDB                  │
│  ├─ yield     RandomForest regressor → MongoDB                   │
│  ├─ weather   httpx → Open-Meteo                                  │
│  ├─ dashboard aggregation pipelines                               │
│  └─ admin     RBAC + audit log                                    │
└───────┬───────────────────────────────────┬───────────────────────┘
        │ PyMongo AsyncMongoClient           │ joblib / Keras
┌───────▼──────────────┐          ┌─────────▼───────────────────────┐
│  MongoDB Atlas       │          │  Model registry (lazy, cached)  │
│  agrivision_ai       │          │  crop_recommender.joblib        │
│  users · predictions │          │  crop_yield_regressor.joblib    │
│  crop_records ·      │          │ plant_disease_mobilenetv2.keras │
│  saved_reports ·     │          │  + *metadata.json (metrics)     │
│  audit_events        │          └─────────────────────────────────┘
└──────────────────────┘
```

**Design decisions worth calling out**

- **Same-origin API.** The frontend calls a relative `/api/v1`. In development the Vite
  proxy forwards it to `http://localhost:8000`; in production the Vercel rewrite does the
  same. This is what allows `SameSite=Lax` session cookies to work without the
  `SameSite=None; Secure` relaxation.
- **Lazy model loading.** `ml/model_registry.py` is the only module allowed to touch an
  artifact. It loads each model once per process, behind a lock, and reports a
  consistent `ModelUnavailableError` when an artifact is missing or corrupt.
- **Metadata-only persistence.** Uploaded images are analysed in memory; only the
  metadata (dimensions, format, byte size) is written to MongoDB. Image binaries are
  never stored.
- **Explicit CORS allow-list.** `cors_origins` never falls back to `*`, because a
  permissive origin plus credentialed cookies is a production foot-gun.
- **Honest degradation.** No `MONGODB_URI` → database-backed endpoints answer `503`
  with an actionable message. No model artifact → that endpoint answers `503` and the
  UI shows a "not installed" panel instead of a fake result.

---

## Technology stack

**Backend** — Python 3.10.11, FastAPI 0.115.6, Uvicorn 0.34.0, Pydantic 2.10.4,
pydantic-settings 2.7.0, PyMongo 4.11.3 (`AsyncMongoClient` - no `motor`), PyJWT 2.10.1,
argon2-cffi 23.1.0, Pillow 11.0.0, opencv-python-headless 4.10.0.84,
tensorflow-cpu 2.19.1 (Keras 3.12.4), scikit-learn 1.5.2, pandas 2.2.3, numpy 2.1.3,
httpx (weather), pytest 8.3.4 + pytest-asyncio 0.25.0 + mongomock 4.3.0.

**Frontend** — React 18.3.1, TypeScript 5.7.2, Vite 6.0.7, Tailwind CSS 3.4.17,
React Router 6.28.0, React Hook Form 7.54.2, Zod 3.24.1, Recharts 2.15.0, Lucide
React 0.468.0, clsx + tailwind-merge.

Every version is pinned in `backend/requirements.txt`, `backend/requirements-dev.txt` and
`frontend/package.json` so the project rebuilds identically.

---

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py               # auth, RBAC, CSRF and DB dependencies
│   │   │   └── v1/                   # auth, admin, crops, dashboard, disease,
│   │   │                             # system, weather, yield_estimate routers
│   │   ├── core/                     # settings, security, logging, rate limiting
│   │   ├── database/                 # connection manager + in-memory test emulator
│   │   ├── models/                   # domain models (user, prediction, record…)
│   │   ├── repositories/             # MongoDB data access
│   │   ├── schemas/                  # Pydantic request/response contracts
│   │   ├── services/                 # auth, agriculture, dashboard, weather, audit
│   │   └── main.py                   # FastAPI app, CORS, middleware, handlers
│   ├── ml/
│   │   ├── config.py                 # paths, class list, hyper-parameters
│   │   ├── preprocessing.py          # image decoding / resizing / normalisation
│   │   ├── model_registry.py         # lazy artifact loading + status reporting
│   │   ├── predict.py                # disease inference
│   │   ├── crop_predictor.py         # crop recommendation inference
│   │   ├── yield_predictor.py        # yield estimation inference
│   │   ├── disease_knowledge.py      # 38-class agronomy knowledge base
│   │   ├── evaluation.py             # metric computation and confusion matrix
│   │   ├── train_cnn.py              # disease CNN training pipeline
│   │   ├── train_crop_model.py       # crop classifier training pipeline
│   │   └── train_yield_model.py      # yield regressor training pipeline
│   ├── scripts/
│   │   ├── create_admin.py           # CLI administrator bootstrap
│   │   └── download_datasets.py      # fetch the three public datasets
│   ├── tests/                        # 180 pytest tests
│   ├── data/
│   │   ├── dataset/                  # downloaded CSVs + materialised images
│   │   └── models/                   # trained artifacts + metadata
│   ├── Dockerfile
│   ├── render.yaml
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── components/{ui,layout,charts,features}/
│   │   ├── contexts/                 # Auth, Theme, Toast providers
│   │   ├── hooks/                    # useAsync, useDebounced
│   │   ├── pages/                    # landing, auth, dashboard, tools, admin
│   │   ├── routes/                   # route table + guards
│   │   ├── services/                 # typed API clients
│   │   ├── types/                    # TypeScript mirrors of the Pydantic schemas
│   │   └── utils/
│   ├── Dockerfile
│   ├── vercel.json
│   └── package.json
├── docs/                             # college project documentation
├── scripts/                          # start-dev.ps1 / start-dev.sh
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Prerequisites

| Requirement | Version used | Notes |
| --- | --- | --- |
| Python | 3.10.11 | 3.10 is required: TensorFlow 2.19 and the pinned wheels are not published for 3.12+/3.14 in this configuration. |
| Node.js | 20+ (tested on 26.3.0) | npm 11.x |
| MongoDB Atlas | Free tier | Any MongoDB 6+ cluster works; a local container also works. |
| Open-Meteo | — | No API key required. |

---

## Installation

```bash
# 1. Clone and enter the project
cd "Default Project"

# 2. Create the Python 3.10 virtual environment
python3.10 -m venv .venv          # Windows: py -3.10 -m venv .venv
source .venv/Scripts/activate     # POSIX:  source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 3. Install the frontend dependencies
cd frontend && npm install && cd ..

# 4. Configure the environment
cp .env.example backend/.env      # then edit backend/.env
```

---

## Environment configuration

`backend/.env` (or the repository-root `.env`) drives everything. `.env.example` is the
template:

```ini
MONGODB_URI=                    # mongodb+srv://user:pass@cluster.mongodb.net
MONGODB_DB_NAME=agrivision_ai
JWT_SECRET_KEY=                 # >= 32 characters in production
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
WEATHER_API_KEY=                # optional - Open-Meteo needs none
```

`backend/.env` takes precedence over the repository-root `.env`, so put backend
secrets in `backend/.env`. Real process environment variables always win over both
files. Empty values are parsed as empty, so do not leave a blank `MONGODB_URI=`
in the root `.env` expecting it to fall back to `backend/.env` - configure it once,
in `backend/.env`.

### MongoDB Atlas setup

1. In the Atlas console open your cluster, then **Connect -> Drivers**.
2. Choose Python and copy the `mongodb+srv://...` connection string. It contains a
   placeholder password; never paste the real string into a chat, an issue or a
   commit.
3. In **Database Access**, create a database user with the minimum role
   (`readWrite` on `agrivision_ai`). Use a unique password.
4. In **Network Access**, add the public egress IP of the machine that runs the
   backend (**Add Current IP Address** while on that network). Cloud/CI runners
   need their own egress IP; `0.0.0.0/0` is not recommended.
5. Put the string in `backend/.env` yourself:

   ```ini
   MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   MONGODB_DB_NAME=agrivision_ai
   ```

6. Diagnose connectivity without leaking the secret:

   ```bash
   cd backend
   python scripts/check_mongodb.py
   ```

The script separates an empty URI, DNS/SRV failure, TLS rejection, timeout, and
authentication failure, and never prints the URI or password. Exit codes: `0` ping
OK, `1` configuration missing, `2` network/TLS/access-list problem, `3` auth/driver
error.

Optional overrides (all have safe defaults):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` enforces the mandatory-secret check and turns on `Secure` cookies. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access-token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token lifetime. |
| `COOKIE_SECURE` | auto | Auto-off in development, forced on in production. |
| `COOKIE_SAMESITE` | `lax` | Cookie `SameSite` policy. |
| `ADDITIONAL_CORS_ORIGINS` | *(empty)* | Comma-separated extra origins. |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `120` / `60` | Global rate limit. |
| `AUTH_RATE_LIMIT_REQUESTS` / `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `10` / `300` | Auth-route rate limit. |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload ceiling (10 MB). |
| `ALLOWED_IMAGE_MIME_TYPES` | `image/jpeg,image/png,image/webp` | Accepted upload types. |
| `INFERENCE_CONFIDENCE_THRESHOLD` | `0.35` | Below this the API flags the result as uncertain. |
| `DEVICE` | `cpu` | `cpu`, `gpu` or `auto`. |
| `MODEL_DIR` | `backend/data/models` | Where artifacts live. |
| `ARGON2_TIME_COST` / `ARGON2_MEMORY_COST` / `ARGON2_PARALLELISM` | `3` / `65536` / `2` | Password-hashing cost. |

> **Never commit a filled-in `.env`.** `.gitignore` already excludes `.env`, `.venv/`,
> `node_modules/`, `dist/` and the trained artifacts.

---

## Datasets and model training

All three datasets are public and downloaded on demand:

| Dataset | Source | Size |
| --- | --- | --- |
| PlantVillage (leaf images) | `GVJahnavi/PlantVillage_dataset` | 54,381 images, 38 classes |
| Crop recommendation | `randalakab/Crop-recommendation` | 2,200 rows, 22 crops |
| Crop yield | `Jakehills/Crop_Yield_Fertilizer` | 25,000 rows, 22 crops |

```bash
cd backend
python -m scripts.download_datasets          # fetch + materialise
```

Then train the models. Each script writes an artifact **and** a `*_metadata.json`
holding the measured metrics, which the API surfaces in `/api/v1/models/status` and the
admin console.

```bash
cd backend

# Disease classifier (CPU-only, ~1-2 h on a laptop)
python -m ml.train_cnn --epochs 6 --batch-size 64 --model-dir data/models

# Crop recommendation
python -m ml.train_crop_model --model-dir data/models

# Yield regression
python -m ml.train_yield_model --model-dir data/models
```

`ml/train_cnn.py` runs two stages: (1) a frozen-backbone MobileNetV2 baseline with
early stopping and `ReduceLROnPlateau`, then (2) a fine-tune pass over the top of the
base network at a lower learning rate. `ml/evaluation.py` computes the accuracy,
precision/recall/F1, the confusion matrix and the per-class breakdown that end up in
the metadata file.

---

## Running the application

Two terminals, or use the helper script.

```bash
# Terminal 1 - API on :8000  (docs at http://localhost:8000/docs)
cd backend
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# Terminal 2 - UI on :5173
cd frontend
npm run dev
```

Or:

```bash
./scripts/start-dev.sh          # macOS / Linux
.\scripts\start-dev.ps1         # Windows PowerShell
```

### First run

1. Register through the UI at `http://localhost:5173/register`.
2. Create the administrator from the CLI (never auto-promoted on sign-up):

   ```bash
   cd backend
   python -m scripts.create_admin --email admin@example.com
   # -> prompts for a password of at least 12 characters
   ```

3. Sign in as the administrator to reach `/admin`.

### Health checks

```bash
curl http://localhost:8000/api/v1/health          # service, database and model status
curl http://localhost:8000/api/v1/models/status    # per-model availability + metrics
```

---

## API reference

All endpoints live under `/api/v1`. Interactive documentation is served by Swagger UI at
`/docs` and ReDoc at `/redoc`; the raw schema is at `/openapi.json`.

### Authentication

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | – | Create an account; sets the session cookies. |
| `POST` | `/auth/login` | – | Sign in; sets the session cookies. |
| `POST` | `/auth/refresh` | refresh cookie | Rotate the access token. |
| `POST` | `/auth/logout` | cookie | Clear the session cookies. |
| `GET` | `/auth/me` | cookie / bearer | Current profile. |
| `PATCH` | `/auth/me` | cookie / bearer | Update name, location, farm size, crops. |
| `POST` | `/auth/change-password` | cookie / bearer | Change the password. |

### Tools

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/disease/predict` | user | `multipart/form-data` field `file` → classification. |
| `GET` | `/disease/history` | user | Paginated **disease** predictions; filters `prediction_type`, `search`. |
| `GET` | `/disease/history/{id}` | user | One disease prediction with full details. |
| `DELETE` | `/disease/history/{id}` | user | Delete one disease prediction. |
| `GET` | `/history` | user | Every prediction (disease, crop, yield) in one list; `prediction_type`, `search`. |
| `GET` | `/history/{id}` | user | One record in full, from whichever collection owns it. |
| `DELETE` | `/history/{id}` | user | Delete one record from whichever collection owns it. |
| `POST` | `/crops/recommend` | user | Rank crops for a soil/climate profile. |
| `GET` | `/crops/history` | user | Paginated crop **and yield** records. |
| `POST` | `/yield/predict` | user | Estimate the yield for a crop and area. |

### Dashboard, weather and system

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/dashboard/overview` | user | Counters, recent activity, top crops, model status. |
| `GET` | `/dashboard/analytics` | user | Daily trend, type mix, confidence buckets, crop distribution (`window_days`, default 30). |
| `GET` | `/weather/search` | – | Geocode a place name (`query`). |
| `GET` | `/weather/current` | – | Current conditions (`latitude`, `longitude`). |
| `GET` | `/weather/forecast` | – | Daily forecast (`latitude`, `longitude`, `days`). |
| `GET` | `/health` | – | Service, database and model health. Always `200`. |
| `GET` | `/models/status` | – | Per-model availability, version and measured metrics. |

### Administration (admin role required)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/admin/users` | Paginated user list (`search`, `role`). |
| `GET` | `/admin/users/{id}` | One user with prediction counts. |
| `PATCH` | `/admin/users/{id}/role` | Promote/demote (`role=user|admin`). |
| `DELETE` | `/admin/users/{id}` | Delete an account and its records. |
| `GET` | `/admin/stats` | Platform-wide counters. |
| `GET` | `/admin/analytics` | Prediction-type and disease-class breakdowns. |
| `GET` | `/admin/activity` | Paginated audit trail. |
| `GET` | `/admin/models` | Model availability and measured metrics. |

### Authentication mechanism

Two mechanisms are supported simultaneously:

1. **Cookie (browser)** - the access token is an `HttpOnly` cookie named
   `agrivision_token`; the refresh token is a `HttpOnly` cookie named
   `agrivision_refresh` scoped to `/api/v1/auth`; a readable `agrivision_csrf` cookie
   carries a random token that must be echoed in the `X-CSRF-Token` header on every
   state-changing request (double-submit pattern). CSRF is **not** required for
   `Authorization: Bearer` requests, because a bearer token cannot be attached
   automatically by a browser.
2. **Bearer token (scripts / mobile)** - send `Authorization: Bearer <access_token>`
   from the login or refresh response body.

---

## Measured model performance

All figures below were produced by the training scripts on the local machine and read
back from the generated `*_metadata.json` files. They are reproducible with the commands
in [Datasets and model training](#datasets-and-model-training).

### Crop recommendation — `crop_recommender.joblib`

RandomForest (300 trees, `max_depth=12`, `class_weight="balanced"`), 80/20 split,
`random_state=42`, **2,200 rows**, **22 crops**, 440 test samples.

| Metric | Value |
| --- | --- |
| Accuracy | **0.9705** |
| Precision (macro) | 0.9724 |
| Recall (macro) | 0.9705 |
| F1 (macro) | 0.9702 |
| F1 (weighted) | 0.9702 |
| Mean prediction confidence | 0.8508 |

### Yield estimation — `crop_yield_regressor.joblib`

RandomForest regressor (300 trees, `max_depth=14`), 80/20 split, `random_state=42`,
**25,000 rows**, **5,000** test samples. Target unit: **tonnes per hectare**
(observed range 20.00 – 99.68).

| Metric | Value |
| --- | --- |
| MAE | **3.7720** t/ha |
| RMSE | **4.7133** t/ha |
| MSE | 22.2150 |
| R² | **0.9122** |
| Max absolute error | 17.5806 |
| Mean residual (bias) | +0.1500 |

### Disease classification – `plant_disease_mobilenetv2.keras`

MobileNetV2 (ImageNet-pretrained, transfer learning in two stages), 38 PlantVillage
classes, **54,381** images, 43,503 train / 10,878 test, `random_state=42`.

| Metric | Value |
| --- | --- |
| Accuracy | **0.9639** |
| Precision (macro) | 0.9601 |
| Recall (macro) | 0.9584 |
| F1 (macro) | 0.9581 |
| F1 (weighted) | 0.9637 |
| Test images | 10,878 |

The measured test-split accuracy, per-class F1 and confusion matrix are written to
`backend/data/models/plant_disease_metadata.json` by `ml/train_cnn.py`, are served
live by `GET /api/v1/models/status`, and are displayed in **Admin → Models**. The
full per-class table and error analysis are in
[docs/07-results.md](docs/07-results.md) §7.4.

---

## Testing

The backend suite covers authentication, authorisation, database behaviour, image
validation, missing-model behaviour, input validation, the ML preprocessing path,
artifact loading, record ownership, error handling and the weather integration.

```bash
cd backend
../.venv/Scripts/python.exe -m pytest tests -q
```

The suite uses `mongomock` as an in-memory MongoDB emulator and `httpx.MockTransport` in
place of the Open-Meteo API, so it runs offline and deterministically. Tests that need
a trained disease artifact are skipped automatically when it is absent.

Frontend verification:

```bash
cd frontend
npx tsc --noEmit          # strict type check
npm run build             # production bundle
```

---

## Docker and cloud deployment

### Docker Compose

```bash
docker compose up -d mongodb         # local MongoDB only
docker compose --profile app up -d    # MongoDB + API + web
```

### Render (API) + Vercel (frontend)

1. Push the repository to GitHub.
2. **Render** → New Web Service → point at `backend/` (the `render.yaml` blueprint is
   included). Set `MONGODB_URI`, `JWT_SECRET_KEY`, `FRONTEND_URL`, `BACKEND_URL`. The
   health-check path is `/api/v1/health`.
3. **Vercel** → Import Project → point at `frontend/`. `vercel.json` rewrites
   `/api/:path*` to the Render service and falls back to `index.html` for the SPA
   route. Set `VITE_API_BASE_URL=/api/v1`.
4. Update `FRONTEND_URL` on Render to the Vercel URL, and `ADDITIONAL_CORS_ORIGINS` if
   you serve the frontend from more than one domain.

The model artifacts are **not** committed. Train them on the target machine (or mount
them) before starting the API, or the endpoints will correctly report that the model is
not installed.

---

## Security model

- **Passwords** are hashed with **Argon2id** (`argon2-cffi`, t=3, m=64 MiB, p=2). A
  dummy hash is computed on unknown-email logins so that response timing does not leak
  account existence.
- **Tokens** are HS256-signed JWTs carrying `sub`, `role` and `type` claims; the access
  token expires in 60 minutes, the refresh token in 7 days.
- **Cookies** are `HttpOnly` + `SameSite=Lax` + `Secure` in production, with the
  refresh cookie path-scoped to `/api/v1/auth`.
- **CSRF** uses a double-submit token, enforced only on cookie-authenticated mutations.
- **Rate limiting** is an in-process sliding-window limiter: 120 requests/min globally
  and 10 requests/5 min on the auth routes.
- **Uploads** are validated by declared MIME type, magic-byte sniffing, decoded with
  Pillow, dimension-checked and size-capped before any processing.
- **Authorisation** is enforced server-side on every protected route; record ownership
  is checked on read and delete.
- **CORS** uses an explicit allow-list and never `*`.
- **Secrets** live only in the environment; the frontend receives no secret of any kind.
- **Admins** are created exclusively through `python -m scripts.create_admin`; a public
  sign-up can never be elevated.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `503` from `/crops/recommend` | The crop model is not installed. | Run `python -m ml.train_crop_model`. |
| `503` from `/disease/predict` | The CNN artifact is not installed. | Run `python -m ml.train_cnn --epochs 6 --batch-size 64`. |
| `503` from `/auth/register` | `MONGODB_URI` is empty. | Put the Atlas URI in `backend/.env` and restart. |
| `503` from `/weather/current` | Open-Meteo is unreachable from this network. | Check outbound HTTPS; the error message names the cause. |
| `Refusing to start` on boot | `ENVIRONMENT=production` without `JWT_SECRET_KEY`/`MONGODB_URI`. | Supply both, or use `ENVIRONMENT=development`. |
| Login succeeds but the next request is `401` | The browser is on a different origin than `FRONTEND_URL`. | Add the origin to `ADDITIONAL_CORS_ORIGINS`, or use the same-origin proxy. |
| `ModuleNotFoundError: tensorflow` | The virtual environment is not the Python 3.10 one. | Recreate it with `py -3.10 -m venv .venv`. |

---

## Documentation

The college-facing documentation set lives in [`docs/`](docs/):

| File | Contents |
| --- | --- |
| [`docs/01-problem-statement.md`](docs/01-problem-statement.md) | Motivation, objectives, scope and stakeholders. |
| [`docs/02-literature-review.md`](docs/02-literature-review.md) | Related work and where this project differs. |
| [`docs/03-methodology.md`](docs/03-methodology.md) | System design, data flow and the three modelling approaches. |
| [`docs/04-dataset.md`](docs/04-dataset.md) | The three datasets, their schema and preprocessing. |
| [`docs/05-architecture.md`](docs/05-architecture.md) | Backend/frontend architecture, database schema and security. |
| [`docs/06-api-reference.md`](docs/06-api-reference.md) | Endpoint-by-endpoint contract. |
| [`docs/07-results.md`](docs/07-results.md) | Measured results with the confusion matrix and error analysis. |
| [`docs/08-testing.md`](docs/08-testing.md) | Test strategy, coverage and the recorded run. |
| [`docs/09-future-work.md`](docs/09-future-work.md) | Limitations and the roadmap. |

---

## Licence

This project was produced as a B.Tech final-year academic submission. The datasets are
used under their respective public licences (PlantVillage, the Crop Recommendation
Dataset and the Crop Yield Prediction Dataset).
