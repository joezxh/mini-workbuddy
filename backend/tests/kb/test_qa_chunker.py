"""QaChunker 测试（P1 Task 10）。

验证 表/列描述 → 问答对、Q/A 成对透传、未识别行兜底保留、DataBlock 透传、
ChunkerBase 契约（连续编号/total_chunks 一致/不跨 Section），以及 /chunkers
端点能看到 qa 切片器。
"""
from __future__ import annotations

import asyncio

from agentscope.message import DataBlock, TextBlock
from agentscope.rag import Section

from app.services.kb.qa_chunker import QaChunker


def _text_section(text: str, source: str = "meta.txt", metadata: dict | None = None):
    return Section(content=TextBlock(text=text), source=source, metadata=metadata or {})


def test_table_and_column_lines_become_qa_pairs():
    chunker = QaChunker()
    sections = [
        _text_section(
            "表: orders | 订单表，存储销售订单\n"
            "列: orders.amount | 订单金额\n"
            "字段: orders.status | 订单状态"
        )
    ]
    chunks = asyncio.run(chunker.chunk(sections))
    assert len(chunks) == 3
    assert "问：orders 是什么？" in chunks[0].content.text
    assert "答：订单表，存储销售订单" in chunks[0].content.text
    assert chunks[1].metadata["qa_type"] == "column"
    assert chunks[1].metadata["qa_name"] == "orders.amount"
    assert chunks[2].metadata["qa_type"] == "column"


def test_explicit_qa_pair_passthrough():
    chunker = QaChunker()
    chunks = asyncio.run(
        chunker.chunk([_text_section("Q: 什么是退款政策？\nA: 7 天无理由退款。")])
    )
    assert len(chunks) == 1
    assert chunks[0].content.text.startswith("问：什么是退款政策？")
    assert "答：7 天无理由退款。" in chunks[0].content.text


def test_unrecognized_lines_kept_as_fallback():
    chunker = QaChunker()
    chunks = asyncio.run(
        chunker.chunk([_text_section("表: t | 描述\n这是一段普通说明文字")])
    )
    assert len(chunks) == 2
    assert chunks[1].content.text == "这是一段普通说明文字"
    assert chunks[1].metadata["qa_type"] == "fallback"


def test_datablock_passthrough():
    chunker = QaChunker()
    section = Section(
        content=DataBlock(
            source={
                "type": "url",
                "url": "https://example.com/img.png",
                "media_type": "image/png",
            }
        ),
        source="img.png",
        metadata={},
    )
    chunks = asyncio.run(chunker.chunk([section]))
    assert len(chunks) == 1
    assert isinstance(chunks[0].content, DataBlock)


def test_contract_index_and_no_cross_section_merge():
    chunker = QaChunker()
    sections = [
        _text_section("表: a | 甲", source="s1", metadata={"doc": 1}),
        _text_section("表: b | 乙", source="s2", metadata={"doc": 2}),
    ]
    chunks = asyncio.run(chunker.chunk(sections))
    assert len(chunks) == 2
    # 连续编号 + total_chunks 一致
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert {c.total_chunks for c in chunks} == {2}
    # 不跨 Section 合并，元数据各自继承
    assert chunks[0].source == "s1" and chunks[1].source == "s2"
    assert chunks[0].metadata["doc"] == 1 and chunks[1].metadata["doc"] == 2


def test_chunkers_endpoint_lists_qa():
    from fastapi.testclient import TestClient

    from app.services.kb.kb_app import CHUNKER_REGISTRY, kb_app

    assert "qa" in CHUNKER_REGISTRY
    with TestClient(kb_app) as client:
        r = client.get("/chunkers")
        assert r.status_code == 200
        types = [item["chunker_type"] for item in r.json()]
        assert "approx_token" in types and "qa" in types
