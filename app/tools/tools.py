"""Implémentation des tools appelés par l'agent via function calling.

Chaque fonction renvoie un dict JSON-sérialisable. Le LLM ne doit jamais inventer prix,
stock ou disponibilité : ces informations proviennent uniquement de ces fonctions.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database.models import Customer, Order, Product
from app.retrieval.bm25_search import BM25Index
from app.retrieval.hybrid_search import hybrid_search


def search_products(session: Session, bm25_index: BM25Index, query: str, top_k: int = 5) -> dict:
    """Recherche hybride de produits pertinents pour une requête client."""
    results = hybrid_search(session, bm25_index, query, top_k=top_k)
    return {
        "results": [
            {
                "product_id": r.product.id,
                "product_name": r.product.product_name,
                "price_fcfa": r.product.price_fcfa,
                "stock_quantity": r.product.stock_quantity,
                "available_sizes": r.product.available_sizes,
                "available_colors": r.product.available_colors,
                "delivery_zones": r.product.delivery_zones,
                "description": r.product.description,
                "match_sources": r.sources,
            }
            for r in results
        ]
    }


def check_stock(session: Session, product_id: str, size: str | None = None) -> dict:
    """Vérifie le stock réel d'un produit (et taille si fournie)."""
    product = session.get(Product, product_id)
    if not product:
        return {"error": f"Produit {product_id} introuvable."}

    available_sizes = [s.strip() for s in (product.available_sizes or "").split(",") if s.strip()]
    if size and available_sizes and size not in available_sizes:
        return {
            "product_id": product_id,
            "requested_size": size,
            "available": False,
            "reason": "taille indisponible",
            "available_sizes": available_sizes,
        }
    return {
        "product_id": product_id,
        "in_stock": product.stock_quantity > 0,
        "stock_quantity": product.stock_quantity,
        "available_sizes": available_sizes,
    }


def get_customer_history(session: Session, customer_phone: str) -> dict:
    """Récupère l'historique de commandes d'un client via son numéro de téléphone."""
    customer = session.query(Customer).filter(Customer.phone == customer_phone).first()
    if not customer:
        return {"found": False}

    orders = session.query(Order).filter(Order.customer_id == customer.customer_id).all()
    return {
        "found": True,
        "customer_name": customer.name,
        "location": customer.location,
        "orders": [
            {
                "order_id": o.order_id,
                "product_id": o.product_id,
                "quantity": o.quantity,
                "status": o.status,
                "date": o.date.isoformat() if o.date else None,
            }
            for o in orders
        ],
    }


def create_order(session: Session, customer_phone: str, customer_name: str, product_id: str,
                  quantity: int = 1, location: str | None = None) -> dict:
    """Crée une commande. Crée le client s'il n'existe pas déjà (première commande)."""
    product = session.get(Product, product_id)
    if not product:
        return {"error": f"Produit {product_id} introuvable."}
    if product.stock_quantity < quantity:
        return {"error": "Stock insuffisant.", "stock_disponible": product.stock_quantity}

    customer = session.query(Customer).filter(Customer.phone == customer_phone).first()
    if not customer:
        customer = Customer(
            customer_id=str(uuid.uuid4())[:8],
            name=customer_name,
            phone=customer_phone,
            location=location or "",
            purchase_history=json.dumps([]),
        )
        session.add(customer)
        session.flush()

    order = Order(
        order_id=str(uuid.uuid4())[:8],
        customer_id=customer.customer_id,
        product_id=product_id,
        quantity=quantity,
        status="pending",
        date=datetime.utcnow(),
    )
    session.add(order)
    product.stock_quantity -= quantity
    session.flush()

    return {
        "order_id": order.order_id,
        "status": order.status,
        "product_name": product.product_name,
        "quantity": quantity,
        "total_fcfa": product.price_fcfa * quantity,
    }


# --- Schémas OpenAI function calling ---

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Recherche des produits pertinents dans le catalogue à partir d'une requête en langage naturel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Requête de recherche, ex: 'robe wax bleue taille M'"},
                    "top_k": {"type": "integer", "description": "Nombre de résultats", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Vérifie la disponibilité réelle en stock d'un produit, éventuellement pour une taille donnée.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "size": {"type": "string", "description": "Taille demandée, optionnelle"},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_history",
            "description": "Récupère l'historique de commandes d'un client à partir de son numéro de téléphone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {"type": "string"},
                },
                "required": ["customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Crée une commande pour un client, après confirmation du produit, de la taille/couleur et de la quantité.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer", "default": 1},
                    "location": {"type": "string"},
                },
                "required": ["customer_phone", "customer_name", "product_id"],
            },
        },
    },
]
