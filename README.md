# Hermas Stock Taker

Converted from the single-file HTML application into a FastAPI + PostgreSQL backend with a split frontend using Jinja templates and static assets. The project implements RBAC, per-user data isolation, and dashboard sharing controls.

## Requirements

- Python 3.11+
- PostgreSQL 14+

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure environment variables:

   ```bash
   cp .env.example .env
   # edit DATABASE_URL and SESSION_SECRET as needed
   ```

3. Run migrations and seed default data:

   ```bash
   alembic upgrade head
   python -m app.db.seed
   ```

4. Start the development server:

   ```bash
   uvicorn app.main:app --reload
   ```

The default administrator account is `Admin` / `adminthegreat`.
