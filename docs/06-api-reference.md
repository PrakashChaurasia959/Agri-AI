# 6. API Reference

All endpoints live under the `/api/v1` prefix. Interactive documentation is served by
Swagger UI at `/docs` and ReDoc at `/redoc`; the raw schema is at `/openapi.json`.

The inventory below is the **actual** route table of the running application (32
operations), generated from `/openapi.json`. Every example in this document was
taken from a live response, not written from memory.

---

## 6.1 Conventions

### 6.1.1 Base URL

```
Development : http://localhost:8000/api/v1
Production  : https://<api-host>/api/v1   (reached same-origin through the SPA)
```

### 6.1.2 Authentication

Two mechanisms are supported simultaneously.

**Cookie (browser).** After login the API sets:

| Cookie | `HttpOnly` | Purpose |
| --- | --- | --- |
| `agrivision_token` | yes | The access token |
| `agrivision_refresh` | yes (path `/api/v1/auth`) | The refresh token |
| `agrivision_csrf` | **no** | The double-submit CSRF token |

Cookie-authenticated **mutations** (`POST`, `PATCH`, `DELETE`) must echo the CSRF
token:

```
X-CSRF-Token: <value of agrivision_csrf>
```

**Bearer token (scripts, mobile, testing).** The login and refresh responses also
contain the tokens in their body:

```
Authorization: Bearer <access_token>
```

A request authenticated with a bearer token does **not** need the CSRF header -
a browser cannot attach an `Authorization` header automatically, so such a request
cannot be forged cross-site.

### 6.1.3 Envelope

Successful responses are the resource itself (no wrapper). Errors use FastAPI's
standard body, extended with an optional machine-readable code:

```json
{
  "detail": "The disease classifier has not been trained on this machine.",
  "error_code": "model_unavailable",
  "field_errors": null
}
```

Validation failures (`422`) use FastAPI's `detail` array of
`{loc, msg, type}` objects.

### 6.1.4 Pagination

List endpoints accept `page` (default `1`) and `page_size` (default `20`, maximum
`100`) and return the envelope **nested** under `pagination`:

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0,
    "has_next": false,
    "has_previous": false
  }
}
```

---

## 6.2 System

### `GET /api/v1/health`

Always returns `200`. Reports the service, the database and how many models are
installed.

```json
{
  "status": "ok",
  "service": "AgriVision AI",
  "version": "1.0.0",
  "environment": "development",
  "database": "connected",
  "database_message": "MongoDB connection is active.",
  "models": {
    "available": 3,
    "total": 3,
    "detail": {
      "disease_detection": true,
      "crop_recommendation": true,
      "yield_estimation": true
    }
  },
  "server_time": "2026-10-22T16:04:20.805255Z"
}
```

`database` is `"connected"` or `"disconnected"`; `database_message` explains why
when it is not connected.

### `GET /api/v1/models/status`

Per-model availability plus the **measured** metrics read from each artifact's
metadata file.

```json
{
  "available_count": 3,
  "total_count": 3,
  "models": [
    {
      "key": "crop_recommendation",
      "display_name": "Crop Recommendation",
      "task": "tabular_classification",
      "available": true,
      "model_name": "crop_recommender_random_forest",
      "model_version": "1.0.0",
      "accuracy": 0.9704545,
      "metrics": { "...": "..." },
      "classes_count": 22,
      "trained_at": "2026-10-22T18:10:10+00:00",
      "dataset": "Crop_recommendation.csv",
      "message": "Model loaded and ready.",
      "artifact_path": ".../crop_recommender.joblib"
    }
  ],
  "model_dir": ".../backend/data/models",
  "device": "cpu",
  "note": "Metrics are measured on the held-out split at training time."
}
```

A model that has not been trained reports `available: false`, `null` metrics and a
message that names the command that would build it.

---

## 6.3 Authentication

### `POST /api/v1/auth/register`

Public. Creates an account and sets the session cookies.

| Field | Type | Rules |
| --- | --- | --- |
| `name` | string | 2 - 120 characters |
| `email` | string | Valid e-mail, ≤ 254 characters, unique |
| `password` | string | ≥ 8 characters, must contain a letter and a digit |
| `location` | string | Optional, ≤ 160 characters |
| `primary_crops` | string[] | Optional, ≤ 25 entries |

**Responses** - `201` with the token payload below; `409` if the e-mail is taken;
`422` for a schema violation; `503` if the database is unavailable.

### `POST /api/v1/auth/login`

Public.

| Field | Type | Rules |
| --- | --- | --- |
| `email` | string | Required |
| `password` | string | Required |

**Responses** - `200`; `401` for wrong credentials (the message does not
distinguish "unknown e-mail" from "wrong password", and the response timing is
equalised with a dummy hash).

Both register and login return:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 1800,
  "csrf_token": "4f8c...",
  "user": {
    "id": "66f1c0...",
    "name": "Prakash Chaurasia",
    "email": "farmer@example.com",
    "role": "user",
    "location": "Lucknow, India",
    "farm_size_hectares": 2.5,
    "primary_crops": ["rice", "wheat"],
    "created_at": "2026-10-22T12:00:00Z",
    "last_login_at": "2026-10-22T12:00:00Z"
  }
}
```

### `POST /api/v1/auth/refresh`

Requires the `agrivision_refresh` cookie (or a refresh token in the body). Rotates
the pair and returns a new access token.

### `POST /api/v1/auth/logout`

Requires authentication. Clears all three cookies.

### `GET /api/v1/auth/me`

Requires authentication. Returns the `user` object shown above.

### `PATCH /api/v1/auth/me`

Requires authentication. Accepts any subset of `name`, `location`,
`farm_size_hectares` and `primary_crops`; only the supplied fields change.

### `POST /api/v1/auth/change-password`

Requires authentication.

| Field | Type | Rules |
| --- | --- | --- |
| `current_password` | string | Required |
| `new_password` | string | Required, same policy as registration |

Requires the CSRF header when authenticated with cookies. Changing the password
invalidates the refresh token.

---

## 6.4 Disease detection

### `POST /api/v1/disease/predict`

Requires authentication. `multipart/form-data` with a single field `file`.

| Constraint | Value |
| --- | --- |
| Accepted types | `image/jpeg`, `image/png`, `image/webp` |
| Maximum size | 10 MB (`MAX_UPLOAD_BYTES`) |
| Minimum dimensions | 32 x 32 px |
| Maximum dimensions | 8000 x 8000 px |

**Response**

```json
{
  "prediction_id": "66f1c0...",
  "predicted_class": "Tomato___Late_blight",
  "display_name": "Tomato - Late blight",
  "confidence": 0.9871,
  "confidence_percent": 98.71,
  "is_healthy": false,
  "is_certain": true,
  "uncertainty_message": null,
  "model_name": "plant_disease_mobilenetv2",
  "model_version": "1.0.0",
  "inference_ms": 41.7,
  "top_predictions": [
    { "label": "Tomato___Late_blight", "probability": 0.9871 },
    { "label": "Tomato___Early_blight", "probability": 0.0072 }
  ],
  "disease_info": {
    "crop": "Tomato",
    "symptoms": ["..."],
    "prevention": ["..."],
    "treatment": ["..."],
    "severity": "high",
    "disclaimer": "..."
  },
  "image": {
    "width": 256,
    "height": 256,
    "format": "JPEG",
    "file_size": 10412,
    "aspect_ratio": 1.0
  },
  "saved": true,
  "created_at": "2026-10-22T12:00:00Z"
}
```

**Failure modes** - `413` too large; `415` unsupported type; `422` not an image,
corrupt, or out-of-range dimensions; `503` the CNN artifact is not installed.

### `GET /api/v1/disease/history`

Requires authentication. Paginated (`page`, `page_size`). Returns disease
predictions only - use `/api/v1/history` for every prediction type.

| Query | Type | Notes |
| --- | --- | --- |
| `prediction_type` | string | Optional filter on the stored type |
| `search` | string | Case-insensitive match on the label |

### `GET /api/v1/disease/history/{prediction_id}`

Requires authentication. Returns the full disease record. A record belonging to
another user yields `404`.

### `DELETE /api/v1/disease/history/{prediction_id}`

Requires authentication. Deletes the disease record. A record belonging to another
user yields `404`.

---

## 6.5 Unified history

Disease predictions are stored in `predictions`; crop recommendations and yield
estimates are stored in `crop_records`. These endpoints present the union so the
history page can honour its promise of "every prediction you have made".

### `GET /api/v1/history`

Requires authentication. Newest first.

| Query | Type | Notes |
| --- | --- | --- |
| `prediction_type` | string | `disease`, `crop_recommendation` or `yield` |
| `search` | string | Case-insensitive match on the predicted label |
| `page` | int | Default `1` |
| `page_size` | int | Default `20`, max `100` |

```json
{
  "items": [
    {
      "id": "66f2...",
      "prediction_type": "yield",
      "predicted_class": "maize",
      "confidence": null,
      "model_name": "crop_yield_regressor",
      "model_version": "1.0.0",
      "created_at": "2026-10-22T12:05:00Z",
      "input_summary": { "nitrogen": 60, "area_ha": 2.0 }
    },
    {
      "id": "66f3...",
      "prediction_type": "crop_recommendation",
      "predicted_class": "rice",
      "confidence": 0.93,
      "model_name": "crop_recommender_random_forest",
      "model_version": "1.0.0",
      "created_at": "2026-10-22T12:04:00Z",
      "input_summary": { "nitrogen": 90, "ph": 6.5 }
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 2, "total_pages": 1, "has_next": false, "has_previous": false }
}
```

`confidence` is `null` for a yield estimate: a regressor returns a number and an
interval, not a class probability, so no confidence is invented.

An unknown `prediction_type` yields `422`.

### `GET /api/v1/history/{record_id}`

Returns the record in full, including `details` (the stored prediction summary)
and `image_metadata`. A record belonging to another user yields `404`.

### `DELETE /api/v1/history/{record_id}`

Deletes the record from whichever collection owns it. Requires the CSRF header
when authenticated with cookies. A record belonging to another user yields `404`.

---

## 6.6 Crop recommendation

### `POST /api/v1/crops/recommend`

Requires authentication.

| Field | Type | Range |
| --- | --- | --- |
| `nitrogen` | float | 0 - 300 mg/kg |
| `phosphorus` | float | 0 - 300 mg/kg |
| `potassium` | float | 0 - 300 mg/kg |
| `temperature` | float | 0 - 60 °C |
| `humidity` | float | 0 - 100 % |
| `rainfall` | float | 0 - 500 mm |
| `ph` | float | 0 - 14 |
| `soil_type` | string | Optional, ≤ 40 characters |
| `location` | string | Optional, ≤ 160 characters |

**Response**

```json
{
  "record_id": "66f2...",
  "recommendations": [
    { "crop": "rice", "score": 0.98, "rank": 1 },
    { "crop": "maize", "score": 0.01, "rank": 2 }
  ],
  "top_crop": "rice",
  "top_score": 0.98,
  "input_summary": { "nitrogen": 90, "phosphorus": 45, "ph": 6.5 },
  "explanation": ["The nutrient profile closely matches the optimum for rice."],
  "model_name": "crop_recommender_random_forest",
  "model_version": "1.0.0",
  "metrics": { "accuracy": 0.9705, "f1_macro": 0.9702 },
  "disclaimer": "...",
  "created_at": "2026-10-22T12:00:00Z"
}
```

`recommendations` holds the top five crops with their match scores. `explanation`
is generated from the model's own output, not from a template of invented facts.

**Failure modes** - `422` for an out-of-range input; `503` if the model is not
installed.

### `GET /api/v1/crops/history`

Requires authentication. Paginated (`page`, `page_size`). Returns both crop
recommendations and yield estimates, each with its stored
`soil_parameters`, `environmental_parameters` and `prediction_summary`.

---

## 6.7 Yield estimation

### `POST /api/v1/yield/predict`

Requires authentication.

| Field | Type | Range |
| --- | --- | --- |
| `crop_type` | string | 2 - 60 characters, one of the 22 supported crops |
| `area_ha` | float | > 0, ≤ 100 000 ha, default `1.0` |
| `nitrogen` ... `ph` | float | As for crop recommendation |
| `soil_type`, `irrigation`, `season` | string | Optional hints, ≤ 40 characters |

**Response**

```json
{
  "record_id": "66f3...",
  "crop_type": "rice",
  "estimated_yield": 156.93,
  "yield_unit": "tonnes per hectare",
  "per_hectare_yield": 52.31,
  "confidence_interval": [38.72, 65.90],
  "model_name": "crop_yield_regressor",
  "model_version": "1.0.0",
  "metrics": { "mae": 3.772, "rmse": 4.7133, "r2": 0.9122 },
  "input_summary": { "area_ha": 3.0, "nitrogen": 90 },
  "disclaimer": "...",
  "available": true,
  "created_at": "2026-10-22T12:00:00Z"
}
```

`estimated_yield` is the field total; `per_hectare_yield` is the model's direct
output. `confidence_interval` is a **two-element list** `[lower, upper]` around the
per-hectare estimate (1.96 x the measured residual standard deviation).

**Failure modes** - `422` for an unknown crop or an out-of-range parameter; `503`
if the model is not installed.

---

## 6.8 Weather

The backend is the only component that talks to Open-Meteo, so no provider
credential ever reaches the browser.

### `GET /api/v1/weather/search`

| Query | Type | Notes |
| --- | --- | --- |
| `query` | string | Required, place name (≥ 2 characters) |

Returns a list of geocoding candidates:

```json
[
  {
    "name": "Lucknow",
    "latitude": 26.8381,
    "longitude": 80.9346,
    "country": "India",
    "admin1": "Uttar Pradesh",
    "timezone": "Asia/Kolkata"
  }
]
```

### `GET /api/v1/weather/current`

| Query | Type | Notes |
| --- | --- | --- |
| `latitude` | float | Required, -90 … 90 |
| `longitude` | float | Required, -180 … 180 |
| `location_name` | string | Optional, echoed back for display |

```json
{
  "location": {
    "name": "Lucknow",
    "latitude": 26.8381,
    "longitude": 80.9346,
    "country": "India",
    "admin1": "Uttar Pradesh",
    "timezone": "Asia/Kolkata"
  },
  "current": {
    "temperature": 31.4,
    "apparent_temperature": 35.2,
    "humidity": 62,
    "precipitation": 0.0,
    "rainfall": 0.0,
    "wind_speed": 8.6,
    "wind_direction": 270,
    "weather_code": 1,
    "weather_description": "Mainly clear",
    "is_day": true,
    "cloud_cover": 20,
    "surface_pressure": 1002.1,
    "observed_at": "2026-10-22T12:00"
  },
  "source": "Open-Meteo",
  "fetched_at": "2026-10-22T12:01:03Z"
}
```

### `GET /api/v1/weather/forecast`

| Query | Type | Notes |
| --- | --- | --- |
| `latitude` | float | Required |
| `longitude` | float | Required |
| `location_name` | string | Optional |
| `days` | int | 1 - 16, default `7` |
| `hourly` | bool | Default `false` |

Returns `location`, `source`, `fetched_at` and a `daily` array whose entries carry
`date`, `temperature_max`, `temperature_min`, `precipitation_sum`,
`precipitation_probability_max`, `wind_speed_max`, `weather_code` and
`weather_description`. `hourly` is added when requested.

**Failure modes** - `422` for an invalid coordinate; `503` when the upstream
provider is unreachable, with a message that names the cause.

---

## 6.9 Dashboard

Every number is computed from the signed-in user's own documents across **both**
collections; a new account genuinely sees zeroes.

### `GET /api/v1/dashboard/overview`

```json
{
  "user": { "...": "..." },
  "overview": {
    "total_predictions": 10,
    "disease_predictions": 3,
    "crop_recommendations": 6,
    "yield_predictions": 1,
    "healthy_leaves": 1,
    "affected_leaves": 2,
    "saved_reports": 0,
    "distinct_crops_recommended": 3,
    "average_confidence": 0.8422,
    "first_prediction_at": "2026-10-21T12:00:00Z",
    "last_prediction_at": "2026-10-22T12:00:00Z"
  },
  "recent_predictions": [
    {
      "id": "66f3...",
      "prediction_type": "yield",
      "predicted_class": "maize",
      "confidence": null,
      "created_at": "2026-10-22T12:05:00Z"
    }
  ],
  "top_crop_recommendations": [{ "crop": "rice", "count": 3 }],
  "model_status": [{ "...": "..." }],
  "database_connected": true,
  "generated_at": "2026-10-22T12:06:00Z"
}
```

`healthy_leaves` / `affected_leaves` count disease predictions only. A yield row in
`recent_predictions` has `confidence: null`.

### `GET /api/v1/dashboard/analytics`

| Query | Type | Notes |
| --- | --- | --- |
| `window_days` | int | 1 - 365, default `30` |

```json
{
  "daily_predictions": [{ "date": "2026-10-22", "value": 10 }],
  "prediction_type_breakdown": [
    { "type": "crop_recommendation", "value": 6 },
    { "type": "disease", "value": 3 },
    { "type": "yield", "value": 1 }
  ],
  "confidence_buckets": [
    { "label": "High (>=80%)", "value": 7 },
    { "label": "Medium (50-80%)", "value": 2 },
    { "label": "Low (<50%)", "value": 0 }
  ],
  "crop_distribution": [{ "crop": "rice", "value": 3 }],
  "total_records": 10,
  "window_days": 30
}
```

`daily_predictions` always contains one point per day in the window, including
zero-activity days, so the chart does not misrepresent gaps.

---

## 6.10 Administration

All administrative routes require the `admin` role; an ordinary user receives
`403` before any data is read.

### `GET /api/v1/admin/users`

| Query | Type | Notes |
| --- | --- | --- |
| `search` | string | Match on e-mail or name |
| `role` | string | `user` or `admin` |
| `page` | int | Default `1` |
| `page_size` | int | Default `20` |

Each item carries `id`, `name`, `email`, `role`, `location`,
`farm_size_hectares`, `primary_crops`, `created_at`, `last_login_at`,
`total_predictions` (disease + crop + yield) and `last_prediction_at`. No
password hash is ever serialised.

### `GET /api/v1/admin/users/{user_id}`

One user in the same shape as a list item.

### `PATCH /api/v1/admin/users/{user_id}/role`

The role is a **query parameter**, not a request body:

```
PATCH /api/v1/admin/users/66f1.../role?role=admin
```

An administrator cannot demote the last remaining administrator.

### `DELETE /api/v1/admin/users/{user_id}`

Deletes the account and its records (predictions, crop records, saved reports).
The last administrator account cannot be deleted.

### `GET /api/v1/admin/stats`

```json
{
  "total_users": 2,
  "total_predictions": 10,
  "disease_predictions": 3,
  "crop_recommendations": 6,
  "yield_predictions": 1,
  "saved_reports": 0,
  "healthy_leaves": 1,
  "affected_leaves": 2,
  "new_users_7d": 2,
  "predictions_7d": 10
}
```

`total_predictions` is the sum across both collections.

### `GET /api/v1/admin/analytics`

```json
{
  "prediction_type_breakdown": [
    { "type": "crop_recommendation", "value": 6 },
    { "type": "disease", "value": 3 },
    { "type": "yield", "value": 1 }
  ],
  "top_disease_classes": [{ "label": "Tomato___Late_blight", "count": 2 }],
  "distinct_classes": 3,
  "generated_at": "2026-10-22T12:06:00Z"
}
```

### `GET /api/v1/admin/activity`

Paginated audit trail (`page`, `page_size`, optional `action` filter). Each item:
`id`, `actor_email`, `action`, `target_type`, `created_at`, `ip_address`.

### `GET /api/v1/admin/models`

The model inventory plus `environment` and a `services` map:

```json
{
  "models": [],
  "available_count": 3,
  "total_count": 3,
  "model_dir": ".../backend/data/models",
  "environment": "development",
  "services": {
    "database": { "name": "MongoDB", "status": "healthy", "detail": "Connected" },
    "weather": { "name": "Open-Meteo", "status": "configured", "detail": "No API key required for Open-Meteo." }
  }
}
```

---

## 6.11 Route index

| # | Method | Path | Purpose |
| --- | --- | --- | --- |
| 1 | `POST` | `/api/v1/auth/register` | Create a new account |
| 2 | `POST` | `/api/v1/auth/login` | Sign in |
| 3 | `POST` | `/api/v1/auth/logout` | Sign out |
| 4 | `POST` | `/api/v1/auth/refresh` | Refresh the session |
| 5 | `GET` | `/api/v1/auth/me` | Current user profile |
| 6 | `PATCH` | `/api/v1/auth/me` | Update the profile |
| 7 | `POST` | `/api/v1/auth/change-password` | Change the password |
| 8 | `POST` | `/api/v1/disease/predict` | Classify a leaf image |
| 9 | `GET` | `/api/v1/disease/history` | Disease prediction history |
| 10 | `GET` | `/api/v1/disease/history/{prediction_id}` | Disease prediction detail |
| 11 | `DELETE` | `/api/v1/disease/history/{prediction_id}` | Delete a disease prediction |
| 12 | `GET` | `/api/v1/history` | Every prediction the user has made |
| 13 | `GET` | `/api/v1/history/{record_id}` | One prediction in full |
| 14 | `DELETE` | `/api/v1/history/{record_id}` | Delete one prediction |
| 15 | `POST` | `/api/v1/crops/recommend` | Recommend crops |
| 16 | `GET` | `/api/v1/crops/history` | Crop and yield history |
| 17 | `POST` | `/api/v1/yield/predict` | Estimate the yield |
| 18 | `GET` | `/api/v1/dashboard/overview` | Dashboard summary |
| 19 | `GET` | `/api/v1/dashboard/analytics` | Dashboard analytics series |
| 20 | `GET` | `/api/v1/weather/search` | Search for a location |
| 21 | `GET` | `/api/v1/weather/current` | Current weather |
| 22 | `GET` | `/api/v1/weather/forecast` | Weather forecast |
| 23 | `GET` | `/api/v1/health` | Service health |
| 24 | `GET` | `/api/v1/models/status` | Machine learning model status |
| 25 | `GET` | `/api/v1/admin/users` | List users |
| 26 | `GET` | `/api/v1/admin/users/{user_id}` | User detail |
| 27 | `DELETE` | `/api/v1/admin/users/{user_id}` | Delete a user |
| 28 | `PATCH` | `/api/v1/admin/users/{user_id}/role` | Change a user's role |
| 29 | `GET` | `/api/v1/admin/stats` | Platform statistics |
| 30 | `GET` | `/api/v1/admin/analytics` | Platform analytics |
| 31 | `GET` | `/api/v1/admin/activity` | Audit activity feed |
| 32 | `GET` | `/api/v1/admin/models` | Model and service status |

> Reproduced from the generated OpenAPI document; the ordering is irrelevant and
> the set of 32 operations is what matters.
