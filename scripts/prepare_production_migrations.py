"""Prepare a known legacy production migration state for Alembic.

This module is intentionally separate from Alembic's env.py. It repairs only
one known production bookkeeping inconsistency created while Phase B migration
branches were deployed independently: an ancestor revision and one or more of
its descendants are simultaneously present in alembic_version.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text

BASE_REVISION = "3f7a9c2d1e64"
LEGACY_DESCENDANT_REVISIONS = frozenset({
    "7e4c91d2ab30",
    "7f1c9e4a6b20",
})
KNOWN_LEGACY_STATES = frozenset(
    {
        frozenset({BASE_REVISION, "7f1c9e4a6b20"}),
        frozenset({BASE_REVISION, "7e4c91d2ab30", "7f1c9e4a6b20"}),
    }
)


LEGACY_MUTATION_ACK = "RI_BUROM_ALLOW_LEGACY_DB_MUTATION"
PRODUCTION_MUTATION_ACK = "RI_BUROM_ALLOW_PRODUCTION_LEGACY_DB_MUTATION"


def require_explicit_legacy_mutation_opt_in() -> None:
    """Refuse to rewrite migration bookkeeping without explicit operator intent."""
    if os.environ.get(LEGACY_MUTATION_ACK) != "YES":
        raise SystemExit(
            f"{LEGACY_MUTATION_ACK}=YES is required before this maintenance script can modify a database."
        )

    app_env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if app_env in {"production", "prod"} and os.environ.get(PRODUCTION_MUTATION_ACK) != "YES_I_HAVE_A_BACKUP":
        raise SystemExit(
            f"Production use additionally requires "
            f"{PRODUCTION_MUTATION_ACK}=YES_I_HAVE_A_BACKUP."
        )


def repair_legacy_migration_state(connection) -> bool:
    """Normalize the exact known dirty version-table states.

    Returns True when the version table was changed, otherwise False.
    """
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "alembic_version" not in tables:
        return False

    versions = frozenset(
        row[0]
        for row in connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).fetchall()
    )

    if versions not in KNOWN_LEGACY_STATES:
        return False

    required_tables = {"packages", "services", "package_items"}
    missing = required_tables - tables
    if missing:
        raise RuntimeError(
            "Refusing to repair legacy migration state because the known Phase B "
            f"schema baseline is incomplete: missing={sorted(missing)!r}."
        )

    # 3f7... is the last revision already represented by the existing schema.
    # Re-running later migrations (6a -> 2c -> 7e/7f -> 9b) is safe because
    # those migrations are written to reconcile existing objects.
    connection.execute(text("DELETE FROM alembic_version"))
    connection.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
        {"revision": BASE_REVISION},
    )
    return True


def main() -> None:
    require_explicit_legacy_mutation_opt_in()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        repaired = repair_legacy_migration_state(connection)

    if repaired:
        print(f"Repaired legacy Alembic version state to {BASE_REVISION}")
    else:
        print("No legacy Alembic repair was required")


if __name__ == "__main__":
    main()
