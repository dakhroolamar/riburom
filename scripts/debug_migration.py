import os
import sys
import traceback
from pathlib import Path

# Ensure imports resolve from the repository root when this script is run as
# `python scripts/debug_migration.py` on Render.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MARKETPLACE_TABLES = (
    "provider_types",
    "service_categories",
    "providers",
    "provider_type_assignments",
    "services",
)

print("=== DIAGNOSTIC SCRIPT START ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print(f"Repository root: {ROOT}", flush=True)
print(f"DATABASE_URL present: {bool(os.environ.get('DATABASE_URL'))}", flush=True)

try:
    print("=== IMPORTING FLASK APP ===", flush=True)
    from app import app, db
    from flask_migrate import upgrade
    print("=== FLASK APP IMPORTED ===", flush=True)
except Exception:
    print("=== APP IMPORT FAILED ===", flush=True)
    traceback.print_exc()
    raise

with app.app_context():
    try:
        engine = db.engine
        print(f"Database dialect: {engine.dialect.name}", flush=True)
        print(f"Database driver: {engine.dialect.driver}", flush=True)
        print(f"Database URL driver: {engine.url.drivername}", flush=True)

        print("=== TESTING DATABASE CONNECTION ===", flush=True)
        with engine.connect() as connection:
            print("Database connection: SUCCESS", flush=True)
            print(
                f"PostgreSQL version: {connection.exec_driver_sql('SELECT version()').scalar()}",
                flush=True,
            )
            print(
                f"Current database: {connection.exec_driver_sql('SELECT current_database()').scalar()}",
                flush=True,
            )
            print(
                f"Current user: {connection.exec_driver_sql('SELECT current_user').scalar()}",
                flush=True,
            )

            tables = connection.exec_driver_sql(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            ).scalars().all()
            print(f"Existing public tables ({len(tables)}): {tables}", flush=True)

            alembic_exists = connection.exec_driver_sql(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'alembic_version'
                )
                """
            ).scalar()
            print(f"alembic_version table exists: {alembic_exists}", flush=True)

            if alembic_exists:
                versions = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version ORDER BY version_num"
                ).scalars().all()
                print(f"Current Alembic revision(s): {versions}", flush=True)

            print("=== DETAILED MARKETPLACE SCHEMA ===", flush=True)
            for table in MARKETPLACE_TABLES:
                if table not in tables:
                    print(f"TABLE {table}: MISSING", flush=True)
                    continue

                rows = connection.exec_driver_sql(
                    """
                    SELECT
                        column_name,
                        data_type,
                        character_maximum_length,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                ).fetchall()
                print(f"TABLE {table} COLUMNS:", flush=True)
                for row in rows:
                    print(f"  {tuple(row)}", flush=True)

                constraints = connection.exec_driver_sql(
                    """
                    SELECT
                        tc.constraint_name,
                        tc.constraint_type,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints tc
                    LEFT JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    LEFT JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                     AND tc.table_schema = ccu.table_schema
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = %s
                    ORDER BY tc.constraint_name, kcu.ordinal_position
                    """,
                    (table,),
                ).fetchall()
                print(f"TABLE {table} CONSTRAINTS:", flush=True)
                for row in constraints:
                    print(f"  {tuple(row)}", flush=True)

                indexes = connection.exec_driver_sql(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = %s
                    ORDER BY indexname
                    """,
                    (table,),
                ).fetchall()
                print(f"TABLE {table} INDEXES:", flush=True)
                for row in indexes:
                    print(f"  {tuple(row)}", flush=True)

                count = connection.exec_driver_sql(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).scalar()
                print(f"TABLE {table} ROW COUNT: {count}", flush=True)

        print("=== DATABASE CONNECTION AND SCHEMA INSPECTION COMPLETE ===", flush=True)

        print("=== STARTING ALEMBIC MIGRATION ===", flush=True)
        upgrade(directory="migrations")
        print("=== ALEMBIC MIGRATION COMPLETE ===", flush=True)

    except BaseException:
        print("=== DIAGNOSTIC FAILURE ===", flush=True)
        traceback.print_exc()
        raise

print("=== DIAGNOSTIC SCRIPT COMPLETE ===", flush=True)
