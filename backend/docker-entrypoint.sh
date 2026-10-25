#!/bin/bash
set -e

echo "=== PayGuard AI Backend Staging Entrypoint ==="

# 1. Wait for Database Readiness
echo "1. Probing database connection readiness..."
python -c "
import sys, time, asyncio
from backend.app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def wait_db():
    engine = create_async_engine(settings.DATABASE_URL)
    for i in range(60):
        try:
            async with engine.connect() as conn:
                await conn.execute(text('SELECT 1;'))
            print('-> Database is ready and accepting queries.')
            await engine.dispose()
            return True
        except Exception as err:
            if i % 5 == 0:
                print(f'   Waiting for database ({i+1}/60)...')
            await asyncio.sleep(1)
    await engine.dispose()
    print('ERROR: Database connection timed out after 60s.')
    return False

if not asyncio.run(wait_db()):
    sys.exit(1)
"

# 2. Run Alembic Migrations
echo "2. Applying Alembic schema migrations..."
alembic upgrade head
echo "-> Alembic migrations applied successfully."

# 3. Seed Synthetic Dataset (Idempotent & Live Re-embedding)
echo "3. Verifying initial dataset and live embeddings..."
python -m backend.app.scripts.seed_data --reembed-live
echo "-> Dataset verified/seeded."

# 4. Start Uvicorn Server (Single Worker for Staging In-Memory Rate Limiting)
echo "4. Launching PayGuard AI API server on 0.0.0.0:8000..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
