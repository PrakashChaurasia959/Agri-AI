"""Core cross-cutting concerns: configuration, security, logging, rate limiting."""

from app.core.config import get_settings

__all__ = ["get_settings"]
