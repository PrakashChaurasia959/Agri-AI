# 9. Future Work

This chapter records what a production deployment would need beyond what this
project implements, and — just as importantly — what it deliberately does **not**
do yet. Every item below is scoped against the measured baseline of the current
system so that the effort is justified rather than speculative.

---

## 9.1 What the current system already does well

Before the gaps, the baseline that any future work has to preserve:

| Capability | Status |
| --- | --- |
| Disease classification (38 PlantVillage classes) | Implemented and measured |
| Crop recommendation (22 crops) | Implemented and measured |
| Yield estimation | Implemented and measured |
| Weather integration (live provider, no key) | Implemented |
| Authentication, RBAC, ownership isolation | Implemented, tested |
| Offline test suite | Implemented, green |
| Reproducible model artifacts with metadata | Implemented |

The point of listing these is that the gaps in §9.2 are *additions* to a working
system, not repairs of a broken one.

---

## 9.2 The most important gaps, in priority order

### 9.2.1 The models were trained on PlantVillage — a real deployment needs field data

This is the single largest limitation of the work.

PlantVillage is a **labelled, segmented, background-removed** dataset. Every image
has a clean, uniform background and the leaf fills the frame. Images taken in a
real field do not look like that: there is soil, neighbouring plants, shadows,
occlusion, motion blur, and the camera is at an arbitrary angle and distance.

The consequence is a classic **dataset shift**: a model that scores well on
PlantVillage degrades on field photographs. The literature consistently reports
this gap for plant-disease classifiers.

**What would be needed**

1. Collect or source a field-validated dataset with the same 38 labels — for
   example images captured with a fixed protocol (distance, angle, lighting)
   across multiple locations and seasons.
2. Record the *ground truth* with an agronomist, not with a crowd label.
3. Fine-tune the existing backbone on the field data, starting from the
   PlantVillage weights, and **report both** numbers: the PlantVillage test
   accuracy and the field test accuracy. Reporting only the first would be
   misleading.
4. Ship both evaluation sets, so the difference is visible rather than implied.

**The honest interim behaviour** — which this project implements — is to display
the measured metrics of the model that is actually installed, and to state the
dataset it was trained on next to them. The API returns the model version and the
metrics; the frontend shows them; nobody is told the model has been validated on
field data when it has not.

### 9.2.2 The yield model has a single target variable

The yield regressor predicts a single scalar: the yield in tonnes per hectare for
a given (crop, soil, weather) combination. A real agronomic decision needs more:

| Additional output | Why it matters |
| --- | --- |
| Per-crop yield **breakdown** | "37 t/ha maize" is actionable; "37 t/ha" is a number without a denominator |
| Stage-wise yield | Season planning needs sowing, vegetative, flowering and grain-filling stages |
| Uncertainty per crop | The residual spread differs by crop; a single global interval is too wide for some crops and too narrow for others |
| Fertiliser requirement | The dataset contains fertiliser columns that the current model ignores |
| Water requirement | Irrigation scheduling is the single biggest lever for yield in most of South Asia |

The dataset used (`Jakehills/Crop_Yield_Fertilizer`, 25 000 rows) already carries
the fertiliser and rainfall columns, so the extension is mostly a modelling and
schema change rather than a data-collection problem.

### 9.2.3 Recommendations are not yet agronomically grounded

The crop recommender maps seven soil/climate features onto 22 crops and produces
a ranked list. What it does **not** do:

- quantify the *magnitude* of the mismatch ("rice needs 60 % more potassium than
  your soil provides");
- account for the crop already planted on the field (rotation);
- respect the user's stated `primary_crops` and `farm_size_hectares`;
- consider market prices, water availability or labour.

A rule engine that translates the model's output into a concrete, quantified
advisory ("add 40 kg/ha potassium; maize would need 25 % more irrigation") would
make the feature far more useful. The `explanation` field in the response is the
natural place for it.

### 9.2.4 A single global confidence interval for yield

The current interval is `1.96 × σ`, where `σ` is the residual standard deviation on
the held-out split — a sound, honest default, but a global one. A per-crop
residual scale, or a quantile regressor (predicting the 10th and 90th percentile
directly), would give a sharper and more honest interval.

### 9.2.5 The disease classifier cannot say "I don't know"

The model is trained with 38 classes and always returns a softmax distribution.
For an image that matches none of them — a healthy plant, a different crop, a
photograph of the soil, an unrelated object — it still returns a label.

The response already contains `is_confident`, `uncertain` and `uncertainty_message`
fields, and the frontend renders them. What is missing is a **reject option**:
either

- a 39th "not a plant leaf / out of distribution" class, trained on a negative
  dataset; or
- an explicit confidence floor below which the API returns
  `{"class": null, "uncertain": true}` instead of a label.

Both are meaningful improvements; the first needs negative data, the second needs
a threshold validated on a held-out "not a leaf" set. Reporting a confidence
without ever abstaining is a known weakness of closed-set classifiers.

### 9.2.6 The models are trained but not continuously improved

There is no loop that collects the predictions the users make, compares them with
what actually happened, and feeds that back into the model. The `predictions`
collection already captures the inputs and the outputs, which is the raw material
for:

- **drift detection** — the distribution of predicted features moving away from
  the training distribution;
- **active learning** — surfacing the images the model was least confident about,
  for a human to label;
- **per-user calibration** — checking whether the reported confidence matches the
  observed accuracy for that user, farm or region.

### 9.2.7 Weather is retrieved but not integrated into the models

The weather service is live and correct, but the yield model takes rainfall and
temperature as *inputs supplied by the user*. It does not fetch the forecast
itself. The obvious integration is:

- the yield request may carry a latitude/longitude instead of manual weather
  values, and the backend fetches the forecast and feeds it to the model;
- the disease endpoint may warn when the forecast indicates conditions favourable
  to a specific pathogen;
- the crop recommender may exclude crops whose water requirement exceeds the
  expected rainfall.

The backend is already the only component that talks to the provider, so this
change stays behind the existing service boundary.

---

## 9.3 Engineering and platform work

### 9.3.1 Authentication and session management

| Gap | Current state | Target |
| --- | --- | --- |
| Multi-factor authentication | Not implemented | TOTP or e-mail OTP for admins |
| Password reset | Not implemented | Token-based reset flow with an expiry |
| Session management UI | Not implemented | "Sign out everywhere" — revoke all refresh tokens |
| Device/audit view | Not implemented | List the sessions with IP and last-used time |
| Email verification | Not implemented | Verify the address before enabling the account |

### 9.3.2 Rate limiting is per-process

The limiter is an in-process sliding window, which is correct for a single
instance and incorrect for several. A shared store (Redis) or a MongoDB-backed
window would be required. The interface is already a dependency, so swapping the
implementation is a contained change.

### 9.3.3 Observability

The application logs structured lines but does not export metrics or traces.

| Signal | Tool |
| --- | --- |
| Request rate, latency, error rate | Prometheus + `prometheus-fastapi-instrumentator` |
| Exception tracking | Sentry |
| Structured logs | `structlog` with JSON output, shipped to Loki/Datadog |
| Frontend errors | Sentry browser SDK |
| Model-drift dashboards | Evidently or a bespoke drift job |

### 9.3.4 Database

| Gap | Note |
| --- | --- |
| No replica-set read preference | Only needed when a cluster is actually large |
| No connection-pool tuning | PyMongo's defaults are fine at this scale; `maxPoolSize` should be set once the instance count is known |
| No schema validation at the database level | `jsonSchema` validation on the collections would protect against a rogue writer |
| No backup/restore policy | Atlas snapshots + a documented restore drill |
| No data retention policy | Prediction history should expire after a defined period |

### 9.3.5 Background work

Nothing is queued. The natural jobs are: weather prefetch and caching, model
warm-up after a restart, drift computation, weekly digest e-mails, and model
retraining triggers. A Celery/RQ worker with Redis, or APScheduler for the
in-process variant, would cover them.

### 9.3.6 Caching

The dashboard aggregations are recomputed on every request. For a user with a long
history this becomes expensive. A short-lived cache (Redis, or an in-process TTL
cache) keyed by `(user_id, window)` would fix it.

### 9.3.7 Testing

| Gap | Note |
| --- | --- |
| No browser-automation suite | Playwright would cover the login → predict → history flow end to end |
| No load testing | Locust or k6 against the API to establish the concurrency profile |
| No model-drift test | A test that re-runs the evaluation on a saved sample set and asserts the accuracy has not collapsed |
| Coverage is not measured | `pytest-cov` would show which branches are untested |

### 9.3.8 Frontend

| Gap | Note |
| --- | --- |
| No offline support | A service worker would let a farmer use the tool without connectivity |
| No i18n | The UI is English-only; the target user base is multilingual |
| No image capture guidance | A short in-app guide (distance, angle, lighting) would materially improve the disease-classification input quality |
| No push notifications | Alerts for a drifting forecast or a new recommendation |

---

## 9.4 Deployment and operations

### 9.4.1 Container and platform work

| Gap | Note |
| --- | --- |
| Model artifacts are not in the image | They are large (~14 MB) and versioned separately; the image should pull them from an artefact store or a mounted volume, keyed by the model version |
| No blue/green deployment | The model version and the API version should be deployable independently |
| No CI/CD pipeline | Build → test → typecheck → containerise → deploy, with the model artifact pinned |
| No health-based readiness probe | The `/api/v1/health` endpoint already distinguishes "process up" from "dependencies ready" — it should drive the readiness probe |
| TLS termination | Handled by the platform, but the `Secure` cookie flag must be verified in the deployed environment |

### 9.4.2 Scaling

The API tier is stateless and already scales horizontally. The two things that
would need attention at scale are the rate limiter (§9.3.2) and the dashboard
aggregations (§9.3.6).

---

## 9.5 Methodological improvements to the ML work itself

### 9.5.1 Better training recipes

The current recipe is a standard two-stage transfer learning:

- Stage 1: frozen backbone, head only;
- Stage 2: the top of the base network unfrozen at a lower learning rate.

Improvements worth trying, in rough order of expected value per unit of compute:

| Technique | Expected effect | Cost |
| --- | --- | --- |
| Longer Stage 1 with cosine decay | Usually a small but reliable gain | Low |
| `MixUp` / `CutMix` | Better generalisation on a small dataset | Low |
| Label smoothing (already applied at 0.05) | — | — |
| Stronger regularisation (weight decay, stochastic depth) | Less overfitting in Stage 2 | Low |
| Test-time augmentation | +0.5–1.5 % accuracy for free at inference | Low |
| A second, different backbone (EfficientNet-B0) and an ensemble | The most reliable gain | High (a second full training run) |
| Self-supervised pre-training on a larger plant-image corpus | The largest potential gain | Very high |

### 9.5.2 Proper uncertainty quantification

Beyond the confidence floor of §9.2.5: temperature scaling on a held-out
calibration split would make the reported confidences *calibrated* — meaning a
prediction stated with 80 % confidence would be correct 80 % of the time. That
property is what makes a confidence number worth showing to a farmer, and it is
cheap to obtain: one extra pass over the test split and a single scalar.

### 9.5.3 Interpretability

A Grad-CAM heat map over the classified leaf would let a user see *which part of
the image* drove the prediction, and would let an agronomist judge whether the
model is looking at the lesion or at the background. Given the background shift
described in §9.2.1, this is a useful diagnostic as well as a trust feature.

### 9.5.4 Better handling of the yield regression

| Idea | Note |
| --- | --- |
| Quantile regression (P10/P50/P90) | Directly produces the interval instead of assuming normality |
| Per-crop residual scaling | Sharper, more honest intervals |
| Gradient boosting (XGBoost / LightGBM) | Often beats a random forest on tabular data |
| Feature importance | Makes the advice explainable ("rainfall and potassium drive this estimate") |

### 9.5.5 Reproducibility and provenance

The metadata files already record the seed, the hyper-parameters and the library
versions. Extending that with a content hash of the dataset, the training
command line and the Git commit would make every artifact traceable to the exact
data and code that produced it.

---

## 9.6 Regulation, ethics and safety

An advisory tool that reaches farmers carries obligations beyond accuracy.

| Concern | Position |
| --- | --- |
| **Liability** | The API returns a `disclaimer` with every prediction. A production deployment needs a clear, legally reviewed statement that the output is advisory and must be confirmed by an agronomist. |
| **Over-treatment** | A false positive can lead to unnecessary pesticide application, with cost and ecological harm. This is the strongest argument for the confidence floor of §9.2.5. |
| **Data privacy** | Images are analysed in memory and discarded; only metadata is stored. The privacy notice should state this plainly. |
| **Bias** | The dataset was collected in a specific region under specific conditions. A model trained on it may perform worse in other agro-climatic zones; §9.2.1 must be answered before deployment beyond that region. |
| **Accessibility** | The target users are often in the field, on a mid-range phone, on a slow connection. Offline support and a low-bandwidth mode are accessibility requirements, not nice-to-haves. |

---

## 9.7 A realistic order of work

If this project were to be extended towards production, the order below maximises
value per unit of effort.

1. **Validate on field data** (§9.2.1). Everything else is a refinement of a number
   that may not transfer.
2. **Add a reject option and calibrate the confidence** (§9.2.5, §9.5.2). Two
   small changes with a large effect on trustworthiness.
3. **Integrate the weather forecast into the models** (§9.2.7). The service
   already exists; this is a modelling change.
4. **Turn the recommendations into quantified advice** (§9.2.3). This is where
   the product becomes genuinely useful to a farmer.
5. **Add CI/CD, observability and a browser test suite** (§9.3.3, §9.3.7).
   Operational maturity before feature work.
6. **Password reset, MFA, session management** (§9.3.1).
7. **Scale the yield model into a multi-target model** (§9.2.2).
8. **Move the rate limiter and the caches to a shared store** (§9.3.2, §9.3.6).
   Only necessary when there is more than one instance.

---

## 9.8 Explicitly out of scope

To keep the boundary clear, the following were deliberately **not** attempted:

| Not attempted | Why |
| --- | --- |
| Training on data the project does not have | Fabricating or substituting a dataset would make the metrics meaningless |
| Pretrained weights fetched from the internet at run time | The artifacts are reproducible from the repository plus the datasets |
| A "works offline" claim for the ML features | The models are server-side; the claim would be false |
| Auto-promoting the first user to admin | A privilege-escalation hazard; administrators are created explicitly through the CLI |
| Storing uploaded images in MongoDB | The privacy and storage cost outweigh the benefit |
| A multi-tenant organisation model | The requirement is a single-farmer tool; a tenancy layer would be speculative |
| Docker Compose as a *production* orchestrator | It is a development convenience; the deployment targets are Render and Vercel |
