"""Mem0 long-term memory service implementation compatible with AgentScope MemoryBase."""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from loguru import logger
import json

try:
    from agentscope.memory import MemoryBase
except ImportError:
    # Fallback if agentscope not installed
    class MemoryBase:
        """Stub base class for when agentscope is not available"""
        def __init__(self, config: Any):
            self.config = config


class Mem0Config:
    """Mem0 configuration loaded from environment variables"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        user_id_field: str = "user_id",
        max_entries: int = 10000,
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_dimension: int = 384,
        use_cloud_api: bool = True,
    ):
        self.api_key = api_key or ""
        self.user_id_field = user_id_field
        self.max_entries = max_entries
        self.embedding_model = embedding_model
        self.vector_dimension = vector_dimension
        self.use_cloud_api = use_cloud_api
    
    @classmethod
    def from_settings(cls) -> 'Mem0Config':
        """Load configuration from settings (when available)"""
        try:
            from app.config import settings
            
            return cls(
                api_key=getattr(settings, 'MEM0_API_KEY', ''),
                max_entries=getattr(settings, 'MEM0_MAX_ENTRIES', 10000),
                use_cloud_api=getattr(settings, 'MEM0_USE_CLOUD_API', True),
            )
        except ImportError:
            # Return default config if settings not available
            return cls()


class LocalMem0Impl:
    """Local Mem0 implementation (in-memory storage for testing/fallback)."""
    
    def __init__(self, user_id: str, config: Mem0Config):
        self.user_id = user_id
        self.config = config
        self._store: Dict[str, List[Dict]] = {}
    
    def record(self, message: str, metadata: Optional[Dict] = None) -> bool:
        """Store a memory entry in local storage."""
        try:
            memory_entry = {
                "memory_id": f"mem_{len(self._store.get(self.user_id, []))+1}",
                "content": message,
                "metadata": metadata or {},
                "created_at": "2026-09-21T10:00:00Z",
            }
            
            if self.user_id not in self._store:
                self._store[self.user_id] = []
            
            self._store[self.user_id].append(memory_entry)
            logger.debug(f"LocalMem0 recorded memory: user={self.user_id}, total_entries={len(self._store[self.user_id])}")
            return True
        
        except Exception as e:
            logger.error(f"LocalMem0 record failed: {type(e).__name__}: {e}")
            return False
    
    def retrieve(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories from local storage (simple keyword matching)."""
        if self.user_id not in self._store:
            return []
        
        try:
            # Simple keyword-based retrieval (in production, use semantic search)
            query_lower = query.lower()
            results = []
            
            for memory in self._store[self.user_id]:
                content_lower = memory["content"].lower()
                # Basic keyword match
                if any(word in content_lower for word in query_lower.split()):
                    results.append({
                        "memory": memory["content"],
                        "confidence": 0.85,  # Default confidence for local storage
                        "metadata": memory["metadata"],
                    })
                
                # If no matches, return all up to limit
                if len(results) >= limit:
                    break
            
            # If no keyword matches, return recent ones
            if not results and self._store[self.user_id]:
                recent = self._store[self.user_id][-limit:]
                results = [
                    {
                        "memory": m["content"],
                        "confidence": 0.7,
                        "metadata": m["metadata"],
                    }
                    for m in recent
                ]
            
            logger.debug(f"LocalMem0 retrieved {len(results)} memories for query: {query}")
            return results
        
        except Exception as e:
            logger.error(f"LocalMem0 retrieve failed: {type(e).__name__}: {e}")
            return []
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if self.user_id not in self._store:
            return False
        
        try:
            original_len = len(self._store[self.user_id])
            self._store[self.user_id] = [
                m for m in self._store[self.user_id] 
                if m["memory_id"] != memory_id
            ]
            
            deleted = len(self._store[self.user_id]) < original_len
            if deleted:
                logger.debug(f"LocalMem0 deleted memory: {memory_id}")
            
            return deleted
        
        except Exception as e:
            logger.error(f"LocalMem0 delete failed: {type(e).__name__}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        count = len(self._store.get(self.user_id, []))
        return {
            "total_memories": count,
            "storage_used_mb": round(count * 0.001, 3),  # Estimate 1KB per memory
        }


class Mem0Service(MemoryBase):
    """Mem0 long-term memory service (compatible with AgentScope MemoryBase interface)."""
    
    def __init__(
        self,
        config: Mem0Config,
        user_id: Optional[str] = None,
    ):
        super().__init__(config)
        self.user_id = user_id
        self.config = config
        self._client = self._init_mem0_client()
    
    def _init_mem0_client(self) -> Any:
        """Initialize Mem0 client (cloud API or local fallback)."""
        if self.config.use_cloud_api and self.config.api_key:
            try:
                from mem0 import MemoryClient
                
                client = MemoryClient(api_key=self.config.api_key)
                logger.info(
                    f"Mem0 cloud client initialized successfully, user_id={self.user_id}"
                )
                return client
            
            except ImportError:
                logger.warning(
                    "mem0 package not installed, falling back to local implementation"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Mem0 cloud client: {e}, using local fallback"
                )
        
        # Fallback to local implementation
        logger.info("Using LocalMem0Impl as fallback")
        return LocalMem0Impl(user_id=self.user_id or "anonymous", config=self.config)
    
    def record(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record a memory entry.
        
        Args:
            message: The memory content to store
            metadata: Optional metadata dictionary (source, timestamp, etc.)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.user_id:
            logger.warning("User ID is empty, skipping memory recording")
            return False
        
        try:
            data = {
                "user_id": self.user_id,
                "message": message,
                "metadata": metadata or {},
            }
            
            result = self._client.add(**data) if hasattr(self._client, 'add') else \
                     self._client.record(message, metadata)
            
            logger.debug(
                f"Mem0Service recorded memory: user={self.user_id}, "
                f"result={result}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Mem0Service record failed: {type(e).__name__}: {e}")
            return False
    
    def retrieve(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories via semantic search.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
        
        Returns:
            List of matching memories with confidence scores
        """
        if not self.user_id:
            logger.warning("User ID is empty, returning empty results")
            return []
        
        try:
            results = (
                self._client.search(
                    query=query,
                    user_id=self.user_id,
                    limit=limit,
                )
                if hasattr(self._client, 'search')
                else self._client.retrieve(query, limit=limit)
            )
            
            # Normalize response format
            if isinstance(results, list):
                formatted_results = []
                for item in results[:limit]:
                    if isinstance(item, dict):
                        formatted_results.append({
                            "memory": item.get("memory", item.get("content", "")),
                            "confidence": item.get("confidence", 0.0),
                            "metadata": item.get("metadata", {}),
                        })
                    else:
                        formatted_results.append({
                            "memory": str(item),
                            "confidence": 0.0,
                            "metadata": {},
                        })
                
                return formatted_results
            
            logger.debug(f"Mem0Service retrieved {len(results)} memories")
            return results if isinstance(results, list) else []
        
        except Exception as e:
            logger.error(f"Mem0Service retrieve failed: {type(e).__name__}: {e}")
            return []
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: The memory ID to delete
        
        Returns:
            bool: True if deleted successfully
        """
        if not self.user_id:
            logger.warning("User ID is empty, deletion failed")
            return False
        
        try:
            result = (
                self._client.delete(memory_id=memory_id)
                if hasattr(self._client, 'delete')
                else self._client.delete(memory_id=memory_id)
            )
            
            logger.debug(f"Mem0Service deleted memory: {memory_id}")
            return True
        
        except Exception as e:
            logger.error(f"Mem0Service delete failed: {type(e).__name__}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory storage statistics.
        
        Returns:
            Dictionary containing memory statistics
        """
        try:
            if hasattr(self._client, 'stats'):
                stats = self._client.stats()
            elif hasattr(self._client, 'get_usage'):
                stats = self._client.get_usage()
            else:
                stats = self._client.get_stats() if hasattr(self._client, 'get_stats') else {}
            
            return stats if isinstance(stats, dict) else {"error": "Invalid stats format"}
        
        except Exception as e:
            logger.error(f"Mem0Service get_stats failed: {type(e).__name__}: {e}")
            return {"total_memories": 0, "error": str(e)}
    
    def clear(self) -> bool:
        """Clear all memories for this user."""
        if not self.user_id:
            return False
        
        try:
            # Use the appropriate method based on client type
            if hasattr(self._client, 'clear'):
                self._client.clear()
            elif isinstance(self._client, LocalMem0Impl):
                self._client._store[self.user_id] = []
            
            logger.info(f"Mem0Service cleared all memories for user: {self.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Mem0Service clear failed: {type(e).__name__}: {e}")
            return False
