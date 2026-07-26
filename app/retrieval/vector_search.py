"""Recherche vectorielle via pgvector (embeddings OpenAI text-embedding-3-small)."""
from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import Product

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def embed_query(query: str) -> list[float]:
    response = _get_client().embeddings.create(model=settings.embedding_model, input=[query])
    return response.data[0].embedding


@dataclass
class VectorResult:
    product_id: str
    score: float  # similarité cosinus (plus haut = plus proche)


def vector_search(session: Session, query: str, top_k: int = 5) -> list[VectorResult]:
    query_embedding = embed_query(query)
    # pgvector: `<=>` = distance cosinus (0 = identique). On convertit en score de similarité.
    rows = (
        session.query(
            Product.id,
            Product.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .order_by("distance")
        .limit(top_k)
        .all()
    )
    return [VectorResult(product_id=r.id, score=1 - float(r.distance)) for r in rows]
