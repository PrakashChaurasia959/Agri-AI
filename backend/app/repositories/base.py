"""Shared repository base class."""

from __future__ import annotations

from typing import Any


class BaseRepository:
    """Common helpers shared by the concrete repositories.

    The database handle is injected rather than imported as a global so that
    tests can point a repository at the in-memory emulator.
    """

    collection_name: str = ""

    def __init__(self, database: Any) -> None:
        self._database = database

    @property
    def collection(self) -> Any:
        return self._database[self.collection_name]

    @staticmethod
    def escape_regex(value: str) -> str:
        """Escape a user supplied string before embedding it in a ``$regex``.

        The value is always used as a *value* inside the filter, never as a
        key, so a crafted string cannot inject additional operators.  Escaping
        the regex metacharacters additionally prevents a user from supplying
        an expensive pattern such as ``.*`` that would degrade query time.
        """
        import re

        return re.escape(value.strip()[:120])
