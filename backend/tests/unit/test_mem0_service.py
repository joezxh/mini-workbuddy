"""Unit tests for Mem0Service - Mem0 long-term memory implementation."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.ai.services.mem0_service import Mem0Service, Mem0Config


class TestMem0ServiceRecord:
    """Test record method"""
    
    @patch('app.ai.services.mem0_service.MemoryClient')
    def test_record_success(self, mock_client_class):
        """Successful memory recording"""
        from mem0 import Memory
        mock_client = Mock()
        mock_client.add.return_value = {"total": 100}
        mock_client_class.return_value = mock_client
        
        service = Mem0Service(config=Mem0Config(), user_id="123")
        
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
    
    @patch('app.ai.services.mem0_service.LocalMem0Impl', autospec=True)
    def test_record_fallback_to_local(self, mock_local_impl_class):
        """Should fall back to local implementation when mem0 not available"""
        from mem0 import Memory as MockMemory
        # Force ImportError-like behavior by making MemoryClient unavailable
        import sys
        from unittest.mock import Mock
        
        mock_local = Mock()
        mock_local.record.return_value = True
        mock_local_impl_class.return_value = mock_local
        
        service = Mem0Service(config=Mem0Config(), user_id="456")
        
        # LocalMem0Impl should be initialized
        assert service._client is not None


class TestMem0ServiceRetrieve:
    """Test retrieve method"""
    
    @patch('app.ai.services.mem0_service.LocalMem0Impl', autospec=True)
    def test_retrieve_success(self, mock_local_impl_class):
        """Successful semantic search"""
        mock_local = Mock()
        mock_local.retrieve.return_value = [
            {"memory": "User prefers short answers", "confidence": 0.92},
            {"memory": "User works at tech company", "confidence": 0.87},
        ]
        mock_local_impl_class.return_value = mock_local
        
        service = Mem0Service(config=Mem0Config(), user_id="789")
        
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
    @patch('app.ai.services.mem0_service.LocalMem0Impl', autospec=True)
    def test_retrieve_on_error(self, mock_local_impl_class):
        """Should return empty list on error"""
        mock_local = Mock()
        mock_local.retrieve.side_effect = Exception("API error")
        mock_local_impl_class.return_value = mock_local
        
        service = Mem0Service(config=Mem0Config(), user_id="error_test")
        
        results = service.retrieve(query="test query")
        
        assert results == []


class TestMem0ServiceDelete:
    """Test delete method"""
    
    @patch('app.ai.services.mem0_service.LocalMem0Impl', autospec=True)
    def test_delete_success(self, mock_local_impl_class):
        """Successful memory deletion"""
        mock_local = Mock()
        mock_local.delete.return_value = {"status": "success"}
        mock_local_impl_class.return_value = mock_local
        
        service = Mem0Service(config=Mem0Config(), user_id="delete_user")
        
        result = service.delete(memory_id="mem_123")
        
        assert result is True
        mock_local.delete.assert_called_once_with(memory_id="mem_123")
    
    def test_delete_without_user_id(self):
        """Should fail without user_id"""
        config = Mem0Config()
        service = Mem0Service(config=config)
        
        result = service.delete(memory_id="any_id")
        
        assert result is False


class TestMem0ServiceStats:
    """Test get_stats method"""
    
    @patch('app.ai.services.mem0_service.LocalMem0Impl', autospec=True)
    def test_get_stats_success(self, mock_local_impl_class):
        """Get memory statistics"""
        mock_local = Mock()
        mock_local.get_stats.return_value = {
            "total_memories": 150,
            "storage_used_mb": 12.5,
        }
        mock_local_impl_class.return_value = mock_local
        
        service = Mem0Service(config=Mem0Config(), user_id="stats_user")
        
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
