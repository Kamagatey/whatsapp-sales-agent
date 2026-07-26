"""Génère data/products.csv, data/customers.csv, data/orders.csv via OpenAI structured output.

Usage:
    python scripts/generate_data.py --n-products 500 --n-customers 80 --n-orders 200

Nécessite OPENAI_API_KEY dans l'environnement (.env). Chaque appel demande un lot de
produits (structured output via `ProductBatch`) pour limiter le nombre de requêtes.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from pathlib import Path

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.schemas import Category, CustomerBatch, ProductBatch  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

CITIES = ["Abidjan", "Yopougon", "Cocody", "Bouaké", "Yamoussoukro", "San-Pédro", "Marcory", "Treichville"]

CATEGORY_PROMPTS = {
    Category.vetements_africains: "vêtements africains (robes wax, boubous, ensembles pagne, chemises)",
    Category.chaussures: "chaussures (sandales, baskets, chaussures de ville, tailles 36-45)",
    Category.cosmetiques: "cosmétiques (soins de la peau, maquillage, produits capillaires africains)",
    Category.accessoires: "accessoires (sacs, bijoux, ceintures, lunettes)",
    Category.telephones: "téléphones (marques populaires en Afrique de l'Ouest, neufs et reconditionnés)",
    Category.electronique: "produits électroniques (écouteurs, chargeurs, powerbanks, petits électroménagers)",
}


def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY manquant : renseignez-le dans .env avant de lancer ce script.")
    return OpenAI(api_key=settings.openai_api_key)


def generate_product_batch(client: OpenAI, category: Category, seller_name: str, batch_size: int) -> ProductBatch:
    prompt = f"""
Tu génères des données synthétiques réalistes pour un petit vendeur ivoirien sur WhatsApp.
Catégorie : {CATEGORY_PROMPTS[category]}.
Vendeur : {seller_name}.

Génère {batch_size} produits DIFFÉRENTS et réalistes pour cette catégorie, vendus à Abidjan
et environs. Les prix doivent être réalistes en FCFA pour ce type de produit sur le marché
ivoirien. Varie les tailles/couleurs quand pertinent (mets une liste vide si non applicable,
par exemple pour les cosmétiques). Les zones de livraison doivent être choisies parmi des
quartiers/villes de Côte d'Ivoire (Abidjan, Yopougon, Cocody, Bouaké, Yamoussoukro, San-Pédro,
Marcory, Treichville). Ajoute 3 à 6 mots-clés de recherche par produit (français courant,
tels qu'un client les taperait sur WhatsApp).
"""
    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Tu es un générateur de données e-commerce pour la Côte d'Ivoire."},
            {"role": "user", "content": prompt},
        ],
        response_format=ProductBatch,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Échec du parsing structured output pour les produits.")
    return parsed


def generate_customer_batch(client: OpenAI, batch_size: int) -> CustomerBatch:
    prompt = f"""
Génère {batch_size} clients ivoiriens fictifs et réalistes (prénom + nom courants en
Côte d'Ivoire), avec un numéro de téléphone au format ivoirien (+225 suivi de 10 chiffres),
et une localisation parmi : {", ".join(CITIES)}.
"""
    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Tu génères des profils clients fictifs pour un jeu de données de test."},
            {"role": "user", "content": prompt},
        ],
        response_format=CustomerBatch,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Échec du parsing structured output pour les clients.")
    return parsed


def build_products(client: OpenAI, n_products: int) -> pd.DataFrame:
    sellers = ["Chez Adjoua Mode", "Ivoire Sneakers", "Beauté d'Abidjan", "Cocody Accessoires",
               "TechCI Store", "Wax & Style"]
    categories = list(Category)
    batch_size = 15
    n_batches = max(1, n_products // batch_size)
    rows = []
    with tqdm(total=n_batches, desc="Génération produits") as pbar:
        for i in range(n_batches):
            category = categories[i % len(categories)]
            seller = random.choice(sellers)
            batch = generate_product_batch(client, category, seller, batch_size)
            for p in batch.products:
                rows.append({
                    "id": str(uuid.uuid4())[:8],
                    "product_name": p.product_name,
                    "category": p.category.value,
                    "description": p.description,
                    "price_fcfa": p.price_fcfa,
                    "stock_quantity": p.stock_quantity,
                    "available_sizes": ",".join(p.available_sizes),
                    "available_colors": ",".join(p.available_colors),
                    "brand": p.brand or "",
                    "seller_name": p.seller_name,
                    "delivery_zones": ",".join(p.delivery_zones),
                    "keywords": ",".join(p.keywords),
                })
            pbar.update(1)
    return pd.DataFrame(rows)


def build_customers(client: OpenAI, n_customers: int) -> pd.DataFrame:
    batch_size = 20
    n_batches = max(1, n_customers // batch_size)
    rows = []
    for _ in tqdm(range(n_batches), desc="Génération clients"):
        batch = generate_customer_batch(client, batch_size)
        for c in batch.customers:
            rows.append({
                "customer_id": str(uuid.uuid4())[:8],
                "name": c.name,
                "phone": c.phone,
                "location": c.location,
                "purchase_history": json.dumps([]),
            })

    df = pd.DataFrame(rows)
    n_before = len(df)
    df = df.drop_duplicates(subset="phone", keep="first").reset_index(drop=True)
    if len(df) < n_before:
        print(f"⚠️ {n_before - len(df)} doublons de téléphone générés par le LLM et supprimés.")
    return df


def build_orders(products: pd.DataFrame, customers: pd.DataFrame, n_orders: int) -> pd.DataFrame:
    """Les commandes n'ont pas besoin d'un LLM : simple échantillonnage réaliste."""
    statuses = ["pending", "confirmed", "delivered", "cancelled"]
    weights = [0.25, 0.3, 0.35, 0.10]
    rows = []
    for _ in range(n_orders):
        product = products.sample(1).iloc[0]
        customer = customers.sample(1).iloc[0]
        rows.append({
            "order_id": str(uuid.uuid4())[:8],
            "customer_id": customer["customer_id"],
            "product_id": product["id"],
            "quantity": random.randint(1, 3),
            "status": random.choices(statuses, weights=weights, k=1)[0],
            "date": pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=random.randint(0, 90)),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-products", type=int, default=500)
    parser.add_argument("--n-customers", type=int, default=80)
    parser.add_argument("--n-orders", type=int, default=200)
    args = parser.parse_args()

    client = get_client()

    products = build_products(client, args.n_products)
    products.to_csv(DATA_DIR / "products.csv", index=False)
    print(f"{len(products)} produits sauvegardés dans data/products.csv")

    customers = build_customers(client, args.n_customers)
    customers.to_csv(DATA_DIR / "customers.csv", index=False)
    print(f"{len(customers)} clients sauvegardés dans data/customers.csv")

    orders = build_orders(products, customers, args.n_orders)
    orders.to_csv(DATA_DIR / "orders.csv", index=False)
    print(f"{len(orders)} commandes sauvegardées dans data/orders.csv")


if __name__ == "__main__":
    main()
