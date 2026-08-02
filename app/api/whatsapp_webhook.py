"""Webhook WhatsApp Cloud API (Meta) — intégration réelle avec l'agent.

Pour l'activer :
1. Créer une app Meta for Developers + un produit WhatsApp (numéro de test gratuit fourni
   par Meta, jusqu'à 5 destinataires vérifiés — suffisant pour une démo/certification).
2. Renseigner dans .env : WHATSAPP_VERIFY_TOKEN, WHATSAPP_ACCESS_TOKEN,
   WHATSAPP_PHONE_NUMBER_ID.
3. Exposer l'API publiquement en HTTPS (ex. `ngrok http 8000` en dev) et déclarer l'URL
   `https://<domaine>/whatsapp/webhook` + le verify token dans la config webhook de Meta.
4. Ce router est déjà inclus dans app/api/main.py.

Voir docs/whatsapp_integration.md pour la comparaison avec les alternatives (Twilio,
Baileys/whatsapp-web.js, OpenClaw, etc.).
"""
from __future__ import annotations

import logging

import requests
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.agent.agent import SalesAgent
from app.config import settings
from app.database.models import Conversation
from app.database.session import SessionLocal

logger = logging.getLogger("whatsapp_webhook")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

GRAPH_API_BASE = "https://graph.facebook.com"


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Étape de vérification exigée par Meta lors de la configuration du webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Forbidden", status_code=403)


def send_whatsapp_message(to_phone: str, text: str) -> dict:
    """Envoie un message texte via l'API Graph de Meta (WhatsApp Cloud API)."""
    print(f"DEBUG - Envoi WhatsApp vers: '{to_phone}'", flush=True)
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        logger.warning("WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID non configurés — envoi ignoré.")
        return {"skipped": True}

    url = f"{GRAPH_API_BASE}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code >= 400:
        logger.error("Échec envoi WhatsApp: %s %s", response.status_code, response.text)
    return response.json()


def _extract_incoming_message(payload: dict) -> tuple[str, str, str] | None:
    """Extrait (from_phone, message_text, wa_message_id) du payload webhook Meta, ou None
    si ce n'est pas un message entrant exploitable (ex: accusé de lecture, statut de livraison)."""
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        messages = value.get("messages")
        if not messages:
            return None  # ex: notification de statut ("delivered", "read"), pas un message
        message = messages[0]
        from_phone = message["from"]
        wa_message_id = message["id"]
        if message.get("type") != "text":
            return from_phone, "[message non textuel reçu — image/audio/document non géré]", wa_message_id
        text = message["text"]["body"]
        return from_phone, text, wa_message_id
    except (KeyError, IndexError):
        logger.warning("Payload webhook WhatsApp inattendu: %s", payload)
        return None


@router.post("/webhook")
def receive_message(payload: dict):
    """Reçoit un message WhatsApp entrant, le fait traiter par l'agent, renvoie la réponse."""
    extracted = _extract_incoming_message(payload)
    if extracted is None:
        return {"status": "ignored"}

    from_phone, text, wa_message_id = extracted
    session_id = f"whatsapp:{from_phone}"

    db: Session = SessionLocal()
    try:
        db.add(Conversation(session_id=session_id, customer_phone=from_phone,
                             role="user", content=text))
        db.commit()

        agent = SalesAgent(db)
        result = agent.handle_message(session_id, from_phone, text)

        db.add(Conversation(session_id=session_id, customer_phone=from_phone,
                             role="assistant", content=result["response"]))
        db.commit()

        send_whatsapp_message(from_phone, result["response"])
        return {"status": "processed", "wa_message_id": wa_message_id}
    finally:
        db.close()
