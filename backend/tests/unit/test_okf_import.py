# -*- coding: utf-8 -*-
"""OKF 导入内核回归测试（针对差距分析文档 §3.3 的 🔴 实现缺陷）。

覆盖点：
- 导入必须持久化全部 frontmatter 字段（此前只写 title/description/tags/status）
- 导入文章必须写入 tenant_id（此前写死 None）
- slug 作用域必须限定在 tenant + knowledge，跨库不得覆盖
- 导入必须触发异步向量索引
- zip 解包安全限制
"""
from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest

from app.services.wiki import okf_service


# ── 替身 ───────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class FakeSession:
    """足够支撑 import_bundle 的最小 Session 替身（不连真实库）。"""

    def __init__(self):
        self.added = []
        self.committed = 0

    def execute(self, stmt):
        return _Result([])

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        pass

    def get(self, model, pk):
        return None


@pytest.fixture
def patched_service(monkeypatch):
    """拦截 service 的查询与副作用，只保留 create 的真实构造逻辑。"""
    state = {
        "existing_by_slug": {},   # slug -> article（作用域内已存在）
        "global_slugs": set(),    # 全局已占用 slug
        "updated": [],            # (article_id, data)
        "indexed": [],            # 被 _enqueue_index 处理的 article id
    }

    from app.services.wiki.article_service import WikiArticleService

    def _slug_exists(self, slug):
        return slug in state["global_slugs"]

    def _find_scoped(self, slug, tenant_id, knowledge_id):
        return state["existing_by_slug"].get(slug)

    def _update(self, article_id, data, change_note, user):
        state["updated"].append((article_id, data))
        return {"id": article_id}

    def _enqueue(self, article_id):
        state["indexed"].append(article_id)

    def _noop_version(self, *a, **kw):
        return None

    def _noop_backlinks(self, *a, **kw):
        return None

    monkeypatch.setattr(WikiArticleService, "slug_exists", _slug_exists)
    monkeypatch.setattr(WikiArticleService, "find_scoped", _find_scoped)
    monkeypatch.setattr(WikiArticleService, "update", _update)
    monkeypatch.setattr(WikiArticleService, "_enqueue_index", _enqueue)
    monkeypatch.setattr(WikiArticleService, "_create_version", _noop_version)
    monkeypatch.setattr(WikiArticleService, "_update_backlinks", _noop_backlinks)
    return state


def _user(tenant_id=9):
    return SimpleNamespace(user_id=1, username="alice", tenant_id=tenant_id)


CONCEPT = """---
type: howto
resource: https://example.com/spec
title: 部署指南
description: 如何部署
tags: [ops]
sources:
- resource: https://example.com/a
  id: s1
  author: bob
verified:
- by: human:carol
  at: '2026-01-02T03:04:05Z'
status: stable
stale_after: '2026-12-31T00:00:00Z'
---
# Schema

正文 [链接](/wiki/other)
"""


# ── 字段全量往返 ───────────────────────────────────────────────────────────

def test_import_persists_all_frontmatter_fields(patched_service):
    """曾经只写 title/description/tags/status，其余六个字段被整体丢弃。"""
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user())

    assert report["imported"] == 1
    article = db.added[0]
    assert article.okf_type == "howto"
    assert article.resource == "https://example.com/spec"
    assert article.sources[0]["id"] == "s1"
    assert article.sources[0]["author"] == "bob"
    assert article.verified[0]["by"] == "human:carol"
    assert article.stale_after is not None
    assert article.stale_after.year == 2026
    assert article.status == 1  # stable → 1


def test_export_import_roundtrip_keeps_fields(patched_service):
    """导出再导入，六个字段不得丢失。"""
    from datetime import datetime

    article = SimpleNamespace(
        id=1, slug="guide", title="部署指南", content="正文", summary="如何部署",
        tags=["ops"], knowledge_id=1, category_id=None, okf_type="howto",
        resource="https://example.com/spec",
        sources=[{"resource": "https://example.com/a", "id": "s1"}],
        verified=[{"by": "human:carol", "at": "2026-01-02T03:04:05Z"}],
        status=1, stale_after=datetime(2026, 12, 31), updated_at=None,
        creator_id=None,
    )
    md = okf_service.serialize_article(article, author_actor="human:alice")

    db = FakeSession()
    okf_service.import_bundle(db, 1, {"guide.md": md}, _user())
    got = db.added[0]
    assert got.okf_type == "howto"
    assert got.resource == "https://example.com/spec"
    assert got.sources[0]["id"] == "s1"
    assert got.verified[0]["by"] == "human:carol"
    assert got.stale_after.year == 2026


def test_import_writes_tenant_id(patched_service):
    """曾经写死 tenant_id=None，导致导入文章可被跨租户检索到。"""
    db = FakeSession()
    okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user(tenant_id=42))
    assert db.added[0].tenant_id == 42


def test_import_uses_explicit_tenant_id_over_user(patched_service):
    db = FakeSession()
    okf_service.import_bundle(
        db, 1, {"guide.md": CONCEPT}, _user(tenant_id=42), tenant_id=7,
    )
    assert db.added[0].tenant_id == 7


# ── slug 作用域 ────────────────────────────────────────────────────────────

def test_cross_knowledge_slug_conflict_creates_suffix_not_overwrite(patched_service):
    """跨知识库同名 slug 必须新建（加 -2），绝不能覆盖别的库的文章。"""
    patched_service["global_slugs"] = {"guide", "guide-2"}
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user())

    assert report["details"]["slug_conflicts"] == 1
    assert db.added[0].slug == "guide-3"
    assert patched_service["updated"] == []  # 没有走更新路径 → 没有覆盖


def test_same_scope_slug_updates_instead_of_creating(patched_service):
    from app.models.wiki.wiki_article import WikiArticle

    existing = WikiArticle(id=5, slug="guide", title="旧标题", knowledge_id=1)
    patched_service["existing_by_slug"]["guide"] = existing
    patched_service["global_slugs"] = {"guide"}

    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user())

    assert report["imported"] == 1
    assert db.added == []  # 未新建
    assert patched_service["updated"][0][0] == 5
    assert patched_service["updated"][0][1]["okf_type"] == "howto"


# ── 向量索引触发 ───────────────────────────────────────────────────────────

def test_import_triggers_async_index(patched_service):
    db = FakeSession()
    okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user())
    assert len(patched_service["indexed"]) == 1


# ── 链接还原与断链报告 ─────────────────────────────────────────────────────

def test_import_restores_md_links_to_wiki_links(patched_service):
    md = "正文 [其它](./other.md#sec)"
    db = FakeSession()
    okf_service.import_bundle(
        db, 1, {"guide.md": md, "other.md": "x"}, _user(),
    )
    body = db.added[0].content
    assert "](/wiki/other#sec)" in body


def test_import_reports_broken_links_without_rejecting(patched_service):
    """§11.3：断链必须容忍，但要出现在报告里。"""
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"guide.md": CONCEPT}, _user())
    assert report["details"]["broken_links"] >= 1
    assert report["imported"] == 1


def test_import_tolerates_unknown_keys_and_missing_type(patched_service):
    md = "---\ntitle: X\nwhatever: 1\n---\n正文"
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"x.md": md}, _user())
    assert report["imported"] == 1
    assert report["details"]["unknown_keys"] == 1
    assert report["details"]["unknown_type"] == 1
    assert db.added[0].okf_type == "concept"


def test_import_skips_reserved_files(patched_service):
    db = FakeSession()
    report = okf_service.import_bundle(
        db, 1, {"index.md": "x", "log.md": "y", "references/index.md": "z",
                "notes.txt": "t", "a.md": "x"}, _user(),
    )
    assert report["imported"] == 1
    assert report["skipped"] == 4


# ── §10 Attested Computation ─────────────────────────────────────────────────

ATTESTED = """---
type: Attested Computation
title: 营收计算
description: FY 营收
status: stable
runtime: bigquery
parameters:
- { name: year, type: integer, required: true }
executor:
  resource: references/skills/run-on-bq.md
  receipt: [job_id, executed_sql, result]
attester:
  resource: references/attesters/revenue.py
---
# Computation

SELECT sum(amount) FROM revenue WHERE year = {{ year }}
"""


def test_import_parses_attested_computation(patched_service):
    db = FakeSession()
    okf_service.import_bundle(db, 1, {"rev.md": ATTESTED}, _user())
    got = db.added[0]
    assert got.okf_type == "Attested Computation"
    ac = got.attested_computation
    assert ac["runtime"] == "bigquery"
    assert ac["parameters"][0]["name"] == "year"
    assert ac["executor"]["receipt"] == ["job_id", "executed_sql", "result"]
    assert ac["attester"]["resource"] == "references/attesters/revenue.py"


def test_import_reports_missing_runtime_for_attested(patched_service):
    """§10.2：type=Attested Computation 但缺 runtime 属契约违背，报告但不拒绝。"""
    md = "---\ntype: Attested Computation\ntitle: X\n---\n正文"
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"x.md": md}, _user())
    assert report["imported"] == 1
    assert report["details"]["attested_missing_runtime"] == 1
    assert any("runtime" in w for w in report["warnings"])
    # 宽容：仍导入，attested_computation 不写非法 runtime
    assert db.added[0].okf_type == "Attested Computation"
    assert db.added[0].attested_computation in (None, {})


def test_export_import_attested_roundtrip(patched_service):
    """导出（含 §10 契约字段）再导入，attested_computation 必须保真。"""
    article = SimpleNamespace(
        id=1, slug="rev", title="营收计算", content="# Computation\nSELECT 1",
        summary="FY 营收", tags=[], knowledge_id=1, category_id=None,
        okf_type="Attested Computation", resource=None, sources=[],
        verified=[], status=1, stale_after=None, updated_at=None, creator_id=None,
        attested_computation={
            "runtime": "bigquery",
            "parameters": [{"name": "year", "type": "integer", "required": True}],
            "executor": {"resource": "references/skills/run-on-bq.md", "receipt": ["job_id"]},
            "attester": {"resource": "references/attesters/revenue.py"},
        },
    )
    md = okf_service.serialize_article(article, author_actor="human:alice")
    db = FakeSession()
    okf_service.import_bundle(db, 1, {"rev.md": md}, _user())
    got = db.added[0]
    assert got.okf_type == "Attested Computation"
    assert got.attested_computation["runtime"] == "bigquery"
    assert got.attested_computation["parameters"][0]["name"] == "year"
    assert got.attested_computation["attester"]["resource"] == "references/attesters/revenue.py"


# ── 导入报告细分（§11.3 报告化）：逐源耗时 / 正文行数 ─────────────────────────

def test_import_report_per_file_timing_and_body_lines(patched_service):
    a = "---\ntype: concept\ntitle: A\n---\nline1\nline2\nline3\n"
    b = "---\ntype: concept\ntitle: B\n---\nsingle\n"
    db = FakeSession()
    report = okf_service.import_bundle(db, 1, {"a.md": a, "b.md": b}, _user())
    assert report["imported"] == 2
    assert len(report["per_file"]) == 2

    by_slug = {e["slug"]: e for e in report["per_file"]}
    assert by_slug["a"]["body_lines"] == 3
    assert by_slug["b"]["body_lines"] == 1
    # 动作字段存在（created / updated）
    assert all(e["action"] in ("created", "updated") for e in report["per_file"])
    # 耗时是浮点且非负
    assert all(isinstance(e["duration_ms"], float) and e["duration_ms"] >= 0
               for e in report["per_file"])

    assert report["totals"]["body_lines"] == 4
    assert report["totals"]["imported"] == 2
    assert isinstance(report["totals"]["duration_ms"], float)


# ── zip 解包安全 ───────────────────────────────────────────────────────────

def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_extract_zip_reads_entries():
    files = okf_service.extract_zip(_zip({"a.md": "A", "sub/b.md": "B"}))
    assert files == {"a.md": "A", "sub/b.md": "B"}


def test_extract_zip_rejects_path_traversal():
    with pytest.raises(ValueError, match="路径穿越"):
        okf_service.extract_zip(_zip({"../evil.md": "x"}))


def test_extract_zip_rejects_absolute_path():
    with pytest.raises(ValueError, match="绝对路径"):
        okf_service.extract_zip(_zip({"/etc/passwd.md": "x"}))


def test_extract_zip_rejects_too_many_entries(monkeypatch):
    monkeypatch.setattr(okf_service, "MAX_ZIP_ENTRIES", 2)
    with pytest.raises(ValueError, match="条目过多"):
        okf_service.extract_zip(_zip({f"{i}.md": "x" for i in range(5)}))


def test_extract_zip_rejects_oversized_entry(monkeypatch):
    monkeypatch.setattr(okf_service, "MAX_ZIP_ENTRY_BYTES", 10)
    with pytest.raises(ValueError, match="单文件过大"):
        okf_service.extract_zip(_zip({"a.md": "x" * 100}))


def test_extract_zip_rejects_total_size(monkeypatch):
    monkeypatch.setattr(okf_service, "MAX_ZIP_TOTAL_BYTES", 20)
    with pytest.raises(ValueError, match="体积超限"):
        okf_service.extract_zip(_zip({"a.md": "x" * 15, "b.md": "y" * 15}))


def test_extract_zip_rejects_empty():
    with pytest.raises(ValueError, match="为空"):
        okf_service.extract_zip(b"")
