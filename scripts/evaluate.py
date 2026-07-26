"""Évaluation retrieval (BM25 vs vector vs hybrid) et LLM (prompts/modèles).

Usage:
    python scripts/evaluate.py --mode retrieval
    python scripts/evaluate.py --mode llm

Métriques retrieval : hit-rate@k et MRR@k, calculées sur data/evaluation_dataset.json
(chaque paire question/produit sert de vérité terrain : le produit source doit apparaître
dans le top-k retourné par la méthode évaluée).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from openai import OpenAI  # noqa: E402

from app.agent.prompts import SYSTEM_PROMPT  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import get_session  # noqa: E402
from app.retrieval.bm25_search import BM25Index  # noqa: E402
from app.retrieval.vector_search import vector_search  # noqa: E402
from app.retrieval.hybrid_search import hybrid_search  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RESULTS_DIR = DATA_DIR / "eval_results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_eval_dataset() -> list[dict]:
    path = DATA_DIR / "evaluation_dataset.json"
    if not path.exists():
        raise SystemExit("data/evaluation_dataset.json introuvable — lancez d'abord "
                          "scripts/generate_eval_dataset.py")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def hit_rate_and_mrr(ranked_ids_per_query: list[list[str]], ground_truth_ids: list[str], k: int = 5) -> tuple[float, float]:
    hits = 0
    reciprocal_ranks = []
    for ranked_ids, gt_id in zip(ranked_ids_per_query, ground_truth_ids):
        top_k = ranked_ids[:k]
        if gt_id in top_k:
            hits += 1
            reciprocal_ranks.append(1 / (top_k.index(gt_id) + 1))
        else:
            reciprocal_ranks.append(0)
    n = len(ground_truth_ids)
    return hits / n, sum(reciprocal_ranks) / n


def evaluate_retrieval(sample_size: int = 100, k: int = 5):
    dataset = load_eval_dataset()[:sample_size]
    with get_session() as session:
        bm25_index = BM25Index(session)

        bm25_ranked, vector_ranked, hybrid_ranked, gt_ids = [], [], [], []
        for item in dataset:
            question = item["question"]
            gt_ids.append(item["product_id"])

            bm25_ranked.append([r.product_id for r in bm25_index.search(question, top_k=k)])
            vector_ranked.append([r.product_id for r in vector_search(session, question, top_k=k)])
            hybrid_ranked.append([r.product.id for r in hybrid_search(session, bm25_index, question, top_k=k)])

    results = {}
    for name, ranked in [("bm25", bm25_ranked), ("vector", vector_ranked), ("hybrid", hybrid_ranked)]:
        hr, mrr = hit_rate_and_mrr(ranked, gt_ids, k=k)
        results[name] = {"hit_rate@k": hr, "mrr@k": mrr}
        print(f"{name:8s} — hit_rate@{k}: {hr:.3f}  mrr@{k}: {mrr:.3f}")

    best = max(results, key=lambda m: results[m]["hit_rate@k"])
    print(f"\nMeilleure méthode : {best}")

    with open(RESULTS_DIR / "retrieval_evaluation.json", "w", encoding="utf-8") as f:
        json.dump({"k": k, "sample_size": len(dataset), "results": results, "best_method": best}, f, indent=2)


PROMPT_VARIANTS = {
    "baseline": SYSTEM_PROMPT,
    "concise": SYSTEM_PROMPT + "\n\nContrainte supplémentaire : réponds en 1 phrase maximum.",
    "no_strict_grounding": (
        "Tu es un assistant commercial WhatsApp. Réponds de façon utile et amicale aux "
        "questions des clients sur les produits."
    ),
}

MODEL_VARIANTS = ["gpt-4o-mini", "gpt-4o"]


def llm_judge_score(client: OpenAI, question: str, expected: str, actual: str) -> int:
    """Juge binaire (0/1) : la réponse du modèle est-elle cohérente avec la réponse attendue ?"""
    prompt = f"""Question client: {question}
Réponse attendue (vérité terrain, basée sur les données réelles): {expected}
Réponse du modèle à évaluer: {actual}

La réponse du modèle est-elle correcte et cohérente avec la réponse attendue (mêmes faits,
pas d'invention) ? Réponds uniquement par 1 (oui) ou 0 (non)."""
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    try:
        return int(completion.choices[0].message.content.strip()[0])
    except (ValueError, IndexError):
        return 0


def evaluate_llm(sample_size: int = 30):
    """Compare des variantes de prompt et de modèle sur un sous-échantillon du dataset Q/R,
    en utilisant le contexte produit réel (pas l'agent complet, pour isoler la qualité du LLM)."""
    dataset = load_eval_dataset()[:sample_size]
    client = OpenAI(api_key=settings.openai_api_key)

    with get_session() as session:
        from app.database.models import Product

        products_by_id = {
            p.id: {
                "document_text": p.document_text
            }
            for p in session.query(Product).all()
        }

    results = {}
    for prompt_name, system_prompt in PROMPT_VARIANTS.items():
        for model in MODEL_VARIANTS:
            scores = []
            latencies = []
            for item in dataset:
                product = products_by_id.get(item["product_id"])
                if not product:
                    continue
                context = product["document_text"]
                start = time.time()
                completion = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Contexte produit:\n{context}\n\nQuestion: {item['question']}"},
                    ],
                )
                latencies.append(time.time() - start)
                actual = completion.choices[0].message.content
                scores.append(llm_judge_score(client, item["question"], item["expected_answer"], actual))
            key = f"{prompt_name}__{model}"
            results[key] = {
                "accuracy": sum(scores) / len(scores) if scores else 0,
                "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0,
                "n": len(scores),
            }
            print(f"{key:35s} — accuracy: {results[key]['accuracy']:.3f}  "
                  f"latence moy.: {results[key]['avg_latency_s']:.2f}s")

    best = max(results, key=lambda k: results[k]["accuracy"])
    print(f"\nMeilleure combinaison prompt/modèle : {best}")

    with open(RESULTS_DIR / "llm_evaluation.json", "w", encoding="utf-8") as f:
        json.dump({"sample_size": len(dataset), "results": results, "best_combination": best}, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["retrieval", "llm"], required=True)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if args.mode == "retrieval":
        evaluate_retrieval(sample_size=args.sample_size or 100, k=args.k)
    else:
        evaluate_llm(sample_size=args.sample_size or 30)


if __name__ == "__main__":
    main()
