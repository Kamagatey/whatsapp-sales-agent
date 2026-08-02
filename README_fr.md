# Assistant Commercial WhatsApp Intelligent — Petits Vendeurs (Côte d'Ivoire)

Projet réalisé dans le cadre de la certification **LLM Zoomcamp** (DataTalksClub).

🇬🇧 [English version](README.md)

Un agent conversationnel LLM qui répond aux clients d'un petit vendeur ivoirien sur WhatsApp
(disponibilité, prix, tailles, livraison, commandes) en s'appuyant sur un pipeline RAG hybride
(vector + BM25) et des outils (function calling) connectés à une base PostgreSQL.

Projet exemple d'inspiration : [Fitness Assistant — LLM Zoomcamp 07-project-example](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/07-project-example)

---

## 1. Problème

Voir [`docs/problem_description.md`](docs/problem_description.md) pour le contexte complet.
En résumé : les petits vendeurs ivoiriens gèrent leurs ventes sur WhatsApp manuellement, ce
qui coûte du temps, génère des réponses incohérentes et fait perdre des clients. Cet
assistant automatise les échanges courants (info produit, stock, livraison, prise de
commande) tout en évitant les hallucinations : le LLM ne répond qu'à partir des données
réelles récupérées via RAG et des outils.

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

Copier `.env.example` en `.env` et renseigner au minimum :

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

Les variables WhatsApp (Meta / Twilio) sont détaillées en section 7.

### Environnement Python (avec uv)

Le projet fournit `requirements.txt` (utilisé par les Dockerfiles) et un `pyproject.toml`
équivalent pour `uv`. Les deux sont interchangeables ; utilise celui que tu préfères.

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
# ou, de façon équivalente :
uv sync
```

### Lancement complet

```bash
docker compose up --build -d
```

Cela démarre :
- `db` : PostgreSQL + pgvector
- `api` : FastAPI sur http://localhost:8000 (docs sur `/docs`)
- `streamlit` : interface de test sur http://localhost:8501
- `grafana` : dashboards sur http://localhost:3000 (admin/admin)

Pour arrêter :
```bash
docker compose down
```

### Génération des données et ingestion (une fois, après le premier lancement)

```bash
docker compose exec api python scripts/generate_data.py          # génère data/products.csv, customers.csv, orders.csv
docker compose exec api python scripts/generate_eval_dataset.py  # génère data/evaluation_dataset.json
docker compose exec api python scripts/ingest.py                 # ingère dans Postgres + construit les index
```

> Si tu préfères lancer ces scripts en local (hors conteneur), préfixe la commande par
> `POSTGRES_HOST=localhost`, car `db` n'est résolu que dans le réseau docker-compose.

### Évaluation retrieval & LLM

```bash
docker compose exec api python scripts/evaluate.py --mode retrieval   # compare BM25 / vector / hybrid (hit-rate, MRR)
docker compose exec api python scripts/evaluate.py --mode llm         # compare prompts/modèles sur le dataset Q/R
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
│   ├── api/            # FastAPI (routes, webhooks WhatsApp, schémas)
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

## 6. Intégration WhatsApp réelle

Trois intégrations coexistent dans le projet, chacune dans son propre routeur FastAPI
(`app/api/whatsapp_webhook.py`, `app/api/twilio_webhook.py`, `app/api/whapi_webhook.py`),
toutes branchées en parallèle dans `app/api/main.py` sans se marcher dessus. Le détail
complet et le pas-à-pas sont dans
[`docs/whatsapp_integration.md`](docs/whatsapp_integration.md). Résumé :

### Meta WhatsApp Cloud API (retenue, gratuite, officielle)

C'est l'intégration principale. Fonctionnement :
1. Créer une app sur [developers.facebook.com](https://developers.facebook.com), option
   *"Tisser des liens avec votre clientèle via WhatsApp"*, ajouter le produit WhatsApp.
2. Meta fournit un numéro de test gratuit + un `Phone Number ID` + un token d'accès
   temporaire (24h — utiliser un token System User pour un usage plus long).
3. Ajouter ses variables dans `.env` :
```
   WHATSAPP_VERIFY_TOKEN=un-secret-que-tu-choisis
   WHATSAPP_ACCESS_TOKEN=...
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_API_VERSION=v21.0
```
4. Exposer l'API en HTTPS (`ngrok http 8000` en dev), déclarer l'URL
   `https://<domaine>/whatsapp/webhook` dans **API Setup → Configuration de la
   production → Webhooks**, avec le même verify token.
5. S'abonner explicitement au champ **`messages`** dans "Champs Webhooks".
6. **Étape souvent manquante côté Meta (changement d'interface fin 2025)** : la
   vérification de l'URL et l'abonnement au champ `messages` ne suffisent pas toujours —
   il faut en plus abonner l'app au WABA via un appel direct à l'API Graph :
```bash
   curl -X POST "https://graph.facebook.com/v21.0/<WHATSAPP_BUSINESS_ACCOUNT_ID>/subscribed_apps" \
     -H "Authorization: Bearer <TOKEN>"
```
   Sans ça, les messages entrants n'arrivent jamais au webhook malgré une configuration
   apparemment correcte.
7. Ajouter les numéros de test dans **"Manage phone number list"**, avec confirmation par
   code WhatsApp.


## 7. Limites connues / prochaines étapes

- Les données sont synthétiques (générées par LLM) : à remplacer par un export réel du vendeur.
- Le numéro de test Meta est limité à 5 destinataires vérifiés ; passage en prod détaillé
  dans [`docs/deployment.md`](docs/deployment.md).