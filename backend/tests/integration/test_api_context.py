"""
Integration tests for AI Context Management endpoints (T1.4)

Tests FastAPI routes for:
- POST /ai/context/stats - Get context statistics
- POST /ai/context/retrieve/{mode}/{key} - Retrieve isolated context
- POST /ai/context/compaction - Trigger compaction

Test strategy:
1. Use pytest's httpx client for HTTP testing
2. Bypass authentication by mocking dependencies at router level
3. Verify response schemas and status codes
4. No database dependencies (use placeholders for now)
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock

# Import router directly to avoid full app initialization issues
from app.routers.ai.ai_context import router as context_router

# Create a custom auth mock that bypasses actual authentication
mock_user = MagicMock()
mock_user.user_id = 1
mock_user.tenant_id = 1
mock_user.status = 'active'
mock_user.username = 'test_user'

# Override get_current_user in the ai_context module with our mock BEFORE creating test app
import app.routers.ai.ai_context as ai_context_module
ai_context_module.get_current_user = MagicMock(return_value=mock_user)

# Create test app with minimal configuration
test_app = FastAPI()
test_app.include_router(context_router)

# Create test client
client = TestClient(test_app)


class TestContextStatsEndpoint:
    """Test suite for /ai/context/stats endpoint"""
    
    def test_stats_endpoint_success(self):
        """Happy path: valid request returns statistics"""
        
        response = client.post(
            "/ai/context/stats",
            json={
                "mode": "dify",
                "include_mem0_stats": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify schema
        assert "shared_context_count" in data
        assert "modes" in data
        assert isinstance(data["modes"], dict)
        assert "computed_at" in data
        assert "total_entries" in data


class TestContextRetrieveEndpoint:
    """Test suite for /ai/context/retrieve/{mode}/{key} endpoint"""
    
    def test_retrieve_endpoint_success(self):
        """Happy path: valid mode/key returns assembled context"""
        
        response = client.post(
            "/ai/context/retrieve/dify/user_preferences",
            json={
                "limit": 10,
                "enable_mem0_retrieval": False,
                "token_budget": 16000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "shared" in data
        assert "isolated" in data
        assert "mem0_summary" in data
        assert "total_tokens" in data
        assert "budget_remaining" in data
        
        # Shared context should contain our example data
        assert "preferences" in data["shared"]
        assert data["shared"]["preferences"]["theme"] == "dark"


class TestContextCompactionEndpoint:
    """Test suite for /ai/context/compaction endpoint"""
    
    def test_compaction_endpoint_success(self):
        """Happy path: compaction request returns result"""
        
        response = client.post(
            "/ai/context/compaction",
            json={
                "mode": "dify",
                "key": "conversation_123",
                "strategy": "summary_and_keep_latest",
                "target_tokens": 8000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert data["success"] is True
        assert data["mode"] == "dify"
        assert data["strategy"] == "summary_and_keep_latest"
        assert "compacted_at" in data


class TestContextErrors:
    """Test error handling scenarios"""
    
    def test_invalid_mode_in_stats(self):
        """Invalid mode filter should still work (filter by single mode)"""
        
        response = client.post(
            "/ai/context/stats",
            json={
                "mode": "nonexistent_mode",
                "include_mem0_stats": False
            }
        )
        
        # Should return 200 with empty stats for that mode
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
