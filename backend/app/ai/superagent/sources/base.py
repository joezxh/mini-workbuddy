"""SourceKind Protocol —— 所有 Source 实现必须对齐此接口。

对齐 dsh-superagent sources/registry.ts + sources/github.ts + sources/feishu.ts。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol, Literal
from datetime import datetime


SourceKind = Literal["github", "feishu", "http", "manual"]


@dataclass
class SourceTrigger:
    """Source 原始 Trigger —— IntakePart 接收的标准格式。"""
    source: SourceKind
    ref_id: str  # Source 内部唯一标识（GitHub Issue/PR 号，Feishu thread_id）
    kind: str    # issue_mention / pull_mention / comment_mention / ci_failure / group_message / dm / manual / http
    sender_id: str | None = None
    sender_name: str | None = None
    title: str | None = None
    body: str | None = None
    url: str | None = None
    context: dict = field(default_factory=dict)   # is_pr / ci_facts / workspace / 截图 等
    workspace_id: int = 0


class SourceKindProtocol(Protocol):
    """所有 Source 实现必须满足此接口。"""

    kind: SourceKind

    # --- 基础配置 ---
    def is_enabled(self) -> bool: ...

    # --- 轮询（poll）---
    async def poll_once(self, workspace_id: int, last_cursor: str | None) -> tuple[list[SourceTrigger], str | None]:
        """一次 poll 循环 —— 返回新 Trigger 列表 + 新 cursor（时间戳/ETag）。"""
        ...

    # --- Source 专属 health ---
    def health(self) -> dict: ...


@dataclass
class HealthStatus:
    """Source 健康状态 —— 来自 SourceRegistry.health_board()。"""
    kind: SourceKind
    status: Literal["healthy", "degraded", "down"] = "healthy"
    failures: int = 0
    last_error: str | None = None
    next_poll: datetime | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "status": self.status, "failures": self.failures,
                "last_error": self.last_error, "next_poll": self.next_poll.isoformat() if self.next_poll else None}
