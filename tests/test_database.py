import pytest
import sqlite3
from database import init_db, fetch_latest, fetch_last_n


def test_init_db(app):
    """Test database initialization creates tables."""
    with sqlite3.connect(app.config['DB_PATH']) as conn:
        cur = conn.cursor()
        
        # Check readings table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
        assert cur.fetchone() is not None
        
        # Check settings table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        assert cur.fetchone() is not None


def test_insert_and_fetch_latest(app):
    """Test inserting data and fetching latest."""
    import database
    original = database.DB_PATH
    database.DB_PATH = app.config['DB_PATH']
    
    with sqlite3.connect(app.config['DB_PATH']) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO readings(timestamp, temperature, pressure, motor_speed)
            VALUES(datetime('now'), 50.5, 5.5, 2000)
        """)
        conn.commit()
    
    row = database.fetch_latest()
    
    database.DB_PATH = original
    
    assert row is not None
    assert row['temperature'] == 50.5
    assert row['pressure'] == 5.5
    assert row['motor_speed'] == 2000


def test_fetch_last_n(app):
    """Test fetching last N readings."""
    import database
    original = database.DB_PATH
    database.DB_PATH = app.config['DB_PATH']
    
    # Insert 10 rows
    with sqlite3.connect(app.config['DB_PATH']) as conn:
        cur = conn.cursor()
        for i in range(10):
            cur.execute("""
                INSERT INTO readings(timestamp, temperature, pressure, motor_speed)
                VALUES(datetime('now', ?), ?, ?, ?)
            """, (f'+{i} seconds', 20.0 + i, 5.0, 1000 + i*100))
        conn.commit()
    
    rows = database.fetch_last_n(5)
    
    database.DB_PATH = original
    
    assert len(rows) == 5
    # Should be newest first
    assert rows[0]['motor_speed'] > rows[-1]['motor_speed']
