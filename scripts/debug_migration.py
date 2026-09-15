import os
import sys
import traceback
from pathlib import Path

# Render executes this file as scripts/debug_migration.py, so explicitly add
# the repository root before importing the Flask application.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
except BaseException:
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

            version = connection.exec_driver_sql("SELECT version()").scalar()
            print(f"PostgreSQL version: {version}", flush=True)

            current_db = connection.exec_driver_sql("SELECT current_database()").scalar()
            current_user = connection.exec_driver_sql("SELECT current_user").scalar()
            print(f"Current database: {current_db}", flush=True)
            print(f"Current user: {current_user}", flush=True)

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

        print("=== DATABASE CONNECTION TEST COMPLETE ===", flush=True)

        print("=== STARTING ALEMBIC MIGRATION ===", flush=True)
        upgrade(directory="migrations")
        print("=== ALEMBIC MIGRATION COMPLETE ===", flush=True)

    except BaseException:
        print("=== DIAGNOSTIC FAILURE ===", flush=True)
        traceback.print_exc()
        raise

print("=== DIAGNOSTIC SCRIPT COMPLETE ===", flush=True)
