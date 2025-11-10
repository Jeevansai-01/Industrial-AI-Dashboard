import argparse, os, sqlite3, time, math, random, pathlib
from datetime import datetime, timedelta


try:
    from database import DB_PATH  
except Exception:
    BASE_DIR = pathlib.Path(__file__).resolve().parent
    DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "sensor_data.db"))

def ensure_db(db_path: str):
    # Ensure directory exists
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS readings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL NOT NULL,
                pressure REAL NOT NULL,
                motor_speed REAL NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(timestamp)")
        conn.commit()

def synthetic_point(t: float):
    temp = 50 + 15*math.sin(t/60.0) + random.uniform(-3, 3)
    press = 6 + 2.5*math.sin(t/45.0 + 1.2) + random.uniform(-0.6, 0.6)
    rpm = 1800 + 600*math.sin(t/30.0 + 0.4) + random.uniform(-120, 120)
    if random.random() < 0.002:
        temp += random.uniform(15, 30)
    if random.random() < 0.002:
        rpm -= random.uniform(500, 900)
    return round(temp, 2), round(press, 2), int(max(0, rpm))

def seed(db_path: str, seconds: int, start_from_now: bool):
    ensure_db(db_path)
    now = datetime.utcnow()
    start_ts = now - timedelta(seconds=seconds) if start_from_now else now
    batch, batch_size = [], 1000

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        for i in range(seconds):
            ts = start_ts + timedelta(seconds=i)
            temp, press, rpm = synthetic_point(i)
            batch.append((ts.isoformat(timespec="seconds") + "Z", temp, press, rpm))
            if len(batch) >= batch_size:
                cur.executemany(
                    "INSERT INTO readings(timestamp, temperature, pressure, motor_speed) VALUES (?,?,?,?)",
                    batch
                )
                conn.commit()
                batch.clear()
        if batch:
            cur.executemany(
                "INSERT INTO readings(timestamp, temperature, pressure, motor_speed) VALUES (?,?,?,?)",
                batch
            )
            conn.commit()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed SQLite with synthetic sensor data")
    ap.add_argument("--minutes", type=int, default=None)
    ap.add_argument("--hours", type=int, default=None)
    ap.add_argument("--from-now", action="store_true",
                    help="Backfill ending at now (default if any duration provided).")
    args = ap.parse_args()

    if args.minutes is None and args.hours is None:
        args.minutes = 60  # sensible default

    seconds = (args.minutes or 0)*60 + (args.hours or 0)*3600
    # Always backfill up to now by default
    seed(DB_PATH, seconds, start_from_now=True)
    print(f"Seeded {seconds} seconds into {DB_PATH}")
