"""父子分段切块器（spec §10.3，Dify 对齐）：父块保存完整上下文，子块用于检索。

对齐 agentscope 2.0.8 ``ChunkerBase`` 契约（与 ``QaChunker`` 同构）：
* ``chunker_type`` 全局唯一（``parent_child``），持久化重建用；
* 嵌套 Pydantic ``Parameters`` 声明可调项；
* ``async def chunk(sections) -> list[Chunk]``，不跨 Section 合并；
* ``chunk_index`` 全局连续 0..N-1，``total_chunks`` 全体一致。

子块 metadata 携带 ``parent_content``/``parent_index``，检索命中子块时由检索层
展开父块内容返回（spec §10.4 父子展开）。近似 token 口径与
``ApproxTokenChunker`` 一致：``len(text.encode("utf-8")) // 4``。
"""
from __future__ import annotations

from typing import List, Union

from agentscope.message import DataBlock, TextBlock
from agentscope.rag import Chunk, ChunkerBase, Section
from pydantic import Field


def _approx_tokens(text: str) -> int:
    return len(text.encode("utf-8")) // 4


def _split_by_tokens(text: str, size: int, overlap: int) -> List[str]:
    """按近似 token 数滑窗切分；size<=0 时整段返回。"""
    if not text:
        return []
    if size <= 0:
        return [text]
    # 近似：1 token ≈ 4 字节（utf-8），故字符窗口 = size * 4
    char_window = size * 4
    char_step = max(char_window - overlap * 4, 1)
    pieces: List[str] = []
    start = 0
    while start < len(text):
        pieces.append(text[start:start + char_window])
        if start + char_window >= len(text):
            break
        start += char_step
    return pieces


class ParentChildChunker(ChunkerBase):
    """父块（完整上下文）+ 子块（检索粒度）双层切片器。"""

    chunker_type = "parent_child"

    class Parameters(ChunkerBase.Parameters):
        parent_size: int = Field(default=1024, description="父块近似 token 上限")
        child_size: int = Field(default=256, description="子块近似 token 上限")
        overlap: int = Field(default=32, description="子块滑窗重叠（近似 token）")

    def __init__(self, parameters: "ParentChildChunker.Parameters | None" = None) -> None:
        super().__init__(parameters)

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []

        for section in sections:
            if isinstance(section.content, DataBlock):
                # 多模态数据不切片，原样透传（ChunkerBase 契约）
                chunks.append(self._mk(section, section.content, {}))
                continue

            text = section.content.text or ""
            if not text:
                continue

            parent_pieces = _split_by_tokens(
                text, self.parameters.parent_size, 0
            ) or [text]
            for parent_index, parent_text in enumerate(parent_pieces):
                child_pieces = _split_by_tokens(
                    parent_text, self.parameters.child_size, self.parameters.overlap
                )
                for piece in child_pieces:
                    chunks.append(self._mk(section, TextBlock(text=piece), {
                        "parent_index": parent_index,
                        "parent_content": parent_text,
                    }))

        # 全局连续编号 0..N-1，total_chunks 一致
        for index, chunk in enumerate(chunks):
            chunk.chunk_index = index
            chunk.total_chunks = len(chunks)
        return chunks

    def _mk(
        self,
        section: Section,
        content: Union[TextBlock, DataBlock],
        extra_meta: dict,
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
