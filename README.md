# Assistant Commercial WhatsApp Intelligent — Petits Vendeurs (Côte d'Ivoire)

Projet réalisé dans le cadre de la certification **LLM Zoomcamp** (DataTalksClub).

Un agent conversationnel LLM qui répond aux clients d'un petit vendeur ivoirien sur WhatsApp
(disponibilité, prix, tailles, livraison, commandes) en s'appuyant sur un pipeline RAG hybride
(vector + BM25) et des outils (function calling) connectés à une base PostgreSQL.

Projet exemple d'inspiration : [Fitness Assistant — LLM Zoomcamp 07-project-example](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/07-project-example)

---

## 1. Problème

Voir `docs/problem_description.md` pour le contexte complet. En résumé : les petits vendeurs
ivoiriens gèrent leurs ventes sur WhatsApp manuellement, ce qui coûte du temps, génère des
réponses incohérentes et fait perdre des clients. Cet assistant automatise les échanges
courants (info produit, stock, livraison, prise de commande) tout en évitant les hallucinations :
le LLM ne répond qu'à partir des données réelles récupérées via RAG et des outils.

## 2. Architecture

```
Client WhatsApp (simulé via Streamlit / API)
        │
        ▼
   FastAPI (app/api)
        │
        ▼
   Agent Loop (app/agent)  ──uses──▶  Tools (app/tools): search_products, check_stock,
        │                              create_order, get_customer_history
        ▼
   Retrieval hybride (app/retrieval): BM25 + vector (pgvector) + fusion
        │
        ▼
   PostgreSQL (produits, clients, commandes, conversations, logs monitoring)
```

Pipeline d'ingestion : `scripts/generate_data.py` → `scripts/ingest.py` (nettoyage →
documents → embeddings → pgvector + index BM25).

## 3. Stack technique

| Composant | Choix | Justification |
|---|---|---|
| LLM | OpenAI (`gpt-4o-mini` par défaut, configurable) | structured output + function calling matures |
| Backend | FastAPI + Pydantic | typage strict, docs auto (OpenAPI), async |
| DB | PostgreSQL + pgvector | une seule base pour données métier et vecteurs |
| Recherche texte | BM25 (`rank_bm25`) | simple, robuste sur peu de documents, pas d'infra dédiée |
| Recherche vectorielle | `text-embedding-3-small` + pgvector | bon rapport coût/qualité |
| Orchestration ingestion | script Python (+ hook Prefect optionnel, voir `scripts/prefect_flow.py`) | reproductible sans infra lourde |
| Interface | Streamlit (simulateur WhatsApp) + FastAPI (API brute) | démonstration interactive + intégration programmatique |
| Monitoring | Postgres (logs) + Grafana (dashboards) | feedback utilisateur + observabilité agent |
| Conteneurisation | Docker + docker-compose | reproductibilité totale |

## 4. Installation

### Prérequis
- Docker & docker-compose
- Une clé API OpenAI

### Variables d'environnement

Copier `.env.example` en `.env` et renseigner :

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=sales_agent
POSTGRES_DB=sales_agent
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### Environnement Python (avec uv)

Le projet fournit `requirements.txt` (utilisé par les Dockerfiles) et un `pyproject.toml`
équivalent pour `uv`. Les deux sont interchangeables ; utilise celui que tu préfères.

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
# ou, de façon équivalente avec pyproject.toml :
uv sync
```

Rien d'autre à adapter dans le code : `uv` ne change que la façon d'installer les
dépendances, pas la structure du projet ni les imports.

### Lancement complet

```bash
docker compose up --build
docker compose up -d db      # s'assurer que la base tourne
docker compose exec api python scripts/ingest.py
```


Cela démarre :
- `db` : PostgreSQL + pgvector
- `api` : FastAPI sur http://localhost:8000 (docs sur `/docs`)
- `streamlit` : interface de test sur http://localhost:8501
- `grafana` : dashboards sur http://localhost:3000 (admin/admin)

### Arret du conteneur

```bash
docker compose down
```

### Génération des données (à faire une fois, avant le premier lancement ou en local)

```bash
pip install -r requirements.txt
python scripts/generate_data.py          # génère data/products.csv, customers.csv, orders.csv
python scripts/generate_eval_dataset.py  # génère data/evaluation_dataset.json
python scripts/ingest.py                 # ingère dans Postgres + construit les index
```

### Évaluation retrieval & LLM

```bash
python scripts/evaluate.py --mode retrieval   # compare BM25 / vector / hybrid (hit-rate, MRR)
#docker compose exec api python scripts/evaluate.py --mode llm
#docker compose exec api python scripts/evaluate.py --mode retrieval
python scripts/evaluate.py --mode llm         # compare prompts/modèles sur le dataset Q/R
```


Les résultats sont sauvegardés dans `data/eval_results/` et affichés dans les notebooks
`notebooks/01_retrieval_evaluation.ipynb` et `notebooks/02_llm_evaluation.ipynb`.

### Tests

```bash
pytest tests/
```

## 5. Structure du dépôt

```
whatsapp-sales-agent/
├── app/
│   ├── api/            # FastAPI (routes, schémas de requête/réponse)
│   ├── agent/           # boucle agent, prompts, orchestration des tools
│   ├── retrieval/        # BM25, vector search, fusion hybride
│   ├── tools/            # implémentation des tools appelés par le LLM
│   ├── database/         # modèles SQLAlchemy, session, config
│   └── monitoring/        # logging des interactions, calcul de métriques
├── data/                # csv générés, dataset d'évaluation, résultats
├── notebooks/           # exploration, évaluation retrieval/LLM
├── scripts/             # generate_data, ingest, evaluate, prefect_flow
├── monitoring/grafana/  # provisioning des dashboards Grafana
├── streamlit_app.py     # simulateur WhatsApp
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 6. Grille d'évaluation LLM Zoomcamp — auto-évaluation

| Critère | Statut | Où |
|---|---|---|
| Problem description | ✅ | `docs/problem_description.md`, section 1 |
| Retrieval pipeline (KB + LLM) | ✅ | `app/retrieval/`, `app/agent/` |
| Retrieval evaluation (≥2 approches) | ✅ | `scripts/evaluate.py --mode retrieval` |
| LLM evaluation (≥2 approches) | ✅ | `scripts/evaluate.py --mode llm` |
| Interface (API ou UI) | ✅ | FastAPI + Streamlit |
| Ingestion pipeline automatisée | ✅ | `scripts/ingest.py` (+ `scripts/prefect_flow.py`) |
| Monitoring (feedback + dashboard ≥5 graphiques) | ✅ | `app/monitoring/`, Grafana |
| Conteneurisation (app + DB) | ✅ | `docker-compose.yml` |
| Reproductibilité (README complet) | ✅ | ce fichier |
| Bonus : logs coût/contexte/réponse | ✅ | `app/monitoring/logger.py` |
| Bonus : préparation déploiement cloud | ✅ | `docs/deployment.md` |

## 7. Intégration WhatsApp réelle

`app/api/whatsapp_webhook.py` est une intégration fonctionnelle avec la **WhatsApp Cloud
API** de Meta (pas un simple stub) : réception des messages entrants, appel de
`SalesAgent`, envoi de la réponse via l'API Graph. Voir **`docs/whatsapp_integration.md`**
pour :
- la comparaison avec les alternatives (Twilio, Baileys/whatsapp-web.js, OpenClaw, etc.)
  et pourquoi la Cloud API de Meta a été retenue ;
- le guide pas-à-pas pour connecter un numéro de test gratuit en quelques minutes.

## 8. Limites connues / prochaines étapes

- Les données sont synthétiques (générées par LLM) : à remplacer par un export réel du vendeur.
- Le numéro de test Meta est limité à 5 destinataires vérifiés ; passage en prod détaillé
  dans `docs/deployment.md`.
- Les coûts OpenAI ne sont pas plafonnés automatiquement ; `app/monitoring/logger.py` calcule
  un coût estimé par appel à ajuster selon les prix en vigueur.
