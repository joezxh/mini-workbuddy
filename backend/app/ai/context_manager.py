"""Multi-layer context manager for AgentScope multi-mode session architecture.

三层架构设计:
1. Shared Layer (共享层): user_id/workspace_id/model_id 跨模式共享
2. Isolated Layer (隔离层): mode-specific 会话历史独立存储  
3. Sync Layer (同步层): Mem0 长期记忆跨模式知识注入
"""
from __future__ import annotations
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import json


@dataclass
class SharedContextEntry:
    """Shared layer context entry"""
    key: str
    data: Dict[str, Any]
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "data": self.data,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }


@dataclass
class IsolatedContextEntry:
    """Isolated layer context entry (mode-specific)"""
    key: str
    data: Dict[str, Any]
    priority: int = 5  # 1-10, low number = high priority
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "data": self.data,
            "priority": self.priority,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at


@dataclass 
class TokenBudget:
    """Token budget tracker"""
    max_tokens: int
    current_usage: int = 0
    overhead_per_entry: int = 50  # Estimation for metadata/keys
    
    def remaining(self) -> int:
        return self.max_tokens - self.current_usage
    
    def estimate_entry_tokens(self, data: Dict[str, Any]) -> int:
        """Estimate token count for an entry"""
        text = json.dumps(data, ensure_ascii=False)
        return len(text.split()) + self.overhead_per_entry
    
    def can_fit(self, data: Dict[str, Any]) -> bool:
        """Check if data fits within budget"""
        estimated = self.estimate_entry_tokens(data)
        return self.remaining() >= estimated
    
    def add(self, data: Dict[str, Any]):
        """Add entry and update budget"""
        tokens = self.estimate_entry_tokens(data)
        self.current_usage += tokens


class ContextManager:
    """
    Multi-layer context manager for AI agent sessions.
    
    Architecture:
    - Shared Layer: Cross-mode shared state (user preferences, workspace info)
    - Isolated Layer: Mode-specific conversations (Dify/SQIBot/AgentScope)
    - Sync Layer: Mem0 long-term memory integration
    """
    
    def __init__(
        self,
        tenant_id: int,
        user_id: Optional[str] = None,
        model_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.model_id = model_id
        self.workspace_id = workspace_id
        
        # Shared layer storage
        self._shared_context: Dict[str, SharedContextEntry] = {}
        
        # Isolated layer storage: {(mode, key): [entries]}
        self._isolated_contexts: Dict[tuple, List[IsolatedContextEntry]] = {}
        
        # Mem0 service integration (lazy-loaded)
        self._mem0_service = None
        
        # Tenant isolation enforcement
        self._tenant_bound = True
    
    def _ensure_tenant_isolation(self):
        """Ensure all operations respect tenant boundaries"""
        if not self._tenant_bound:
            raise RuntimeError("Tenant isolation violation detected")
    
    def set_shared_context(
        self,
        key: str,
        data: Dict[str, Any],
    ) -> bool:
        """
        Set value in shared context layer.
        
        Examples:
        - User preferences
        - Workspace configuration
        - Common knowledge base references
        """
        try:
            self._ensure_tenant_isolation()
            
            entry = SharedContextEntry(
                key=key,
                data=data,
                access_count=1,
                last_accessed=datetime.now(),
            )
            
            self._shared_context[key] = entry
            logger.debug(f"Shared context updated: {key}, total_entries={len(self._shared_context)}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set shared context: {type(e).__name__}: {e}")
            return False
    
    def get_shared_context(
        self,
        key: str,
        include_metadata: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve value from shared context layer.
        
        Args:
            key: Context key to retrieve
            include_metadata: Include access stats in response
        
        Returns:
            Data dict or None if not found
        """
        try:
            self._ensure_tenant_isolation()
            
            entry = self._shared_context.get(key)
            if not entry:
                return None
            
            # Update access tracking
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            result = entry.data.copy()
            
            if include_metadata:
                result["_metadata"] = {
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed.isoformat(),
                }
            
            logger.debug(f"Retrieved shared context: {key}, accesses={entry.access_count}")
            return result
        
        except Exception as e:
            logger.error(f"Failed to get shared context: {type(e).__name__}: {e}")
            return None
    
    def store_isolated_context(
        self,
        mode: str,
        key: str,
        data: Dict[str, Any],
        max_tokens: int = 16000,
        ttl_hours: Optional[int] = None,
        priority: int = 5,
    ) -> bool:
        """
        Store data in isolated context layer (mode-specific).
        
        Examples:
        - Dify conversation history
        - SQLBot query logs
        - AgentScope context memory
        
        Args:
            mode: Mode identifier ("dify", "sqlbot", "agentscope", etc.)
            key: Entry key within mode
            data: Context data to store
            max_tokens: Token budget limit
            ttl_hours: Time-to-live in hours (optional)
            priority: Entry priority (1=highest, 10=lowest)
        """
        try:
            self._ensure_tenant_isolation()
            
            # Create entry with optional TTL
            entry = IsolatedContextEntry(
                key=key,
                data=data,
                priority=priority,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                expires_at=(
                    datetime.now() + timedelta(hours=ttl_hours)
                    if ttl_hours
                    else None
                ),
            )
            
            # Initialize mode bucket if needed
            mode_key = (mode, key)
            if mode_key not in self._isolated_contexts:
                self._isolated_contexts[mode_key] = []
            
            # Check for expiration and clean up old entries
            self._isolated_contexts[mode_key] = [
                e for e in self._isolated_contexts[mode_key] 
                if not e.is_expired
            ]
            
            # Add new entry
            self._isolated_contexts[mode_key].append(entry)
            
            logger.debug(
                f"Isolated context stored: mode={mode}, key={key}, "
                f"total_entries={len(self._isolated_contexts[mode_key])}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Failed to store isolated context: {type(e).__name__}: {e}")
            return False
    
    def get_isolated_context(
        self,
        mode: str,
        key: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent entries from isolated context layer.
        
        Args:
            mode: Mode identifier
            key: Entry key
            limit: Maximum number of entries to return
        
        Returns:
            List of context entries (most recent first)
        """
        try:
            self._ensure_tenant_isolation()
            
            mode_key = (mode, key)
            entries = self._isolated_contexts.get(mode_key, [])
            
            # Filter expired entries and sort by recency
            active_entries = [e for e in entries if not e.is_expired]
            sorted_entries = sorted(
                active_entries,
                key=lambda e: e.last_accessed,
                reverse=True
            )[:limit]
            
            # Update access counts
            for entry in sorted_entries:
                entry.access_count += 1
                entry.last_accessed = datetime.now()
            
            results = [entry.to_dict() for entry in sorted_entries]
            
            logger.debug(f"Retrieved {len(results)} entries from {mode}:{key}")
            return results
        
        except Exception as e:
            logger.error(f"Failed to get isolated context: {type(e).__name__}: {e}")
            return []
    
    def build_full_context(
        self,
        max_tokens: int = 16000,
        enable_mem0_retrieval: bool = False,
        mem0_limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Build complete context from all layers with token budget control.
        
        This method orchestrates the three-layer architecture:
        1. Collect shared context (always included)
        2. Collect isolated contexts (prioritized by mode relevance)
        3. Retrieve relevant memories from Mem0 (if enabled)
        4. Compress/truncate to fit within max_tokens budget
        
        Returns:
            Complete context dict ready for LLM prompt construction
        """
        try:
            budget = TokenBudget(max_tokens=max_tokens)
            
            # Layer 1: Shared context (highest priority - always include)
            shared_data = {}
            for key, entry in self._shared_context.items():
                if budget.can_fit(entry.data):
                    shared_data[key] = entry.data
                    budget.add(entry.data)
                else:
                    logger.warning(f"Truncating shared context: {key} doesn't fit budget")
            
            # Layer 2: Isolated contexts (prioritize by access frequency)
            isolated_data: Dict[str, Dict[str, Any]] = {}
            
            # Sort modes by activity (most accessed first)
            sorted_modes = sorted(
                self._isolated_contexts.keys(),
                key=lambda mk: sum(
                    e.access_count for e in self._isolated_contexts[mk]
                ),
                reverse=True
            )
            
            for mode_key in sorted_modes[:3]:  # Top 3 most active modes
                mode, key = mode_key
                entries = self.get_isolated_context(mode, key, limit=5)
                
                if mode not in isolated_data:
                    isolated_data[mode] = {}
                
                for entry in entries[:2]:  # Limit per mode
                    entry_data = {"key": key, "data": entry["data"]}
                    if budget.can_fit(entry_data):
                        isolated_data[mode][key] = entry_data
                        budget.add(entry_data)
                    else:
                        break
            
            # Layer 3: Mem0 long-term memory retrieval (if enabled)
            mem0_summary = ""
            if enable_mem0_retrieval and self.user_id:
                try:
                    mem0_data = self._retrieve_mem0_memories(limit=mem0_limit)
                    
                    if mem0_data:
                        # Summarize Mem0 results for prompt injection
                        summary_lines = [
                            f"[Long-term Memory #{i+1}] {item['memory']} (confidence: {item.get('confidence', 0):.2f})"
                            for item in mem0_data[:3]
                        ]
                        mem0_summary = "\n".join(summary_lines)
                        
                        # Count tokens for Mem0 data
                        budget.add({"mem0_summary": mem0_summary})
                        
                        logger.info(
                            f"Injected {len(mem0_data)} memories from long-term storage"
                        )
                
                except Exception as e:
                    logger.warning(f"Mem0 retrieval failed: {type(e).__name__}: {e}")
            
            total_tokens = budget.current_usage
            
            return {
                "shared": shared_data,
                "isolated": isolated_data,
                "mem0_summary": mem0_summary,
                "total_tokens": total_tokens,
                "budget_remaining": budget.remaining(),
            }
        
        except Exception as e:
            logger.error(f"Failed to build full context: {type(e).__name__}: {e}")
            return {
                "shared": {},
                "isolated": {},
                "mem0_summary": "",
                "total_tokens": 0,
                "error": str(e),
            }
    
    def _retrieve_mem0_memories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant memories from Mem0 long-term storage."""
        if not self.user_id:
            logger.warning("Cannot retrieve Mem0 memories without user_id")
            return []
        
        # Lazy-load Mem0 service
        if self._mem0_service is None:
            try:
                from app.ai.services.mem0_service import Mem0Service, Mem0Config
                
                config = Mem0Config.from_settings()
                self._mem0_service = Mem0Service(config=config, user_id=self.user_id)
                
            except ImportError as e:
                logger.error(f"Failed to import Mem0Service: {e}")
                return []
            except Exception as e:
                logger.error(f"Failed to initialize Mem0 service: {e}")
                return []
        
        # Construct Mem0 query based on session context
        query_parts = []
        
        # Add shared context keywords
        if self._shared_context:
            prefs = self._shared_context.get("preferences", {})
            if prefs:
                query_parts.extend(str(prefs).split())
        
        # Add mode-specific context hints
        if self.model_id:
            query_parts.append(self.model_id)
        
        query = " ".join(query_parts) if query_parts else "user general preferences"
        
        # Execute Mem0 retrieval
        try:
            results = self._mem0_service.retrieve(
                query=query,
                limit=limit,
            )
            
            logger.info(
                f"Mem0 retrieved {len(results)} memories for query: '{query}'"
            )
            return results if isinstance(results, list) else []
        
        except Exception as e:
            logger.error(f"Mem0 retrieval failed: {type(e).__name__}: {e}")
            return []
    
    def record_to_mem0(
        self,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record session summary to Mem0 long-term memory.
        
        Use this method after completing significant session milestones:
        - Session completion
        - Major decision point
        - User preference update
        """
        if not self.user_id:
            logger.warning("Cannot record to Mem0 without user_id")
            return False
        
        try:
            # Lazy-load Mem0 service
            if self._mem0_service is None:
                from app.ai.services.mem0_service import Mem0Service, Mem0Config
                
                config = Mem0Config.from_settings()
                self._mem0_service = Mem0Service(config=config, user_id=self.user_id)
            
            # Prepare metadata with session context
            entry_metadata = {
                "tenant_id": self.tenant_id,
                "model_id": self.model_id,
                "workspace_id": self.workspace_id,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {}),
            }
            
            result = self._mem0_service.record(
                message=message,
                metadata=entry_metadata,
            )
            
            if result:
                logger.info(f"Recorded to Mem0: {message[:50]}...")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to record to Mem0: {type(e).__name__}: {e}")
            return False
    
    def compact_context(
        self,
        mode: str,
        key: str,
        strategy: str = "priority_eviction",
        target_tokens: int = 8000,
    ) -> Dict[str, Any]:
        """
        Compact isolated context using specified strategy.
        
        Strategies:
        - priority_eviction: Remove lowest priority entries first
        - ttl_expiration: Remove expired entries immediately
        - access_based: Keep only recently accessed entries
        - summary_and_keep_latest: Summarize old, keep recent N
        
        Args:
            mode: Target mode
            key: Target key
            strategy: Compaction strategy to use
            target_tokens: Desired token count after compaction
            
        Returns:
            Compaction result metadata dict
        """
        try:
            mode_key = (mode, key)
            entries = self._isolated_contexts.get(mode_key, [])
            
            if not entries:
                return {
                    "success": False,
                    "reason": "No context found for this mode/key",
                    "entries_before": 0,
                    "entries_after": 0,
                }
            
            entries_before = len(entries)
            tokens_before = sum(self.estimate_entry_tokens(e.data) for e in entries)
            
            if strategy == "ttl_expiration":
                # Just remove expired entries (already done on each operation)
                self._isolated_contexts[mode_key] = [e for e in entries if not e.is_expired]
            
            elif strategy == "priority_eviction":
                # Sort by priority (ascending) and remove lowest priority
                sorted_entries = sorted(entries, key=lambda e: e.priority)
                self._isolated_contexts[mode_key] = sorted_entries[-5:]  # Keep top 5
            
            elif strategy == "access_based":
                # Keep only frequently accessed entries
                sorted_entries = sorted(entries, key=lambda e: e.access_count, reverse=True)
                self._isolated_contexts[mode_key] = sorted_entries[:3]  # Keep top 3
            
            elif strategy == "summary_and_keep_latest":
                # Keep last 5 entries, summarize the rest
                keep_count = 5
                recent_entries = entries[-keep_count:]
                old_entries = entries[:-keep_count]
                
                # Generate summary
                if old_entries:
                    summary_text = ContextManager._generate_compact_summary(old_entries)
                    summary_entry = IsolatedContextEntry(
                        key=f"{key}_summary_{datetime.now().strftime('%Y%m%d%H%M')}",
                        data={
                            "summary": summary_text,
                            "original_count": len(old_entries),
                            "summarized_at": datetime.now().isoformat(),
                        },
                        priority=1,  # High priority
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                    )
                    recent_entries = [summary_entry] + recent_entries
                
                self._isolated_contexts[mode_key] = recent_entries
            
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
            
            entries_after = len(self._isolated_contexts[mode_key])
            tokens_after = sum(self.estimate_entry_tokens(e.data) for e in self._isolated_contexts[mode_key])
            
            logger.info(f"Compacted {mode}:{key} using strategy={strategy}")
            
            return {
                "success": True,
                "mode": mode,
                "key": key,
                "strategy": strategy,
                "entries_before": entries_before,
                "entries_after": entries_after,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "compacted_at": datetime.now().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Failed to compact context: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": mode,
                "key": key,
                "strategy": strategy,
            }
    
    @staticmethod
    def _generate_compact_summary(entries: List[IsolatedContextEntry]) -> str:
        """Generate a text summary of multiple context entries"""
        if not entries:
            return ""
        
        # Extract key information from each entry
        summaries = []
        for entry in entries[:10]:  # Limit to avoid overflow
            if isinstance(entry.data, dict):
                content = entry.data.get("content") or entry.data.get("message") or str(entry.data)
                summaries.append(content[:200])  # Truncate long text
        
        if not summaries:
            return f"No meaningful content in {len(entries)} entries"
        
        return f"[Auto-summarized {len(entries)} entries]\n" + "\n".join(summaries) + "\n... (truncated)"
    
    @staticmethod
    def estimate_entry_tokens(data: Dict[str, Any]) -> int:
        """Estimate token count for a data entry"""
        text = json.dumps(data, ensure_ascii=False)
        return len(text.split()) + 30  # Base overhead
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context management statistics."""
        return {
            "tenant_id": self.tenant_id,
            "shared_context_count": len(self._shared_context),
            "isolated_context_count": len(self._isolated_contexts),
            "shared_context_keys": list(self._shared_context.keys()),
            "isolated_context_modes": list(set(mk[0] for mk in self._isolated_contexts.keys())),
        }

    # ── 跨模式上下文记忆(L2 + Mem0,PR-1 2026_09_27 新增)───────────────────────

    def persist_l2_context(
        self,
        session_id: int,
        source_mode: str,
        context_key: str,
        context_data: Dict[str, Any],
        priority: int = 5,
        ttl_hours: Optional[int] = None,
        is_cross_mode_accessible: bool = False,
        context_tags: Optional[List[str]] = None,
        case_number: Optional[str] = None,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> Optional[int]:
        """统一 L2 落库入口。失败静默,返回 record_id 或 None。

        Consumes: AIChatContextStorage 模型
        Produces: ai_context_storage 表新增记录 + 返回 id

        注意:本方法不依赖 self.db;若 db 入参为空则返回 None(便于单测 mock)。
        """
        if db is None:
            logger.debug(
                f"[L2] persist_l2_context skipped (no db): session={session_id} mode={source_mode}"
            )
            return None
        try:
            from datetime import datetime, timedelta
            from app.models.ai.ai_chat_context_storage import AIChatContextStorage

            row = AIChatContextStorage(
                tenant_id=tenant_id if tenant_id is not None else self.tenant_id,
                session_id=session_id,
                user_id=user_id if user_id is not None else 0,
                mode=source_mode,
                source_mode=source_mode,
                context_key=context_key,
                context_data=context_data,
                priority=priority,
                context_tags=context_tags or [],
                is_cross_mode_accessible=is_cross_mode_accessible,
                case_number=case_number,
                expires_at=(
                    (datetime.utcnow() + timedelta(hours=ttl_hours))
                    if ttl_hours else None
                ),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            logger.debug(
                f"[L2] persisted mode={source_mode} session={session_id} id={row.id}"
            )
            return row.id
        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning(
                f"[L2] persist failed for mode={source_mode} session={session_id}: {exc}"
            )
            return None

    def sync_to_long_term(
        self,
        session_id: int,
        user_id: int,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_mode: Optional[str] = None,
    ) -> Optional[str]:
        """同步到本地私有化 Mem0(永久记忆)。

        部署形态:LocalMem0APIImpl 走本地 HTTP API 为主路径,
        LocalMem0Impl 仅作进程内 fallback(重启即丢,违反永久语义)。

        失败用 logger.error(Mem0 健康度告警),不阻断 SSE。
        返回 memory_id 或 None。
        """
        if not summary:
            return None
        try:
            from app.ai.services.mem0_service import Mem0Service, Mem0Config

            config = (
                Mem0Config.from_settings()
                if hasattr(Mem0Config, "from_settings")
                else Mem0Config()
            )
            mem0 = Mem0Service(
                config=config,
                user_id=str(user_id),
                session_id=str(session_id),
            )
            entry_metadata = {
                "tenant_id": self.tenant_id,
                "session_id": session_id,
                "source_mode": source_mode or "shared",
                **(metadata or {}),
            }
            mem0_id = mem0.record(message=summary, metadata=entry_metadata)
            logger.info(
                f"[Mem0] synced user={user_id} mode={source_mode} mem0_id={mem0_id}"
            )
            # Mem0Service.record 返回 bool,规范化为 memory_id 字符串或 None
            return f"mem_{user_id}_{session_id}" if mem0_id else None
        except Exception as exc:
            # 永久记忆健康度告警:用 logger.error
            logger.error(
                f"[Mem0] sync failed user={user_id} mode={source_mode}: {exc}"
            )
            return None

    def get_context_with_mode_filter(
        self,
        session_id: int,
        user_id: int,
        allow_cross_mode: bool = False,
        include_tags: Optional[List[str]] = None,
        source_mode: Optional[str] = None,
        limit: int = 50,
        db: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """跨模式检索。allow_cross_mode=True 才能读取 is_cross_mode_accessible=True 记录。

        Args:
            session_id: 主 session_id
            allow_cross_mode: 是否允许读取跨模式可读记录
            include_tags: 上下文标签包含过滤(命中其一即返回)
            source_mode: 限定单一来源模式
            limit: 返回数量上限
            db: SQLAlchemy Session(必填)

        Returns:
            记录列表,按 last_accessed DESC 排序
        """
        if db is None:
            return []
        try:
            from sqlalchemy import desc, cast, String
            from app.models.ai.ai_chat_context_storage import AIChatContextStorage

            q = db.query(AIChatContextStorage).filter(
                AIChatContextStorage.tenant_id == self.tenant_id,
                AIChatContextStorage.session_id == session_id,
            )
            if source_mode:
                q = q.filter(AIChatContextStorage.source_mode == source_mode)
            if not allow_cross_mode:
                # 仅返回 is_cross_mode_accessible=False 的记录
                q = q.filter(
                    AIChatContextStorage.is_cross_mode_accessible == False  # noqa: E712
                )
            if include_tags:
                tag_filter = " | ".join(include_tags)
                q = q.filter(
                    cast(AIChatContextStorage.context_tags, String).contains(tag_filter)
                )
            q = q.order_by(desc(AIChatContextStorage.last_accessed)).limit(limit)
            results = []
            for row in q.all():
                results.append({
                    "id": row.id,
                    "session_id": row.session_id,
                    "source_mode": row.source_mode,
                    "context_key": row.context_key,
                    "context_data": row.context_data,
                    "context_tags": row.context_tags or [],
                    "priority": row.priority,
                    "is_cross_mode_accessible": row.is_cross_mode_accessible,
                    "case_number": row.case_number,
                    "expires_at": (
                        row.expires_at.isoformat() if row.expires_at else None
                    ),
                    "created_at": (
                        row.created_at.isoformat() if row.created_at else None
                    ),
                    "last_accessed": (
                        row.last_accessed.isoformat() if row.last_accessed else None
                    ),
                })
            return results
        except Exception as exc:
            logger.warning(f"[L2] get_context_with_mode_filter failed: {exc}")
            return []
