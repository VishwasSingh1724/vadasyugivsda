.PHONY: install dev test lint analyse ingest openapi requirements docker-up
PY = backend/.venv/bin

install:
	cd backend && uv venv --python 3.12 -q && uv pip install -q -e ".[dev]"
	cd frontend && npm ci

dev:  ## API on :8077, UI on :5173 (proxied). Login: demo / demo-password
	cd backend && AUTH_USERNAME=demo AUTH_PASSWORD=demo-password SESSION_SECRET=local-dev-only-secret-0123456789abcdef .venv/bin/uvicorn app.main:app --reload --port 8077 & \
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app scripts
	cd frontend && npm run lint && npm run typecheck

analyse:  ## Headline January numbers used in the pitch
	cd backend && .venv/bin/python -m scripts.analyse 2>/dev/null | grep -v '^{'

ingest:  ## Refresh data/ from Elexon (needs network)
	cd backend && .venv/bin/python -m scripts.ingest

openapi:  ## Regenerate the API contract and the frontend types
	cd backend && .venv/bin/python -m scripts.export_openapi
	cd frontend && npm run gen:api

requirements:  ## Re-pin runtime deps used by Vercel/Docker
	uv pip compile backend/pyproject.toml -o requirements.txt --python-version 3.12

docker-up:
	docker compose up --build
