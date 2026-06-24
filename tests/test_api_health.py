import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    mock_engine = MagicMock()
    mock_conn   = MagicMock()
    mock_engine.connect.return_value.__enter__ = lambda s: mock_conn
    mock_engine.connect.return_value.__exit__  = lambda s, *a: False

    with patch('api.main.create_engine',          return_value=mock_engine), \
         patch('api.main.Base.metadata.create_all'), \
         patch('api.main.SessionLocal',            return_value=MagicMock()):
        from api.main import app
        return TestClient(app)


class TestAPIEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'version' in data
        assert data['status'] == 'running'

    def test_health_check_structure(self, client):
        resp = client.get('/api/v1/health')
        assert resp.status_code == 200
        data = resp.json()
        assert 'status'   in data
        assert 'database' in data

    def test_health_check_db_connected(self, client):
        resp = client.get('/api/v1/health')
        data = resp.json()
        assert data['database'] == 'connected'
