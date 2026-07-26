"""Génère data/evaluation_dataset.json : Q/R synthétiques par produit, via structured output.

Usage:
    python scripts/generate_eval_dataset.py --n-per-product 2 --sample 150

`--sample` limite le nombre de produits utilisés (pour contrôler le coût), sinon tous les
produits de data/products.csv sont utilisés.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.schemas import QAPairBatch  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY manquant.")
    return OpenAI(api_key=settings.openai_api_key)


def generate_qa_for_product(client: OpenAI, product: dict, n_per_product: int) -> QAPairBatch:
    prompt = f"""
Voici un produit vendu par un petit vendeur ivoirien sur WhatsApp :

- id: {product['id']}
- nom: {product['product_name']}
- catégorie: {product['category']}
- description: {product['description']}
- prix: {product['price_fcfa']} FCFA
- tailles disponibles: {product['available_sizes']}
- couleurs disponibles: {product['available_colors']}
- zones de livraison: {product['delivery_zones']}
- stock: {product['stock_quantity']}

Génère {n_per_product} questions DIFFÉRENTES qu'un client ivoirien pourrait poser sur
WhatsApp à propos de ce produit précis (style familier, parfois abrégé), ainsi que la
réponse attendue basée UNIQUEMENT sur les informations ci-dessus (ne pas inventer).
Le champ product_id doit valoir exactement "{product['id']}" pour chaque question.
"""
    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Tu génères un dataset d'évaluation question/réponse pour un RAG."},
            {"role": "user", "content": prompt},
        ],
        response_format=QAPairBatch,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError(f"Échec parsing QA pour produit {product['id']}")
    return parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-per-product", type=int, default=2)
    parser.add_argument("--sample", type=int, default=150,
                         help="Nombre de produits à échantillonner (0 = tous)")
    args = parser.parse_args()

    products_path = DATA_DIR / "products.csv"
    if not products_path.exists():
        raise SystemExit("data/products.csv introuvable — lancez d'abord scripts/generate_data.py")

    products = pd.read_csv(products_path).fillna("")
    if args.sample:
        products = products.sample(min(args.sample, len(products)), random_state=42)

    client = get_client()
    all_pairs = []
    for _, row in tqdm(products.iterrows(), total=len(products), desc="Génération Q/R"):
        batch = generate_qa_for_product(client, row.to_dict(), args.n_per_product)
        all_pairs.extend([qa.model_dump() for qa in batch.qa_pairs])

    out_path = DATA_DIR / "evaluation_dataset.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, ensure_ascii=False, indent=2)
    print(f"{len(all_pairs)} paires Q/R sauvegardées dans {out_path}")


if __name__ == "__main__":
    main()
