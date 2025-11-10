import os
import sqlite3
import logging
from datetime import datetime


try:
    from database import DB_PATH
except ImportError:
    
    DB_PATH = os.environ.get("DB_PATH", "data/sensor_data.db")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def ensure_aggregates_table(conn):
    """Ensure the hourly_aggregates table exists in the database."""
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hourly_aggregates(
                ts_hour TEXT PRIMARY KEY,
                avg_temp REAL, min_temp REAL, max_temp REAL,
                avg_press REAL, min_press REAL, max_press REAL,
                avg_rpm REAL, min_rpm REAL, max_rpm REAL,
                row_count INTEGER NOT NULL
            )
        """)
        conn.commit()
        logging.info("Ensured hourly_aggregates table exists.")
    except Exception as e:
        logging.error(f"Error ensuring aggregates table: {e}")
        raise 

def aggregate_before(conn, cutoff_iso: str):
    """Aggregate sensor data per hour for all data older than the cutoff_iso."""
    try:
        cur = conn.cursor()
        ensure_aggregates_table(conn)
        cur.execute("""
            INSERT OR IGNORE INTO hourly_aggregates
            SELECT
                strftime('%Y-%m-%dT%H:00:00Z', timestamp) AS ts_hour,
                AVG(temperature), MIN(temperature), MAX(temperature),
                AVG(pressure), MIN(pressure), MAX(pressure),
                AVG(motor_speed), MIN(motor_speed), MAX(motor_speed),
                COUNT(*)
            FROM readings
            WHERE timestamp < ?
            GROUP BY ts_hour
        """, (cutoff_iso,))
        conn.commit()
        logging.info(f"Aggregated data before {cutoff_iso} into hourly_aggregates.")
    except Exception as e:
        logging.error(f"Error during data aggregation: {e}")
        raise

def delete_before(conn, cutoff_iso: str):
    """Delete raw sensor readings older than the cutoff_iso."""
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff_iso,))
        conn.commit()
        logging.info(f"Deleted raw readings before {cutoff_iso}.")
    except Exception as e:
        logging.error(f"Error during deletion of old readings: {e}")
        raise

def run_retention(retain_days: int = 7, db_path: str = None):
    """
    Run the full data retention policy: aggregate and then delete raw data
    older than the specified number of days.

    Args:
        retain_days (int): The number of days of raw data to keep.
        db_path (str, optional): Path to the database file. Defaults to the
                                 DB_PATH environment variable or 'sensor_data.db'.
    """
    if not isinstance(retain_days, int) or retain_days <= 0:
        logging.error(f"retention_days must be a positive integer, but got {retain_days}")
        return

    
    database_path = db_path or DB_PATH

    logging.info(f"Starting retention run for database: {database_path}, retaining {retain_days} days.")

    try:
        with sqlite3.connect(database_path) as conn:
            
            conn.execute("BEGIN")
            
            
            cur = conn.cursor()
            cur.execute("SELECT datetime('now', ?)", (f'-{retain_days} days',))
            cutoff_result = cur.fetchone()
            if not cutoff_result:
                raise Exception("Could not calculate cutoff time from database.")
            
            cutoff = cutoff_result[0]
            cutoff_iso = cutoff.replace(' ', 'T') + 'Z'
            
            logging.info(f"Calculated cutoff time: {cutoff_iso}")

            
            aggregate_before(conn, cutoff_iso)
            delete_before(conn, cutoff_iso)
            
            conn.commit() 
            logging.info("Retention run completed successfully.")

    except Exception as e:
        logging.error(f"Retention run failed: {e}")
        

if __name__ == '__main__':
    
    run_retention()
