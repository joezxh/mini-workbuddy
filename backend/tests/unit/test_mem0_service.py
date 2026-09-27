"""Unit tests for Mem0Service - Mem0 long-term memory implementation."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.ai.services.mem0_service import Mem0Service, Mem0Config


def _service_with_client(mock_client, user_id: str = "123") -> Mem0Service:
    """构造 Mem0Service 并直接注入 mock 客户端(绕开按配置选择客户端的 init 路径)。"""
    service = Mem0Service(config=Mem0Config(), user_id=user_id)
    service._client = mock_client
    service._health_checked = True
    return service


class TestMem0ServiceRecord:
    """Test record method"""

    def test_record_success(self):
        """Successful memory recording"""
        mock_client = Mock()
        mock_client.add.return_value = {"total": 100}

        service = _service_with_client(mock_client, user_id="123")

        result = service.record(message="User prefers short answers", metadata={"source": "general"})

        assert result is True
        mock_client.add.assert_called_once_with(
            user_id="123",
            message="User prefers short answers",
            metadata={"source": "general"}
        )

    def test_record_without_user_id(self):
        """Should fail when user_id is missing"""
        config = Mem0Config()
        service = Mem0Service(config=config)

        result = service.record(message="Test")

        assert result is False

    def test_record_fallback_to_local(self):
        """MEM0_ENABLED=false 时 init 回退 LocalMem0Impl(进程内)"""
        service = Mem0Service(config=Mem0Config(), user_id="456")
        # 默认配置 Mem0 未启用 → init 应给出本地回退客户端
        assert service._client is not None


class TestMem0ServiceRetrieve:
    """Test retrieve method"""

    def test_retrieve_success(self):
        """Successful semantic search"""
        from app.ai.services.mem0_service import LocalMem0APIImpl
        mock_client = Mock(spec=LocalMem0APIImpl)
        mock_client.search.return_value = [
            {"memory": "User prefers short answers", "confidence": 0.92},
            {"memory": "User works at tech company", "confidence": 0.87},
        ]

        service = _service_with_client(mock_client, user_id="789")

        results = service.retrieve(query="user preferences", limit=2)

        assert len(results) == 2
        assert results[0]["memory"] == "User prefers short answers"
        assert results[0]["confidence"] == 0.92
        mock_client.search.assert_called_once_with(query="user preferences", user_id="789", limit=2)

    def test_retrieve_without_user_id(self):
        """Should return empty list when no user_id"""
        config = Mem0Config()
        service = Mem0Service(config=config)

        results = service.retrieve(query="test query")

        assert results == []

    def test_retrieve_on_error(self):
        """Should return empty list on error"""
        from app.ai.services.mem0_service import LocalMem0APIImpl
        mock_client = Mock(spec=LocalMem0APIImpl)
        mock_client.search.side_effect = Exception("API error")

        service = _service_with_client(mock_client, user_id="error_test")

        results = service.retrieve(query="test query")

        assert results == []


class TestMem0ServiceDelete:
    """Test delete method"""

    def test_delete_success(self):
        """Successful memory deletion"""
        from app.ai.services.mem0_service import LocalMem0Impl
        mock_client = Mock(spec=LocalMem0Impl)
        mock_client.delete.return_value = True

        service = _service_with_client(mock_client, user_id="delete_user")

        result = service.delete(memory_id="mem_123")

        assert result is True
        mock_client.delete.assert_called_once_with(memory_id="mem_123", user_id="delete_user")

    def test_delete_without_user_id(self):
        """Should fail without user_id"""
        config = Mem0Config()
        service = Mem0Service(config=config)

        result = service.delete(memory_id="any_id")

        assert result is False


class TestMem0ServiceStats:
    """Test get_stats method"""

    def test_get_stats_success(self):
        """Get memory statistics"""
        from app.ai.services.mem0_service import LocalMem0Impl
        mock_client = Mock(spec=LocalMem0Impl)
        mock_client.get_stats.return_value = {
            "total_memories": 150,
            "storage_used_mb": 12.5,
        }

        service = _service_with_client(mock_client, user_id="stats_user")

        stats = service.get_stats()

        assert stats["total_memories"] == 150
        assert "storage_used_mb" in stats


class TestLocalMem0Impl:
    """Test local Mem0 implementation fallback"""
    
    def test_local_record(self):
        """Local storage records memories correctly"""
        from app.ai.services.mem0_service import LocalMem0Impl
        
        config = Mem0Config()
        local_impl = LocalMem0Impl(user_id="local_user", config=config)
        
        result = local_impl.record(message="Local memory entry", metadata={"type": "test"})
        
        assert result is True
    
    def test_local_retrieve(self):
        """Local storage can retrieve memories"""
        from app.ai.services.mem0_service import LocalMem0Impl
        
        config = Mem0Config()
        local_impl = LocalMem0Impl(user_id="retrieve_user", config=config)
        
        # Record some memories first
        local_impl.record(message="Memory A")
        local_impl.record(message="Memory B")
        
        results = local_impl.retrieve(query="test", limit=10)
        
        assert len(results) >= 2
        assert any(r["memory"] == "Memory A" for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
