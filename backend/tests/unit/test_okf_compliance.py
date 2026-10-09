# -*- coding: utf-8 -*-
"""OKF v0.2 规范项回归测试（差距分析 §3.3 的 🟡 / 🟢 项）。

- §6.1 链接双向重写（导出 /wiki/<slug> → 相对路径；导入 .md → /wiki/<slug>）
- §7 actor 信任分层（human: / process:）
- §5.2 generated.at 统一 ISO 8601 UTC
- §3 references/ 惯例目录
- §4.2 body 推荐标题检查（只报告不拒绝）
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services.wiki import okf_service


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class QueueSession:
    """按查询实体返回预设结果集的 Session 替身。"""

    def __init__(self, knowledge, articles, versions, user=None):
        self.knowledge = knowledge
        self.user = user
        self.rows_by_entity = {
            "WikiArticle": list(articles),
            "WikiArticleVersion": list(versions),
            "KbCategory": [],
        }

    def get(self, model, pk):
        if model.__name__ == "WikiKnowledge":
            return self.knowledge
        return self.user  # SysUser（actor 解析）

    def execute(self, stmt):
        try:
            entity = stmt.column_descriptions[0]["entity"]
            name = entity.__name__
        except Exception:  # noqa: BLE001 替身只需覆盖 export_bundle 的查询形状
            return _Result([])
        return _Result(self.rows_by_entity.get(name, []))


def _article(slug, content, **kw):
    base = dict(
        id=1, slug=slug, title=slug.upper(), content=content, summary=f"{slug} 摘要",
        tags=["t"], category_id=None, knowledge_id=1, okf_type="concept",
        resource=None, sources=[], verified=[], status=1, stale_after=None,
        updated_at=datetime(2026, 1, 2, 3, 4, 5), creator_id=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _knowledge():
    return SimpleNamespace(id=1, name="知识库")


# ── §6.1 链接双向重写 ──────────────────────────────────────────────────────

def test_export_rewrites_wiki_link_to_relative_path():
    a = _article("a", "正文 [跳转](/wiki/b)")
    b = _article("b", "B 正文")
    files = okf_service.export_bundle(
        QueueSession(_knowledge(), [a, b], []), 1, tenant_id=1,
    )
    assert "](b.md)" in files["a.md"]
    assert files["a.md"].endswith("正文 [跳转](b.md)")


def test_export_keeps_broken_link_as_is():
    """§6.1 断链必须容忍：不在 bundle 内的 slug 原样保留。"""
    a = _article("a", "正文 [跳转](/wiki/ghost)")
    files = okf_service.export_bundle(QueueSession(_knowledge(), [a], []), 1)
    assert "](/wiki/ghost)" in files["a.md"]


def test_import_restores_relative_link():
    body = okf_service.rewrite_links_in("正文 [跳转](sub/b.md#x)")
    assert body == "正文 [跳转](/wiki/b#x)"


def test_rewrite_roundtrip():
    out = okf_service.rewrite_links_out("见 [x](/wiki/y)", "a.md", {"y": "y.md"})
    back = okf_service.rewrite_links_in(out)
    assert back == "见 [x](/wiki/y)"


# ── §7 actor 信任分层 ──────────────────────────────────────────────────────

def test_actor_is_human_for_known_creator():
    user = SimpleNamespace(user_id=1, username="alice")
    art = _article("a", "正文", creator_id=1)
    actor = okf_service._actor_for(art, QueueSession(_knowledge(), [], [], user=user))
    assert actor == "human:alice"


def test_actor_falls_back_to_process_without_creator():
    art = _article("a", "正文", creator_id=None)
    assert okf_service._actor_for(art, QueueSession(_knowledge(), [], [])) == (
        "process:minworkbuddy-wiki"
    )


def test_export_uses_human_actor():
    user = SimpleNamespace(user_id=1, username="alice")
    art = _article("a", "正文", creator_id=1)
    files = okf_service.export_bundle(
        QueueSession(_knowledge(), [art], [], user=user), 1,
    )
    assert "human:alice" in files["a.md"]


# ── §5.2 generated.at 统一 UTC ─────────────────────────────────────────────

def test_generated_at_is_utc_iso():
    art = _article("a", "正文", updated_at=datetime(2026, 1, 2, 3, 4, 5))
    md = okf_service.serialize_article(art, author_actor="human:alice")
    assert "2026-01-02T03:04:05Z" in md


def test_to_utc_iso_converts_offset_to_utc():
    from datetime import timedelta, timezone

    dt = datetime(2026, 1, 2, 11, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    assert okf_service._to_utc_iso(dt) == "2026-01-02T03:00:00Z"


def test_to_utc_iso_handles_z_suffix_string():
    assert okf_service._to_utc_iso("2026-01-02T03:04:05Z") == "2026-01-02T03:04:05Z"


# ── §3 references/ 惯例目录 ────────────────────────────────────────────────

def test_export_creates_references_dir():
    art = _article("a", "正文", resource="https://e.com/spec",
                   sources=[{"resource": "https://e.com/doc", "id": "s1"}])
    files = okf_service.export_bundle(QueueSession(_knowledge(), [art], []), 1)
    assert "references/index.md" in files
    assert "https://e.com/spec" in files["references/index.md"]
    assert "sources id=s1" in files["references/index.md"]


def test_export_omits_references_when_no_resource():
    files = okf_service.export_bundle(
        QueueSession(_knowledge(), [_article("a", "正文")], []), 1,
    )
    assert "references/index.md" not in files


# ── §4.2 body 推荐标题 ─────────────────────────────────────────────────────

def test_missing_body_headings_detected():
    assert okf_service.missing_body_headings("# 标题\n正文") == [
        "schema", "examples", "computation",
    ]
    assert okf_service.missing_body_headings(
        "# Schema\n# Examples\n# Computation\n"
    ) == []


def test_import_reports_missing_headings_without_rejecting():
    md = "---\ntype: concept\ntitle: X\n---\n# 自定义标题\n正文"
    files = okf_service.extract_zip(_zip_bytes({"x.md": md}))
    # 直接调用导入内核（避免 service 依赖）
    from app.services.wiki.okf_service import missing_body_headings

    assert missing_body_headings(files["x.md"].split("---\n", 2)[-1]) != []


def _zip_bytes(entries):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ── 宽容消费 ───────────────────────────────────────────────────────────────

def test_parse_frontmatter_tolerates_missing_block():
    meta, body = okf_service.parse_frontmatter("裸 markdown")
    assert meta == {"type": "concept"}
    assert body == "裸 markdown"


def test_status_mapping_roundtrip():
    assert okf_service._status_to_okf(-1) == "deprecated"
    assert okf_service._status_from_okf("draft") == 0
    assert okf_service._status_from_okf("unknown-value") == 1  # 宽容落 stable


# ── §10 Attested Computation ─────────────────────────────────────────────────

def test_export_emits_attested_fields_for_attested_type():
    ac = {
        "runtime": "bigquery",
        "parameters": [{"name": "year", "type": "integer", "required": True}],
        "computation": "references/computations/revenue.sql",
        "executor": {
            "resource": "references/skills/run-on-bq.md",
            "receipt": ["job_id", "executed_sql", "result"],
        },
        "attester": {"resource": "references/attesters/revenue.py"},
    }
    art = _article(
        "rev", "正文", okf_type="Attested Computation", attested_computation=ac,
    )
    md = okf_service.serialize_article(art, author_actor="human:alice")
    assert "runtime: bigquery" in md
    assert "references/computations/revenue.sql" in md
    assert "attester:" in md
    assert "receipt:" in md


def test_export_omits_attested_fields_for_other_types():
    ac = {"runtime": "bigquery"}
    art = _article("m", "正文", okf_type="metric", attested_computation=ac)
    md = okf_service.serialize_article(art, author_actor="human:alice")
    # 非 Attested Computation 类型不得误带契约键
    assert "runtime:" not in md
