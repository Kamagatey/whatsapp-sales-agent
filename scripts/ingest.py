"""Pipeline d'ingestion : CSV → nettoyage → document texte → embeddings → PostgreSQL/pgvector.

Usage:
    python scripts/ingest.py

Étapes (voir README section 6 pour la justification de chaque choix technique) :
  1. Lecture de data/products.csv, customers.csv, orders.csv
  2. Nettoyage (valeurs manquantes, types)
  3. Construction d'un `document_text` par produit (pour BM25 + embeddings), avec métadonnées
  4. Calcul des embeddings OpenAI par lot
  5. Chargement dans PostgreSQL (upsert)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database.models import Customer, Order, Product  # noqa: E402
from app.database.session import get_session, init_db  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EMBEDDING_BATCH_SIZE = 100


def build_document_text(row: pd.Series) -> str:
    """Document utilisé pour la recherche (BM25 + embeddings). Contient les infos clés
    en langage naturel pour maximiser le rappel sur des requêtes en français familier."""
    return (
        f"{row['product_name']}. Catégorie: {row['category']}. {row['description']} "
        f"Prix: {row['price_fcfa']} FCFA. "
        f"Tailles disponibles: {row['available_sizes'] or 'non applicable'}. "
        f"Couleurs disponibles: {row['available_colors'] or 'non applicable'}. "
        f"Marque: {row['brand'] or 'non précisée'}. Vendeur: {row['seller_name']}. "
        f"Livraison: {row['delivery_zones']}. Mots-clés: {row['keywords']}. "
        f"Stock disponible: {row['stock_quantity']} unités."
    )


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    text_cols = ["available_sizes", "available_colors", "brand", "delivery_zones", "keywords"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str)
    df["price_fcfa"] = df["price_fcfa"].fillna(0).astype(int)
    df["stock_quantity"] = df["stock_quantity"].fillna(0).astype(int)
    df["document_text"] = df.apply(build_document_text, axis=1)
    return df


def compute_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in tqdm(range(0, len(texts), EMBEDDING_BATCH_SIZE), desc="Embeddings"):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(model=settings.embedding_model, input=batch)
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


def load_products(session, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        existing = session.get(Product, row["id"])
        values = dict(
            product_name=row["product_name"],
            category=row["category"],
            description=row["description"],
            price_fcfa=int(row["price_fcfa"]),
            stock_quantity=int(row["stock_quantity"]),
            available_sizes=row["available_sizes"],
            available_colors=row["available_colors"],
            brand=row["brand"],
            seller_name=row["seller_name"],
            delivery_zones=row["delivery_zones"],
            keywords=row["keywords"],
            document_text=row["document_text"],
            embedding=row["embedding"],
        )
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(Product(id=row["id"], **values))


def load_customers(session, df: pd.DataFrame) -> None:
    df = df.drop_duplicates(subset="phone", keep="first")  # sécurité si le CSV contient encore des doublons
    for _, row in df.iterrows():
        existing = (
            session.query(Customer).filter(Customer.phone == row["phone"]).first()
            or session.get(Customer, row["customer_id"])
        )
        values = dict(
            name=row["name"],
            phone=row["phone"],
            location=row["location"],
            purchase_history=row.get("purchase_history", "[]"),
        )
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(Customer(customer_id=row["customer_id"], **values))


def load_orders(session, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        existing = session.get(Order, row["order_id"])
        values = dict(
            customer_id=row["customer_id"],
            product_id=row["product_id"],
            quantity=int(row["quantity"]),
            status=row["status"],
            date=pd.to_datetime(row["date"]),
        )
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(Order(order_id=row["order_id"], **values))


def main():
    print("Initialisation du schéma PostgreSQL...")
    init_db()

    products = clean_products(pd.read_csv(DATA_DIR / "products.csv"))
    customers = pd.read_csv(DATA_DIR / "customers.csv").fillna("")
    orders = pd.read_csv(DATA_DIR / "orders.csv").fillna("")

    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY manquant : impossible de calculer les embeddings.")

    client = OpenAI(api_key=settings.openai_api_key)
    products["embedding"] = compute_embeddings(client, products["document_text"].tolist())

    with get_session() as session:
        load_customers(session, customers)
        load_products(session, products)
        load_orders(session, orders)

    print(f"Ingestion terminée : {len(products)} produits, {len(customers)} clients, "
          f"{len(orders)} commandes chargés dans PostgreSQL.")


if __name__ == "__main__":
    main()
