# 4. Dataset

Three public datasets are used, one per modelling task. All three are downloaded
automatically by `backend/scripts/download_datasets.py`; nothing is committed to the
repository.

---

## 4.1 Summary

| # | Dataset | Task | Rows / items | Classes | Source |
| --- | --- | --- | --- | --- | --- |
| D1 | PlantVillage | Disease classification | 54,381 images | 38 | `GVJahnavi/PlantVillage_dataset` (Hugging Face) |
| D2 | Crop Recommendation | Crop classification | 2,200 rows | 22 | `randalakab/Crop-recommendation` (Hugging Face) |
| D3 | Crop Yield Prediction | Yield regression | 25,000 rows | 22 crops | `Jakehills/Crop_Yield_Fertilizer` (Hugging Face) |

Materialised location: `backend/data/dataset/`

```
backend/data/dataset/
├── PlantVillage/
│   ├── train/<class-name>/*.jpg     43,503 images
│   └── test/<class-name>/*.jpg      10,878 images
├── _raw/                             downloaded parquet shards
├── crop_recommendation.csv           D2
├── crop_yield.csv                    D3
└── manifest.json                     provenance + file counts
```

---

## 4.2 D1 — PlantVillage

### 4.2.1 Provenance

The dataset is published on the Hugging Face Hub as
`GVJahnavi/PlantVillage_dataset` in Parquet form. The download script reads the
shards, decodes the embedded image bytes and writes them to disk as JPEG files
organised by class, which lets the Keras `image_dataset_from_directory` pipeline
consume the data with a deterministic class ordering.

### 4.2.2 Class inventory (38)

| Crop | Classes |
| --- | --- |
| Apple | `Apple_scab`, `Black_rot`, `Cedar_apple_rust`, `healthy` |
| Blueberry | `healthy` |
| Cherry | `healthy`, `Powdery_mildew` |
| Corn (maize) | `Cercospora_leaf_spot Gray_leaf_spot`, `Common_rust_`, `healthy`, `Northern_Leaf_Blight` |
| Grape | `Black_rot`, `Esca_(Black_Measles)`, `healthy`, `Leaf_blight_(Isariopsis_Leaf_Spot)` |
| Orange | `Haunglongbing_(Citrus_greening)` |
| Peach | `Bacterial_spot`, `healthy` |
| Pepper, bell | `Bacterial_spot`, `healthy` |
| Potato | `Early_blight`, `healthy`, `Late_blight` |
| Raspberry | `healthy` |
| Soybean | `healthy` |
| Squash | `Powdery_mildew` |
| Strawberry | `healthy`, `Leaf_scorch` |
| Tomato | `Bacterial_spot`, `Early_blight`, `healthy`, `Late_blight`, `Leaf_Mold`, `Septoria_leaf_spot`, `Spider_mites Two-spotted_spider_mite`, `Target_Spot`, `Tomato_mosaic_virus`, `Tomato_Yellow_Leaf_Curl_Virus` |

The canonical class list is mirrored in `ml/disease_knowledge.py` so that the label
index, the knowledge base and the training label file can never disagree.

### 4.2.3 Split

The upstream dataset already provides a `train`/`test` partition:

| Partition | Images | Share |
| --- | --- | --- |
| Train | 43,503 | 80.0 % |
| Test | 10,878 | 20.0 % |
| **Total** | **54,381** | 100 % |

The **test** partition is used strictly for the final evaluation. During training, a
validation split is carved out of the training partition (`validation_split=0.2` in the
Keras pipeline) and is used for early stopping and learning-rate scheduling.

### 4.2.4 Preprocessing

Applied identically at training and inference time:

1. Decode to RGB.
2. Random resized crop / flip / rotation / zoom / brightness / contrast (training only).
3. Resize to **224 × 224** with bilinear interpolation.
4. Scale to `[0, 1]` (`× 1/255`).
5. Standardise with the ImageNet statistics:
   `µ = (0.485, 0.456, 0.406)`, `σ = (0.229, 0.224, 0.225)`.

224 × 224 is the native MobileNetV2 input resolution, so no upscaling artefact is
introduced for the majority of the source images (PlantVillage images are typically
256 × 256).

### 4.2.5 Known limitations

- **Controlled capture conditions.** Leaves were photographed against a plain
  background under laboratory lighting. The model will see a genuine domain shift on a
  field photograph. This is stated in the UI ("photograph one leaf against a plain
  background") and in the response disclaimer.
- **Class balance.** A few classes have far fewer samples than the largest ones. The
  confusion matrix in `docs/07-results.md` shows where this hurts.
- **No real-world validation set.** There is no held-out field dataset in the public
  domain at this scale, so the reported accuracy is an upper bound on field performance.
- **Symptom overlap.** Several diseases produce visually similar lesions (for example
  the two tomato blights); the confusion matrix quantifies this.

---

## 4.3 D2 — Crop Recommendation

### 4.3.1 Schema

| Column | Type | Unit | Range observed |
| --- | --- | --- | --- |
| `N` | float | mg/kg | 0 – 145 |
| `P` | float | mg/kg | 5 – 148 |
| `K` | float | mg/kg | 5 – 205 |
| `temperature` | float | °C | 8.5 – 43.5 |
| `humidity` | float | % | 14 – 100 |
| `ph` | float | – | 3.5 – 9.5 |
| `rainfall` | float | mm | 18.7 – 300.0 |
| `label` | category | – | 22 crops |

### 4.3.2 Labels (22)

`apple`, `banana`, `blackgram`, `chickpea`, `coconut`, `coffee`, `cotton`, `grapes`,
`jute`, `kidneybeans`, `lentil`, `maize`, `mango`, `mothbeans`, `mungbean`, `muskmelon`,
`orange`, `papaya`, `pigeonpeas`, `pomegranate`, `rice`, `watermelon`.

### 4.3.3 Preprocessing and split

- Label encoded to a contiguous integer range; the encoder is persisted inside the
  pipeline so inference needs no separate mapping file.
- No missing values and no duplicate rows were found in the source data.
- Stratified 80/20 train/test split, `random_state=42` → **1,760 train / 440 test**.
- The test split is stratified, so every class has exactly 20 test samples (visible in
  the per-class `support` values in the metadata file).

### 4.3.4 API-side validation

`CropRecommendationRequest` enforces the same physical ranges the model was trained on:

| Field | Constraint |
| --- | --- |
| `nitrogen`, `phosphorus`, `potassium` | `0 ≤ x ≤ 300` mg/kg |
| `temperature` | `0 ≤ x ≤ 60` °C |
| `humidity` | `0 ≤ x ≤ 100` % |
| `rainfall` | `0 ≤ x ≤ 500` mm |
| `ph` | `0 ≤ x ≤ 14` |
| `soil_type` | optional, ≤ 40 characters |
| `location` | optional, ≤ 160 characters |

Out-of-range values return `422` with a per-field message rather than being silently
clamped, because clamping would produce a prediction the user did not ask for.

---

## 4.4 D3 — Crop Yield Prediction

### 4.4.1 Schema

The same seven features as D2, plus a continuous target:

| Column | Type | Unit |
| --- | --- | --- |
| `N`, `P`, `K` | float | mg/kg |
| `temperature` | float | °C |
| `humidity` | float | % |
| `ph` | float | – |
| `rainfall` | float | mm |
| `yield` | float | **tonnes per hectare** |

### 4.4.2 Target statistics

| Statistic | Value |
| --- | --- |
| Minimum | 20.00 t/ha |
| Maximum | 99.68 t/ha |
| Rows | 25,000 |
| Crops | 22 |
| Test rows | 5,000 (20 %) |

### 4.4.3 Preprocessing and split

- Stratified 80/20 split on the crop label (`random_state=42`) → **20,000 train / 5,000
  test**. Stratification matters here because the per-crop yield distribution differs;
  an unstratified split would bias the MAE.
- The same `StandardScaler` → `RandomForestRegressor` pipeline shape as D2, so the two
  tabular models share one serialisation strategy.

### 4.4.4 API-side validation

`YieldPredictionRequest` reuses the D2 constraints and adds:

| Field | Constraint |
| --- | --- |
| `crop_type` | 2 – 60 characters; must be one of the 22 supported crops |
| `area_ha` | `0 < x ≤ 100,000` hectares |

---

## 4.5 Reproducibility

| Aspect | Control |
| --- | --- |
| Split | `random_state=42`, stratified where a label exists |
| Library versions | Recorded in every `*_metadata.json` under `library_versions` |
| Dataset provenance | Recorded under `dataset_source` (the exact dataset identifier) |
| Configuration | The full hyper-parameter dictionary is stored in the metadata file |
| Artifacts | Written atomically next to the metadata, so a metadata file always matches its model |

Recorded library versions for the tabular models:

```
scikit-learn 1.5.2
pandas       2.2.3
numpy        2.1.3
```

---

## 4.6 Data governance

- No image binaries are written to MongoDB. Only metadata (dimensions, format, byte
  size) is persisted, which keeps the database small and reduces privacy exposure.
- No dataset file is committed; `.gitignore` excludes `backend/data/dataset/` and
  `backend/data/models/`.
- Personal records are scoped to a `user_id` and every read and delete re-checks
  ownership server-side.
- Passwords are stored only as Argon2id hashes.
