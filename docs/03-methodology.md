# 3. Methodology

This chapter describes how AgriVision AI was designed and built: the system
decomposition, the three modelling approaches, the request lifecycle, and the
engineering decisions taken along the way.

---

## 3.1 Requirements analysis

The requirements were decomposed into four layers, each with an explicit contract:

| Layer | Responsibility | Implementation |
| --- | --- | --- |
| **Presentation** | Rendering, forms, charts, routing | React 18 + TypeScript + Tailwind (frontend) |
| **Interface** | HTTP contract, validation, serialisation | FastAPI routers + Pydantic schemas (`backend/app/api/v1`, `backend/app/schemas`) |
| **Domain** | Business rules, model invocation, aggregation | Service classes (`backend/app/services`), ML modules (`backend/ml`) |
| **Data** | Persistence, indexes, ownership scoping | Repositories over PyMongo (`backend/app/repositories`) |

The rule applied throughout: **the domain layer never imports FastAPI, and the
interface layer never touches MongoDB directly.** Every route is a thin adapter that
validates input, calls a service, and shapes the response.

---

## 3.2 System decomposition

The platform decomposes into six subsystems:

1. **Identity & Access** — registration, login, token issuance and rotation, session
   cookies, CSRF, role-based authorisation, rate limiting.
2. **Disease Intelligence** — image validation, preprocessing, CNN inference, knowledge
   attachment, persistence.
3. **Agronomic Advisory** — crop recommendation and yield estimation over tabular
   features, with explanations and planning intervals.
4. **Environmental Context** — geocoding, current conditions, forecast.
5. **Personal Records** — history, dashboard aggregation, saved reports.
6. **Governance** — administrative statistics, user administration, model status, audit
   trail.

Subsystems 2, 3 and 4 are stateless with respect to each other; they share only the
model registry and the prediction collection.

---

## 3.3 The disease-classification approach

### 3.3.1 Pipeline

```
upload (multipart)          POST /api/v1/disease/predict
   │
   ├─► bounded read         stream in 1 MiB chunks, abort above MAX_UPLOAD_BYTES
   ├─► MIME allow-list      declared Content-Type must be JPEG/PNG/WebP
   ├─► magic-byte sniffing  the bytes must actually be one of those formats
   ├─► Pillow decode        `Image.open` + `verify()`, then reopen and load
   ├─► dimension guard      min 32 px, max 8000 px on each side
   ├─► EXIF transpose       honour the camera orientation flag
   ├─► preprocessing         RGB → 224×224 bilinear → /255 → (x−µ)/σ
   ├─► model registry       lazily load the Keras artifact (cached per process)
   ├─► inference            forward pass → softmax → top-5 probabilities
   ├─► knowledge lookup     class → crop, symptoms, prevention, treatment
   ├─► persistence          insert a `predictions` document (metadata only)
   └─► response             label, display name, confidence, top-5, plan, image meta
```

### 3.3.2 Why this order

Validation happens **before** the model is loaded. This was a real defect found by the
test-suite: the original code loaded the (large) Keras artifact first and validated the
image afterwards, so an invalid upload still paid the model-loading cost and could
surface a model error instead of the correct validation error. The order was corrected
in `ml/predict.py`.

### 3.3.3 Normalisation constants

The preprocessing uses the ImageNet statistics `(µ = [0.485, 0.456, 0.406]`,
`σ = [0.229, 0.224, 0.225]`) because the backbone is ImageNet-pretrained. They are
declared in three places — `DiseaseTrainingConfig` (training), `InferenceConfig`
(inference) and `PreprocessConfig` (image decoding) — and the three **must** agree;
§3.3.5 explains what happens when they do not. Each is a dataclass with
`.mean`/`.std` accessors rather than module-level constants, so a test can construct an
alternative configuration without monkey-patching globals.

### 3.3.4 Training strategy

`ml/train_cnn.py` runs in two stages.

**Stage 1 — frozen-backbone baseline.** MobileNetV2 with the classification head
replaced, the convolutional base frozen. Only the head trains. This is fast
(a few minutes per epoch on CPU), gives a surprisingly strong starting point, and
establishes a baseline that Stage 2 must beat.

**Stage 2 — fine-tuning.** The top of the base network is unfrozen and trained at a
reduced learning rate (one order of magnitude below Stage 1). Fine-tuning a frozen
feature extractor is the standard compromise when the domain differs from the
pretraining domain but the dataset is too small to train a full network from scratch.

Both stages use:

- the training-split-only augmentation pipeline described in §3.3.5;
- `EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True)`;
- `ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-6)`;
- `categorical_crossentropy` loss with 0.05 label smoothing, and the `accuracy`
  metric;
- a fixed `random_state` so a rerun reproduces the same split.

The best weights are restored after early stopping, and the final evaluation is
performed on the held-out test split — **not** on the validation split — by
`ml/evaluation.py`, which writes the accuracy, the macro/weighted precision, recall and
F1, the full confusion matrix and the per-class breakdown into
`plant_disease_metadata.json`.

### 3.3.5 Augmentation, and where the normalisation lives

Augmentation is applied **inside the training dataset pipeline only**. The persisted
model therefore contains no random layer and is a pure inference model.

| Operation | Setting | Keras layer |
| --- | --- | --- |
| Horizontal flip | always | `RandomFlip("horizontal")` |
| Rotation | ± 25° | `RandomRotation(±25/360)` |
| Translation | ± 10 % of width/height | `RandomTranslation` |
| Shear | ± 8° | `RandomShear(tan 8°)` |
| Zoom | ± 15 % | `RandomZoom` |
| Brightness | × 0.85 – × 1.15 | multiplicative, applied explicitly |

The brightness step is deliberately **not** `keras.layers.RandomBrightness`: that layer
is an *additive* offset scaled to a `value_range=(0, 255)` by default, so on a
`[0, 1]` image it saturates the entire frame to black. A multiplicative factor is
applied explicitly instead, which is what the configuration expresses.

**Normalisation.** The pipeline divides by 255 and then standardises with the ImageNet
mean and standard deviation — exactly what
`keras.applications.mobilenet_v2.preprocess_input` does, and exactly what
`ml/preprocessing.py` does at inference time. This normalisation lives in the **data
pipeline**, not in a `Rescaling` layer inside the model.

That placement is not a stylistic choice. An earlier revision of this project divided
the images by 255 in the dataset *and* inserted a `Rescaling(1/255)` layer inside the
network. The backbone therefore received values around `1e-3` instead of
ImageNet-normalised values, and the run behaved like this:

```
138/578 =========  accuracy: 0.0970 - loss: 3.3959
578/578 =========  accuracy: 0.0987 - loss: 3.3952 - val_accuracy: 0.0000e+00 - val_loss: 2.9232
```

The training loss sat at `ln(38) = 3.64`, i.e. the network had learned nothing beyond
the class prior, and the validation accuracy was literally zero. The run was
"successful" in the sense that it exited without an error, which is precisely why the
defect was only found by reading the training curve rather than the exit code.

Two regression tests now prevent a recurrence:

1. `test_the_training_normalisation_matches_the_inference_normalisation` asserts that
   `DiseaseTrainingConfig`, `InferenceConfig` and `PreprocessConfig` agree on the
   rescale factor, the mean, the standard deviation and the input size.
2. `test_the_training_pipeline_produces_the_same_tensor_as_the_inference_path`
   asserts that the training normalisation and the inference normalisation produce
   numerically identical tensors for the same pixels.
3. `test_the_model_does_not_rescale_the_input_a_second_time` asserts that the built
   model contains no `Rescaling` layer.

---

## 3.4 The crop-recommendation approach

### 3.4.1 Feature vector

The trained pipeline expects exactly seven features in a fixed order:

```
[nitrogen, phosphorus, potassium, temperature, humidity, rainfall, ph]
```

The ordering is enforced in one place — `CropRecommendationRequest.feature_vector` in
`backend/app/schemas/crop.py` — so the API cannot drift from the trained model. This
was also a real bug caught by the test-suite: the property originally returned eight
values (it included `soil_type`) for a seven-feature model.

### 3.4.2 Model

A `Pipeline` containing `StandardScaler` followed by
`RandomForestClassifier(n_estimators=300, max_depth=12, min_samples_leaf=2,
class_weight="balanced", n_jobs=-1, random_state=42)`.

- **Scaling** is included inside the pipeline so the saved artifact is self-contained
  and cannot be used incorrectly at inference time.
- **`class_weight="balanced"`** protects against the mild class imbalance in the
  training data.
- **`predict_proba`** gives the match score exposed to the user, and the top-1
  probability drives the "mean prediction confidence" metric.

### 3.4.3 Explanation generation

The `explanation` returned to the user is generated from the model's own output — the
top crop, the match score and the input values that were most extreme relative to the
dataset — not from a fixed marketing string. It is a list of sentences so the frontend
can render it as a bulleted rationale.

---

## 3.5 The yield-estimation approach

### 3.5.1 Model

A `Pipeline` of `StandardScaler` + `RandomForestRegressor(n_estimators=300,
max_depth=14, min_samples_leaf=3, n_jobs=-1, random_state=42)` predicting tonnes per
hectare.

### 3.5.2 From per-hectare to field total

The model predicts a **per-hectare** yield. The API multiplies by the supplied area to
give the field total, and returns both:

- `per_hectare_yield` — the model's direct output (t/ha);
- `estimated_yield` — the field total (t) for the supplied `area_ha`.

### 3.5.3 The planning interval

The interval is derived from the model's own test-split residuals:

```
residual_std = std(y_test - ŷ_test)          # measured during training
half_width   = 1.96 × residual_std            # ≈ 95 % for a normal residual
interval     = [max(0, ŷ − half_width), ŷ + half_width]
```

The residual standard deviation is stored in the metadata file and returned in
`metrics`, so the interval is traceable to a measured quantity rather than being a
magic constant. The response carries a disclaimer stating that the interval is a
planning aid derived from observed error spread, not a formal predictive
distribution.

---

## 3.6 Weather integration

The backend is the only component that talks to Open-Meteo:

- `app/services/weather_service.py` uses `httpx.AsyncClient` with a
  `weather_timeout_seconds` (default 10 s) timeout and a retry on transient failures;
- geocoding uses the Open-Meteo geocoding API (`/v1/search`), which requires no key;
- the forecast uses the standard forecast API with `daily` and `hourly` parameter sets;
- WMO weather codes are mapped to human-readable descriptions and to icon codes on the
  frontend;
- every failure is translated into a `WeatherServiceError` carrying an HTTP status and a
  message the user can act on — **never** into a fabricated reading.

In the automated test-suite the HTTP transport is replaced with
`httpx.MockTransport`, so the tests exercise the real parsing and error-handling code
without touching the network.

---

## 3.7 Request lifecycle

### 3.7.1 Authenticated browser request

```
Browser
  │  Cookie: agrivision_token=<JWT>; agrivision_csrf=<random>
  ▼
Rate-limit middleware (sliding window, per client IP + path class)
  ▼
CORS middleware (explicit allow-list)
  ▼
Route dependency chain
  ├─ require_csrf        → rejects cookie-authenticated mutations without X-CSRF-Token
  ├─ require_database    → 503 if MONGODB_URI is unset or the cluster is unreachable
  ├─ get_current_user    → decodes the JWT, loads the user, 401 on failure
  └─ require_admin       → 403 unless the role is `admin`
  ▼
Pydantic request validation (422 with per-field messages)
  ▼
Service → model registry → (inference) → repository → MongoDB
  ▼
Pydantic response model → JSON
```

### 3.7.2 Authentication strategy

A **hybrid** strategy was chosen after evaluating the alternatives:

| Option | Problem |
| --- | --- |
| Token in `localStorage` | Vulnerable to XSS; requires manual token plumbing on every request. |
| Token in a `HttpOnly` cookie | Requires CSRF defence; otherwise a malicious site can issue authenticated writes. |
| Bearer only | Inconvenient for a browser SPA; the token must be held in JavaScript-accessible storage. |

The implemented approach:

- **Access token** → `HttpOnly` cookie `agrivision_token`, `SameSite=Lax`,
  `Secure` in production.
- **Refresh token** → `HttpOnly` cookie `agrivision_refresh`, path-scoped to
  `/api/v1/auth` so it is never sent with ordinary API calls.
- **CSRF token** → readable cookie `agrivision_csrf`, echoed in the `X-CSRF-Token`
  header (double-submit). Enforced **only** for cookie-authenticated mutations; a
  request authenticated with `Authorization: Bearer` cannot be forged cross-site and is
  therefore exempt.

This keeps the token out of JavaScript's reach while still allowing a script or a
mobile client to authenticate with a bearer token.

### 3.7.3 Same-origin deployment

`SameSite=Lax` cookies are not sent on cross-site sub-requests, and `SameSite=None`
requires `Secure` plus an explicit CORS allow-list. To avoid that complexity the API is
deployed **same-origin** with the frontend:

- development: the Vite dev server proxies `/api` → `http://localhost:8000`;
- production: the Vercel rewrite maps `/api/:path*` → the API service.

The frontend therefore calls a relative `/api/v1` by default.

---

## 3.8 Data-flow for the primary use case

A farmer classifies a leaf photo:

1. The browser POSTs the file to `/api/v1/disease/predict` as `multipart/form-data`,
   with the session cookie and the CSRF header.
2. The API validates the upload (§3.3.1) and, if the CNN artifact is absent, answers
   `503` with the exact training command — the frontend renders a "model not
   installed" panel rather than an empty result.
3. The forward pass produces a probability vector. The top-1 label, its confidence and
   the top-5 alternatives are assembled.
4. `ml/disease_knowledge.py` supplies the agronomic plan for the label.
5. A `predictions` document is inserted with `user_id`, `prediction_type`,
   `predicted_class`, `confidence`, `model_name`, `model_version`, `input_summary`,
   `details` and `image_metadata`. **The image bytes are discarded.**
6. The response is rendered: label, confidence gauge, top-5 chart, symptoms, prevention,
   treatment and the disclaimer.

---

## 3.9 Engineering decisions and their rationale

| Decision | Rationale | Alternative rejected |
| --- | --- | --- |
| PyMongo `AsyncMongoClient` instead of `motor` | `motor` is deprecated and folded into PyMongo 4.9+; one dependency instead of two. | `motor` |
| Model registry as the only artifact accessor | One consistent error surface; no `ImportError` from deep inside a request. | Direct `joblib.load` in the service |
| Lazy, lock-protected model loading | The first request pays the load cost, not the boot; repeated requests are free. | Eager loading at import time (breaks test isolation) |
| Metadata-only image persistence | MongoDB stays small; the user still gets a searchable history. | Storing image binaries |
| `mongomock` in the test-suite | Deterministic, offline, no credential dependency. | Requiring a live cluster for CI |
| Admin created only via CLI | A public sign-up can never be elevated. | `ADMIN_BOOTSTRAP_*` env vars auto-promoting the first user |
| Explicit CORS allow-list | `*` with credentials is a production foot-gun. | `allow_origins=["*"]` |
| In-process sliding-window rate limiter | Zero infrastructure; adequate for a single-instance deployment. | Redis-backed limiter |
| RandomForest over XGBoost for the tabular models | Equal validation accuracy, better-calibrated `predict_proba`, simpler dependency story. | Gradient boosting |
| MobileNetV2 over ResNet-50 / EfficientNet-B0 | Accuracy-per-second and memory footprint on CPU-only hardware. | Deeper ResNet |

---

## 3.10 Testing methodology

The suite is organised by concern rather than by module, so a failure names a
behaviour rather than a file:

| File | Concern |
| --- | --- |
| `test_auth.py` | Registration, login, refresh, logout, profile, password change, validation, token claims. |
| `test_authorization.py` | Ownership scoping, role enforcement, CSRF, rate limiting. |
| `test_database.py` | Persistence, index creation, DB-absent degradation, write failures. |
| `test_disease.py` | Upload validation, malformed images, missing-model behaviour, inference. |
| `test_crops.py` | Crop-recommendation and yield input validation, ranges, history. |
| `test_ml_pipeline.py` | Preprocessing, artifact loading, feature ordering, calibration. |
| `test_system.py` | Health, model status, error envelope, OpenAPI shape. |
| `test_weather.py` | Geocoding, current conditions, forecast parsing, upstream failure. |

Shared fixtures in `conftest.py` provide the in-memory database, an
`httpx.AsyncClient` bound to the ASGI app, registered accounts, CSRF headers and an
empty model directory for the "not trained" cases.

---

## 3.11 Ethical and safety considerations

- Every model response carries a **disclaimer** stating that the output is advisory and
  that a laboratory or extension-officer confirmation is required before acting on a
  treatment.
- Chemical treatments are described generically; the UI explicitly tells the user to
  confirm the product, dose and pre-harvest interval with a local extension officer.
- The system stores no image binaries, reducing both the privacy exposure and the
  storage cost, and it never shares one user's records with another — ownership is
  enforced on every read and delete.
- The platform does not recommend a specific commercial product, so it does not
  promote any manufacturer.
