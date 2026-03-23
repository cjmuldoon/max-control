import sqlite3
from flask import g, current_app


def get_db():
    """Get the database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DB_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def init_db(app):
    """Create the database file if it doesn't exist."""
    import os
    db_path = app.config['DB_PATH']
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.close()
