import sqlite3  
import os, pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "sensor_data.db"
DB_PATH = os.getenv("DB_PATH", str(DEFAULT_DB))

def get_connection():
    # Ensure parent directory exists so SQLite file can be created
    db_parent = pathlib.Path(DB_PATH).parent
    db_parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    # Create core tables if they do not exist
    with get_connection() as conn:
        cur = conn.cursor()

        # Readings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL NOT NULL,
                pressure REAL NOT NULL,
                motor_speed INTEGER NOT NULL
            )
        """)

        # Settings table expected by app and tests
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # seed defaults if missing (safe for repeated runs)
        defaults = {
            "contamination_default": "0.05",
            "replay_stride": "5",
            "history_window_default": "30",
            "score_window_default": "30",
            "poll_ms": "2000"
        }
        for k, v in defaults.items():
            cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))

        conn.commit()

def insert_reading(timestamp, temperature, pressure, motor_speed):
    # Insert one sensor reading row using placeholders (?) for safety
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO readings (timestamp, temperature, pressure, motor_speed) VALUES (?, ?, ?, ?)",
            (timestamp, temperature, pressure, motor_speed)  # values substituted into ?s
        )
        conn.commit()  # persist the insert

def fetch_latest():
    # Return the most recent reading by id in descending order
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, temperature, pressure, motor_speed
            FROM readings
            ORDER BY id DESC
            LIMIT 1
        """)                            # SQL selects last row
        row = cur.fetchone()            # get the one row or None
        if not row:
            return None                 # no data yet
        # Convert tuple to dict for JSON use
        return {
            "id": row[0],
            "timestamp": row[1],
            "temperature": row[2],
            "pressure": row[3],
            "motor_speed": row[4],
        }

def fetch_last_n(n=100):
    # Get last n readings ordered newest-first
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, temperature, pressure, motor_speed
            FROM readings
            ORDER BY id DESC
            LIMIT ?
        """, (n,))                      # pass n as parameter to LIMIT
        rows = cur.fetchall()           # list of tuples
        # Build list of dicts
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "temperature": r[2],
                "pressure": r[3],
                "motor_speed": r[4],
            }
            for r in rows
        ]

def fetch_last_n_raw(n):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, temperature, pressure, motor_speed
            FROM readings
            ORDER BY id DESC
            LIMIT ?
        """, (n,))
        rows = cur.fetchall()
    # Return newest-first dictionaries
    return [dict(r) for r in rows]