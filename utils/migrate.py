"""Simple file-based migration runner for the iScholar backend.

On startup this module:
1. Ensures a `schema_migrations` tracking table exists.
2. Acquires a named database lock to prevent concurrent migration runs.
3. Scans the `migrations/` directory for *.sql files in filename order.
4. Runs any that have not yet been recorded as applied.
"""

import logging
import os
import glob

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
_LOCK_NAME = "ischolar_migrations"
_LOCK_TIMEOUT = 10  # seconds


def run_migrations(get_connection):
    """Apply any pending SQL migrations.

    Args:
        get_connection: Callable that returns a PyMySQL connection.
    """
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Acquire an exclusive advisory lock to prevent concurrent migration runs
        cursor.execute("SELECT GET_LOCK(%s, %s) AS acquired", (_LOCK_NAME, _LOCK_TIMEOUT))
        row = cursor.fetchone()
        if not row or not row.get("acquired"):
            raise RuntimeError("Could not acquire migration lock; another process may be migrating")

        # Ensure tracking table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                filename   VARCHAR(255) NOT NULL UNIQUE,
                applied_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()

        # Collect already-applied migrations
        cursor.execute("SELECT filename FROM schema_migrations")
        applied = {row["filename"] for row in cursor.fetchall()}

        # Find all *.sql files sorted by name
        pattern = os.path.join(MIGRATIONS_DIR, "*.sql")
        migration_files = sorted(glob.glob(pattern))

        for filepath in migration_files:
            filename = os.path.basename(filepath)
            if filename in applied:
                continue

            logger.info("Applying migration: %s", filename)
            with open(filepath, "r", encoding="utf-8-sig") as f:
                sql = f.read()

            # Strip comment lines and execute each non-empty statement
            statements = []
            current = []
            for line in sql.splitlines():
                stripped = line.strip()
                if stripped.startswith("--") or stripped == "":
                    continue
                current.append(line)
                if stripped.endswith(";"):
                    statements.append("\n".join(current).rstrip(";").strip())
                    current = []
            if current:
                stmt = "\n".join(current).rstrip(";").strip()
                if stmt:
                    statements.append(stmt)

            for statement in statements:
                cursor.execute(statement)

            cursor.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (filename,)
            )
            connection.commit()
            logger.info("Applied migration: %s", filename)

    except Exception as exc:
        connection.rollback()
        logger.error("Migration failed: %s", exc)
        raise
    finally:
        try:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (_LOCK_NAME,))
        except Exception:
            pass
        cursor.close()
        connection.close()
