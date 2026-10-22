"""Shared response envelopes and pagination helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Simple ``{"message": "..."}`` payload."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Documented error payload returned by the global exception handlers."""

    detail: str
    error_code: str | None = None
    field_errors: dict[str, str] | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata attached to every list endpoint."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool = False
    has_previous: bool = False


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    items: list[T]
    pagination: PaginationMeta

    @classmethod
    def build(
        cls, items: list[T], *, page: int, page_size: int, total: int
    ) -> "PaginatedResponse[T]":
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=items,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
        )
