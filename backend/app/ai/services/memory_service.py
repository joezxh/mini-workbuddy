# -*- coding: utf-8 -*-
"""LongTermMemoryService - 长期记忆服务占位

当前版本使用 InMemory 存储（单进程有效，重启丢失）。
未来升级路径：
1. SQLite FTS5 全文检索（轻量，无外部依赖）
2. pgvector 向量检索（与 Dify 共用 pgvector 实例）
3. Redis + BloomFilter（高频场景）

接口设计参考 AgentScope 2.0 LongTermMemoryBase。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger
import threading


class MemoryEntry:
    """单条记忆条目"""

    def __init__(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
    ):
        self.key = key
        self.content = content
        self.metadata = metadata or {}
        self.tags = tags or []
        self.created_at = created_at or datetime.utcnow()
        self.access_count = 0
        self.last_accessed: Optional[datetime] = None

    def access(self) -> None:
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class LongTermMemoryService:
    """长期记忆服务（InMemory 实现）"""

    def __init__(self, max_entries: int = 10000):
        self._store: Dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()
        self._max_entries = max_entries

    def record(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """写入一条记忆"""
        with self._lock:
            if key in self._store:
                entry = self._store[key]
                entry.content = content
                entry.metadata = metadata or entry.metadata
                entry.tags = tags or entry.tags
                entry.access()
                return True

            if len(self._store) >= self._max_entries:
                self._evict_lru()

            self._store[key] = MemoryEntry(key, content, metadata, tags)
            logger.debug("Memory recorded: key=" + key)
            return True

    def retrieve(
        self,
        key: str,
    ) -> Optional[MemoryEntry]:
        """按 key 检索记忆"""
        with self._lock:
            entry = self._store.get(key)
            if entry:
                entry.access()
            return entry

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """关键词全文搜索（简单 substring match）"""
        results = []
        query_lower = query.lower()
        with self._lock:
            for entry in self._store.values():
                if query_lower in entry.content.lower():
                    entry.access()
                    results.append(entry)
        results.sort(key=lambda e: (e.access_count, e.created_at), reverse=True)
        return results[:limit]

    def delete(self, key: str) -> bool:
        """删除记忆"""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def list_keys(self, tag: Optional[str] = None) -> List[str]:
        """列出所有 key（可选 tag 过滤）"""
        with self._lock:
            if tag:
                return [e.key for e in self._store.values() if tag in e.tags]
            return list(self._store.keys())

    def count(self) -> int:
        """记忆总数"""
        with self._lock:
            return len(self._store)

    def clear(self) -> int:
        """清空所有记忆"""
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    def _evict_lru(self) -> None:
        """Evict least recently used entry when capacity reached"""
        if not self._store:
            return
        lru_key = min(
            self._store.values(),
            key=lambda e: (e.last_accessed or e.created_at, e.access_count)
        ).key
        del self._store[lru_key]
        logger.debug("Evicted LRU entry: key=" + lru_key)

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        with self._lock:
            if not self._store:
                return {"total": 0, "max_entries": self._max_entries}
            total_access = sum(e.access_count for e in self._store.values())
            tags: set = set()
            for e in self._store.values():
                tags.update(e.tags)
            return {
                "total": len(self._store),
                "max_entries": self._max_entries,
                "total_access_count": total_access,
                "unique_tags": len(tags),
                "oldest": min(e.created_at for e in self._store.values()).isoformat(),
                "newest": max(e.created_at for e in self._store.values()).isoformat(),
            }


# 全局单例
_memory_service: Optional[LongTermMemoryService] = None
_memory_lock = threading.Lock()


def get_memory_service() -> LongTermMemoryService:
    """获取全局长期记忆服务单例"""
    global _memory_service
    with _memory_lock:
        if _memory_service is None:
            _memory_service = LongTermMemoryService()
        return _memory_service
