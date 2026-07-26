"""Test de la logique de fusion RRF, isolée de la base de données."""


def reciprocal_rank_fusion(bm25_ids: list[str], vector_ids: list[str], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for rank, pid in enumerate(bm25_ids):
        scores[pid] = scores.get(pid, 0) + 1 / (k + rank + 1)
    for rank, pid in enumerate(vector_ids):
        scores[pid] = scores.get(pid, 0) + 1 / (k + rank + 1)
    return scores


def test_rrf_boosts_items_found_by_both_methods():
    bm25_ids = ["a", "b", "c"]
    vector_ids = ["b", "d", "a"]
    scores = reciprocal_rank_fusion(bm25_ids, vector_ids)
    # "b" et "a" apparaissent dans les deux listes -> devraient dominer "c" et "d"
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["d"]


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([], []) == {}
