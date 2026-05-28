.PHONY: dev dev-bg down test test-unit test-int migrate migration lint format shell create-admin check build logs

dev:
	docker compose up --build

dev-bg:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f backend celery-worker

shell:
	docker compose exec backend bash

test:
	docker compose exec backend pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

test-unit:
	docker compose exec backend pytest tests/unit/ -v

test-int:
	docker compose exec backend pytest tests/integration/ -v

migrate:
	docker compose exec backend alembic upgrade head

migration:
	@test -n "$(msg)" || (echo "Usage: make migration msg='describe your change'" && exit 1)
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

lint:
	docker compose exec backend ruff check app/ workers/ tests/
	docker compose exec backend mypy app/ workers/ --ignore-missing-imports

format:
	docker compose exec backend ruff format app/ workers/ tests/

create-admin:
	docker compose exec backend python scripts/create_admin.py

check: lint test
