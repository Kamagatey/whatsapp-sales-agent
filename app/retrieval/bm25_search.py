"""Recherche textuelle BM25 sur le catalogue produit.

L'index est reconstruit en mémoire à partir de la base (peu coûteux : quelques centaines
de produits). Pour un catalogue beaucoup plus grand, on persisterait l'index (ex. disque
ou Elasticsearch), mais ce n'est pas justifié à cette échelle.
"""
from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.database.models import Product


def _tokenize(text: str) -> list[str]:
    return text.lower().replace(",", " ").replace(".", " ").split()


@dataclass
class BM25Result:
    product_id: str
    score: float


class BM25Index:
    def __init__(self, session: Session):
        self.products: list[Product] = session.query(Product).all()
        corpus = [_tokenize(p.document_text or "") for p in self.products]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int = 5) -> list[BM25Result]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.products, scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [BM25Result(product_id=p.id, score=float(s)) for p, s in ranked if s > 0]
