"""Schémas Pydantic partagés : génération de données, API, évaluation."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    vetements_africains = "vêtements africains"
    chaussures = "chaussures"
    cosmetiques = "cosmétiques"
    accessoires = "accessoires"
    telephones = "téléphones"
    electronique = "produits électroniques"


class ProductGen(BaseModel):
    """Schéma utilisé pour la génération synthétique via OpenAI structured output."""

    product_name: str
    category: Category
    description: str = Field(..., description="Description commerciale courte, 1-2 phrases")
    price_fcfa: int = Field(..., ge=500, le=500000)
    stock_quantity: int = Field(..., ge=0, le=200)
    available_sizes: List[str] = Field(default_factory=list)
    available_colors: List[str] = Field(default_factory=list)
    brand: Optional[str] = None
    seller_name: str
    delivery_zones: List[str]
    keywords: List[str] = Field(default_factory=list)


class ProductBatch(BaseModel):
    """Wrapper pour demander plusieurs produits en un seul appel structured output."""

    products: List[ProductGen]


class CustomerGen(BaseModel):
    name: str
    phone: str
    location: str


class CustomerBatch(BaseModel):
    customers: List[CustomerGen]


class QAPair(BaseModel):
    """Une paire question/réponse générée à partir d'un produit, pour l'évaluation."""

    product_id: str
    question: str
    expected_answer: str


class QAPairBatch(BaseModel):
    qa_pairs: List[QAPair]


# --- Schémas API ---

class ChatRequest(BaseModel):
    session_id: str
    customer_phone: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    retrieval_method: str
    tools_called: List[str] = Field(default_factory=list)
    latency_ms: int
    interaction_log_id: int


class FeedbackRequest(BaseModel):
    interaction_log_id: int
    session_id: str
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = None
