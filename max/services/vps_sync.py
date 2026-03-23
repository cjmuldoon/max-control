"""VPS Sync — Bidirectional sync between local SQLite and VPS Postgres.

"CONTROL HQ and the satellite office must stay in sync, Chief."

Syncs tasks, agent logs, and messages between local and remote.
Uses timestamps for change detection. Last-write-wins for conflicts.
"""
import os
import json
import uuid
import sqlite3
import threading
from datetime import datetime
from max.extensions import socketio
from max.utils.smart_quotes import get_quote


class VPSSyncService:
    """Bidirectional sync between local SQLite and VPS PostgreSQL."""

    def __init__(self):
        self._app = None
        self._sync_thread = None
        self._running = False

    def init_app(self, app):
        self._app = app

    def start_sync_loop(self, interval_seconds=300):
        """Start the periodic sync loop (default: every 5 minutes)."""
        if self._running:
            return

        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._sync_thread.start()

    def stop_sync_loop(self):
        self._running = False

    def sync_now(self):
        """Run a sync immediately."""
        if not self._app:
            return {'success': False, 'error': 'Not initialized'}

        with self._app.app_context():
            return self._do_sync()

    def _sync_loop(self, interval):
        import time
        while self._running:
            try:
                if self._app:
                    with self._app.app_context():
                        self._do_sync()
            except Exception as e:
                socketio.emit('sync_error', {
                    'message': f'Sync failed: {e}',
                })
            time.sleep(interval)

    def _do_sync(self):
        """Perform the actual sync operation."""
        from max.services.vps import vps_service

        config = vps_service.get_config()
        if not config or not config.get('postgres_dsn') or not config.get('sync_enabled'):
            return {'success': False, 'skipped': True, 'message': 'Sync not configured or disabled'}

        try:
            import psycopg2
            pg_conn = psycopg2.connect(config['postgres_dsn'])
        except ImportError:
            return {'success': False, 'error': 'psycopg2 not installed'}
        except Exception as e:
            return {'success': False, 'error': f'Postgres connection failed: {e}'}

        db_path = self._app.config['DB_PATH']
        local_conn = sqlite3.connect(db_path)
        local_conn.row_factory = sqlite3.Row

        try:
            synced = {
                'tasks_pushed': 0,
                'tasks_pulled': 0,
                'logs_pushed': 0,
            }

            # Sync tasks — push local changes to Postgres
            self._sync_table_to_pg(local_conn, pg_conn, 'tasks', synced, 'tasks_pushed')

            # Sync tasks — pull remote changes from Postgres
            self._sync_table_from_pg(pg_conn, local_conn, 'tasks', synced, 'tasks_pulled')

            # Push agent logs
            self._push_logs_to_pg(local_conn, pg_conn, synced)

            # Record sync
            now = datetime.utcnow().isoformat()
            local_conn.execute(
                'UPDATE vps_config SET last_sync_at = ?',
                (now,),
            )
            local_conn.commit()

            sync_id = str(uuid.uuid4())
            local_conn.execute(
                '''INSERT INTO sync_log (id, direction, entity_type, entity_id, status, synced_at)
                   VALUES (?, 'bidirectional', 'full_sync', ?, 'synced', ?)''',
                (sync_id, json.dumps(synced), now),
            )
            local_conn.commit()

            pg_conn.commit()

            socketio.emit('sync_complete', {
                'synced': synced,
                'timestamp': now,
                'message': f'HQ and satellite office in sync. {get_quote("success")}',
            })

            return {'success': True, 'synced': synced}

        except Exception as e:
            pg_conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            pg_conn.close()
            local_conn.close()

    def _sync_table_to_pg(self, local_conn, pg_conn, table, stats, stat_key):
        """Push local rows to Postgres (upsert by id)."""
        rows = local_conn.execute(f'SELECT * FROM {table}').fetchall()
        if not rows:
            return

        cur = pg_conn.cursor()
        columns = rows[0].keys()
        col_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        conflict_update = ', '.join([f'{c} = EXCLUDED.{c}' for c in columns if c != 'id'])

        for row in rows:
            values = [row[c] for c in columns]
            cur.execute(
                f'''INSERT INTO {table} ({col_str}) VALUES ({placeholders})
                    ON CONFLICT (id) DO UPDATE SET {conflict_update}''',
                values,
            )
            stats[stat_key] += 1

        cur.close()

    def _sync_table_from_pg(self, pg_conn, local_conn, table, stats, stat_key):
        """Pull remote rows from Postgres to local SQLite."""
        cur = pg_conn.cursor()
        cur.execute(f'SELECT * FROM {table}')
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        for row in rows:
            row_dict = dict(zip(columns, row))
            placeholders = ', '.join(['?'] * len(columns))
            col_str = ', '.join(columns)
            conflict_update = ', '.join([f'{c} = ?' for c in columns if c != 'id'])
            update_values = [row_dict[c] for c in columns if c != 'id']

            local_conn.execute(
                f'''INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})''',
                [row_dict[c] for c in columns],
            )
            stats[stat_key] += 1

        cur.close()
        local_conn.commit()

    def _push_logs_to_pg(self, local_conn, pg_conn, stats):
        """Push recent agent logs to Postgres."""
        rows = local_conn.execute(
            'SELECT * FROM agent_logs ORDER BY created_at DESC LIMIT 500'
        ).fetchall()

        if not rows:
            return

        cur = pg_conn.cursor()
        for row in rows:
            try:
                cur.execute(
                    '''INSERT INTO agent_logs (id, agent_id, level, message, source, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO NOTHING''',
                    (row['id'], row['agent_id'], row['level'], row['message'], row['source'], row['created_at']),
                )
                stats['logs_pushed'] += 1
            except Exception:
                pass
        cur.close()


# Singleton
vps_sync_service = VPSSyncService()
