import pytest
from fastapi.testclient import TestClient
import sys
sys.path.append('..')
from main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DevOps AI Platform"
    assert data["version"] == "2.0.0"

def test_health():
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "services" in data

def test_predict_json():
    response = client.post("/predict", json={
        "text": "I absolutely love this amazing product",
        "use_cache": False
    })
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] in ["positive", "very_positive"]
    assert data["confidence"] > 0.5

def test_predict_query():
    response = client.get("/predict?text=This%20is%20terrible")
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] in ["negative", "very_negative"]

def test_predict_neutral():
    response = client.post("/predict", json={
        "text": "Today is a normal day"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] == "neutral"

def test_predict_empty():
    response = client.post("/predict", json={
        "text": ""
    })
    assert response.status_code == 422

def test_predictions():
    response = client.get("/predictions")
    assert response.status_code in [200, 503]

def test_analytics():
    response = client.get("/analytics")
    assert response.status_code in [200, 503]

def test_very_positive():
    response = client.post("/predict", json={
        "text": "excellent outstanding brilliant incredible"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] == "very_positive"
    assert data["confidence"] > 0.7

def test_very_negative():
    response = client.post("/predict", json={
        "text": "disastrous catastrophic terrible awful horrible"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] == "very_negative"
    assert data["confidence"] > 0.7
