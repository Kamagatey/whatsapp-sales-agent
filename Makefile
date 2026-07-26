.PHONY: install generate-data generate-eval ingest evaluate-retrieval evaluate-llm test up down

install:
	pip install -r requirements.txt

generate-data:
	python scripts/generate_data.py

generate-eval:
	python scripts/generate_eval_dataset.py

ingest:
	python scripts/ingest.py

evaluate-retrieval:
	uv run python scripts/evaluate.py --mode retrieval

evaluate-llm:
	uv run python scripts/evaluate.py --mode llm

test:
	pytest tests/ -v

up:
	docker compose up --build

down:
	docker compose down -v
