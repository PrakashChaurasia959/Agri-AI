# 5. Architecture

This chapter describes how the system is put together: the runtime topology, the
backend layering, the frontend layering, the data model, and the security
architecture.

---

## 5.1 Runtime topology

AgriVision AI is deployed as **two stateless web tiers** plus one managed database.

```
                        ┌──────────────────────────────────────────┐
   Browser  ──HTTPS──▶  │  Vercel edge (static assets + SPA)       │
                        │  · serves the React bundle               │
                        │  · rewrites /api/*  ──────────────┐      │
                        └────────────────────────────────────┼──────┘
                                                             │ same-origin
                                                             ▼
                        ┌──────────────────────────────────────────┐
                        │  Render / container: FastAPI (uvicorn)    │
                        │  · 31 REST routes under /api/v1          │
                        │  · JWT + CSRF + RBAC + rate limiting      │
                        │  · 3 model artifacts (lazy, cached)       │
                        │  · httpx → Open-Meteo                     │
                        └───────────┬───────────────┬──────────────┘
                                    │               │
                        ┌───────────▼──────┐   ┌────▼─────────────────┐
                        │ MongoDB Atlas    │   │ Filesystem          │
                        │ agrivision_ai    │   │ data/models/*.keras │
                        │ 5 collections    │   │ data/models/*.joblib│
                        └──────────────────┘   └──────────────────────┘
```

Two consequences of this topology are worth stating explicitly:

1. **The API is stateless.** Sessions live in signed JWTs, not in server memory, so
   the API tier scales horizontally without sticky sessions.
2. **The frontend and the API share an origin.** The browser only ever talks to
   `/api/v1` on its own host, so `SameSite=Lax` cookies work without relaxing the
   cookie policy and without a wildcard CORS policy.

---

## 5.2 Backend layering

The backend is a **four-layer** FastAPI application. Each layer may only call the
layer below it.

```
┌──────────────────────────────────────────────────────────────┐
│ Interface layer    app/api/v1/*.py  +  app/api/deps.py        │
│   · routers: thin adapters                                 │
│   · dependencies: auth, RBAC, CSRF, database, pagination    │
│   · never touches MongoDB directly                          │
├──────────────────────────────────────────────────────────────┤
│ Schema layer       app/schemas/*.py                          │
│   · Pydantic request/response contracts                    │
│   · the single source of truth for the API shape            │
├──────────────────────────────────────────────────────────────┤
│ Domain layer       app/services/*.py  +  ml/*.py             │
│   · authentication, agriculture, dashboard, weather, audit  │
│   · model invocation through the model registry only        │
├──────────────────────────────────────────────────────────────┤
│ Data layer         app/repositories/*.py  +  app/database/    │
│   · MongoDB access, index management, ownership scoping     │
└──────────────────────────────────────────────────────────────┘
```

### 5.2.1 Routers

| Router | Prefix | Responsibility |
| --- | --- | --- |
| `auth.py` | `/auth` | Registration, login, refresh, logout, profile, password change |
| `disease.py` | `/disease` | Image upload, classification, disease history |
| `history.py` | `/history` | Unified history across both prediction collections |
| `crops.py` | `/crops` | Crop recommendation, crop history |
| `yield_estimate.py` | `/yield` | Yield estimation |
| `weather.py` | `/weather` | Geocoding, current conditions, forecast |
| `dashboard.py` | `/dashboard` | Overview and analytics aggregations |
| `admin.py` | `/admin` | User administration, platform statistics, audit trail |
| `system.py` | `/` | Health, model status, API root |

All are mounted under `/api/v1` by `app/main.py`. The full inventory is 32 operations.

### 5.2.2 Dependencies

`app/api/deps.py` holds the four reusable dependencies:

| Dependency | Responsibility | Failure mode |
| --- | --- | --- |
| `get_current_user` | Decode the JWT, load the user document, verify the account is active | `401` |
| `require_admin` | Assert `role == "admin"` | `403` |
| `require_database` | Assert that a MongoDB connection is available | `503` |
| `require_csrf` | Verify the double-submit token on cookie-authenticated mutations | `403` |

`require_csrf` deliberately **skips** the check when the request carries an
`Authorization: Bearer` header: a bearer token cannot be attached automatically by a
browser, so a cross-site attacker cannot forge such a request.

`require_database` is what makes the "no credentials ⇒ honest 503" behaviour
possible. It is a dependency, not an `if` inside the handler, so no database-backed
route can forget it.

### 5.2.3 Services

| Service | Responsibility |
| --- | --- |
| `auth_service.py` | Registration, credential verification, token issuance and rotation, cookie management |
| `agriculture_service.py` | Orchestrates the three ML capabilities and converts model output into API responses |
| `dashboard_service.py` | MongoDB aggregation pipelines for the dashboard |
| `weather_service.py` | Open-Meteo client, WMO code mapping, error translation |
| `audit_service.py` | Records administrative actions into `audit_events` |

### 5.2.4 Repositories

| Repository | Collection | Notable behaviour |
| --- | --- | --- |
| `user_repository.py` | `users` | Unique index on `email`; role filtering; password updates |
| `prediction_repository.py` | `predictions` | Scoped by `user_id`; paginated; searchable; deletable |
| `record_repository.py` | `crop_records`, `saved_reports` | Scoped by `user_id`; report listing |

Every read and delete of a user-owned document passes the owner id into the query, so
ownership is enforced in the data layer as well as in the route.

### 5.2.5 Model registry

`ml/model_registry.py` is the only module permitted to touch a model artifact.

```
registry.load_disease_model()
        │
        ├─ artifact present?  ──no──▶ ModelUnavailableError("model_not_trained")
        ├─ labels present?    ──no──▶ ModelUnavailableError("model_incomplete")
        ├─ loads cleanly?     ──no──▶ ModelUnavailableError("model_load_failed")
        └─ yes ──▶ cached bundle {model, labels, metadata, metrics, version}
```

Loading is lazy and guarded by a lock, so the first request pays the cost and every
later request is free. The failure taxonomy is exposed verbatim in
`GET /api/v1/models/status`, which is what allows the frontend to render a precise
"model not installed — run this command" panel instead of a generic error.

---

## 5.3 Frontend layering

```
frontend/src/
├── pages/          route-level screens
├── components/
│   ├── ui/         Button, Card, Input, Select, Badge, Table, Dialog, …
│   ├── layout/     AppShell, Navbar, Sidebar, Footer
│   ├── charts/     Recharts wrappers (TrendChart, DistributionChart, …)
│   └── features/   domain components (DiseaseResult, CropTable, YieldCard, …)
├── contexts/       AuthContext, ThemeContext, ToastContext
├── hooks/          useAsync, useDebounced
├── services/       typed API clients + the fetch wrapper
├── types/          TypeScript mirrors of the Pydantic schemas
└── utils/          cn(), formatters
```

### 5.3.1 Routing and guards

`src/routes/` declares the route table as data, and the guards are applied
declaratively:

| Guard | Behaviour |
| --- | --- |
| `RequireAuth` | Redirects to `/login` and remembers the intended destination |
| `RequireAdmin` | Redirects a non-admin to `/dashboard` |
| `GuestOnly` | Redirects an authenticated user to `/dashboard` |

### 5.3.2 The API client

`src/services/api.ts` is a single wrapper around `fetch` that applies the platform's
session rules uniformly:

- base URL is relative (`/api/v1`) so the same code works in dev and in production;
- `credentials: "include"` on every request so the session cookies travel;
- the `X-CSRF-Token` header is attached to mutations, read from the readable
  `agrivision_csrf` cookie;
- a `401` triggers a single refresh attempt and a replay of the original request;
- failures are normalised into a typed `ApiError` carrying the status, the
  machine-readable `code` and the human-readable `message` from the backend.

Because the error type is shared, every screen can render a consistent error state
without re-implementing the parsing.

### 5.3.3 Type safety across the boundary

`src/types/index.ts` is a hand-maintained mirror of the Pydantic schemas. The
backend is the authority; the TypeScript types exist so that a mismatch becomes a
**compile error** rather than a runtime surprise. The frontend's `tsc --noEmit` is
part of the verification procedure for that reason.

### 5.3.4 Design system

Tailwind's theme colours map to CSS variables (`--background`, `--foreground`,
`--card`, `--border`, `--muted`, `--ring`, …), which are redefined by the dark-mode
block. Consequently:

- light and dark themes share a single source of truth;
- no component hard-codes a colour, so a palette change propagates everywhere;
- `cn()` (clsx + tailwind-merge) resolves conflicting class names predictably.

---

## 5.4 Data model

### 5.4.1 Collections

| Collection | Document | Key fields |
| --- | --- | --- |
| `users` | Account | `email` (unique), `password_hash`, `name`, `role`, `is_active`, `farm_size_hectares`, `primary_crops`, `location`, `created_at`, `updated_at`, `last_login_at` |
| `predictions` | Disease prediction | `user_id`, `prediction_type`, `predicted_class`, `confidence`, `model_name`, `model_version`, `input_summary`, `details`, `image_metadata`, `created_at` |
| `crop_records` | Crop recommendation **or** yield estimate | `user_id`, `crop_type`, `soil_parameters`, `environmental_parameters`, `prediction_summary` (carries `top_crop`/`top_score` for a recommendation and `estimated_yield`/`per_hectare_yield` for a yield estimate), `created_at` |
| `saved_reports` | Saved report | `user_id`, `title`, `report_type`, `payload`, `created_at` |
| `audit_events` | Administrative action | `actor_id`, `actor_email`, `action`, `target_type`, `target_id`, `details`, `created_at` |

### 5.4.2 Indexes

Created idempotently at boot by `DatabaseManager.ensure_indexes`:

| Collection | Index | Purpose |
| --- | --- | --- |
| `users` | `email` (unique) | Login lookup; duplicate-registration protection |
| `users` | `role` | Admin user filtering |
| `users` | `created_at` | Newest-first user listing |
| `predictions` | `user_id, created_at ↓` | Per-user history, newest first |
| `predictions` | `prediction_type, created_at ↓` | Per-type history filtering |
| `predictions` | `created_at` | Platform-wide recency |
| `crop_records` | `user_id, created_at ↓` | Per-user crop history |
| `crop_records` | `created_at` | Platform-wide recency |
| `saved_reports` | `user_id, created_at ↓` | Per-user report listing |
| `audit_events` | `created_at` | Newest-first audit trail |

The compound indexes are ordered so that the *most selective* field leads, which
matches the actual query shapes (always filtered by `user_id`, sorted by
`created_at`).

### 5.4.3 Why no image binaries

A disease prediction stores only the image *metadata* — format, dimensions, byte
size, aspect ratio. The image itself is analysed in memory and discarded. The
consequences:

- the database stays small and the history queries stay fast;
- the privacy exposure is limited to "this user classified a leaf", not "this user
  photographed their field";
- the API never has to serve or authorise image blobs.

The trade-off is that a prediction cannot be re-run against its original image. For
an advisory tool this is the right trade-off, and it is stated in the documentation.

---

## 5.5 Security architecture

### 5.5.1 Defence in depth

| Layer | Control |
| --- | --- |
| Transport | HTTPS in production; `Secure` cookies |
| Origin | Explicit CORS allow-list; never `*` |
| Session | `HttpOnly` cookie; `SameSite=Lax`; short-lived access token; scoped refresh token |
| Request | Double-submit CSRF token on cookie-authenticated mutations |
| Credentials | Argon2id hashing; constant-ish response timing on unknown accounts |
| Authorisation | Role-based access control; per-record ownership checks |
| Input | Pydantic range and type validation; upload type, magic-byte, dimension and size checks |
| Abuse | Sliding-window rate limiting, stricter on the auth routes |
| Accountability | Administrative actions written to an audit trail |
| Supply chain | Pinned dependency versions; no secret in the repository or in the browser bundle |

### 5.5.2 Token model

| Token | Location | Lifetime | Scope |
| --- | --- | --- | --- |
| Access | `agrivision_token` cookie (`HttpOnly`) or `Authorization: Bearer` | 60 minutes | All authenticated routes |
| Refresh | `agrivision_refresh` cookie (`HttpOnly`, path `/api/v1/auth`) | 7 days | `POST /auth/refresh` only |
| CSRF | `agrivision_csrf` cookie (readable) | Session | Echoed in `X-CSRF-Token` |

The access token is a JWT signed with HS256 carrying `sub`, `role` and `type`. The
refresh token is **not** a JWT — it is an opaque random string whose hash is stored
on the user document, so a database leak does not yield usable refresh tokens. The
`type` claim lets the refresh endpoint reject an access token presented by mistake.

### 5.5.3 Cookie lifetime matrix

| Cookie | `HttpOnly` | `SameSite` | `Secure` | Path |
| --- | --- | --- | --- | --- |
| `agrivision_token` | yes | `Lax` | production only | `/` |
| `agrivision_refresh` | yes | `Lax` | production only | `/api/v1/auth` |
| `agrivision_csrf` | **no** (must be readable) | `Lax` | production only | `/` |

### 5.5.4 Rate limiting

A custom in-process sliding-window limiter, applied per client IP:

| Scope | Default | Rationale |
| --- | --- | --- |
| All routes | 120 requests / 60 s | General abuse protection |
| `/api/v1/auth/*` | 10 requests / 300 s | Brute-force protection on the credential endpoints |

A single-instance deployment needs no external store. A multi-instance deployment
would need a shared store (Redis) — this is recorded as future work in
`docs/09-future-work.md`.

---

## 5.6 Error architecture

Every error leaves the API in the same envelope:

```json
{
  "error": {
    "code": "model_not_trained",
    "message": "The disease classifier has not been trained on this machine.",
    "details": { "hint": "python -m ml.train_cnn --epochs 6 --batch-size 64" }
  }
}
```

| Status | Used for |
| --- | --- |
| `400` | Malformed request that passed schema validation |
| `401` | Missing, malformed or expired credentials |
| `403` | Authenticated but not permitted (role or ownership) |
| `404` | Resource does not exist **or** is not visible to the caller |
| `409` | Conflict (e.g. the e-mail is already registered) |
| `413` | Upload exceeds the size limit |
| `415` | Unsupported media type |
| `422` | Schema validation failure (with per-field messages) |
| `429` | Rate limit exceeded |
| `503` | A required dependency is unavailable (database or model) |

`404` is used rather than `403` for another user's document so that the API does
not confirm the existence of records the caller cannot see.

---

## 5.7 Observability

| Signal | Mechanism |
| --- | --- |
| Request logging | Structured logger with method, path, status and duration |
| Errors | Unhandled exceptions are logged with a traceback and returned as a generic envelope |
| Health | `GET /api/v1/health` reports the service, database and per-model status |
| Model metrics | Served from the artifacts' metadata files — the deployed system reports its own measured accuracy |
| Audit trail | Administrative actions stored in `audit_events` and visible in the admin console |

---

## 5.8 Deployment architecture

### 5.8.1 Containers

| Image | Base | Contents |
| --- | --- | --- |
| `backend/Dockerfile` | `python:3.10-slim` | Dependencies, application, non-root user, health check |
| `frontend/Dockerfile` | `node:20-alpine` | Multi-stage build; the runtime stage serves the static bundle |
| `docker-compose.yml` | — | MongoDB + API + web, with the `app` profile |

### 5.8.2 Platform-as-a-service

- **Render** hosts the API using `backend/render.yaml`; the health-check path is
  `/api/v1/health`.
- **Vercel** hosts the frontend; `frontend/vercel.json` rewrites `/api/:path*` to
  the API service and falls back to `index.html` for client-side routes.

### 5.8.3 Environment matrix

| Variable | Development | Production |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` |
| `JWT_SECRET_KEY` | any value | mandatory, ≥ 32 characters |
| `MONGODB_URI` | optional (503 if absent) | mandatory |
| `COOKIE_SECURE` | auto-off | forced on |
| `CORS_ORIGINS` | `http://localhost:5173` | the deployed frontend URL |
| `MODEL_DIR` | `backend/data/models` | a mounted volume or a baked-in image layer |

In `production` the application refuses to start without a JWT secret and a
MongoDB URI — failing fast is preferable to running with an insecure default.
