"""Logging des interactions pour le monitoring (bonus : coût, contexte, réponse)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.database.models import InteractionLog

# Prix approximatifs (USD / 1M tokens) — à ajuster selon la tarification OpenAI en vigueur.
MODEL_PRICING_PER_MILLION = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING_PER_MILLION.get(model, {"prompt": 0.0, "completion": 0.0})
    return (prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]) / 1_000_000


def log_interaction(
    session: Session,
    session_id: str,
    user_message: str,
    retrieved_context: list[dict],
    retrieval_method: str,
    tools_called: list[dict],
    final_response: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    error: str | None = None,
) -> InteractionLog:
    log = InteractionLog(
        session_id=session_id,
        user_message=user_message,
        retrieved_context=json.dumps(retrieved_context, ensure_ascii=False),
        retrieval_method=retrieval_method,
        tools_called=json.dumps(tools_called, ensure_ascii=False),
        final_response=final_response,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
        latency_ms=latency_ms,
        error=error,
    )
    session.add(log)
    session.flush()
    return log
