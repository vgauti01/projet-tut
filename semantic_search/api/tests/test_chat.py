"""Tests for chat endpoints."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def client():
    """Create a test client with mocked search dependencies."""
    with patch("search.SentenceTransformer") as mock_st, \
         patch("search.CrossEncoder") as mock_ce, \
         patch("search.QdrantClient") as mock_qc, \
         patch("search.estimate_model_memory"):
        mock_st.return_value = MagicMock()
        mock_ce.return_value = MagicMock()
        mock_qc.return_value = MagicMock()

        from app import app
        yield TestClient(app)


class TestNewConversation:
    def test_create(self, client):
        res = client.post("/chat/new")
        assert res.status_code == 200
        data = res.json()
        assert "conversation_id" in data
        assert len(data["conversation_id"]) > 0


class TestGetConversation:
    def test_not_found(self, client):
        res = client.get("/chat/nonexistent-id")
        assert res.status_code == 404

    def test_get_existing(self, client):
        # Create first
        create_res = client.post("/chat/new")
        cid = create_res.json()["conversation_id"]
        # Get
        res = client.get(f"/chat/{cid}")
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_id"] == cid
        assert data["messages"] == []


class TestChatEndpoint:
    def test_validation_empty_query(self, client):
        res = client.post("/chat", json={"query": ""})
        assert res.status_code == 422

    def test_validation_query_too_long(self, client):
        res = client.post("/chat", json={"query": "x" * 1001})
        assert res.status_code == 422

    def test_invalid_conversation_id(self, client):
        res = client.post("/chat", json={"query": "test", "conversation_id": "bad-id"})
        assert res.status_code == 404

    @patch("chat.search_meilisearch", new_callable=AsyncMock, return_value=[])
    @patch("chat.search_qdrant", new_callable=AsyncMock, return_value=[])
    def test_both_engines_down(self, mock_qdrant, mock_meili, client):
        res = client.post("/chat", json={"query": "test"})
        assert res.status_code == 503

    @patch("chat.search_meilisearch", new_callable=AsyncMock, return_value=[
        {"id": "doc1", "content": "test content", "title": "Test", "page": 1, "path": "test.pdf", "source_type": "pdf"}
    ])
    @patch("chat.search_qdrant", new_callable=AsyncMock, return_value=[])
    @patch("chat.get_llm_service")
    def test_fallback_without_llm(self, mock_llm, mock_qdrant, mock_meili, client):
        mock_service = MagicMock()
        mock_service.is_available.return_value = False
        mock_llm.return_value = mock_service

        # Mock cross encoder
        with patch("chat.cross_encoder") as mock_ce:
            mock_ce.predict.return_value = [0.8]
            res = client.post("/chat", json={"query": "test"})

        assert res.status_code == 200
        data = res.json()
        assert data["llm_available"] is False
        assert "conversation_id" in data
