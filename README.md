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
   # edit DATABASE_URL, SESSION_SECRET, GOOGLE_CLIENT_ID, and GOOGLE_SUPERUSER_EMAIL as needed
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

Google authentication is required for all users. Configure a Google Identity Services
client and set `GOOGLE_CLIENT_ID` to the OAuth 2.0 Client ID. Set `GOOGLE_SUPERUSER_EMAIL`
to the Gmail account that should become the first administrator; that account can then
invite additional Gmail users and assign roles.

### Updating Tailwind styles

The application no longer pulls Tailwind CSS from a CDN so that the UI works on networks without external internet access. If you
change template markup and need to rebuild the bundled stylesheet, run:

```bash
npx tailwindcss@3.4.10 -i app/static/css/tailwind-input.css -o app/static/css/tailwind.css --minify
```

The Tailwind configuration lives in `tailwind.config.js`.
