"""Dashboard aggregation service.

Every number returned by the dashboard is computed from the documents that
belong to the signed-in user.  Nothing is hard-coded and no sample data is
injected for new accounts - a brand new user genuinely sees zeroes and an
empty state.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.logging_config import get_logger
from app.models.base import ensure_utc
from app.models.prediction import PredictionType
from app.schemas.dashboard import (
    ConfidencePoint,
    DashboardAnalytics,
    DashboardOverview,
    RecentActivity,
)
from app.services.record_kinds import as_prediction_row

logger = get_logger(__name__)

HEALTHY_MARKERS = ("healthy",)


class DashboardService:
    """Builds the dashboard overview and analytics payloads."""

    def __init__(self, predictions, crop_records, reports) -> None:
        self._predictions = predictions
        self._crop_records = crop_records
        self._reports = reports

    async def _all_rows(self, user_id: ObjectId) -> list[dict[str, Any]]:
        """Every prediction the user owns, from both collections.

        Disease predictions live in ``predictions``; crop recommendations and
        yield estimates live in ``crop_records``.  The dashboard has to merge
        them, otherwise two of the three prediction types are invisible.
        """
        predictions = await self._predictions.all_for_user(user_id)
        crop_records = await self._crop_records.all_for_user(user_id)
        return [*predictions, *(as_prediction_row(doc) for doc in crop_records)]

    async def build_overview(self, user_id: ObjectId) -> DashboardOverview:
        """Aggregate the counters shown at the top of the dashboard."""
        rows = await self._all_rows(user_id)

        total = len(rows)
        disease = 0
        crop = 0
        yield_count = 0
        healthy = 0
        affected = 0
        confidences: list[float] = []
        first_at: datetime | None = None
        last_at: datetime | None = None

        for record in rows:
            prediction_type = str(record.get("prediction_type", ""))
            if prediction_type == PredictionType.DISEASE.value:
                disease += 1
            elif prediction_type == PredictionType.CROP_RECOMMENDATION.value:
                crop += 1
            elif prediction_type == PredictionType.YIELD.value:
                yield_count += 1

            if prediction_type == PredictionType.DISEASE.value:
                label = str(record.get("predicted_class", "")).lower()
                details = record.get("details") or {}
                is_healthy = details.get("is_healthy")
                if is_healthy is None:
                    is_healthy = any(marker in label for marker in HEALTHY_MARKERS)
                if is_healthy:
                    healthy += 1
                else:
                    affected += 1

            confidence = record.get("confidence")
            if isinstance(confidence, (int, float)):
                confidences.append(float(confidence))

            created_at = ensure_utc(record.get("created_at"))
            if created_at is not None:
                if first_at is None or created_at < first_at:
                    first_at = created_at
                if last_at is None or created_at > last_at:
                    last_at = created_at

        saved_reports = await self._reports.count_for_user(user_id)
        distinct_crops = await self._crop_records.distinct_crops(user_id)

        average_confidence = (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        )

        return DashboardOverview(
            total_predictions=total,
            disease_predictions=disease,
            crop_recommendations=crop,
            yield_predictions=yield_count,
            healthy_leaves=healthy,
            affected_leaves=affected,
            saved_reports=saved_reports,
            distinct_crops_recommended=len(distinct_crops),
            average_confidence=average_confidence,
            first_prediction_at=first_at,
            last_prediction_at=last_at,
        )

    async def recent_activity(self, user_id: ObjectId, limit: int = 8) -> list[RecentActivity]:
        """The most recent predictions for the activity feed, newest first."""
        predictions = await self._predictions.recent_for_user(user_id, limit=limit)
        crop_records = await self._crop_records.recent_for_user(user_id, limit=limit)

        rows: list[RecentActivity] = [
            RecentActivity(
                id=str(record["_id"]),
                prediction_type=str(record.get("prediction_type", "unknown")),
                predicted_class=str(record.get("predicted_class", "unknown")),
                confidence=float(record["confidence"])
                if isinstance(record.get("confidence"), (int, float))
                else None,
                created_at=ensure_utc(record.get("created_at"))
                or datetime.now(timezone.utc),
            )
            for record in predictions
        ]
        for document in crop_records:
            row = as_prediction_row(document)
            rows.append(
                RecentActivity(
                    id=str(document["_id"]),
                    prediction_type=row["prediction_type"],
                    predicted_class=row["predicted_class"],
                    confidence=row["confidence"],
                    created_at=ensure_utc(row["created_at"])
                    or datetime.now(timezone.utc),
                )
            )

        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[:limit]

    async def build_analytics(
        self, user_id: ObjectId, window_days: int = 30
    ) -> DashboardAnalytics:
        """Build the chart series for the analytics panel.

        The series are computed in Python from the user's own documents.  That
        keeps the behaviour identical on every MongoDB deployment (including
        the in-memory emulator used by the tests) and avoids depending on
        server-side date operators.
        """
        window_days = max(1, min(window_days, 365))
        since = datetime.now(timezone.utc) - timedelta(days=window_days)

        rows = await self._all_rows(user_id)

        daily_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        confidence_buckets = {"High (>=80%)": 0, "Medium (50-80%)": 0, "Low (<50%)": 0}
        crop_counts: dict[str, int] = {}

        for record in rows:
            created_at = ensure_utc(record.get("created_at"))
            if created_at is None:
                continue
            if created_at < since:
                continue

            key = created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
            daily_counts[key] = daily_counts.get(key, 0) + 1

            prediction_type = str(record.get("prediction_type", "unknown"))
            type_counts[prediction_type] = type_counts.get(prediction_type, 0) + 1

            confidence = record.get("confidence")
            if isinstance(confidence, (int, float)):
                if confidence >= 0.8:
                    confidence_buckets["High (>=80%)"] += 1
                elif confidence >= 0.5:
                    confidence_buckets["Medium (50-80%)"] += 1
                else:
                    confidence_buckets["Low (<50%)"] += 1

            if prediction_type == PredictionType.CROP_RECOMMENDATION.value:
                crop = str(record.get("predicted_class", "")).strip()
                if crop:
                    crop_counts[crop] = crop_counts.get(crop, 0) + 1

        # Build a continuous daily series so the chart has no gaps.
        daily_points = []
        cursor = datetime.now(timezone.utc).date() - timedelta(days=window_days - 1)
        end = datetime.now(timezone.utc).date()
        while cursor <= end:
            key = cursor.strftime("%Y-%m-%d")
            daily_points.append({"date": key, "value": daily_counts.get(key, 0)})
            cursor += timedelta(days=1)

        type_breakdown = [
            {
                "type": key,
                "label": key.replace("_", " ").title(),
                "value": value,
            }
            for key, value in sorted(type_counts.items(), key=lambda item: item[1], reverse=True)
        ]

        crop_distribution = [
            {"crop": crop, "value": count}
            for crop, count in sorted(crop_counts.items(), key=lambda item: item[1], reverse=True)[:8]
        ]

        return DashboardAnalytics(
            daily_predictions=daily_points,
            prediction_type_breakdown=type_breakdown,
            confidence_buckets=[
                ConfidencePoint(label=label, value=value)
                for label, value in confidence_buckets.items()
            ],
            crop_distribution=crop_distribution,
            total_records=sum(type_counts.values()),
            window_days=window_days,
        )


__all__ = ["DashboardService"]
