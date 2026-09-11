"""QaChunker —— 结构化业务数据 → 问答对切片（P1 Task 10，可选件）。

面向 DataOps 元数据场景：把「表/列描述」类结构化文本切成独立的问答对切片，
使检索命中粒度是「一个字段的一份说明」而非整篇文档，提升中文表格类知识的
召回与引用精度。

识别的行格式（每行一个条目，中英文冒号与分隔符均可）：
    表: orders | 订单表，存储销售订单        → 问：orders 是什么？答：订单表，…
    列: orders.amount | 订单金额            → 问：orders.amount 是什么？答：订单金额
    Q: 什么是退款政策？                     → 原样成对透传
    A: 7 天无理由退款。

未被识别的行不丢弃：按 Section 聚合为一个兜底切片，保留原文。

遵守 ``ChunkerBase`` 契约：不跨 Section 合并；``DataBlock`` 原样透传不切片；
``chunk_index`` 全局连续 0..N-1；每个 Chunk 的 ``total_chunks`` 一致；
``source``/``metadata`` 继承自父 Section（并附加 qa_type/qa_name）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from agentscope.message import DataBlock, TextBlock
from agentscope.rag import Chunk, ChunkerBase, Section


# 行前缀 → qa_type（同时兼容中英文冒号）
_PREFIX_TYPES = (
    ("表", "table"),
    ("列", "column"),
    ("字段", "column"),
)
_QA_PAIR_RE = re.compile(r"^\s*(?:Q|问)\s*[:：]\s*(?P<q>.+?)\s*$", re.IGNORECASE)
_ANS_RE = re.compile(r"^\s*(?:A|答)\s*[:：]\s*(?P<a>.*)\s*$", re.IGNORECASE)
_NAME_DESC_SPLIT = re.compile(r"\||｜")


def _parse_entry_line(line: str) -> Optional[Tuple[str, str, str]]:
    """解析 ``表/列: name | description`` 行，返回 (qa_type, name, description)。"""
    stripped = line.strip()
    for prefix, qa_type in _PREFIX_TYPES:
        if stripped.startswith(prefix) and len(stripped) > len(prefix):
            rest = stripped[len(prefix):]
            if rest[:1] in (":", "："):
                rest = rest[1:]
            else:
                return None
            parts = [p.strip() for p in _NAME_DESC_SPLIT.split(rest, maxsplit=1)]
            name = parts[0] if parts and parts[0] else ""
            desc = parts[1] if len(parts) > 1 else ""
            if not name:
                return None
            return qa_type, name, desc
    return None


class QaChunker(ChunkerBase):
    """结构化数据问答切片器（chunker_type=``qa``）。"""

    chunker_type = "qa"

    class Parameters(ChunkerBase.Parameters):
        """问答模板参数（{name}/{description} 占位）。"""

        question_template: str = "问：{name} 是什么？"
        answer_template: str = "答：{description}"

    def __init__(self, parameters: "QaChunker.Parameters | None" = None) -> None:
        super().__init__(parameters)

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []

        for section in sections:
            if isinstance(section.content, DataBlock):
                # 多模态数据不切片，原样透传
                chunks.append(self._mk(section, section.content, {}))
                continue

            text = section.content.text or ""
            fallback_lines: List[str] = []
            pending_q: Optional[str] = None

            for line in text.splitlines():
                if not line.strip():
                    continue

                entry = _parse_entry_line(line)
                if entry is not None:
                    qa_type, name, desc = entry
                    chunks.append(
                        self._mk(
                            section,
                            TextBlock(text=self._render(name, desc)),
                            {"qa_type": qa_type, "qa_name": name},
                        )
                    )
                    continue

                q_match = _QA_PAIR_RE.match(line)
                if q_match is not None:
                    pending_q = q_match.group("q")
                    continue

                a_match = _ANS_RE.match(line)
                if a_match is not None and pending_q is not None:
                    chunks.append(
                        self._mk(
                            section,
                            TextBlock(
                                text=f"问：{pending_q}\n答：{a_match.group('a')}"
                            ),
                            {"qa_type": "pair"},
                        )
                    )
                    pending_q = None
                    continue

                fallback_lines.append(line)

            if fallback_lines:
                chunks.append(
                    self._mk(
                        section,
                        TextBlock(text="\n".join(fallback_lines)),
                        {"qa_type": "fallback"},
                    )
                )

        # 全局连续编号 0..N-1，total_chunks 一致
        for index, chunk in enumerate(chunks):
            chunk.chunk_index = index
            chunk.total_chunks = len(chunks)
        return chunks

    # ------------------------------------------------------------------ #
    def _render(self, name: str, description: str) -> str:
        p = self.parameters
        return f"{p.question_template.format(name=name)}\n{p.answer_template.format(description=description)}"

    def _mk(
        self,
        section: Section,
        content: Union[TextBlock, DataBlock],
        extra_meta: Dict[str, Any],
    ) -> Chunk:
        metadata = dict(section.metadata or {})
        metadata.update(extra_meta)
        return Chunk(
            content=content,
            source=section.source,
            chunk_index=0,      # 统一重编号
            total_chunks=0,     # 统一重编号
            metadata=metadata,
        )
