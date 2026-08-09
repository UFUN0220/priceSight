"""Expiring offer cache with optional local SQLite persistence and lookup metadata."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3
import time

from app.comparison.models import NormalizedOffer


@dataclass(frozen=True)
class CacheLookup:
    offer: NormalizedOffer | None
    age_seconds: float | None

    @property
    def hit(self) -> bool:
        return self.offer is not None


@dataclass(frozen=True)
class _Entry:
    offer: NormalizedOffer
    created_at: float
    expires_at: float


class OfferCache:
    """Identity-complete cache; memory is the default, SQLite is opt-in for local persistence."""

    def __init__(self, ttl_seconds: int = 300, path: str | Path | None = None) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, _Entry] = {}
        self.path = Path(path) if path is not None else None
        self._connection: sqlite3.Connection | None = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path)
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS offer_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    platform_id TEXT NOT NULL,
                    source_store TEXT NOT NULL,
                    normalized_product TEXT NOT NULL,
                    specification TEXT NOT NULL
                )
                """
            )
            self._connection.commit()

    @staticmethod
    def key(*, platform: str, store: str, product: str, specification: str) -> str:
        identity = "|".join((platform, store, product, specification))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def lookup(self, key: str) -> CacheLookup:
        now = time.time()
        if self._connection is None:
            entry = self._entries.get(key)
            if entry is None:
                return CacheLookup(offer=None, age_seconds=None)
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return CacheLookup(offer=None, age_seconds=None)
            return CacheLookup(offer=entry.offer, age_seconds=max(0.0, now - entry.created_at))

        row = self._connection.execute(
            "SELECT payload, created_at, expires_at FROM offer_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return CacheLookup(offer=None, age_seconds=None)
        payload, created_at, expires_at = row
        if float(expires_at) <= now:
            self._connection.execute("DELETE FROM offer_cache WHERE cache_key = ?", (key,))
            self._connection.commit()
            return CacheLookup(offer=None, age_seconds=None)
        return CacheLookup(
            offer=NormalizedOffer.model_validate_json(payload),
            age_seconds=max(0.0, now - float(created_at)),
        )

    def get(self, key: str) -> NormalizedOffer | None:
        return self.lookup(key).offer

    def set(self, key: str, offer: NormalizedOffer) -> None:
        now = time.time()
        created_at = now
        expires_at = now + self.ttl_seconds
        if self._connection is None:
            self._entries[key] = _Entry(offer=offer, created_at=created_at, expires_at=expires_at)
            return
        specification = offer.specification.model_dump_json()
        self._connection.execute(
            """
            INSERT INTO offer_cache(
                cache_key, payload, created_at, expires_at,
                platform_id, source_store, normalized_product, specification
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload=excluded.payload,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at,
                platform_id=excluded.platform_id,
                source_store=excluded.source_store,
                normalized_product=excluded.normalized_product,
                specification=excluded.specification
            """,
            (
                key,
                offer.model_dump_json(),
                created_at,
                expires_at,
                offer.platform_id,
                offer.source_store,
                offer.identity.normalized_name,
                specification,
            ),
        )
        self._connection.commit()

    def clear(self) -> None:
        self._entries.clear()
        if self._connection is not None:
            self._connection.execute("DELETE FROM offer_cache")
            self._connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
