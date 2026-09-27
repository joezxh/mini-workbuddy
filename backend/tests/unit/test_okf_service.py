"""OKF v0.2 合规层单测（spec §9：序列化/宽容解析/round-trip）。"""

from types import SimpleNamespace

from app.services.wiki.okf_service import parse_frontmatter, serialize_article

SAMPLE_FRONTMATTER = """---
type: concept
title: 测试概念
description: 一句摘要
tags:
- a
- b
sources:
- resource: https://example.com/x
  id: src1
generated:
  by: process:minworkbuddy-wiki
  at: '2026-09-27T00:00:00Z'
status: stable
---

正文内容保持原样。
"""


def _article(**overrides):
    base = dict(
        okf_type=None, resource=None, title="T", summary="D",
        tags=["x"], sources=None, verified=None, status=1,
        stale_after=None, slug="t", content="正文",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_parse_frontmatter_tolerant():
    meta, body = parse_frontmatter(SAMPLE_FRONTMATTER)
    assert meta["type"] == "concept"
    assert body.lstrip().startswith("正文内容")


def test_parse_frontmatter_bare_markdown_degrades():
    """宽容消费（§11.3）：无 frontmatter 退化读取，type 缺省 concept。"""
    meta, body = parse_frontmatter("裸 Markdown")
    assert meta["type"] == "concept"
    assert "裸 Markdown" in body


def test_parse_frontmatter_broken_yaml_degrades():
    meta, body = parse_frontmatter("---\n: : :\n---\n内容")
    assert meta["type"] == "concept"
    assert "内容" in body


def test_serialize_article_contains_required_type_and_actor():
    md = serialize_article(_article(), author_actor="human:u1",
                           generated_at="2026-09-27T00:00:00Z")
    assert "type: concept" in md          # 缺省回填 concept（仅 type 即合规）
    assert "human:u1" in md               # actor 约定（§7）
    assert "2026-09-27T00:00:00Z" in md   # ISO 8601 UTC
    assert "正文" in md


def test_roundtrip_preserves_type_tags_status():
    art = _article(okf_type="howto", tags=["x"], status=0,
                   sources=[{"resource": "https://e.com", "id": "s1"}],
                   content="A\nB\n")
    md = serialize_article(art, author_actor="human:u1",
                           generated_at="2026-09-27T00:00:00Z")
    meta, body = parse_frontmatter(md)
    assert meta["type"] == "howto"
    assert meta["tags"] == ["x"]
    assert meta["status"] == "draft"          # 0→draft 映射（§9.2）
    assert meta["sources"][0]["id"] == "s1"   # 溯源家族（§5.1）
    assert body.strip() == "A\nB"


def test_roundtrip_archived_maps_deprecated():
    art = _article(status=-1)
    md = serialize_article(art, author_actor="human:u1",
                           generated_at="2026-09-27T00:00:00Z")
    meta, _ = parse_frontmatter(md)
    assert meta["status"] == "deprecated"
