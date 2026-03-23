import os
import sqlite3
from flask import current_app

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')


def run_migrations(app):
    """Run all pending SQL migrations in order.

    Tracks applied migrations in a _migrations table.
    "Missed it by that much" — we don't miss any migrations.
    """
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys=ON')

    # Ensure migrations tracking table exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()

    # Get already-applied migrations
    applied = {row[0] for row in conn.execute('SELECT name FROM _migrations').fetchall()}

    # Find and run pending migrations
    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith('.sql')
    )

    for filename in migration_files:
        if filename in applied:
            continue

        filepath = os.path.join(MIGRATIONS_DIR, filename)
        with open(filepath, 'r') as f:
            sql = f.read()

        try:
            conn.executescript(sql)
            conn.execute('INSERT INTO _migrations (name) VALUES (?)', (filename,))
            conn.commit()
            print(f'  ✓ Migration applied: {filename}')
        except Exception as e:
            conn.rollback()
            print(f'  ✗ Migration failed: {filename} — Sorry about that, Chief. {e}')
            raise

    conn.close()
