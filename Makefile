.PHONY: install dev fmt lint type test itest bench videos api up down clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

fmt:
	ruff format sentinel apps scripts tests

lint:
	ruff check sentinel apps scripts tests

type:
	mypy sentinel

test:
	pytest -q tests/unit

itest:
	pytest -q tests/integration

videos:
	python scripts/generate_test_videos.py --out datasets/videos

bench:
	python scripts/run_benchmark.py --dataset datasets/manifests/eval.yaml --config configs/development.yaml

api:
	uvicorn apps.api.main:app --reload

up:
	docker compose up -d

down:
	docker compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache data/benchmark
