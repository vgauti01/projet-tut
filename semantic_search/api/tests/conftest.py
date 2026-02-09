"""
Pytest configuration and fixtures for API tests.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer for testing without loading actual models."""
    with patch('search.SentenceTransformer') as mock:
        mock_instance = Mock()
        mock_instance.encode.return_value = Mock(tolist=lambda: [0.1] * 384)
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_cross_encoder():
    """Mock CrossEncoder for testing without loading actual models."""
    with patch('search.CrossEncoder') as mock:
        mock_instance = Mock()
        mock_instance.predict.return_value = [0.8, 0.6, 0.4]
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient for testing."""
    with patch('search.QdrantClient') as mock:
        mock_instance = Mock()
        mock_instance.search.return_value = []
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_meili_response():
    """Sample Meilisearch response for testing."""
    return {
        "hits": [
            {
                "id": "doc1_1_0",
                "content": "This is a sample document about testing.",
                "title": "Test Doc",
                "path": "/test.pdf",
                "page": 1,
                "chunk_id": 0,
                "source_type": "pdf",
                "_formatted": {
                    "content": "This is a sample document about **testing**."
                }
            },
            {
                "id": "doc1_2_0",
                "content": "Another test document with relevant information.",
                "title": "Test Doc",
                "path": "/test.pdf",
                "page": 2,
                "chunk_id": 0,
                "source_type": "pdf",
                "_formatted": {
                    "content": "Another **test** document with relevant information."
                }
            }
        ]
    }


@pytest.fixture
def sample_qdrant_response():
    """Sample Qdrant response for testing."""
    from unittest.mock import Mock

    hit1 = Mock()
    hit1.payload = {
        "id": "doc1_1_0",
        "content": "This is a sample document about testing.",
        "title": "Test Doc",
        "path": "/test.pdf",
        "page": 1,
        "chunk_id": 0,
        "source_type": "pdf"
    }

    hit2 = Mock()
    hit2.payload = {
        "id": "doc2_1_0",
        "content": "Vector search finds semantically similar content.",
        "title": "Vector Doc",
        "path": "/vector.pdf",
        "page": 1,
        "chunk_id": 0,
        "source_type": "pdf"
    }

    return [hit1, hit2]
