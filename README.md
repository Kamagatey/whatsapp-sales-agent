# WhatsApp Sales Assistant — Small Sellers (Côte d'Ivoire)

Built for the **LLM Zoomcamp** certification (DataTalksClub).

🇫🇷 [Version française](README_fr.md)

An LLM-powered conversational agent that answers customers on WhatsApp for a small Ivorian
seller (product availability, price, sizes, delivery, orders), backed by a hybrid RAG
pipeline (vector + BM25) and function-calling tools connected to PostgreSQL.

Inspiration project: [Fitness Assistant — LLM Zoomcamp 07-project-example](https://github.com/DataTalksClub/llm-zoomcamp/tree/main/07-project-example)

---

## 1. Problem

See [`docs/problem_description.md`](docs/problem_description.md) for full context.
In short: small Ivorian sellers manage sales on WhatsApp manually, which wastes time,
produces inconsistent answers, and loses customers. This assistant automates common
exchanges (product info, stock, delivery, placing orders) while avoiding hallucinations:
the LLM only answers from real data retrieved via RAG and tools.

## 2. Architecture

```
WhatsApp client (simulated via Streamlit / API)
        │
        ▼
   FastAPI (app/api)
        │
        ▼
   Agent Loop (app/agent)  ──uses──▶  Tools (app/tools): search_products, check_stock,
        │                              create_order, get_customer_history
        ▼
   Hybrid retrieval (app/retrieval): BM25 + vector (pgvector) + fusion
        │
        ▼
   PostgreSQL (products, customers, orders, conversations, monitoring logs)
```

Ingestion pipeline: `scripts/generate_data.py` → `scripts/ingest.py` (cleaning →
documents → embeddings → pgvector + BM25 index).

## 3. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| LLM | OpenAI (`gpt-4o-mini` by default, configurable) | mature structured output + function calling |
| Backend | FastAPI + Pydantic | strict typing, auto docs (OpenAPI), async |
| DB | PostgreSQL + pgvector | one database for business data and vectors |
| Text search | BM25 (`rank_bm25`) | simple, robust on a few hundred documents, no extra infra |
| Vector search | `text-embedding-3-small` + pgvector | good cost/quality ratio |
| Ingestion orchestration | Python script (+ optional Prefect hook, see `scripts/prefect_flow.py`) | reproducible without heavy infra |
| Interface | Streamlit (WhatsApp simulator) + FastAPI (raw API) | interactive demo + programmatic integration |
| Monitoring | Postgres (logs) + Grafana (dashboards) | user feedback + agent observability |
| Containerization | Docker + docker-compose | full reproducibility |

## 4. Installation

### Prerequisites
- Docker & docker-compose
- An OpenAI API key

### Environment variables

Copy `.env.example` to `.env` and fill in at least:

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

WhatsApp variables (Meta / Twilio) are detailed in section 7.

### Python environment (with uv)

The project ships both `requirements.txt` (used by the Dockerfiles) and an equivalent
`pyproject.toml` for `uv`. Either works; use whichever you prefer.

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
# or, equivalently:
uv sync
```

### Running everything

```bash
docker compose up --build -d
```

This starts:
- `db`: PostgreSQL + pgvector
- `api`: FastAPI on http://localhost:8000 (docs at `/docs`)
- `streamlit`: test interface on http://localhost:8501
- `grafana`: dashboards on http://localhost:3000 (admin/admin)

To stop:
```bash
docker compose down
```

### Data generation and ingestion (once, after the first startup)

```bash
docker compose exec api python scripts/generate_data.py          # generates data/products.csv, customers.csv, orders.csv
docker compose exec api python scripts/generate_eval_dataset.py  # generates data/evaluation_dataset.json
docker compose exec api python scripts/ingest.py                 # ingests into Postgres + builds indexes
```

> If you'd rather run these scripts locally (outside the container), prefix the command
> with `POSTGRES_HOST=localhost`, since `db` only resolves inside the docker-compose
> network.

### Retrieval & LLM evaluation

```bash
docker compose exec api python scripts/evaluate.py --mode retrieval   # compares BM25 / vector / hybrid (hit-rate, MRR)
docker compose exec api python scripts/evaluate.py --mode llm         # compares prompts/models on the Q&A dataset
```

Results are saved to `data/eval_results/` and displayed in the notebooks
`notebooks/01_retrieval_evaluation.ipynb` and `notebooks/02_llm_evaluation.ipynb`.

### Tests

```bash
pytest tests/
```

## 5. Repository structure

```
whatsapp-sales-agent/
├── app/
│   ├── api/            # FastAPI (routes, WhatsApp webhooks, schemas)
│   ├── agent/           # agent loop, prompts, tool orchestration
│   ├── retrieval/        # BM25, vector search, hybrid fusion
│   ├── tools/            # tool implementations called by the LLM
│   ├── database/         # SQLAlchemy models, session, config
│   └── monitoring/        # interaction logging, metrics computation
├── data/                # generated CSVs, evaluation dataset, results
├── notebooks/           # exploration, retrieval/LLM evaluation
├── scripts/             # generate_data, ingest, evaluate, prefect_flow
├── monitoring/grafana/  # Grafana dashboard provisioning
├── streamlit_app.py     # WhatsApp simulator
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 6. Real WhatsApp integration

Three integrations coexist in the project, each in its own FastAPI router
(`app/api/whatsapp_webhook.py`, `app/api/twilio_webhook.py`, `app/api/whapi_webhook.py`),
all wired in parallel in `app/api/main.py` without interfering with each other. Full
detail and step-by-step guide: [`docs/whatsapp_integration.md`](docs/whatsapp_integration.md).
Summary:

### Meta WhatsApp Cloud API (chosen, free, official)

The primary integration. How it works:
1. Create an app on [developers.facebook.com](https://developers.facebook.com), choosing
   the *"Connect with your customers on WhatsApp"* option, and add the WhatsApp product.
2. Meta provides a free test number + a `Phone Number ID` + a temporary access token
   (24h — use a System User token for longer-lived access).
3. Add these to `.env`:
```
   WHATSAPP_VERIFY_TOKEN=a-secret-you-choose
   WHATSAPP_ACCESS_TOKEN=...
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_API_VERSION=v21.0
```
4. Expose the API over HTTPS (`ngrok http 8000` in dev), register the URL
   `https://<domain>/whatsapp/webhook` under **API Setup → Production configuration →
   Webhooks**, with the same verify token.
5. Explicitly subscribe to the **`messages`** field under "Webhook fields".
6. **Step that's easy to miss with Meta's newer UI (late 2025 change)**: verifying the
   URL and subscribing to `messages` isn't always enough — you also need to subscribe
   the app to the WABA directly via the Graph API:
```bash
   curl -X POST "https://graph.facebook.com/v21.0/<WHATSAPP_BUSINESS_ACCOUNT_ID>/subscribed_apps" \
     -H "Authorization: Bearer <TOKEN>"
```
   Without this, incoming messages never reach the webhook despite an apparently
   correct configuration.
7. Add test numbers under **"Manage phone number list"**, confirmed via a WhatsApp code.


## 7. Known limitations / next steps

- Data is synthetic (LLM-generated): should be replaced with a real export from the seller.
- The Meta test number is limited to 5 verified recipients; production rollout is
  detailed in [`docs/deployment.md`](docs/deployment.md).