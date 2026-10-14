.PHONY: install up down logs lint format test test-unit test-db-up test-db-down

TEST_DATABASE_URL ?= postgresql+asyncpg://tracker:tracker@localhost:5433/prices_test

install:
	uv sync

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker beat

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy deribit_tracker tests

format:
	uv run ruff check --fix .
	uv run ruff format .

test-unit:
	uv run pytest -m "not integration"

test-db-up:
	docker compose -f docker-compose.test.yml up -d --wait

test-db-down:
	docker compose -f docker-compose.test.yml down

test: test-db-up
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest
