.PHONY: install run test lint format benchmark load-test docker-up docker-down clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTHON) -m pytest -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

benchmark:
	$(PYTHON) scripts/benchmark.py

load-test:
	$(PYTHON) scripts/load_test.py --requests 200 --concurrency 10

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__ */*./__pycache__ *.sqlite3 gateway.db
