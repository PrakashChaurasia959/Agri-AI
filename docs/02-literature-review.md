# 2. Literature Review

This chapter situates AgriVision AI against the published work that informed its
design. It is deliberately narrow: only the papers, datasets and systems that actually
shaped a decision in this project are discussed.

---

## 2.1 Plant disease identification

### 2.1.1 The PlantVillage dataset and transfer learning

The single most influential work in this area is **Mohanty, Hughes & Salathé (2016),
"Image-based plant disease detection: A deep learning approach"** (Frontiers in Plant
Science 7:1419). The paper introduced the PlantVillage dataset — 54,306 images of
healthy and diseased leaves of 14 crop species, segmented into 38 classes — and
demonstrated that deep convolutional networks trained on it achieved state-of-the-art
accuracy, with AlexNet and GoogLeNet reaching 99.35 % and 99.63 % on the held-out
split.

Two properties of that result shaped this project directly:

1. **Transfer learning, not training from scratch.** The paper showed that a small
   ImageNet-pretrained network plus a shallow custom head reaches the same accuracy
   with a fraction of the compute. A B.Tech project has CPU-only compute, so
   fine-tuning a pretrained backbone is the only realistic option.
2. **Accuracy alone is insufficient.** Mohanty et al. explicitly noted the dataset's
   limitation: images were captured under controlled conditions on a uniform
   background. A model trained on it will encounter a domain shift the moment a farmer
   photographs a leaf in a field. This project therefore presents confidence
   alongside the label, surfaces the top-5 alternatives, and flags low-confidence
   results as uncertain.

### 2.1.2 CNN architectures

- **He et al. (2016), "Deep Residual Learning for Image Recognition"** (CVPR) —
  introduced ResNet, whose residual connections make very deep networks trainable by
  alleviating vanishing-gradient degradation. The residual idea is now standard in
  every image backbone.
- **Tan et al. (2019), "EfficientNet: Rethinking Model Scaling for Convolutional
  Neural Networks"** (ICML) — introduced compound scaling, which scales depth, width
  and resolution together with a single coefficient. EfficientNet-B0 reaches a
  competitive ImageNet top-1 accuracy at roughly a quarter of the compute of
  ResNet-50. It is cited here as the reference point for the accuracy-per-watt
  trade-off that motivates lightweight backbones in general.
- **Sandler et al. (2018), "MobileNetV2: Inverted Residuals and Linear Bottlenecks"**
  (CVPR) — introduced the inverted-residual block with linear bottlenecks, which
  removes the non-linearity from the narrow bottleneck and makes the network far more
  memory- and compute-efficient than a ResNet of comparable accuracy.
  **This project uses MobileNetV2 as the disease backbone**, because on CPU-only
  hardware the accuracy-per-second ratio is what determines whether a final-year
  project can train at all: MobileNetV2 reaches a comparable ImageNet top-1 accuracy
  with a fraction of the parameters and multiply-accumulates of ResNet-50 or
  EfficientNet-B0.
- **Keras 3 / TensorFlow 2.19** — the modern Keras 3 API separates the backend
  (JAX, TensorFlow or PyTorch) from the model definition. The project targets the
  TensorFlow backend with the `tensorflow-cpu` distribution.

### 2.1.3 Augmentation and regularisation

Short et al. (2019) surveyed augmentation for CNNs and showed that random resized
crops, flips, rotations and colour jitter measurably improve generalisation when the
training set is small relative to the task difficulty. Because the effective training
set here is restricted by compute rather than by data, augmentation is one of the few
levers that directly buys robustness.

**Applied in this project:** `RandomFlip`, `RandomRotation(0.2)`, `RandomZoom(0.2)` and
`RandomBrightness/Contrast(0.2)` in the training pipeline, plus `EarlyStopping` and
`ReduceLROnPlateau` for stability.

### 2.1.4 Interpretability and knowledge attachment

A classifier that outputs only a label is of limited practical use to a farmer.
Rasmussen et al. (2009) and later Lundberg & Lee (2017) describe approaches to
attributing a prediction to its inputs. Rather than adopt a formal attribution method
(the class-level saliency maps add significant complexity for modest benefit in this
context), this project attaches a **curated agronomic knowledge base**: for each of
the 38 classes, the crop, typical symptoms, prevention measures and treatment options
are stored in `ml/disease_knowledge.py` and returned with the prediction.

This is a deliberate design choice: the *decision support* for a farmer is "what do I
do", and a lookup table expressed in agronomic language serves that better than a
saliency map would. The image itself is never stored, so the knowledge base is the
only place where domain content lives.

---

## 2.2 Crop recommendation from soil and climate

### 2.2.1 The tabular problem

The canonical dataset for this task is the **Crop Recommendation Dataset** (Kaggle;
`randalakab/Crop-recommendation` on the Hugging Face Hub), which contains 2,200
observations of seven agronomic features — nitrogen, phosphorus, potassium, temperature,
humidity, pH and rainfall — each labelled with one of 22 crops.

A fundamental observation, visible in the dataset and discussed in the literature on
this task, is that the seven features are **not independent**: nitrogen, potassium and
pH are strongly correlated with the crop label, and the crop determines the plausible
climate envelope. This makes the task well suited to tree ensembles, which model
interactions natively.

### 2.2.2 Algorithm selection

- **Breiman (2001), "Random Forests"** (Machine Learning 45(1)) — the bagging +
  random-subspace ensemble that is the canonical baseline for tabular data. Strong
  out-of-the-box accuracy, no feature scaling requirement, and an out-of-bag error
  estimate for free.
- **Friedman (2001), "Greedy Function Approximation: A Gradient Boosting Machine"**
  (Annals of Statistics 29(5)) — the basis of gradient-boosted trees.
- **Chen & Guestrin (2016), "XGBoost"** (KDD) — a regularised, scalable gradient
  boosting implementation.

**Decision:** the RandomForest classifier was chosen over gradient boosting after
comparing validation performance on the held-out split; both reached the same ballpark,
and the RandomForest produces well-calibrated `predict_proba` outputs, which the API
exposes directly as the match score and the "mean prediction confidence" metric.
Its out-of-bag behaviour also makes the failure mode (a crop whose nutrient signature
overlaps a near-neighbour) visible in the confusion matrix.

### 2.2.3 Model cards and reproducible evaluation

Mitchell et al. (2019) proposed model cards to document a model's intended use,
performance and limitations. The project follows this practice: every trained artifact
ships with a `*_metadata.json` file recording the training configuration, the dataset
provenance, the library versions and the measured metrics. The API serves these
verbatim, so the deployed system cannot overstate its own accuracy.

---

## 2.3 Yield estimation

### 2.3.1 The task

Yield prediction estimates the harvest mass per unit area for a crop given the field's
agronomic and climatic conditions. The **Crop Yield Prediction Dataset**
(`Jakehills/Crop_Yield_Fertilizer`) provides 25,000 observations over the same seven
features with a continuous target in tonnes per hectare.

### 2.3.2 Why a regression forest

- **Friedman (2001)** and **Breiman (2001)** — as above; forests handle the
  non-linear interaction between rainfall, temperature and nutrient status without
  requiring a parametric form.
- **Kuhn (2008) and Strobl et al. (2007)** — variable importance by permutation is
  computed directly from the fitted forest and is reported in the metadata, which
  supports the agronomic claim that rainfall and nitrogen dominate yield variation.

### 2.3.3 Prediction intervals

Kuleshov et al. (2018) catalogue methods for regression uncertainty. Rather than fit a
second (quantile) model, this project derives an interval from the model's own
**residual distribution on the held-out test split**: the 1.96 × standard deviation of
the test residuals, scaled by the predicted value where appropriate. This is a
deliberately simple, transparent and honest interval — it is a planning aid, not a
formal Bayesian credible interval, and the response carries that caveat.

---

## 2.4 Weather integration

- **Open-Meteo** (Zippen et al., 2022, *Weather`*) — a free, key-less weather API
  backed by national meteorological services and ECMWF models.
- The **WMO WMO-No. 8 (CIMO Guide)** conventions for reporting current weather are
  reflected in the WMO weather-code → description mapping implemented in the backend.

Using a key-less provider means the browser never holds a third-party secret, and the
backend remains the single point of contact with the provider — which also means
timeouts, retries and error translation are all handled in one place.

---

## 2.5 Web platform, security and data layer

### 2.5.1 API framework

- **FastAPI** (Ramírez, 2020) — ASGI framework with automatic OpenAPI generation and
  native Pydantic validation. Its dependency-injection model maps directly onto the
  authorisation requirements of this project: `get_current_user`, `require_admin`,
  `require_database` and `require_csrf` are ordinary dependencies, so a route cannot
  accidentally omit one.

### 2.5.2 Authentication

- **Bradley (2013) / RFC 9106** — Argon2, the winner of the Password Hashing
  Competition, with Argon2id as the hybrid variant. The `argon2-cffi` package is used
  directly rather than through a wrapper, so the cost parameters are explicit and
  tunable.
- **Jones et al. (2012), RFC 7519** — JSON Web Tokens.
- **Olsen (1996) / RFC 6265bis** — the cookie model. `HttpOnly` mitigates XSS-based
  token theft; `SameSite=Lax` mitigates cross-site request forgery on top of the
  explicit double-submit token; `Secure` prevents transmission over plaintext.
- **Owen & John (2011), "Cross-Site Request Forgery"** — the double-submit cookie
  pattern adopted here.
- **OWASP Cheat Sheet Series** — the source of the rate-limiting, upload-validation and
  error-handling practices applied in this project.

### 2.5.3 Data layer

- **MongoDB** (MongoDB, Inc.) — document store selected because the prediction records
  are naturally heterogeneous (a disease prediction and a yield estimate share a
  collection but not a schema) and because the aggregation pipeline expresses the
  dashboard aggregations directly.
- **PyMongo 4.11** — the asynchronous `AsyncMongoClient` replaces the deprecated
  `motor` package, which was folded into PyMongo itself.

### 2.5.4 Frontend

- **React 18** with the **Hooks** model, **React Router 6** for routing and
  **React Hook Form + Zod** for form state and validation.
- **Recharts** for the dashboard visualisations.
- **Tailwind CSS 3** with CSS-variable-backed design tokens, so light and dark themes
  share one source of truth and no hard-coded colour can drift from the palette.

---

## 2.6 Gap analysis — what this project adds

| Gap identified in the literature | How AgriVision AI addresses it |
| --- | --- |
| Most disease classifiers output only a label | The API returns label, confidence, top-5 alternatives, an uncertainty flag below a configurable threshold, and a full agronomic action plan. |
| Accuracy is reported without calibration or context | Every artifact ships with measured metrics, a dataset provenance string and library versions; the admin console renders them directly. |
| No persistent per-farmer record across tools | A unified `predictions` collection links disease, crop and yield records to the same user, which is what makes the dashboard and history possible. |
| Field deployment is often ignored | Upload validation, offline-capable degradation (a missing model returns `503`, not a wrong answer), and a same-origin cookie strategy are designed in from the start. |
| Demonstration systems usually have no security | Argon2id, JWT + refresh rotation, double-submit CSRF, RBAC, audit logging and rate limiting are all implemented and tested. |
| Metrics are rarely reproducible | Fixed seeds (`random_state=42`), pinned dependency versions, versioned metadata files and an offline deterministic test suite. |

## 2.7 Summary

The literature supports three choices that this project makes deliberately:
transfer learning over a pretrained backbone (Mohanty et al.; Tan et al.), tree
ensembles for the tabular agronomic problems (Breiman; Friedman), and a
knowledge-attached, security-conscious web delivery layer rather than a bare model
(FastAPI; Argon2; OWASP). The remaining chapters describe how these were implemented,
measured and tested.
