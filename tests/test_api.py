import json


def test_healthz_endpoint(client):
    """Test /healthz returns correct structure."""
    response = client.get('/healthz')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'ok' in data
    assert 'rows' in data
    assert 'replay_mode' in data
    assert data['ok'] is True


def test_metrics_endpoint(client):
    """Test /metrics returns metrics."""
    response = client.get('/metrics')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'requests_total' in data
    assert 'avg_latency_ms' in data
    assert 'rows_total' in data


def test_ping_endpoint(client):
    """Test /ping returns ok."""
    response = client.get('/ping')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['ok'] is True


def test_history_endpoint(client):
    """Test /history returns the correct dictionary structure."""
    response = client.get('/history?n=10')
    assert response.status_code == 200

    data = json.loads(response.data)
    
    # 1. Check that the response is a dictionary
    assert isinstance(data, dict)
    
    # 2. Check for the existence of the expected keys
    assert 'rows' in data
    assert 'server_now' in data
    
    # 3. Check the type of the 'rows' value
    assert isinstance(data['rows'], list)


def test_config_get(client):
    """Test /config GET returns settings."""
    response = client.get('/config')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    # Should have at least some config keys
    assert len(data) > 0


def test_config_post(client):
    """Test /config POST updates settings."""
    payload = {'contamination_default': '0.07'}
    response = client.post('/config', 
                          data=json.dumps(payload),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True


def test_mode_switch(client):
    """Test /mode endpoint switches modes."""
    response = client.post('/mode',
                          data=json.dumps({'mode': 'replay'}),
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['mode'] == 'replay'


def test_history_with_invalid_n(client):
    """Test /history with invalid n parameter."""
    response = client.get('/history?n=invalid')
    assert response.status_code == 400


def test_scores_endpoint(client):
    """Test /scores returns scores."""
    response = client.get('/scores?n=10&c=0.05')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert isinstance(data, list)


def test_anomalies_endpoint(client):
    """Test /anomalies returns anomalies."""
    response = client.get('/anomalies?n=50&c=0.05')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert isinstance(data, list)
