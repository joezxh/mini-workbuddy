"""Wiki LLM 问答服务（G9）。

检索相关片段 → 拼装带编号上下文 → 调用 LLM 生成答案并附引用标注。

依赖现有 GPUStack Chat 接口（``app.config.settings`` 中的 GPUSTACK_* 配置）。
LLM 调用失败或无可检索内容时，返回友好提示，不影响主链路。
"""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from app.config import settings
from app.services.wiki.search_service import WikiSearchService


logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """你是一个严谨的知识库问答助手。请仅基于下面的「参考资料」回答用户问题。
要求：
1. 回答中必须使用 [数字] 标注引用来源，数字对应参考资料前的编号；
2. 若参考资料不足以回答问题，请如实说明「根据现有知识库内容无法确认」；
3. 不要编造参考资料之外的信息。

参考资料:
{context}

用户问题: {query}"""


class LLMWikiService:
    """问 AI：检索 → 拼装 → LLM 生成答案 + 引用。"""

    def __init__(self, db) -> None:
        self.db = db

    def ask(
        self,
        query: str,
        *,
        top_k: int = 5,
        knowledge_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        search_svc = WikiSearchService(self.db)
        result = search_svc.search(
            query,
            mode="semantic",
            top_k=top_k,
            knowledge_id=knowledge_id,
            user_id=user_id,
        )
        items = result["items"]
        context_parts: List[str] = []
        citations = []
        for i, item in enumerate(items, 1):
            snippet = (item.get("content") or item.get("snippet") or "")[:600]
            context_parts.append(f"[{i}] {item['title']}\n{snippet}")
            citations.append(
                {
                    "ref": i,
                    "article_id": item["id"],
                    "slug": item["slug"],
                    "title": item["title"],
                    "snippet": (item.get("content") or item.get("snippet") or "")[:200],
                }
            )
        context = "\n\n".join(context_parts)
        if not context:
            return {
                "answer": "抱歉，当前知识库中暂无与您问题相关的内容，无法作答。",
                "citations": [],
                "mode": "llm_wiki",
            }
        answer = self._chat(self._system_prompt(), _PROMPT_TEMPLATE.format(context=context, query=query))
        if answer is None:
            return {
                "answer": "抱歉，大模型暂时不可用，请稍后重试或改用关键词检索。",
                "citations": citations,
                "mode": "llm_wiki",
            }
        return {"answer": answer, "citations": citations, "mode": "llm_wiki"}

    @staticmethod
    def _system_prompt() -> str:
        return "你是企业私有知识库（Wiki）的智能问答助手，回答必须基于给定参考资料并标注引用。"

    def _chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1200, timeout: float = 180.0) -> Optional[str]:
        url = settings.GPUSTACK_API_URL.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GPUSTACK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.GPUSTACK_CHAT_MODEL,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            logger.error(f"[LLMWikiService] LLM 调用失败: {e}")
            return None
