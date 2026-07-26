"""Orchestration optionnelle du pipeline d'ingestion avec Prefect.

Non requis pour faire tourner le projet (scripts/ingest.py suffit), mais démontre
comment automatiser/planifier l'ingestion (score "ingestion pipeline" de la grille
LLM Zoomcamp). Installer avec `pip install prefect` pour l'utiliser.

Usage:
    python scripts/prefect_flow.py            # exécution unique
    prefect deployment build ... (planification récurrente, hors scope de ce script)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover
    print("Prefect n'est pas installé. `pip install prefect` pour utiliser ce flow.")
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).resolve().parent


@task(retries=1)
def run_generate_data():
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "generate_data.py")], check=True)


@task(retries=1)
def run_generate_eval_dataset():
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "generate_eval_dataset.py")], check=True)


@task(retries=2)
def run_ingest():
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "ingest.py")], check=True)


@flow(name="whatsapp-sales-agent-ingestion")
def ingestion_pipeline(regenerate_data: bool = False):
    if regenerate_data:
        run_generate_data()
        run_generate_eval_dataset()
    run_ingest()


if __name__ == "__main__":
    ingestion_pipeline()
