import hashlib
import json
from typing import Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.db.models import LLMCache
from backend.app.core.logging import logger

def compute_cache_key(
    messages: list[dict[str, Any]],
    model: str,
    params: dict[str, Any],
) -> str:
    """
    Computes a canonical SHA-256 hash over the prompt messages, target model,
    and invocation parameters (temperature, max_tokens, etc.).
    """
    canonical_payload = {
        "messages": messages,
        "model": model,
        "params": sorted(params.items()),
    }
    canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ResponseCache:
    """
    PostgreSQL-backed response cache.
    Ensures repeated prompts with identical configurations cost zero API calls.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def get(self, key_hash: str) -> Optional[Tuple[dict[str, Any], int]]:
        """
        Lookup response from cache. Returns (response_dict, tokens) or None on miss.
        """
        if self.db is None:
            return None

        try:
            stmt = select(LLMCache).where(LLMCache.key_hash == key_hash)
            record = self.db.scalars(stmt).first()
            if record:
                logger.info(f"LLM cache hit [key: {key_hash[:12]}...]")
                return record.response, record.tokens
        except Exception as e:
            logger.warning(f"Error reading from LLM cache: {e}")
        return None

    def set(self, key_hash: str, response: dict[str, Any], tokens: int = 0) -> None:
        """
        Persist response and token count into cache.
        """
        if self.db is None:
            return

        try:
            stmt = select(LLMCache).where(LLMCache.key_hash == key_hash)
            existing = self.db.scalars(stmt).first()
            if existing:
                existing.response = response
                existing.tokens = tokens
            else:
                entry = LLMCache(
                    key_hash=key_hash,
                    response=response,
                    tokens=tokens,
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(entry)
            self.db.commit()
            logger.info(f"Saved response to LLM cache [key: {key_hash[:12]}...]")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Error persisting to LLM cache: {e}")

