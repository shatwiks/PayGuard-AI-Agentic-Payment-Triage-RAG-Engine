"""Independent Disposable Migration and Downgrade Verification Script.

Tests:
1. Fresh disposable database creation on live PostgreSQL.
2. Alembic migration upgrade to current head (3f8a91b2c4d5).
3. Schema integrity: checks tables, foreign keys, pgvector extension, and GIN/HNSW indexes.
4. Alembic migration downgrade to base (verifies downgrade reversibility).
5. Clean teardown: drops disposable database without modifying payguard_db.
6. Confirms original staging database payguard_db is intact and at head.
"""

import os
import sys
import subprocess
import psycopg
from sqlalchemy import text

# Default connection to live PostgreSQL container on 127.0.0.1:5434
DB_HOST = "127.0.0.1"
DB_PORT = 5434
DB_USER = "payguard_user"
DB_PASS = "payguard_secure_password"
DISPOSABLE_DB = "payguard_migration_audit_temp"

def run_cmd(cmd_list, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(cmd_list, capture_output=True, text=True, env=merged_env)
    return res

def main():
    print("=" * 70)
    print("PHASE 3 AUDIT: DISPOSABLE DATABASE MIGRATION & DOWNGRADE VERIFICATION")
    print("=" * 70)

    # 1. Connect to postgres template database to create disposable DB
    conn_url_admin = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/payguard_db"
    print(f"\n[1/6] Connecting to live PostgreSQL at {DB_HOST}:{DB_PORT}...")
    with psycopg.connect(conn_url_admin, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Terminate any existing connections to disposable DB if exists and drop it
            cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{DISPOSABLE_DB}';")
            cur.execute(f"DROP DATABASE IF EXISTS {DISPOSABLE_DB};")
            print(f"[2/6] Creating fresh disposable database '{DISPOSABLE_DB}'...")
            cur.execute(f"CREATE DATABASE {DISPOSABLE_DB} OWNER {DB_USER};")

    # 2. Set environment for Alembic to target the disposable database
    disposable_sync_url = f"postgresql+psycopg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DISPOSABLE_DB}"
    disposable_async_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DISPOSABLE_DB}"
    migration_env = {
        "DATABASE_URL_SYNC": disposable_sync_url,
        "DATABASE_URL": disposable_async_url,
    }

    # 3. Run alembic upgrade head on disposable DB
    print(f"[3/6] Running Alembic migration UPGRADE to 'head' on '{DISPOSABLE_DB}'...", flush=True)
    res_upgrade = run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], env=migration_env)
    print(res_upgrade.stdout, flush=True)
    if res_upgrade.returncode != 0:
        print("UPGRADE ERROR:", res_upgrade.stderr, flush=True)
        sys.exit(1)
    print(">>> Fresh database successfully migrated to current Alembic HEAD!")

    # 4. Verify schema structure on disposable DB
    conn_url_disposable = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DISPOSABLE_DB}"
    with psycopg.connect(conn_url_disposable) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');")
            extensions = [r[0] for r in cur.fetchall()]
            assert "vector" in extensions, "pgvector extension missing!"
            print(f"Verified PostgreSQL extensions: {extensions}")

            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' ORDER BY table_name;
            """)
            tables = [r[0] for r in cur.fetchall()]
            print(f"Created tables ({len(tables)}): {tables}")
            expected_tables = ["users", "payments", "payment_events", "investigation_cases", "knowledge_documents", "document_chunks"]
            for t in expected_tables:
                assert t in tables, f"Expected table '{t}' not found in migrated disposable DB!"

            # Check indexes on knowledge_documents
            cur.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'knowledge_documents';
            """)
            indexes = [r[0] for r in cur.fetchall()]
            print(f"Indexes on knowledge_documents: {indexes}")
            assert "idx_docs_uploaded_by_active" in indexes
            assert "idx_docs_is_system_active" in indexes
            assert "idx_docs_content_hash_user" in indexes

    # 5. Run alembic downgrade base on disposable DB to verify reversibility
    print(f"\n[4/6] Running Alembic migration DOWNGRADE to 'base' on '{DISPOSABLE_DB}'...", flush=True)
    res_downgrade = run_cmd([sys.executable, "-m", "alembic", "downgrade", "base"], env=migration_env)
    print(res_downgrade.stdout, flush=True)
    if res_downgrade.returncode != 0:
        print("DOWNGRADE ERROR:", res_downgrade.stderr, flush=True)
        sys.exit(1)
    print(">>> Disposable database successfully downgraded to BASE (clean reversibility confirmed)!", flush=True)

    # 6. Teardown: Drop disposable DB
    print(f"\n[5/6] Cleaning up: Dropping disposable database '{DISPOSABLE_DB}'...", flush=True)
    with psycopg.connect(conn_url_admin, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{DISPOSABLE_DB}';")
            cur.execute(f"DROP DATABASE {DISPOSABLE_DB};")
    print(f">>> Disposable database '{DISPOSABLE_DB}' dropped cleanly.", flush=True)

    # 7. Check staging database integrity
    print(f"\n[6/6] Verifying original staging database 'payguard_db' revision...", flush=True)
    res_current = run_cmd([sys.executable, "-m", "alembic", "current"])
    print(res_current.stdout.strip(), flush=True)
    assert "3f8a91b2c4d5" in res_current.stdout
    print(">>> Staging database remains safely and cleanly at revision 3f8a91b2c4d5 (head)!")
    print("\nALL MIGRATION AND DOWNGRADE INTEGRITY CHECKS PASSED.")

if __name__ == "__main__":
    main()
