"""常用分段切块器（Markdown 标题 / 句子 / 固定长度）。

补足 ``ApproxTokenChunker``（按 token 近似切分）之外的常见切块需求，供知识库
「切片方案」下拉选择（spec §10.7）：

* ``markdown``   —— 按 Markdown 标题（``#``~``######``）切块，保留标题上下文
* ``sentence``   —— 按句末标点切句后聚块，支持句级重叠
* ``fixed_size`` —— 按固定字符长度滑窗切块，支持字符级重叠

三者均遵守 ``ChunkerBase`` 四条约定：不跨 Section 合并；``DataBlock`` 原样透传
不切片；``chunk_index`` 全局连续 0..N-1；每个 Chunk 的 ``total_chunks`` 一致。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Union

from agentscope.message import DataBlock, TextBlock
from agentscope.rag import Chunk, ChunkerBase, Section

# Markdown 标题行（1~6 级）
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# 句末标点：中文 。！？；… 与英文 .!?（英文句号需后接空白或行尾，避免切断小数/缩写）
_SENT_END_RE = re.compile(r"(?<=[。！？；…])|(?<=[.!?])(?=\s|$)")


def _renumber(chunks: List[Chunk]) -> List[Chunk]:
    """全局连续编号 0..N-1，且 total_chunks 一致（ChunkerBase 契约）。"""
    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
        chunk.total_chunks = len(chunks)
    return chunks


def _mk_chunk(
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


def _split_fixed(text: str, size: int, overlap: int) -> List[str]:
    """固定长度滑窗切分（overlap < size 时前进 step = size - overlap）。"""
    if size <= 0:
        return [text] if text else []
    step = max(1, size - max(0, overlap))
    out: List[str] = []
    start = 0
    while start < len(text):
        out.append(text[start:start + size])
        start += step
    return out


def _split_sentences(text: str) -> List[str]:
    """按句末标点切句，保留标点；空白行不产生句子。"""
    raw = _SENT_END_RE.split(text)
    # re.split 带捕获组时会把分隔符一并放入结果，需与后一句合并
    sentences: List[str] = []
    buf = ""
    for part in raw or []:
        if part is None:
            continue
        buf += part
        if buf and (buf[-1] in "。！？；….!?"):
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return [s for s in sentences if s]


# ──────────────────────────────────────────────────────────────────────────
class MarkdownChunker(ChunkerBase):
    """按 Markdown 标题切块（chunker_type=``markdown``）。

    标题行开启一个新块；同标题下正文超长再按 ``max_chars`` 细分，
    细分片段默认保留该标题作为上下文前缀（``keep_heading=True``）。
    正文在首个标题之前的部分作为独立块（通常是文档摘要/前言）。
    """

    chunker_type = "markdown"

    class Parameters(ChunkerBase.Parameters):
        max_chars: int = 800        # 单块正文上限（超出再细分）
        keep_heading: bool = True   # 细分片段是否带上标题前缀

    def __init__(self, parameters: "MarkdownChunker.Parameters | None" = None) -> None:
        super().__init__(parameters)

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []
        p = self.parameters

        for section in sections:
            if isinstance(section.content, DataBlock):
                chunks.append(_mk_chunk(section, section.content, {}))
                continue

            text = section.content.text or ""
            # 按标题切成 (heading, body) 片段；首个标题前的内容 heading 为空
            blocks: List[tuple] = []
            cur_head, cur_body = "", []
            for line in text.splitlines():
                m = _HEADING_RE.match(line)
                if m:
                    if cur_body or cur_head:
                        blocks.append((cur_head, "\n".join(cur_body).strip()))
                    cur_head, cur_body = line.strip(), []
                else:
                    cur_body.append(line)
            if cur_body or cur_head:
                blocks.append((cur_head, "\n".join(cur_body).strip()))

            for heading, body in blocks:
                content = f"{heading}\n{body}" if heading else body
                if not content.strip():
                    continue
                if len(body) <= p.max_chars or p.max_chars <= 0:
                    chunks.append(_mk_chunk(
                        section, TextBlock(text=content),
                        {"chunk_type": "markdown", "heading": heading},
                    ))
                    continue
                # 正文过长：按 max_chars 细分，可选保留标题前缀
                prefix = f"{heading}\n" if (heading and p.keep_heading) else ""
                for i, piece in enumerate(_split_fixed(body, p.max_chars, 0)):
                    chunks.append(_mk_chunk(
                        section, TextBlock(text=f"{prefix}{piece}"),
                        {"chunk_type": "markdown", "heading": heading, "part": i + 1},
                    ))

        return _renumber(chunks)


# ──────────────────────────────────────────────────────────────────────────
class SentenceChunker(ChunkerBase):
    """按句切分后聚合（chunker_type=``sentence``）。

    先按句末标点切句，再按 ``max_chars`` 累积成块；``overlap_sentences``
    指定相邻块之间重叠的句子数，缓解跨块语义断裂。
    """

    chunker_type = "sentence"

    class Parameters(ChunkerBase.Parameters):
        max_chars: int = 500          # 单块字符上限
        overlap_sentences: int = 0    # 相邻块重叠的句子数

    def __init__(self, parameters: "SentenceChunker.Parameters | None" = None) -> None:
        super().__init__(parameters)

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []
        p = self.parameters

        for section in sections:
            if isinstance(section.content, DataBlock):
                chunks.append(_mk_chunk(section, section.content, {}))
                continue

            sentences = _split_sentences(section.content.text or "")
            if not sentences:
                continue

            buf: List[str] = []
            for sent in sentences:
                candidate = "".join(buf) + sent
                if buf and len(candidate) > p.max_chars:
                    chunks.append(_mk_chunk(
                        section, TextBlock(text="".join(buf)),
                        {"chunk_type": "sentence"},
                    ))
                    # 保留末尾若干句作为重叠
                    buf = buf[-p.overlap_sentences:] if p.overlap_sentences > 0 else []
                buf.append(sent)
            if buf:
                chunks.append(_mk_chunk(
                    section, TextBlock(text="".join(buf)),
                    {"chunk_type": "sentence"},
                ))

        return _renumber(chunks)


# ──────────────────────────────────────────────────────────────────────────
class FixedSizeChunker(ChunkerBase):
    """固定字符长度切块（chunker_type=``fixed_size``）。

    纯滑窗切分，与语言无关，适合无标题/无句末标点的纯文本或日志类文档。
    """

    chunker_type = "fixed_size"

    class Parameters(ChunkerBase.Parameters):
        chunk_size: int = 500   # 单块字符数
        overlap: int = 50       # 相邻块重叠字符数（必须 < chunk_size）

    def __init__(self, parameters: "FixedSizeChunker.Parameters | None" = None) -> None:
        super().__init__(parameters)

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []
        p = self.parameters
        overlap = min(max(0, p.overlap), max(0, p.chunk_size - 1))

        for section in sections:
            if isinstance(section.content, DataBlock):
                chunks.append(_mk_chunk(section, section.content, {}))
                continue
            text = (section.content.text or "").strip()
            if not text:
                continue
            for piece in _split_fixed(text, p.chunk_size, overlap):
                chunks.append(_mk_chunk(
                    section, TextBlock(text=piece),
                    {"chunk_type": "fixed_size"},
                ))

        return _renumber(chunks)


COMMON_CHUNKERS = (MarkdownChunker, SentenceChunker, FixedSizeChunker)
