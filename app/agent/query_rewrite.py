"""Réécriture de requête utilisateur avant recherche (étape 9 du cahier des charges).

Les messages WhatsApp sont souvent abrégés ("j veux chauss noir 42"). On les réécrit en
requête de recherche standard avant de les envoyer au retrieval, ce qui améliore le rappel
BM25 en particulier (voir scripts/evaluate.py pour la comparaison avec/sans réécriture).
"""
from __future__ import annotations

from openai import OpenAI

from app.agent.prompts import QUERY_REWRITE_PROMPT
from app.config import settings


def rewrite_query(client: OpenAI, message: str) -> str:
    completion = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": QUERY_REWRITE_PROMPT.format(message=message)}],
        temperature=0,
    )
    return completion.choices[0].message.content.strip()
