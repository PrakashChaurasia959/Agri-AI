"""Download and materialise the datasets used by the ML pipelines.

Usage
-----
::

    python -m scripts.download_datasets --disease      # PlantVillage images
    python -m scripts.download_datasets --tabular      # CSV datasets
    python -m scripts.download_datasets --all

The PlantVillage images are mirrored on the Hugging Face Hub as parquet
files.  They are decoded and written to disk in the classic
``<class folder>/<image>.jpg`` layout that ``image_dataset_from_directory``
expects, so the training script works with a plain directory tree.

Sources and licence notes
-------------------------
* PlantVillage - Hughes, J. D. & Salathé, M. (2015), *An open access
  repository of images on plant health* (arXiv:1511.08060).  The dataset is
  distributed for research and education use; review the dataset card of the
  mirror you use before any commercial deployment.
* Crop Recommendation Dataset - N, P, K, temperature, humidity, pH, rainfall
  with a crop label.  Mirrored at
  ``https://huggingface.co/datasets/randalakab/Crop-recommendation``.
* Crop Yield Prediction Dataset - the same agronomic features plus a yield
  column.  Mirrored at
  ``https://huggingface.co/datasets/Jakehills/Crop_Yield_Fertilizer``.

Each mirror's dataset card carries the upstream licence; review it before
committing the data to a public repository.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.config import (  # noqa: E402
    CROP_RECOMMENDATION_CSV,
    CROP_YIELD_CSV,
    DATASET_DIR,
    PLANTVILLAGE_DIR,
)

PLANTVILLAGE_BASE = (
    "https://huggingface.co/datasets/GVJahnavi/PlantVillage_dataset/resolve/main/data"
)
PLANTVILLAGE_FILES: tuple[tuple[str, str], ...] = (
    ("train-00000-of-00002.parquet", "train-0.parquet"),
    ("train-00001-of-00002.parquet", "train-1.parquet"),
    ("test-00000-of-00001.parquet", "test.parquet"),
)

CROP_RECOMMENDATION_URL = (
    "https://huggingface.co/datasets/randalakab/Crop-recommendation/resolve/main/"
    "crop_recommendation.csv"
)
CROP_YIELD_URL = (
    "https://huggingface.co/datasets/Jakehills/Crop_Yield_Fertilizer/resolve/main/"
    "Crop_Yield_Fertilizer.csv"
)

RAW_DIR = DATASET_DIR / "_raw"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def download_file(url: str, destination: Path, *, retries: int = 5) -> Path:
    """Download ``url`` to ``destination`` with retries and resume support."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.stat().st_size > 0:
        print(f"  [skip] {destination.name} already present "
              f"({destination.stat().st_size / 1e6:.1f} MB)")
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            print(f"  [get ] {destination.name} (attempt {attempt}/{retries})")
            request = urllib.request.Request(
                url, headers={"User-Agent": "agrivision-ai/1.0 (dataset fetcher)"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                with partial.open("wb") as handle:
                    shutil.copyfileobj(response, handle, length=1024 * 1024)
            partial.replace(destination)
            print(f"  [ok  ] {destination.name} "
                  f"({destination.stat().st_size / 1e6:.1f} MB)")
            return destination
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  [warn] download failed: {type(exc).__name__}: {exc}")
            if attempt == retries:
                break
    raise RuntimeError(f"Could not download {url}")


# ---------------------------------------------------------------------------
# PlantVillage
# ---------------------------------------------------------------------------
def _class_names_from_metadata(raw_dir: Path) -> list[str]:
    """Read the class names from the parquet schema metadata.

    The Hugging Face writer stores the label mapping in one of two shapes
    depending on the dataset revision - ``class_label.names`` (older) or a
    plain ``names`` list (current).  Both are handled.
    """
    import pyarrow.parquet as pq

    schema = pq.read_schema(raw_dir / PLANTVILLAGE_FILES[0][1])
    metadata = schema.metadata or {}
    raw = metadata.get(b"huggingface")
    if not raw:
        return []
    info = json.loads(raw.decode("utf-8"))
    features = info.get("info", {}).get("features", {})
    label_feature = features.get("label", {})
    names = label_feature.get("class_label", {}).get("names") or label_feature.get("names")
    return [str(name) for name in (names or [])]


def _iter_rows(parquet_path: Path) -> Iterator[tuple[bytes, int]]:
    """Yield ``(image_bytes, label_index)`` pairs from a parquet shard."""
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(parquet_path)
    for batch in parquet_file.iter_batches(batch_size=256):
        data = batch.to_pydict()
        for image_struct, label in zip(data["image"], data["label"]):
            if isinstance(image_struct, dict):
                payload = image_struct.get("bytes")
            else:  # pragma: no cover - defensive
                payload = None
            if payload:
                yield payload, int(label)


def materialise_plantvillage(*, limit: int | None = None, skip_images: bool = False) -> Path:
    """Decode the parquet shards into a class-folder directory tree."""
    import pyarrow.parquet as pq  # noqa: F401  (import check)

    print("Downloading PlantVillage parquet shards ...")
    for remote, local in PLANTVILLAGE_FILES:
        download_file(f"{PLANTVILLAGE_BASE}/{remote}", RAW_DIR / local)

    class_names = _class_names_from_metadata(RAW_DIR)
    if not class_names:
        raise RuntimeError("Could not read the class mapping from the parquet metadata")

    print(f"Found {len(class_names)} classes")

    if skip_images:
        print("  [skip] image materialisation requested (--skip-images)")
        return PLANTVILLAGE_DIR

    PLANTVILLAGE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = PLANTVILLAGE_DIR / "manifest.json"
    manifest: dict[str, Any] = {"classes": class_names, "files": {}}

    written = 0
    for _remote, local in PLANTVILLAGE_FILES:
        shard = RAW_DIR / local
        # The upstream dataset ships with an official train/test split.  The
        # test shard is kept strictly separate so that the reported test
        # metrics are computed on images the model has never been fitted on.
        split = "test" if local.startswith("test") else "train"
        print(f"  decoding {local} -> {split} ...")
        for index, (payload, label_index) in enumerate(_iter_rows(shard)):
            if limit is not None and written >= limit:
                break
            class_name = class_names[label_index]
            folder = PLANTVILLAGE_DIR / split / class_name
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{local.replace('.parquet', '')}_{index:06d}.jpg"
            if not target.exists():
                target.write_bytes(payload)
            manifest["files"].setdefault(local, 0)
            manifest["files"][local] += 1
            written += 1
        if limit is not None and written >= limit:
            break

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Materialised {written} images into {PLANTVILLAGE_DIR}")
    return PLANTVILLAGE_DIR


# ---------------------------------------------------------------------------
# Tabular datasets
# ---------------------------------------------------------------------------
def materialise_tabular() -> None:
    """Download the two tabular datasets."""
    print("Downloading the crop recommendation dataset ...")
    download_file(CROP_RECOMMENDATION_URL, CROP_RECOMMENDATION_CSV)

    print("Downloading the crop yield dataset ...")
    download_file(CROP_YIELD_URL, CROP_YIELD_CSV)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the AgriVision AI datasets")
    parser.add_argument("--disease", action="store_true", help="Download PlantVillage images")
    parser.add_argument("--tabular", action="store_true", help="Download the CSV datasets")
    parser.add_argument("--all", action="store_true", help="Download everything")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only materialise this many images (useful for a quick smoke test)",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Download the parquet shards but do not decode them into image files",
    )
    args = parser.parse_args(argv)

    if not (args.disease or args.tabular or args.all):
        parser.print_help()
        return 1

    if args.tabular or args.all:
        materialise_tabular()

    if args.disease or args.all:
        materialise_plantvillage(limit=args.limit, skip_images=args.skip_images)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
