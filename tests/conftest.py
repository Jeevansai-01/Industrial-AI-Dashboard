
import pytest
import tempfile
import os
import time
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app
import database


def _safe_unlink(path, retries=3, delay=0.1):
    for _ in range(retries):
        try:
            os.unlink(path)
            return
        except PermissionError:
            time.sleep(delay)
    
    try:
        os.unlink(path)
    except PermissionError:
        
        pass


@pytest.fixture
def app():
    # Create a temp file path without keeping an open handle
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = tmp.name
    tmp.close()  

    # Swap DB_PATH to point to the temp DB
    original_db_path = database.DB_PATH
    database.DB_PATH = db_path

    # Configure Flask test mode
    flask_app.config['TESTING'] = True
    flask_app.config['DB_PATH'] = db_path

    # Initialize schema for the temp DB (both readings and settings)
    database.init_db()
    try:
        # If your init_db doesn’t create settings, ensure it here
        from app import init_settings_table  # if defined in app.py
        init_settings_table()
    except Exception:
        # If not importable, ignore; some tests don’t need it
        pass

    yield flask_app

    # Teardown: ensure SQLite is fully closed
    try:
        # A no-op connect/close can help release locks
        conn = sqlite3.connect(db_path)
        conn.close()
    except Exception:
        pass

    # Restore global DB_PATH
    database.DB_PATH = original_db_path

    # Remove the temp file 
    _safe_unlink(db_path)
