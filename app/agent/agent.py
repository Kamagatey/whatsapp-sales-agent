"""Boucle agent : LLM + function calling sur les tools métier.

Flux (voir README section "Agent Loop") :
  1. Réécriture de la requête client (query_rewrite)
  2. Construction de l'index BM25 (léger, en mémoire) pour la session
  3. Appel LLM avec les tools disponibles ; boucle tant que le modèle demande des tools
  4. Retour de la réponse finale + métadonnées (tools appelés, méthode de retrieval)
"""
from __future__ import annotations

import json
import time

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.query_rewrite import rewrite_query
from app.config import settings
from app.monitoring.logger import log_interaction
from app.retrieval.bm25_search import BM25Index
from app.tools import tools as tools_module
from app.tools.tools import TOOL_DEFINITIONS

MAX_TOOL_ITERATIONS = 5

TOOL_FUNCTIONS = {
    "search_products": tools_module.search_products,
    "check_stock": tools_module.check_stock,
    "get_customer_history": tools_module.get_customer_history,
    "create_order": tools_module.create_order,
}


class SalesAgent:
    def __init__(self, session: Session):
        self.session = session
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.bm25_index = BM25Index(session)  # reconstruit par instance ; à mettre en cache pour la prod

    def _call_tool(self, name: str, arguments: dict) -> dict:
        func = TOOL_FUNCTIONS.get(name)
        if func is None:
            return {"error": f"Tool inconnu: {name}"}
        if name == "search_products":
            return func(self.session, self.bm25_index, **arguments)
        return func(self.session, **arguments)

    def handle_message(self, session_id: str, customer_phone: str | None, message: str) -> dict:
        start = time.time()
        rewritten = rewrite_query(self.client, message)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Message client original: {message}\n"
                                          f"Intention reformulée (pour t'aider à chercher): {rewritten}\n"
                                          f"Téléphone client (si connu): {customer_phone or 'inconnu'}"},
        ]

        tools_called: list[dict] = []
        retrieved_context: list[dict] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        final_content = ""
        error = None

        try:
            for _ in range(MAX_TOOL_ITERATIONS):
                completion = self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                )
                usage = completion.usage
                if usage:
                    total_prompt_tokens += usage.prompt_tokens
                    total_completion_tokens += usage.completion_tokens

                choice = completion.choices[0]
                messages.append(choice.message.model_dump(exclude_none=True))

                if not choice.message.tool_calls:
                    final_content = choice.message.content or ""
                    break

                for tool_call in choice.message.tool_calls:
                    args = json.loads(tool_call.function.arguments or "{}")
                    result = self._call_tool(tool_call.function.name, args)
                    tools_called.append({"name": tool_call.function.name, "arguments": args})
                    if tool_call.function.name == "search_products":
                        retrieved_context.extend(result.get("results", []))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            else:
                final_content = "Désolé, je n'ai pas pu traiter votre demande complètement. Un vendeur va revenir vers vous."

            self.session.commit()
        except Exception as exc:  # on log l'erreur mais on répond quand même proprement au client
            error = str(exc)
            final_content = "Désolé, une erreur technique est survenue. Un vendeur va vous répondre rapidement."

        latency_ms = int((time.time() - start) * 1000)
        log = log_interaction(
            session=self.session,
            session_id=session_id,
            user_message=message,
            retrieved_context=retrieved_context,
            retrieval_method="hybrid",
            tools_called=tools_called,
            final_response=final_content,
            model=settings.openai_model,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            latency_ms=latency_ms,
            error=error,
        )
        self.session.commit()

        return {
            "response": final_content,
            "retrieval_method": "hybrid",
            "tools_called": [t["name"] for t in tools_called],
            "latency_ms": latency_ms,
            "interaction_log_id": log.id,
        }
