"""Recherche hybride : fusion des scores BM25 et vectoriels (reciprocal rank fusion).

RRF est préféré à une simple somme pondérée de scores car BM25 et la similarité cosinus
ne vivent pas sur la même échelle — fusionner par rang évite d'avoir à calibrer des poids.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database.models import Product
from app.retrieval.bm25_search import BM25Index
from app.retrieval.vector_search import vector_search

RRF_K = 60  # constante standard pour reciprocal rank fusion


@dataclass
class HybridResult:
    product: Product
    score: float
    sources: list[str]


def hybrid_search(session: Session, bm25_index: BM25Index, query: str, top_k: int = 5) -> list[HybridResult]:
    bm25_results = bm25_index.search(query, top_k=20)
    vector_results = vector_search(session, query, top_k=20)

    rrf_scores: dict[str, float] = {}
    sources: dict[str, set[str]] = {}

    for rank, r in enumerate(bm25_results):
        rrf_scores[r.product_id] = rrf_scores.get(r.product_id, 0) + 1 / (RRF_K + rank + 1)
        sources.setdefault(r.product_id, set()).add("bm25")

    for rank, r in enumerate(vector_results):
        rrf_scores[r.product_id] = rrf_scores.get(r.product_id, 0) + 1 / (RRF_K + rank + 1)
        sources.setdefault(r.product_id, set()).add("vector")

    ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    products_by_id = {p.id: p for p in session.query(Product).filter(Product.id.in_([i for i, _ in ranked_ids])).all()}

    results = []
    for product_id, score in ranked_ids:
        product = products_by_id.get(product_id)
        if product:
            results.append(HybridResult(product=product, score=score, sources=sorted(sources[product_id])))
    return results
