"""AgentDeliveryService —— 按 request_id 幂等投递（Task 7.5）。

同一 request_id 的 Input 只投递一次（对齐 dsh-superagent AgentDelivery）：
  ① 模块级内存缓存（本进程内，跨实例共享）
  ② repo 可用时扫描 sa_effect 中 kind=delivery 且 status=done 的记录，
     payload.request_id 相同即视为已投递（跨 Session restart 兜底）
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

# 模块级 request_id → 投递记录（跨实例共享，进程内去重面）
_DELIVERED_REQUESTS: dict[str, dict] = {}


def _repo_has_delivered(repo: Any, request_id: str) -> bool:
    """查询 sa_effect：kind=delivery 且 status=done 且 payload.request_id 匹配。

    查询失败（repo 接口不符 / DB 不可用）退回内存缓存，不抛异常。
    """
    try:
        from app.models.superagent import SuperAgentEffect
        with repo.atomic() as db:
            rows = db.query(SuperAgentEffect).filter(
                SuperAgentEffect.kind == "delivery",
                SuperAgentEffect.status == "done",
            ).all()
        for r in rows:
            if (getattr(r, "payload", None) or {}).get("request_id") == request_id:
                return True
    except Exception as e:
        logger.warning(f"AgentDeliveryService · repo 去重查询失败（退回内存缓存）: {e}")
    return False


class AgentDeliveryService:
    """按 request_id 去重的 Input 投递服务。"""

    def __init__(self, repo: Any | None = None):
        self.repo = repo

    async def deliver(self, ticket_id: str, inputs: list[dict],
                      repo: Any | None = None) -> list[dict]:
        """投递 inputs，返回实际投递的子集；已投递过的 request_id 跳过。

        无 request_id 的 input 无法去重，每次都投递（调用方保证语义）。
        """
        repo = repo if repo is not None else self.repo
        delivered: list[dict] = []
        for raw in inputs or []:
            item = dict(raw or {})
            request_id = str(item.get("request_id") or "").strip()
            if request_id:
                if request_id in _DELIVERED_REQUESTS:
                    logger.info(
                        f"AgentDeliveryService · skip duplicated (memory) · "
                        f"ticket={ticket_id} · request_id={request_id}"
                    )
                    continue
                if repo is not None and _repo_has_delivered(repo, request_id):
                    _DELIVERED_REQUESTS[request_id] = {"ticket_id": ticket_id}
                    logger.info(
                        f"AgentDeliveryService · skip duplicated (repo) · "
                        f"ticket={ticket_id} · request_id={request_id}"
                    )
                    continue
                _DELIVERED_REQUESTS[request_id] = {
                    "ticket_id": ticket_id,
                    "delivered_at": datetime.utcnow().isoformat(),
                }
            delivered.append(item)
            logger.info(
                f"AgentDeliveryService · deliver · ticket={ticket_id} · "
                f"request_id={request_id or '(none)'}"
            )
        return delivered
