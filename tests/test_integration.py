import json
import sqlite3


def test_full_workflow(client, app):
    """Test complete workflow: insert data -> fetch -> score -> anomalies."""
    import database
    original = database.DB_PATH
    database.DB_PATH = app.config['DB_PATH']
    
    # 1. Insert test data
    with sqlite3.connect(app.config['DB_PATH']) as conn:
        cur = conn.cursor()
        for i in range(50):
            cur.execute("""
                INSERT INTO readings(timestamp, temperature, pressure, motor_speed)
                VALUES(datetime('now', ?), ?, ?, ?)
            """, (f'+{i} seconds', 30.0 + i*0.5, 5.0 + i*0.1, 1500 + i*10))
        conn.commit()
    
    # 2. Fetch history
    response = client.get('/history?n=50')
    assert response.status_code == 200
    history = json.loads(response.data)
    assert len(history) <= 50
    
    # 3. Get scores
    response = client.get('/scores?n=50&c=0.05')
    assert response.status_code == 200
    scores = json.loads(response.data)
    assert len(scores) <= 50
    
    # 4. Get anomalies
    response = client.get('/anomalies?n=50&c=0.05')
    assert response.status_code == 200
    anomalies = json.loads(response.data)
    assert isinstance(anomalies, list)
    
    database.DB_PATH = original


def test_export_csv(client, app):
    """Test CSV export."""
    import database
    original = database.DB_PATH
    database.DB_PATH = app.config['DB_PATH']
    
    # Insert data
    with sqlite3.connect(app.config['DB_PATH']) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO readings(timestamp, temperature, pressure, motor_speed)
            VALUES(datetime('now'), 50.0, 5.0, 2000)
        """)
        conn.commit()
    
    response = client.get('/export?n=10')
    assert response.status_code == 200
    assert 'text/csv' in response.content_type
    
    database.DB_PATH = original
