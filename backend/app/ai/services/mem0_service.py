"""Mem0 long-term memory service implementation compatible with AgentScope MemoryBase."""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
from loguru import logger
import json
import httpx
from urllib.parse import urljoin

try:
    from agentscope.memory import MemoryBase
except ImportError:
    # Fallback if agentscope not installed
    class MemoryBase:
        """Stub base class for when agentscope is not available"""
        def __init__(self, config: Any):
            self.config = config


class Mem0Config:
    """Mem0 configuration loaded from environment variables - Enhanced for local deployment"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rag_url: str = "",
        user_id_field: str = "user_id",
        max_entries: int = 10000,
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_dimension: int = 384,
        use_cloud_api: bool = False,
        enabled: bool = True,
        retention_days: int = 90,
    ):
        self.api_key = api_key or ""
        self.rag_url = rag_url.strip("/") if rag_url else ""
        self.user_id_field = user_id_field
        self.max_entries = max_entries
        self.embedding_model = embedding_model
        self.vector_dimension = vector_dimension
        self.use_cloud_api = use_cloud_api
        self.enabled = enabled
        self.retention_days = retention_days
    
    @classmethod
    def from_settings(cls) -> 'Mem0Config':
        """Load configuration from settings (when available)"""
        try:
            from app.config import settings
            
            return cls(
                api_key=getattr(settings, 'MEM0_API_KEY', ''),
                rag_url=getattr(settings, 'MEM0_RAG_URL', ''),
                max_entries=getattr(settings, 'MEM0_MAX_ENTRIES', 10000),
                use_cloud_api=getattr(settings, 'MEM0_USE_CLOUD_API', False),
                enabled=getattr(settings, 'MEM0_ENABLED', False),
                retention_days=getattr(settings, 'MEM0_RETENTION_DAYS', 90),
            )
        except ImportError:
            # Return default config if settings not available
            return cls()
    
    @property
    def is_local_deployment(self) -> bool:
        """判断是否为本地私有化部署模式"""
        return not self.use_cloud_api and bool(self.rag_url)



class LocalMem0APIImpl:
    """本地 Mem0 API 客户端实现（私有化部署模式）"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http_client: Optional[httpx.Client] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（包含认证信息）"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _request(self, method: str, endpoint: str, json_data: Optional[Dict] = None, 
                 params: Optional[Dict] = None) -> httpx.Response:
        """发送 HTTP 请求到 Mem0 API"""
        url = urljoin(self.base_url, endpoint)
        
        try:
            with httpx.Client(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True
            ) as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    json=json_data,
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response
        
        except httpx.HTTPError as e:
            logger.error(f"Mem0 API request failed ({method} {endpoint}): {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Mem0 API unexpected error ({method} {endpoint}): {type(e).__name__}: {e}")
            raise
    
    def add(self, user_id: str, message: str, metadata: Optional[Dict] = None) -> Union[Dict, bool]:
        """添加记忆条目"""
        try:
            payload = {
                "user_id": user_id,
                "message": message,
                "metadata": metadata or {}
            }
            
            response = self._request("POST", "/memories", json_data=payload)
            result = response.json()
            
            logger.debug(f"Mem0API added memory: user={user_id}, result={result}")
            return result or True
        
        except Exception as e:
            logger.error(f"Mem0API.add failed: {type(e).__name__}: {e}")
            return False
    
    def search(self, query: str, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        try:
            payload = {
                "query": query,
                "user_id": user_id,
                "limit": limit
            }
            
            response = self._request("POST", "/search", json_data=payload)
            results = response.json()
            
            # Normalize response format
            if isinstance(results, list):
                formatted_results = []
                for item in results[:limit]:
                    if isinstance(item, dict):
                        formatted_results.append({
                            "memory": item.get("memory", item.get("content", "")),
                            "confidence": item.get("confidence", item.get("score", 0.0)),
                            "metadata": item.get("metadata", {}),
                        })
                    else:
                        formatted_results.append({
                            "memory": str(item),
                            "confidence": 0.0,
                            "metadata": {},
                        })
                
                return formatted_results
            
            logger.warning(f"Unexpected Mem0 API search response format: {type(results)}")
            return []
        
        except Exception as e:
            logger.error(f"Mem0API.search failed: {type(e).__name__}: {e}")
            return []
    
    def delete(self, memory_id: str, user_id: Optional[str] = None) -> bool:
        """删除记忆"""
        try:
            payload = {"memory_id": memory_id}
            if user_id:
                payload["user_id"] = user_id
            
            response = self._request("DELETE", "/memories", json_data=payload)
            result = response.json()
            
            logger.debug(f"Mem0API.deleted memory: {memory_id}, result={result}")
            return True
        
        except Exception as e:
            logger.error(f"Mem0API.delete failed: {type(e).__name__}: {e}")
            return False
    
    def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            params = {"user_id": user_id} if user_id else None
            response = self._request("GET", "/memories/stats", params=params)
            stats = response.json()
            return stats if isinstance(stats, dict) else {}
        
        except Exception as e:
            logger.error(f"Mem0API.get_stats failed: {type(e).__name__}: {e}")
            return {"total_memories": 0, "error": str(e)}
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = self._request("GET", "/health")
            health_data = response.json()
            is_healthy = health_data.get("status", health_data.get("healthy", False))
            
            logger.info(f"Mem0 API health check: {'healthy' if is_healthy else 'unhealthy'}")
            return is_healthy
        
        except Exception as e:
            logger.error(f"Mem0 API health check failed: {type(e).__name__}: {e}")
            return False
    
    def compress_memories(self, user_id: str, token_limit: int = 10000) -> bool:
        """压缩记忆（如果该接口存在）"""
        try:
            payload = {
                "user_id": user_id,
                "token_limit": token_limit
            }
            
            response = self._request("POST", "/memories/compress", json_data=payload)
            result = response.json()
            
            logger.info(f"Mem0 API compressed memories for user={user_id}, tokens={token_limit}")
            return True
        
        except httpx.HTTPError as e:
            # 404 表示不支持压缩功能
            if e.response.status_code == 404:
                logger.warning("Mem0 API compression endpoint not found (not supported)")
                return False
            logger.error(f"Mem0API.compress_memories failed: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            logger.error(f"Mem0API.compress_memories failed: {type(e).__name__}: {e}")
            return False


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
        self._health_checked = False
    
    def _init_mem0_client(self) -> Any:
        """Initialize Mem0 client (cloud API or local deployment)."""
        
        # Check if Mem0 is enabled in configuration
        if not self.config.enabled:
            logger.warning("Mem0 service is disabled via MEM0_ENABLED=false, using local fallback")
            return LocalMem0Impl(user_id=self.user_id or "anonymous", config=self.config)
        
        # Priority order: 
        # 1. Local private deployment (has RAG URL and cloud API disabled)
        # 2. Cloud API (has API key and use_cloud_api=true)
        # 3. Local fallback
        if self.config.is_local_deployment:
            return self._init_local_deployment_client()
        
        if self.config.use_cloud_api and self.config.api_key:
            return self._init_cloud_client()
        
        # Fallback to local implementation
        logger.info("No valid Mem0 configuration found, using LocalMem0Impl as fallback")
        return LocalMem0Impl(user_id=self.user_id or "anonymous", config=self.config)
    
    def _init_local_deployment_client(self) -> LocalMem0APIImpl:
        """初始化本地私有化部署客户端"""
        try:
            logger.info(
                f"Initializing Mem0 local deployment client: "
                f"url={self.config.rag_url}, key={'***' if self.config.api_key else 'none'}"
            )
            
            client = LocalMem0APIImpl(
                base_url=self.config.rag_url,
                api_key=self.config.api_key
            )
            
            # Perform health check after initialization
            if client.health_check():
                self._health_checked = True
                logger.info(f"Mem0 local deployment client initialized successfully, user_id={self.user_id}")
            else:
                logger.warning("Mem0 local deployment health check failed, will retry on next operation")
            
            return client
        
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 local deployment client: {e}")
            raise
    
    def _init_cloud_client(self) -> Any:
        """初始化云端 API 客户端"""
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
            raise
        except Exception as e:
            logger.warning(
                f"Failed to initialize Mem0 cloud client: {e}, using local fallback"
            )
            raise
    
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
            # Check health before first operation
            if not self._health_checked and isinstance(self._client, LocalMem0APIImpl):
                if not self._client.health_check():
                    logger.error("Mem0 API health check failed during record operation")
                    return False
            
            result = self._client.add(
                user_id=self.user_id,
                message=message,
                metadata=metadata or {}
            )
            
            logger.debug(
                f"Mem0Service recorded memory: user={self.user_id}, "
                f"result={result}"
            )
            return bool(result)
        
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
            # Check health before first operation
            if not self._health_checked and isinstance(self._client, LocalMem0APIImpl):
                if not self._client.health_check():
                    logger.error("Mem0 API health check failed during retrieve operation")
                    return []
            
            results = self._client.search(
                query=query,
                user_id=self.user_id,
                limit=limit
            )
            
            logger.debug(f"Mem0Service retrieved {len(results)} memories")
            return results
        
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
            result = self._client.delete(
                memory_id=memory_id,
                user_id=self.user_id
            )
            
            logger.debug(f"Mem0Service deleted memory: {memory_id}")
            return bool(result)
        
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
            if isinstance(self._client, LocalMem0APIImpl):
                stats = self._client.get_stats(user_id=self.user_id)
            elif hasattr(self._client, 'stats'):
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
            if isinstance(self._client, LocalMem0APIImpl):
                # For local API implementation, we might need a different endpoint
                logger.warning("Mem0 API clear operation requires custom endpoint")
                # Currently, there's no standard clear endpoint in Mem0 API
                # This is a placeholder for future implementation
                return False
            elif isinstance(self._client, LocalMem0Impl):
                self._client._store[self.user_id] = []
            elif hasattr(self._client, 'clear'):
                self._client.clear()
            
            logger.info(f"Mem0Service cleared all memories for user: {self.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Mem0Service clear failed: {type(e).__name__}: {e}")
            return False
    
    def compress_memories(self) -> bool:
        """Compress memories to reduce token usage (if supported by Mem0 API)."""
        if not self.user_id:
            logger.warning("User ID is empty, skipping memory compression")
            return False
        
        try:
            # Check if compression is enabled
            if not getattr(self.config, 'enable_compression', False):
                logger.info("Memory compression is disabled via configuration")
                return False
            
            # Try compression if available
            if isinstance(self._client, LocalMem0APIImpl):
                token_limit = getattr(self.config, 'completion_token_limit', 10000)
                return self._client.compress_memories(
                    user_id=self.user_id,
                    token_limit=token_limit
                )
            
            logger.info("Memory compression is not supported with cloud API")
            return True
        
        except Exception as e:
            logger.error(f"Mem0Service compress_memories failed: {type(e).__name__}: {e}")
            return False
