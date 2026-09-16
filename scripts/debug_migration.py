"""Render deploy preparation and migration gate for RI BUROM.

The filename is retained because Render currently invokes
`python scripts/debug_migration.py` in the Build Command.  Unlike the legacy
version, importing app.py is now side-effect free; all compatibility/bootstrap
work is invoked explicitly here exactly once during the build.
"""

import os
import sys
import traceback
from pathlib import Path

# Ensure imports resolve from the repository root when this script is run as
# `python scripts/debug_migration.py` on Render.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=== RI BUROM DEPLOY PREPARATION START ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print(f"Repository root: {ROOT}", flush=True)
print(f"DATABASE_URL present: {bool(os.environ.get('DATABASE_URL'))}", flush=True)

try:
    print("=== IMPORTING SIDE-EFFECT-FREE FLASK APP ===", flush=True)
    from app import app, db, run_deploy_bootstrap
    from flask_migrate import upgrade
    print("=== FLASK APP IMPORTED ===", flush=True)
except Exception:
    print("=== APP IMPORT FAILED ===", flush=True)
    traceback.print_exc()
    raise

try:
    # Preserve the compatibility/bootstrap responsibilities production
    # currently relies on, but run them explicitly in the build process rather
    # than implicitly every time app.py is imported by Gunicorn.
    print("=== RUNNING EXPLICIT DEPLOY BOOTSTRAP ===", flush=True)
    bootstrap_result = run_deploy_bootstrap()
    print(
        "Deploy bootstrap complete "
        f"(initial_owner_created={bootstrap_result['initial_owner_created']})",
        flush=True,
    )

    with app.app_context():
        engine = db.engine
        print(f"Database dialect: {engine.dialect.name}", flush=True)
        print(f"Database driver: {engine.dialect.driver}", flush=True)

        # Keep the deployment gate intentionally minimal.  Do not print
        # database names/users, schema definitions, row counts, or traveller
        # data into Render build logs.
        print("=== TESTING DATABASE CONNECTION ===", flush=True)
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1").scalar()
            print("Database connection: SUCCESS", flush=True)

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

            if alembic_exists:
                versions = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version ORDER BY version_num"
                ).scalars().all()
                print(f"Current Alembic revision(s): {versions}", flush=True)
            else:
                print("Alembic version table not present yet", flush=True)

        print("=== STARTING ALEMBIC MIGRATION ===", flush=True)
        upgrade(directory="migrations")
        print("=== ALEMBIC MIGRATION COMPLETE ===", flush=True)

except BaseException:
    print("=== DEPLOY PREPARATION FAILURE ===", flush=True)
    traceback.print_exc()
    raise

print("=== RI BUROM DEPLOY PREPARATION COMPLETE ===", flush=True)
