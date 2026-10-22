# 8. Testing

This chapter describes the test strategy, what the suite covers, and the recorded
results of the runs performed on the development machine.

---

## 8.1 Objectives

The test suite exists to protect the properties that make the system trustworthy:

| Objective | What it protects |
| --- | --- |
| **O1 — Correctness** | The API returns exactly the documented contract for every documented input. |
| **O2 — Security** | Unauthenticated access is refused; cross-user access is impossible; mutations cannot be forged. |
| **O3 — Resilience** | The absence of the database or of a model produces an honest `503`, never a crash and never a fabricated answer. |
| **O4 — Honesty** | Reported metrics come from the artifacts, not from constants. |
| **O5 — Reproducibility** | The ML layer behaves identically in the test-suite and in production. |

The suite is a **regression net for real defects**, not a coverage exercise. Every
test that exists was either written to pin down a behaviour that matters or added
after a genuine bug was found. §8.6 lists those bugs.

---

## 8.2 Strategy

### 8.2.1 Offline by design

The suite must run on a machine with no MongoDB Atlas cluster and no network access
to Open-Meteo. Two substitutions achieve this:

| Real dependency | Test substitute | What is still exercised |
| --- | --- | --- |
| MongoDB Atlas | `mongomock` 4.3.0 (in-memory emulator) | The repositories, the aggregation pipelines, the index definitions, the ownership scoping |
| Open-Meteo | `httpx.MockTransport` | The real HTTP client, the real response parsing, the real error translation |

The application code is **not** modified for testing: the emulator is injected
through the application's own database-manager seam, so the production code path is
the one under test.

### 8.2.2 Test levels

| Level | What it covers | Example |
| --- | --- | --- |
| Unit | A single function or class in isolation | The image validator rejects a truncated PNG |
| Contract | The HTTP surface — status, body shape, headers | `POST /auth/login` sets the three cookies |
| Integration | Several components against the in-memory database | A prediction is written and can be read back, paginated and deleted |
| ML pipeline | Preprocessing, artifact loading, normalisation parity | The training normalisation equals the inference normalisation |

### 8.2.3 Configuration isolation

`tests/conftest.py` sets, for the whole session:

| Variable | Value | Reason |
| --- | --- | --- |
| `ENVIRONMENT` | `test` | Disables the production secret check |
| `MONGODB_URI` | *(empty)* by default | Makes the "no database" path the default; the DB-backed fixtures install the emulator explicitly |
| `JWT_SECRET_KEY` | A fixed test value | Deterministic tokens |
| `ARGON2_TIME_COST` / `ARGON2_MEMORY_COST` / `ARGON2_PARALLELISM` | `1` / `8192` / `1` | Keeps hashing fast enough for a large suite while still exercising the real algorithm |
| `RATE_LIMIT_*` | Raised limits | The limiter has its own dedicated tests |

The model registry is a **module-level singleton**. The `empty_model_dir` fixture
temporarily repoints `registry._model_dir` at an empty directory and calls
`registry._reset()`, which is how the "model not trained" behaviour is tested
without moving files around.

---

## 8.3 Fixtures

| Fixture | Provides |
| --- | --- |
| `memory_db` | An in-memory MongoDB database with the production indexes created |
| `disconnected_db` | A database manager whose client is closed — the "cluster unreachable" case |
| `client` | An `httpx.AsyncClient` bound to the ASGI app, with the emulator installed |
| `account` | A registered ordinary user (e-mail, password, and the cookies from the response) |
| `admin_account` | A registered user whose role is `admin` |
| `empty_model_dir` | Points the model registry at an empty directory and restores it afterwards |
| `make_image_bytes` | A helper that synthesises a real JPEG/PNG/BMP/GIF of a given size |

The `client` fixture is an `async` fixture, and the tests use `pytest-asyncio`'s
`auto` mode so that no test needs an explicit marker.

---

## 8.4 Coverage by area

### 8.4.1 Authentication — `tests/test_auth.py`

| Behaviour | Assertion |
| --- | --- |
| Registration | Creates the user, hashes the password, sets the three cookies |
| Duplicate registration | `409`, and the second attempt does not overwrite the first account |
| Password policy | Rejects a short password and a password without a digit (`422`) |
| Login | Succeeds with correct credentials, returns the access token in the body |
| Login failures | `401` for a wrong password **and** for an unknown e-mail, with the same message |
| Token claims | The access token carries `sub`, `role` and `type`; the refresh token does not work as an access token |
| Refresh | Rotates the pair; the old refresh token stops working |
| Logout | Clears all three cookies |
| `GET /auth/me` | Returns the profile, and `401` without a token |
| `PATCH /auth/me` | Updates only the supplied fields |
| `change-password` | Requires the current password; the old password stops working |

### 8.4.2 Authorisation — `tests/test_authorization.py`

| Behaviour | Assertion |
| --- | --- |
| Protected routes | `401` without credentials |
| Role enforcement | An ordinary user receives `403` on every `/admin/*` route |
| Ownership | User A cannot read or delete user B's prediction — `404`, not `403` |
| CSRF | A cookie-authenticated mutation without `X-CSRF-Token` is refused (`403`) |
| CSRF exemption | A bearer-authenticated mutation needs no CSRF token |
| Bearer authentication | `Authorization: Bearer` works on every protected route |
| Rate limiting | The auth limiter eventually returns `429` |

### 8.4.3 Database — `tests/test_database.py`

| Behaviour | Assertion |
| --- | --- |
| Persistence | A written prediction is read back with all its fields |
| Indexes | The production index definitions are created on the emulator |
| Absent database | A database-backed route returns `503` with an actionable message |
| Unreachable cluster | A write failure is translated into a `503`, not an unhandled exception |
| Isolation | One user's documents never appear in another user's listing |

### 8.4.4 Disease — `tests/test_disease.py`

| Behaviour | Assertion |
| --- | --- |
| Empty upload | Rejected (`422`) |
| Non-image bytes | Rejected (`422`) |
| A real GIF / BMP | Rejected as an unsupported format (`422`) |
| A truncated PNG | Rejected as corrupt (`422`) |
| An oversized file | Rejected with `413` |
| An unsupported MIME type | Rejected with `415` |
| A sub-32-pixel image | Rejected |
| Missing model | `503` with the training command in the message |
| Valid upload (model present) | Returns a label, a confidence and a top-5 list |

The last group is `skipif`-guarded on the trained artifact being present, so the
suite is green both before and after training.

### 8.4.5 Crops and yield — `tests/test_crops.py`

| Behaviour | Assertion |
| --- | --- |
| Feature ranges | Out-of-range N/P/K, temperature, humidity, rainfall and pH are rejected (`422`) |
| Unknown crop | An unsupported `crop_type` is rejected |
| Non-positive area | `area_ha <= 0` is rejected |
| Feature-vector length | The request schema produces exactly the seven features the model expects |
| Successful recommendation | Returns a ranked list with a top crop and an explanation |
| Successful yield estimate | Returns a per-hectare figure and a field total consistent with the area |
| History | Records are written, paginated and scoped to the owner |

### 8.4.6 ML pipeline — `tests/test_ml_pipeline.py`

| Behaviour | Assertion |
| --- | --- |
| Image validation | The format, dimension, size and MIME allow-list rules |
| Preprocessing | The output shape, dtype and the exact ImageNet normalisation |
| Normalisation parity | `DiseaseTrainingConfig` == `InferenceConfig` == `PreprocessConfig` |
| Numeric parity | The training tensor equals the inference tensor for the same pixels |
| No double rescale | The built model contains no `Rescaling` layer |
| Augmentation | The augmentation actually changes the pixels |
| Knowledge base | All 38 classes have symptoms, prevention and treatment |
| Knowledge coverage | Every class folder in the dataset has a guidance entry |
| Registry | Missing, incomplete and corrupt artifacts each produce their own error code |
| Trained artifacts | The crop and yield models load and agree with their metadata files |

### 8.4.7 System — `tests/test_system.py`

| Behaviour | Assertion |
| --- | --- |
| Health | `200` and the documented shape |
| Model status | The per-model status and the metric fields |
| Error envelope | Every error response uses the same envelope shape |
| OpenAPI | The document is generated, contains the expected paths, and declares the security scheme |
| Unknown route | `404` with the standard envelope |

### 8.4.8 Weather — `tests/test_weather.py`

| Behaviour | Assertion |
| --- | --- |
| Geocoding | The provider's response is mapped onto the schema |
| Current conditions | Every documented field is present and correctly typed |
| Forecast | The daily entries carry the documented fields |
| Invalid coordinates | `422` |
| Upstream failure | A provider error becomes a `503` with a message naming the cause — never a fabricated reading |

---

## 8.5 Frontend verification

The frontend is verified statically rather than with a browser-automation suite:

| Check | Command | Meaning |
| --- | --- | --- |
| Type check | `npx tsc --noEmit` | The TypeScript mirrors of the backend schemas are consistent; a schema drift becomes a compile error |
| Production build | `npm run build` | The bundle compiles, the code splits, and the Tailwind pipeline is valid |
| Bundle inspection | the build output sizes | Regressions in bundle size are visible |

---

## 8.6 Defects the suite found

The test-suite was written alongside the implementation and earned its keep. These
are the real defects it exposed, with the fix:

| # | Defect | Symptom | Fix |
| --- | --- | --- | --- |
| 1 | `PaginationParams.__init__` used `Annotated[int, Query(...)]` under `from __future__ import annotations` | FastAPI raised `PydanticUserError` on **every** paginated route at import time | Rewrote the class so the annotation is evaluated at runtime |
| 2 | `AsyncCursor` had no `sort`, `skip` or `limit` | History pagination could not be ordered or paged | Implemented the cursor operations |
| 3 | `ml/predict.py` loaded the model before validating the image | An invalid upload paid the model-loading cost and could surface a model error instead of the validation error | Reordered: validate, then load |
| 4 | `CropRecommendationRequest.feature_vector` returned **8** values | A 7-feature model received a mis-shaped vector | Removed the extra field |
| 5 | `ml/disease_knowledge.py` was missing `Tomato___Late_blight` | A real class could be predicted but had no guidance | Added the entry; a test now asserts full coverage |
| 6 | The CNN training pipeline divided by 255 **and** inserted a `Rescaling(1/255)` layer | The backbone saw inputs of ~1e-3; training accuracy stayed at ~0.10 and validation accuracy was 0.0 | Removed the layer; the normalisation now lives in the data pipeline only |
| 7 | The training pipeline never applied the mean/std normalisation that the inference path applies | Train/serve skew: the model was fitted on a different input distribution from the one it would be served | Applied the identical normalisation in the training pipeline; three regression tests now assert the parity |
| 8 | `build_augmentation()` was never called | The augmentation was documented but never happened | Wired it into the training dataset pipeline only; a test asserts that it changes the pixels |
| 9 | Three `AsyncCollection.aggregate` calls were not awaited (`top_crops_for_user`, `aggregate_type_breakdown`, `aggregate_daily_counts`) | `GET /dashboard/overview` answered `500` against a real MongoDB driver | Awaited the aggregation in all three; `tests/test_driver_contract.py` now asserts that every `aggregate` call is a coroutine |
| 10 | The in-memory emulator's `aggregate` was synchronous | The emulator hid defect 9 while a real cluster failed | Made `AsyncCollection.aggregate` an `async def`; the contract test compares the emulator with `pymongo.asynchronous.collection.AsyncCollection` |
| 11 | `created_at` was always `null` in the crop, yield and disease responses | A saved prediction reported no timestamp even though one was stored | The services now return `(result, record_id, created_at)` and the endpoints pass it through; the tests compare the response timestamp with the stored document |
| 12 | The dashboard only counted the `predictions` collection | Crop recommendations and yield estimates - two of the three prediction types - were invisible in every counter, the activity feed and both analytics charts | `DashboardService` merges `predictions` and `crop_records` through `app/services/record_kinds.py`; regression tests assert the counts, the feed and the analytics breakdown |
| 13 | Analytics compared a stored `created_at` (naive, as PyMongo returns it) with `datetime.now(timezone.utc)` (aware) | `TypeError: can't compare offset-naive and offset-aware datetimes` as soon as a record existed inside the window - it passed only because the test account was empty | Added `ensure_utc()` in `app/models/base.py` and normalised every stored timestamp before comparison |
| 14 | `GET /disease/history` returned disease predictions only, while the history page promises "every prediction you have made" and offers Crop and Yield filters | Crop and yield records never appeared in the history list, and their filter tabs were always empty | Added the unified `GET /api/v1/history` (+ detail and delete) that merges both collections; `tests/test_history.py` covers listing, filtering, search, pagination, ownership and deletion |
| 15 | The admin user list and detail counted only `predictions` | A user with crop and yield activity showed `0` predictions and no last activity | Both endpoints now sum `predictions` and `crop_records` and take the later of the two timestamps |
| 16 | `PATCH /admin/users/{id}/role` was documented with a JSON body but implemented with a query parameter | A client following the documentation received `422` | The implementation is the contract; `docs/06-api-reference.md` now shows `?role=admin` and the admin e2e exercises it |

Defects 6–8 are the subject of `docs/09-future-work.md` because they share a common
root cause: **a pipeline that fails silently still exits with code 0.** The defence
against that class of defect is now a set of assertions about the *values* flowing
through the pipeline, not only about the shapes.

---

## 8.7 Recorded results

### 8.7.1 Backend

Command:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

Result on the development machine (Python 3.10.11, Windows):

```
176 passed, 4 skipped in 95.27s
```

The four skips are the disease-inference tests, which are guarded on the trained CNN
artifact being present. After the CNN was trained the same suite runs the full set:

```
180 passed
```

Environment of the recorded run:

| | |
| --- | --- |
| Python | 3.10.11 |
| TensorFlow | 2.19.1 (CPU) |
| Keras | 3.12.4 |
| scikit-learn | 1.5.2 |
| PyMongo | 4.11.3 |
| mongomock | 4.3.0 |
| pytest | 8.3.4 |
| pytest-asyncio | 0.25.0 |

### 8.7.2 Frontend

```
> npx tsc --noEmit
> (no output — exit code 0)

> npm run build
vite v6.0.7 building for production...
✓ 1844 modules transformed.
dist/index.html                 1.77 kB │ gzip:   0.81 kB
dist/assets/index-*.css       33.84 kB │ gzip:   9.14 kB
dist/assets/forms-*.js        82.83 kB │ gzip:  25.90 kB
dist/assets/react-*.js       165.06 kB │ gzip:  53.13 kB
dist/assets/index-*.js       181.29 kB │ gzip:  56.40 kB
dist/assets/charts-*.js      422.09 kB │ gzip: 133.42 kB
✓ built in 11.20s
```

The bundle is split so that the charting library is only downloaded on the screens
that use it.

### 8.7.3 Live end-to-end verification

The offline suite runs against an in-memory database. To catch defects that only
appear with the real driver, the finished application was also exercised against a
running stack:

| Component | Version / configuration |
| --- | --- |
| API | `uvicorn app.main:app` on `127.0.0.1:8000` |
| Database | MongoDB 8.3.8 on `localhost:27017`, database `agrivision_ai` |
| Models | the trained joblib artifacts on disk (see `docs/07-results.md`) |
| Weather | live Open-Meteo requests (no mock transport) |
| Frontend | `vite` dev server on `127.0.0.1:5173` |

Two scripts drive the API with `httpx` exactly as a browser would, including the
double-submit CSRF token:

| Script | Checks | Result |
| --- | --- | --- |
| `e2e_verify.py` | 83 | **83/83 passed** |
| `e2e_admin.py` | 32 | **32/32 passed** |

The 83 checks cover:

1. health and model status;
2. registration, duplicate e-mail rejection, and login;
3. refusal of a wrong password;
4. CSRF enforcement on cookie-authenticated mutations;
5. profile read and update;
6. crop recommendation, persistence and input validation;
7. yield estimation, the interval and the field total;
8. `/crops/history` persistence;
9. the unified `/history` list, filters, detail, delete and ownership;
10. dashboard overview and analytics;
11. admin routes returning `403` to an ordinary user;
12. anonymous requests returning `401`;
13. **live** weather, forecast and geocoding responses;
14. bearer-token authentication without a CSRF header;
15. logout invalidating the session.

The 32 admin checks cover the platform statistics, the merged per-user counts, the
analytics breakdown, the audit trail, the model inventory, role promotion and
demotion, CSRF enforcement on the role change, and the fact that the role change is
enforced on the next login.

---

## 8.8 Reproducing the suite

```bash
# 1. Backend
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q

# 2. Frontend
cd frontend
npx tsc --noEmit
npm run build
```

Neither command needs a database, a network connection or a trained model. The
trained artifacts only unlock the additional inference tests.
