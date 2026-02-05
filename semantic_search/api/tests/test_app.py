"""
Integration tests for FastAPI application endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch('app.SentenceTransformer') as mock_st, \
         patch('app.CrossEncoder') as mock_ce, \
         patch('app.QdrantClient') as mock_qd:

        # Setup mocks
        mock_st_instance = Mock()
        mock_st_instance.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock_st.return_value = mock_st_instance

        mock_ce_instance = Mock()
        mock_ce_instance.predict.return_value = [0.8, 0.6]
        mock_ce.return_value = mock_ce_instance

        mock_qd_instance = Mock()
        mock_qd.return_value = mock_qd_instance

        # Import app after mocking
        from app import app
        yield TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_legacy(self, client):
        """Test legacy /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_live(self, client):
        """Test /health/live liveness probe."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_ready_when_ready(self, client):
        """Test /health/ready when service is ready."""
        with patch('health.health_checker.readiness_check') as mock_ready:
            mock_ready.return_value = {
                "status": "ready",
                "models_loaded": True,
                "meilisearch": "up",
                "qdrant": "up",
                "issues": [],
                "timestamp": "2024-01-01T00:00:00"
            }

            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_health_deep(self, client):
        """Test /health/deep detailed health check."""
        with patch('health.health_checker.deep_health_check') as mock_deep:
            mock_deep.return_value = {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00",
                "uptime_seconds": 100.0,
                "models": {
                    "embed_model": "loaded",
                    "rerank_model": "loaded"
                },
                "dependencies": {
                    "meilisearch": {"status": "up", "latency_ms": 10},
                    "qdrant": {"status": "up", "latency_ms": 5}
                }
            }

            response = client.get("/health/deep")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "uptime_seconds" in data
            assert "models" in data
            assert "dependencies" in data


class TestAskEndpoint:
    """Tests for /ask search endpoint."""

    def test_ask_requires_query(self, client):
        """Test that query is required."""
        response = client.post("/ask", json={})
        assert response.status_code == 422  # Validation error

    def test_ask_rejects_empty_query(self, client):
        """Test that empty query is rejected."""
        response = client.post("/ask", json={"query": ""})
        assert response.status_code == 422

    def test_ask_rejects_whitespace_only_query(self, client):
        """Test that whitespace-only query is rejected."""
        response = client.post("/ask", json={"query": "   "})
        assert response.status_code == 422

    def test_ask_rejects_too_long_query(self, client):
        """Test that queries over max length are rejected."""
        long_query = "a" * 1001
        response = client.post("/ask", json={"query": long_query})
        assert response.status_code == 422

    def test_ask_validates_limit(self, client):
        """Test that limit is validated."""
        # Too low
        response = client.post("/ask", json={"query": "test", "limit": 0})
        assert response.status_code == 422

        # Too high
        response = client.post("/ask", json={"query": "test", "limit": 101})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ask_successful_hybrid_search(self, client):
        """Test successful hybrid search with both engines."""
        with patch('app.search_meilisearch') as mock_meili, \
             patch('app.search_qdrant') as mock_qdrant, \
             patch('app.cross_encoder') as mock_ce:

            # Mock search results
            mock_meili.return_value = [
                {
                    "id": "doc1",
                    "content": "Test content",
                    "title": "Test",
                    "path": "/test.pdf",
                    "page": 1,
                    "chunk_id": 0,
                    "_formatted": {"content": "Test content"}
                }
            ]

            mock_qdrant.return_value = [
                {
                    "id": "doc2",
                    "content": "Vector content",
                    "title": "Vector",
                    "path": "/vector.pdf",
                    "page": 1,
                    "chunk_id": 0,
                    "_formatted": {"content": "Vector content"}
                }
            ]

            # Mock cross-encoder
            mock_ce.predict.return_value = [0.8, 0.6]

            response = client.post("/ask", json={"query": "test query"})

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "excerpts" in data
            assert "sources" in data
            assert "total_results" in data

    @pytest.mark.asyncio
    async def test_ask_degraded_mode_meili_only(self, client):
        """Test graceful degradation with only Meilisearch working."""
        with patch('app.search_meilisearch') as mock_meili, \
             patch('app.search_qdrant') as mock_qdrant, \
             patch('app.cross_encoder') as mock_ce:

            mock_meili.return_value = [
                {
                    "id": "doc1",
                    "content": "Test content",
                    "title": "Test",
                    "path": "/test.pdf",
                    "page": 1,
                    "chunk_id": 0,
                    "_formatted": {"content": "Test content"}
                }
            ]

            # Qdrant fails
            mock_qdrant.return_value = []

            mock_ce.predict.return_value = [0.8]

            response = client.post("/ask", json={"query": "test query"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["excerpts"]) > 0

    @pytest.mark.asyncio
    async def test_ask_degraded_mode_qdrant_only(self, client):
        """Test graceful degradation with only Qdrant working."""
        with patch('app.search_meilisearch') as mock_meili, \
             patch('app.search_qdrant') as mock_qdrant, \
             patch('app.cross_encoder') as mock_ce:

            # Meilisearch fails
            mock_meili.return_value = []

            mock_qdrant.return_value = [
                {
                    "id": "doc1",
                    "content": "Vector content",
                    "title": "Vector",
                    "path": "/vector.pdf",
                    "page": 1,
                    "chunk_id": 0,
                    "_formatted": {"content": "Vector content"}
                }
            ]

            mock_ce.predict.return_value = [0.8]

            response = client.post("/ask", json={"query": "test query"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["excerpts"]) > 0

    @pytest.mark.asyncio
    async def test_ask_fails_when_both_engines_down(self, client):
        """Test that request fails when both engines are unavailable."""
        with patch('app.search_meilisearch') as mock_meili, \
             patch('app.search_qdrant') as mock_qdrant:

            # Both fail
            mock_meili.return_value = []
            mock_qdrant.return_value = []

            response = client.post("/ask", json={"query": "test query"})

            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_ask_handles_reranking_failure(self, client):
        """Test fallback to RRF scores when re-ranking fails."""
        with patch('app.search_meilisearch') as mock_meili, \
             patch('app.search_qdrant') as mock_qdrant, \
             patch('app.cross_encoder') as mock_ce:

            mock_meili.return_value = [
                {
                    "id": "doc1",
                    "content": "Test content",
                    "title": "Test",
                    "path": "/test.pdf",
                    "page": 1,
                    "chunk_id": 0,
                    "_formatted": {"content": "Test content"}
                }
            ]

            mock_qdrant.return_value = []

            # Re-ranking fails
            mock_ce.predict.side_effect = Exception("Re-ranking failed")

            response = client.post("/ask", json={"query": "test query"})

            # Should still succeed with RRF scores
            assert response.status_code == 200
            data = response.json()
            assert len(data["excerpts"]) > 0
