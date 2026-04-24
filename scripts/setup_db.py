"""
NPIDE - Database setup script.

For PostgreSQL, it executes schema.sql and seed.sql.
For SQLite fallback, it creates tables from SQLAlchemy models and then loads
seed.sql so the app can run locally without Postgres installed.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


def run_sql_file(conn, filepath: Path) -> None:
    sql_text = filepath.read_text(encoding="utf-8")
    sql_text = re.sub(r"--.*$", "", sql_text, flags=re.MULTILINE)
    statements = [stmt.strip() for stmt in sql_text.split(";") if stmt.strip()]

    print(f"[DB] Executing {len(statements)} statements from {filepath.name}...")
    for i, stmt in enumerate(statements, 1):
        try:
            conn.execute(text(stmt))
        except Exception as e:
            print(f"[DB]   Statement {i} failed: {e}")
            preview = stmt[:120].encode("ascii", errors="ignore").decode("ascii")
            print(f"[DB]   Statement: {preview}...")
    conn.commit()
    print(f"[DB] {filepath.name} complete.")


def setup_database():
    print("=" * 60)
    print("  NPIDE - Database Setup")
    print("=" * 60)

    from backend.data_layer.database import Base, engine, get_db_dialect, ping_db
    import backend.data_layer.models  # noqa: F401

    if not ping_db():
        print("[DB] Cannot connect to the configured database.")
        sys.exit(1)

    dialect = get_db_dialect()
    print(f"[DB] Connected using dialect: {dialect}")

    project_root = Path(__file__).parent.parent
    schema_file = project_root / "schema.sql"
    seed_file = project_root / "seed.sql"

    if dialect == "sqlite":
        print("[DB] Rebuilding SQLite tables from ORM metadata...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            run_sql_file(conn, seed_file)
    else:
        with engine.connect() as conn:
            if schema_file.exists():
                run_sql_file(conn, schema_file)
            if seed_file.exists():
                run_sql_file(conn, seed_file)

    with engine.connect() as conn:
        if dialect == "sqlite":
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            ).fetchall()
        else:
            tables = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            ).fetchall()

        print(f"\n[DB] Tables: {[row[0] for row in tables]}")

        for table in ["citizens", "schemes", "applications", "grievances", "policy_analytics", "district_monthly"]:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"[DB]   {table}: {count} rows")
            except Exception as e:
                print(f"[DB]   {table}: failed ({e})")

    print("\nDatabase setup complete.")


if __name__ == "__main__":
    setup_database()
