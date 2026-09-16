"""Render migration gate for RI BUROM.

Render currently invokes this filename from the Build Command. App imports are
side-effect free. Established Alembic-managed databases run Alembic directly;
the legacy bootstrap is reserved for a database not yet adopted by Alembic.
"""

import os
import sys
import traceback
from pathlib import Path

from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=== RI BUROM DEPLOY MIGRATION START ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Repository root: {ROOT}", flush=True)
print(f"DATABASE_URL present: {bool(os.environ.get('DATABASE_URL'))}", flush=True)

try:
    from app import app, db, run_deploy_bootstrap, run_post_migration_bootstrap
    from flask_migrate import upgrade
except Exception:
    print("=== APP IMPORT FAILED ===", flush=True)
    traceback.print_exc()
    raise

try:
    with app.app_context():
        engine = db.engine
        print(f"Database dialect: {engine.dialect.name}", flush=True)
        print(f"Database driver: {engine.dialect.driver}", flush=True)
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1").scalar()
            print("Database connection: SUCCESS", flush=True)
        alembic_exists = 'alembic_version' in set(inspect(engine).get_table_names())

    if alembic_exists:
        print(
            "Alembic-managed database detected; skipping db.create_all and "
            "legacy schema repair.",
            flush=True,
        )
    else:
        print(
            "No Alembic version table found; running one-time legacy/fresh "
            "database adoption bootstrap.",
            flush=True,
        )
        result = run_deploy_bootstrap()
        print(
            "Legacy/fresh bootstrap complete "
            f"(initial_owner_created={result['initial_owner_created']})",
            flush=True,
        )

    with app.app_context():
        if 'alembic_version' in set(inspect(db.engine).get_table_names()):
            with db.engine.connect() as connection:
                versions = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version ORDER BY version_num"
                ).scalars().all()
            print(f"Current Alembic revision(s): {versions}", flush=True)

        print("=== STARTING ALEMBIC MIGRATION ===", flush=True)
        upgrade(directory="migrations")
        print("=== ALEMBIC MIGRATION COMPLETE ===", flush=True)

    result = run_post_migration_bootstrap()
    print(
        "Post-migration defaults complete "
        f"(initial_owner_created={result['initial_owner_created']})",
        flush=True,
    )
except BaseException:
    print("=== DEPLOY MIGRATION FAILURE ===", flush=True)
    traceback.print_exc()
    raise

print("=== RI BUROM DEPLOY MIGRATION COMPLETE ===", flush=True)
