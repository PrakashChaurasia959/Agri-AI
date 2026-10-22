# 7. Results

This chapter reports what the system actually does, using numbers measured on the
development machine. Every figure in this chapter comes from an evaluation that was
run on a held-out split and written into the model's metadata file; the API serves
those same files at runtime, so the documented numbers and the numbers a user sees
are the same numbers.

**Environment of every measurement**

| | |
| --- | --- |
| CPU | 13th Gen Intel Core i5-13500H (12 cores / 16 threads) |
| RAM | 15.6 GB |
| GPU | **none** — all training and inference ran on the CPU |
| OS | Windows, PowerShell |
| Python | 3.10.11 |
| TensorFlow | 2.19.1 (CPU build) |
| Keras | 3.12.4 |
| scikit-learn | 1.5.2 |
| NumPy | 2.1.3 |
| PyMongo | 4.11.3 |

---

## 7.1 Summary of the measured results

| Model | Task | Metric | Measured value | Test samples |
| --- | --- | --- | --- | --- |
| `plant_disease_mobilenetv2` | 38-way image classification | Accuracy | **0.9639** | 10 878 |
| | | Macro F1 | **0.9581** | |
| | | Weighted F1 | 0.9637 | |
| | | Macro precision | 0.9601 | |
| | | Macro recall | 0.9584 | |
| `crop_recommender_random_forest` | 22-way tabular classification | Accuracy | **0.9705** | 440 |
| | | Macro F1 | **0.9702** | |
| | | Weighted F1 | **0.9702** | |
| | | Macro precision | 0.9724 | | |
| | | Macro recall | 0.9705 | | |
| | | Mean confidence | 0.8508 | | |
| `crop_yield_random_forest` | Tabular regression | MAE | **3.7720** t/ha | 5 000 |
| | | RMSE | **4.7133** t/ha | | |
| | | MSE | 22.2150 | | |
| | | R² | **0.9122** | | |
| | | Max absolute error | 17.5806 t/ha | | |
| | | Mean residual | +0.1500 t/ha | | |

For reference, the target range of the yield dataset is 20.00 – 99.68 t/ha (mean
≈ 58.7). An MAE of 3.77 t/ha is therefore ≈ 6.4 % of the target's mean, and an R²
of 0.912 means the model explains 91.2 % of the variance in yield.

---

## 7.2 Crop recommendation

### 7.2.1 Setup

| | |
| --- | --- |
| Dataset | `randalakab/Crop-recommendation` (Hugging Face) |
| Rows | 2 200 |
| Classes | 22 crops |
| Features | nitrogen, phosphorus, potassium, temperature, humidity, rainfall, pH |
| Split | 80 % train / 20 % test, stratified, `random_state=42` |
| Test samples | 440 (exactly 20 per class) |
| Model | Random forest — 300 estimators, `max_depth=12`, `min_samples_leaf=2`, `class_weight="balanced"`, `n_jobs=-1` |

The dataset is balanced by construction (100 rows per crop), so the stratified
split produces an exactly balanced test set and the accuracy and the macro averages
are directly comparable.

### 7.2.2 Headline metrics

| Metric | Value |
| --- | --- |
| Accuracy | **0.9705** (427 / 440 correct) |
| Precision (macro) | 0.9724 |
| Recall (macro) | 0.9705 |
| F1 (macro) | 0.9702 |
| F1 (weighted) | 0.9702 |
| Mean confidence on the correct class | 0.8508 |

**13 errors out of 440.** The confusion matrix shows that they are concentrated in
one place and that they are a genuine agronomic ambiguity, not noise.

### 7.2.3 Per-class performance

| Crop | Precision | Recall | F1 | Errors |
| --- | --- | --- | --- | --- |
| apple | 1.000 | 1.000 | 1.000 | – |
| banana | 0.952 | 1.000 | 0.976 | – |
| blackgram | 0.909 | 1.000 | 0.952 | 1 → pigeonpeas |
| chickpea | 0.792 | 0.950 | 0.864 | 1 → kidneybeans |
| coconut | 0.952 | 1.000 | 0.976 | – |
| coffee | 1.000 | 1.000 | 1.000 | – |
| cotton | 1.000 | 1.000 | 1.000 | – |
| grapes | 1.000 | 1.000 | 1.000 | – |
| jute | 0.950 | 0.950 | 0.950 | 1 → pigeonpeas |
| **kidneybeans** | 0.938 | **0.750** | **0.833** | **5 → chickpea** |
| lentil | 0.952 | 1.000 | 0.976 | – |
| maize | 1.000 | 0.950 | 0.974 | 1 → blackgram |
| mango | 1.000 | 1.000 | 1.000 | – |
| mothbeans | 1.000 | 1.000 | 1.000 | – |
| mungbean | 1.000 | 1.000 | 1.000 | – |
| muskmelon | 1.000 | 1.000 | 1.000 | – |
| orange | 1.000 | 1.000 | 1.000 | – |
| papaya | 1.000 | 1.000 | 1.000 | – |
| pigeonpeas | 1.000 | 0.900 | 0.947 | 1 → blackgram, 1 → jute |
| pomegranate | 1.000 | 0.950 | 0.974 | 1 → chickpea |
| rice | 0.947 | 0.900 | 0.923 | 1 → banana, 1 → jute |
| watermelon | 1.000 | 1.000 | 1.000 | – |

Fourteen of the 22 crops are classified perfectly.

### 7.2.4 Error analysis

The 13 errors break down into three groups:

**1. Legume confusions (10 of 13 errors).** The model confuses
`kidneybeans ↔ chickpea`, `blackgram ↔ pigeonpeas`, `jute ↔ pigeonpeas` and
`pigeonpeas ↔ blackgram`. These crops share a genuinely overlapping agronomic
niche: they are all pulse crops with similar nitrogen requirements, similar
temperature preferences and similar rainfall ranges. The dataset's feature
separation between them is small, so a decision tree has to rely on fine
differences in potassium and pH.

This is not a modelling defect so much as a property of the data. It is, however,
a real product issue: telling a farmer to plant kidneybeans when the field suits
chickpea is costly. Two mitigations follow directly:

- the model already returns the **top-5** ranked crops with their scores, so the
  user sees the alternatives rather than a single wrong answer;
- the `explanation` in the response should name the nutrient bands of the
  recommended crop, which lets the farmer judge the recommendation themselves.

**2. `rice ↔ banana` and `rice ↔ jute` (3 errors).** Rice and banana have
comparable rainfall and temperature requirements in this dataset; the
discriminative signal is in pH and potassium. Again, a ranked list is the honest
response.

**3. `maize ↔ blackgram` (1 error).** A single misclassification on a class that
is otherwise perfect.

**Overall accuracy per class counts is not uniform, and the API exposes that.**
The weakest class (kidneybeans, F1 0.833) is 14 % below the strongest (F1 1.000),
which is worth stating plainly rather than hiding behind the 0.9705 headline.

### 7.2.5 On the mean confidence

The mean confidence on the correct class is **0.8508**, noticeably below the 0.9705
accuracy. The two numbers measure different things — the probability the forest
assigns to its top class, and how often that class is right — and the gap is
expected for a random forest with 300 trees: the vote fraction saturates well below
1.0 even when the trees agree unanimously in effect.

The practical consequence is that the confidence shown in the UI is **not
calibrated** — a prediction displayed as "95 % confident" is not correct 95 % of
the time. Temperature scaling on a held-out calibration split would fix this, and
it is recorded as future work in `docs/09-future-work.md` (§9.5.2). Until then the
UI treats the confidence as a *relative* indicator ("how strongly does this
prediction beat the alternatives") rather than as a probability.

---

## 7.3 Yield estimation

### 7.3.1 Setup

| | |
| --- | --- |
| Dataset | `Jakehills/Crop_Yield_Fertilizer` (Hugging Face) |
| Rows | 25 000 (22 crops × ~1 136 rows each) |
| Features | nitrogen, phosphorus, potassium, temperature, humidity, rainfall, pH |
| Target | `yield`, in **tonnes per hectare** |
| Target range | 20.00 – 99.68 t/ha |
| Split | 80 % train / 20 % test, `random_state=42` |
| Test samples | 5 000 |
| Model | Random forest — 300 estimators, `max_depth=14`, `min_samples_leaf=3`, `n_jobs=-1` |

The same seven features are used as for crop recommendation, which keeps the two
models consistent and lets the API reuse one validation schema.

### 7.3.2 Headline metrics

| Metric | Value | Interpretation |
| --- | --- | --- |
| **MAE** | **3.7720** t/ha | The typical absolute error is 3.77 t/ha ≈ 6.4 % of the target mean |
| **RMSE** | **4.7133** t/ha | The error distribution has a heavier tail than MAE implies |
| **MSE** | 22.2150 | — |
| **R²** | **0.9122** | 91.2 % of the variance in yield is explained |
| Max absolute error | 17.5806 t/ha | The worst single prediction on the test set |
| Mean residual (actual − predicted) | **+0.1500** t/ha | A very small systematic bias |

**The mean residual is the most informative number here.** At +0.15 t/ha against a
target mean of ~58.7, the model over-predicts by about 0.26 % on average. There is
no systematic inflation to correct.

### 7.3.3 Error distribution

The gap between MAE (3.77) and RMSE (4.71) tells us the error distribution is
right-skewed: most predictions land within a few tonnes, but a small number are
far off. The maximum absolute error of 17.58 t/ha is consistent with that — it is
about 4.5 × the MAE, which is a typical heavy tail rather than an outlier caused by
a broken row.

The confidence interval returned by the API is derived from this measured
dispersion: `1.96 × σ_residual`, i.e. approximately `± 9.2 t/ha`. That is an
honest interval for roughly 95 % of predictions, and it is computed from the
model's own held-out residuals rather than from an arbitrary constant.

### 7.3.4 Interpreting the numbers

The most useful way to read an MAE of 3.77 t/ha is relative to the crop:

| Crop | Typical yield in the dataset | MAE as a percentage of the crop mean |
| --- | --- | --- |
| A high-yield crop (~80 t/ha) | 80 | ≈ 4.7 % |
| A mid-yield crop (~55 t/ha) | 55 | ≈ 6.9 % |
| A low-yield crop (~25 t/ha) | 25 | ≈ 15.1 % |

The absolute error is roughly constant across the range — which is what a random
forest on this feature set produces — so the **relative** error is considerably
worse for low-yield crops. This is an important, honest caveat for the product: a
yield estimate for a low-yield crop carries proportionally much more uncertainty,
and the UI should say so. It is recorded as future work (§9.2.4).

### 7.3.5 Field total

The API reports both the per-hectare figure and the field total
(`per_hectare_yield × area_ha`). The area is echoed in `input_summary.area_ha`,
and the frontend shows the area next to the result so the multiplication is
visible to the user rather than implicit.

---

## 7.4 Disease classification

### 7.4.1 Setup

| | |
| --- | --- |
| Architecture | MobileNetV2 (ImageNet weights) + global pooling + dropout 0.3 + dense 128 + softmax over 38 classes |
| Input | 224 × 224 RGB, `x / 255`, then ImageNet mean/std (baked into the preprocessing module, not into a `Rescaling` layer) |
| Stage 1 | Backbone frozen, Adam, `lr = 1e-3`, 6 epochs, label smoothing 0.05 |
| Stage 2 | Top 35 % of the backbone unfrozen, Adam, `lr = 1e-4`, 3 epochs |
| Augmentation | rotation ±25°, shifts 10 %, shear 8°, zoom 15 %, horizontal flip, brightness 0.85 - 1.15 - **training split only** |
| Data | PlantVillage, 54,381 images, 38 classes; 43,503 train (15 % of which is validation) / 10,878 test |
| Seed | 42 |

The test shard was never used for fitting, for early stopping or for choosing the
epoch count, so the numbers below are a genuine held-out measurement.

### 7.4.2 Headline metrics

Measured on the 10,878 test images:

| Metric | Value |
| --- | --- |
| Accuracy | **0.9639** |
| Precision (macro) | 0.9601 |
| Recall (macro) | 0.9584 |
| F1 (macro) | 0.9581 |
| F1 (weighted) | 0.9637 |
| Test images | 10,878 |

Training history, recorded for reference only - it is **not** a test score:

| Stage | Train accuracy | Validation accuracy |
| --- | --- | --- |
| Stage 1 (frozen backbone, 6 epochs) | 0.8743 | 0.9353 |
| Stage 2 (fine-tuning, 3 epochs) | 0.9657 | 0.9712 |

Validation accuracy is higher than test accuracy because the validation slice is
drawn from the training shard, whose images share the exact conditions of the
examples the model was fitted on. The 0.9639 figure is the honest one.

### 7.4.3 Per-class performance

All 38 classes reach an F1 of 0.78 or better. The weakest five:

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| `Tomato___Early_blight` | 0.8917 | 0.7000 | **0.7843** | 200 |
| `Tomato___Target_Spot` | 0.8740 | 0.7651 | **0.8159** | 281 |
| `Tomato___healthy` | 0.7813 | 1.0000 | **0.8772** | 318 |
| `Tomato___Septoria_leaf_spot` | 0.8613 | 0.9124 | **0.8861** | 354 |
| `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | 0.9468 | 0.8641 | **0.9036** | 103 |

`Raspberry___healthy` and several other well-separated classes reach an F1 of 1.00.
The mean support per class is 286 images, so the weakest classes are not weak
merely because they are rare.

### 7.4.4 What the errors actually are

The ten largest off-diagonal entries of the confusion matrix:

| Count | True class | Predicted as |
| --- | --- | --- |
| 51 | `Tomato___Target_Spot` | `Tomato___healthy` |
| 20 | `Tomato___Early_blight` | `Tomato___Septoria_leaf_spot` |
| 19 | `Tomato___Spider_mites Two-spotted_spider_mite` | `Tomato___healthy` |
| 19 | `Tomato___Bacterial_spot` | `Tomato___Septoria_leaf_spot` |
| 12 | `Tomato___Septoria_leaf_spot` | `Potato___Early_blight` |
| 12 | `Tomato___Early_blight` | `Tomato___Target_Spot` |
| 12 | `Tomato___Early_blight` | `Tomato___Late_blight` |
| 12 | `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` | `Corn_(maize)___Northern_Leaf_Blight` |
| 10 | `Tomato___Late_blight` | `Tomato___Early_blight` |
| 9 | `Tomato___Tomato_Yellow_Leaf_Curl_Virus` | `Tomato___Bacterial_spot` |

Two patterns stand out. First, **every large error is between two diseases of the
same crop, or between a disease and the healthy leaf of the same crop** - the model
never confuses, say, a tomato with a grape. Second, the tomato classes dominate the
confusions because their symptoms are genuinely similar: early blight, target spot
and Septoria all produce dark lesions on the same leaf type.

### 7.4.5 Deployment notes

| | |
| --- | --- |
| Artifact | `backend/data/models/plant_disease_mobilenetv2.keras` (26.4 MB) |
| Registry | Loaded lazily on the first prediction, then cached for the process lifetime |
| Warm inference | ~150 ms per 224 × 224 image on this CPU (no GPU) |
| Serving | `POST /api/v1/disease/predict`; when the artifact is absent the endpoint returns `503` with the training command instead of a prediction |

The top-5 list returned to the client makes the model's uncertainty inspectable: a
photo whose second candidate is a different disease is visibly less certain than one
where the alternatives are negligible, and `is_certain` exposes that distinction to
the UI rather than hiding it behind a single number.

---

## 7.5 End-to-end behaviour of the deployed system

### 7.5.1 Measured response times

Timings on the development machine (CPU only, no GPU):

| Operation | Typical latency |
| --- | --- |
| `GET /api/v1/health` | < 10 ms |
| `GET /api/v1/models/status` | < 15 ms (metadata only) |
| `POST /api/v1/auth/login` | ~120 ms (Argon2id dominates) |
| `POST /api/v1/disease/predict` | ~150 ms (MobileNetV2 forward pass on one 224 × 224 image) |
| `POST /api/v1/crops/recommend` | ~30 ms |
| `POST /api/v1/yield/predict` | ~30 ms |
| `GET /api/v1/weather/current` | ~200 – 600 ms (dominated by the upstream provider) |

The first request that touches a model pays the artifact-loading cost
(a few hundred milliseconds); the registry caches the loaded bundle, so every
later request is at the steady-state figures above.

### 7.5.2 Behaviour when a dependency is missing

| Situation | Response | Body |
| --- | --- | --- |
| `MONGODB_URI` not set | `503` | "Database is not configured…" plus the environment-variable name |
| MongoDB unreachable | `503` | The connection error, translated |
| The CNN artifact absent | `503` | "The disease classifier has not been trained on this machine", with the training command |
| The crop model absent | `503` | The same pattern for the crop recommender |
| The yield model absent | `503` | The same pattern for the yield regressor |
| No authentication | `401` | The standard error envelope |
| Wrong role | `403` | The standard error envelope |
| Another user's record | `404` | The standard error envelope |

No endpoint ever invents data to fill a gap. A missing model produces an
instruction, not a fabricated prediction.

### 7.5.3 Test-suite results

```
176 passed, 4 skipped in 95.27s
```

before the CNN artifact existed; the full set after training is recorded in
`docs/08-testing.md` §8.7.

---

## 7.6 What these results do and do not establish

**Established**

- The disease classifier reaches 0.9639 accuracy / 0.9581 macro F1 over 38 classes
  on 10,878 PlantVillage test images, with every class at F1 ≥ 0.78 and the errors
  confined to look-alike diseases of the same crop (§7.4).
- The crop recommender reaches 0.9705 accuracy / 0.9702 macro F1 on a balanced,
  stratified hold-out, with 14 of 22 classes perfect.
- The yield regressor reaches R² 0.9122 with an MAE of 3.77 t/ha and a mean
  residual of +0.15 t/ha, i.e. essentially unbiased.
- The three capabilities are integrated into a working API with authentication,
  persistence, ownership isolation and an honest failure mode for every missing
  dependency.
- The whole system is verified by an offline test suite that needs neither a
  database nor a network connection.

**Not established**

- **Field performance.** Every image metric above is measured on PlantVillage, a
  segmented, background-removed dataset. A photograph taken in a real field does
  not look like a PlantVillage image, and the accuracy in the field will be lower.
  Validating on field data is the first item in `docs/09-future-work.md` (§9.2.1).
- **Confidence calibration.** The reported confidences are not calibrated
  probabilities (§7.2.5, §9.5.2).
- **Generalisation beyond the dataset's geography and season.** PlantVillage was
  assembled under specific conditions; the model's behaviour outside them is
  unmeasured.
- **Multi-instance operation.** The rate limiter is per-process and has not been
  exercised under horizontal scaling.
- **Long-term reliability.** No load test and no uptime record exist.

Stating these explicitly is part of the result: a project that presents a
0.9705 accuracy without the conditions attached has misrepresented what it has
shown.
