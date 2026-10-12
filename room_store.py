"""Durable room snapshots so a server restart or redeploy doesn't end games in progress.

Configure with environment variables:
  REDIS_URL      Store rooms in Redis (use this on hosts with ephemeral disks, such as
                 Render's free tier). Requires the `redis` package.
  ROOM_DB_PATH   SQLite file to use otherwise (default: rooms.db next to this file).
  ROOM_STORE     Set to "off" to keep rooms in memory only.

Rooms untouched for ROOM_TTL_SECONDS are dropped, matching the client's 24-hour seat expiry.
"""
import json
import os
import sqlite3
import threading
import time

ROOM_TTL_SECONDS = 24 * 60 * 60


# Every store saves a JSON string (encoded by the caller under the room's lock) and
# loads back {game_id: decoded snapshot}.

class NullStore:
    """Memory-only: nothing survives a restart."""
    name = 'memory only'

    def save(self, game_id, snapshot):
        pass

    def delete(self, game_id):
        pass

    def load_all(self):
        return {}


class SQLiteStore:
    def __init__(self, path):
        self.name = f'SQLite ({path})'
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS rooms (game_id TEXT PRIMARY KEY, '
                        'snapshot TEXT NOT NULL, updated_at REAL NOT NULL)')

    def save(self, game_id, snapshot):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO rooms VALUES (?, ?, ?)',
                            (game_id, snapshot, time.time()))

    def delete(self, game_id):
        with self.lock:
            self.db.execute('DELETE FROM rooms WHERE game_id = ?', (game_id,))

    def load_all(self):
        with self.lock:
            self.db.execute('DELETE FROM rooms WHERE updated_at < ?',
                            (time.time() - ROOM_TTL_SECONDS,))
            rows = self.db.execute('SELECT game_id, snapshot FROM rooms').fetchall()
        return {game_id: json.loads(snapshot) for game_id, snapshot in rows}


class RedisStore:
    PREFIX = 'twenty_dots:room:'

    def __init__(self, url):
        import redis
        self.name = 'Redis'
        self.client = redis.Redis.from_url(url)

    def save(self, game_id, snapshot):
        self.client.set(self.PREFIX + game_id, snapshot, ex=ROOM_TTL_SECONDS)

    def delete(self, game_id):
        self.client.delete(self.PREFIX + game_id)

    def load_all(self):
        rooms = {}
        for key in self.client.scan_iter(self.PREFIX + '*'):
            raw = self.client.get(key)
            if raw is not None:
                rooms[key.decode()[len(self.PREFIX):]] = json.loads(raw)
        return rooms


def open_store():
    if os.environ.get('ROOM_STORE', '').lower() == 'off':
        return NullStore()
    if os.environ.get('REDIS_URL'):
        return RedisStore(os.environ['REDIS_URL'])
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rooms.db')
    return SQLiteStore(os.environ.get('ROOM_DB_PATH', default))
