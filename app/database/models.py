"""Modèles SQLAlchemy — produits, clients, commandes, conversations, logs monitoring."""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

EMBEDDING_DIM = 1536  # text-embedding-3-small


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    product_name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    price_fcfa = Column(Integer, nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    available_sizes = Column(String)   # ex: "S,M,L,XL" ou "38,39,40,41,42"
    available_colors = Column(String)  # ex: "bleu,rouge,noir"
    brand = Column(String)
    seller_name = Column(String, nullable=False)
    delivery_zones = Column(String)    # ex: "Abidjan,Yopougon,Cocody"
    keywords = Column(String)          # mots-clés séparés par virgules, pour BM25/metadata

    # Document textuel utilisé pour l'indexation (BM25 + embeddings)
    document_text = Column(Text)
    embedding = Column(Vector(EMBEDDING_DIM))

    orders = relationship("Order", back_populates="product")


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, unique=True)
    location = Column(String)
    purchase_history = Column(Text)  # JSON sérialisé d'IDs de commandes passées

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="pending")  # pending/confirmed/delivered/cancelled
    date = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product", back_populates="orders")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    customer_phone = Column(String, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant" | "tool"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class InteractionLog(Base):
    """Log détaillé pour le monitoring : question, contexte récupéré, réponse, coût, latence."""

    __tablename__ = "interaction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    user_message = Column(Text, nullable=False)
    retrieved_context = Column(Text)          # JSON des documents récupérés
    retrieval_method = Column(String)          # "bm25" | "vector" | "hybrid"
    tools_called = Column(Text)                # JSON des tools appelés + arguments
    final_response = Column(Text, nullable=False)
    model = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    estimated_cost_usd = Column(Float)
    latency_ms = Column(Integer)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserFeedback(Base):
    """Feedback utilisateur (pouce haut/bas) sur une réponse de l'assistant."""

    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interaction_log_id = Column(Integer, ForeignKey("interaction_logs.id"))
    session_id = Column(String, index=True)
    rating = Column(Integer, nullable=False)  # 1 = positif, -1 = négatif
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
