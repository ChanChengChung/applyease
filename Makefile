.PHONY: install db-upgrade db-check dev-backend dev-frontend test build docker-up docker-down

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install
	cd browser-extension && npm install

db-upgrade:
	cd backend && .venv/bin/python -m app.cli db upgrade

db-check:
	cd backend && .venv/bin/python -m app.cli db check

dev-backend:
	cd backend && .venv/bin/python -m app.cli db upgrade && .venv/bin/uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test
	cd browser-extension && npm test

build:
	cd frontend && npm run build
	cd browser-extension && npm run build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
