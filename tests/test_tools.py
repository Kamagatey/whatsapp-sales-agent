"""Tests unitaires légers sur la logique métier des tools (sans dépendance à Postgres/pgvector).

Ces tests valident les règles métier pures (ex: refus de commande si stock insuffisant)
en utilisant des objets simples plutôt qu'une vraie session SQLAlchemy/pgvector, pour
rester exécutables sans base de données.
"""
from types import SimpleNamespace

from app.tools.tools import check_stock


class FakeSession:
    """Simule session.get(Product, id) pour tester check_stock sans base de données."""

    def __init__(self, product):
        self._product = product

    def get(self, model, product_id):
        return self._product if self._product and self._product.id == product_id else None


def make_product(**kwargs):
    defaults = dict(
        id="p1", product_name="Robe Wax Bleue", category="vêtements africains",
        description="Robe wax", price_fcfa=15000, stock_quantity=5,
        available_sizes="S,M,L", available_colors="bleu", brand="", seller_name="Test",
        delivery_zones="Abidjan", keywords="robe,wax",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_check_stock_product_not_found():
    session = FakeSession(None)
    result = check_stock(session, "unknown")
    assert "error" in result


def test_check_stock_in_stock():
    session = FakeSession(make_product(stock_quantity=10))
    result = check_stock(session, "p1")
    assert result["in_stock"] is True
    assert result["stock_quantity"] == 10


def test_check_stock_size_unavailable():
    session = FakeSession(make_product(available_sizes="S,M"))
    result = check_stock(session, "p1", size="XL")
    assert result["available"] is False
    assert "XL" not in result["available_sizes"]


def test_check_stock_out_of_stock():
    session = FakeSession(make_product(stock_quantity=0))
    result = check_stock(session, "p1")
    assert result["in_stock"] is False
