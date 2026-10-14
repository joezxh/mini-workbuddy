"""导入服务单测：覆盖 / 跳过 / 新建 / 失败隔离 / 租户隔离。

不连真实数据库：用轻量替身 Session（仅实现导入服务用到的 query/add/get/execute/commit），
并把后台任务与文档源替换成可控替身，专注验证「覆盖 or 新建」的判定逻辑。
"""
from __future__ import annotations

import asyncio

import pytest

from app.connectors.doc_sources import FetchDocResult
from app.models.connectors.external_doc_map import KbExternalDocMap
from app.models.kb.kb_document import KbDocument, new_document_uuid
from app.services.kb import external_import_service as svc


def run(coro):
    """独立事件循环执行协程：避免受其它用例的 loop 状态影响。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── 替身 ──────────────────────────────────────────────────────────
class _FakeQ:
    """只支持 ``Model.col == value`` 形式的等值过滤。"""

    def __init__(self, rows):
        self._rows = rows
        self._conds = []

    def filter(self, *exprs):
        for e in exprs:
            self._conds.append((e.left.key, e.right.value))
        return self

    def one_or_none(self):
        matches = [
            r for r in self._rows
            if all(getattr(r, k, None) == v for k, v in self._conds)
        ]
        if not matches:
            return None
        assert len(matches) == 1, "替身过滤条件不足以唯一定位"
        return matches[0]


class FakeSession:
    def __init__(self):
        self.rows = {KbDocument: [], KbExternalDocMap: []}
        self.commits = 0
        self.executed = []
        self._next_id = 1

    def query(self, model):
        return _FakeQ(self.rows.setdefault(model, []))

    def add(self, obj):
        if isinstance(obj, KbDocument) and not obj.uuid_code:
            obj.uuid_code = new_document_uuid()
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1
        self.rows.setdefault(type(obj), []).append(obj)

    def flush(self):
        pass

    def get(self, model, pk):
        return next((r for r in self.rows.get(model, []) if r.id == pk), None)

    def execute(self, stmt):
        self.executed.append(stmt)
        return None

    def commit(self):
        self.commits += 1


class FakeSource:
    """文档源替身：按 external_doc_id 返回可配置正文。"""

    def __init__(self, payloads, fail_ids=()):
        self.payloads = payloads
        self.fail_ids = set(fail_ids)
        self.fetched = []

    async def fetch_doc(self, doc_id):
        self.fetched.append(doc_id)
        if doc_id in self.fail_ids:
            raise RuntimeError("平台限流")
        title, body = self.payloads[doc_id]
        return FetchDocResult(title=title, markdown=body, updated_at="2026-10-12")

    async def aclose(self):
        pass


@pytest.fixture
def dispatched(monkeypatch):
    """捕获后台派发，返回列表 [(doc_pk, filename)]。"""
    calls = []
    monkeypatch.setattr(
        svc, "run_in_background", lambda fn, name=None: calls.append(fn)
    )
    return calls


def _patch_source(monkeypatch, source):
    monkeypatch.setattr(svc, "get_doc_source", lambda st, cred: source)


# ── 内容哈希 ──────────────────────────────────────────────────────
def test_content_hash_normalizes_line_endings():
    assert svc.content_hash("a\r\nb") == svc.content_hash("a\nb")
    assert svc.content_hash("  x  ") == svc.content_hash("x")


def test_content_hash_changes_with_content():
    assert svc.content_hash("v1") != svc.content_hash("v2")


# ── 新建 ──────────────────────────────────────────────────────────
def test_first_import_creates_document_and_mapping(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource({"e1": ("架构说明", "# 架构\n\n正文")}))

    summary = run(svc.import_documents(
        db, 1, 100, "feishu", {"app_id": "x"},
        [{"doc_id": "e1", "title": "架构说明"}],
    ))

    assert (summary.total, summary.created, summary.updated, summary.unchanged,
            summary.failed) == (1, 1, 0, 0, 0)
    doc = db.rows[KbDocument][0]
    assert doc.source_type == "connector" and doc.status == "pending"
    assert doc.collection == "kb_100" and doc.name == "架构说明.md"
    mapping = db.rows[KbExternalDocMap][0]
    assert mapping.external_doc_id == "e1" and mapping.content_hash == svc.content_hash("# 架构\n\n正文")
    assert len(dispatched) == 1 and db.commits >= 1


# ── 未变更：跳过嵌入 ──────────────────────────────────────────────
def test_unchanged_content_skips_ingest(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource({"e1": ("架构说明", "same body")}))
    run(svc.import_documents(db, 1, 100, "feishu", {}, [{"doc_id": "e1", "title": "t"}]))

    dispatched.clear()
    summary = run(svc.import_documents(
        db, 1, 100, "feishu", {}, [{"doc_id": "e1", "title": "t"}]
    ))

    assert (summary.created, summary.updated, summary.unchanged) == (0, 0, 1)
    assert dispatched == [], "内容未变化不应重复触发摄取"
    assert len(db.rows[KbDocument]) == 1, "不应重复创建文档"


# ── 覆盖：复用同一文档 ────────────────────────────────────────────
def test_changed_content_overwrites_same_document(monkeypatch, dispatched):
    db = FakeSession()
    src = FakeSource({"e1": ("架构说明", "v1 body")})
    _patch_source(monkeypatch, src)
    run(svc.import_documents(db, 1, 100, "feishu", {}, [{"doc_id": "e1", "title": "t"}]))
    uuid_before = db.rows[KbDocument][0].uuid_code

    src.payloads["e1"] = ("架构说明", "v2 body")
    dispatched.clear()
    db.executed.clear()
    summary = run(svc.import_documents(
        db, 1, 100, "feishu", {}, [{"doc_id": "e1", "title": "t"}]
    ))

    assert (summary.created, summary.updated, summary.unchanged) == (0, 1, 0)
    assert len(db.rows[KbDocument]) == 1
    doc = db.rows[KbDocument][0]
    assert doc.uuid_code == uuid_before, "覆盖必须复用同一 uuid_code"
    assert doc.status == "pending" and doc.segment_count == 0
    assert db.executed, "覆盖前必须清理旧切片"
    assert len(dispatched) == 1


# ── 失败隔离 ──────────────────────────────────────────────────────
def test_single_failure_does_not_block_others(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource(
        {"ok": ("正常", "body"), "bad": ("坏", "")}, fail_ids=("bad",)
    ))
    summary = run(svc.import_documents(
        db, 1, 100, "feishu", {},
        [{"doc_id": "ok", "title": "正常"}, {"doc_id": "bad", "title": "坏"}],
    ))
    assert (summary.created, summary.failed) == (1, 1)
    assert len(db.rows[KbDocument]) == 1
    assert len(dispatched) == 1


def test_empty_body_counts_as_failed(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource({"e": ("空", "   ")}))
    summary = run(svc.import_documents(db, 1, 100, "feishu", {}, [{"doc_id": "e", "title": "空"}]))
    assert summary.failed == 1 and summary.created == 0


# ── 租户 / 知识库隔离 ─────────────────────────────────────────────
def test_import_is_scoped_by_tenant_and_knowledge(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource({"e1": ("文档", "body")}))
    run(svc.import_documents(db, 1, 100, "feishu", {}, [{"doc_id": "e1", "title": "t"}]))
    summary = run(svc.import_documents(db, 2, 999, "feishu", {}, [{"doc_id": "e1", "title": "t"}]))

    assert summary.created == 1, "不同租户/知识库互不复用映射"
    assert len(db.rows[KbExternalDocMap]) == 2


def test_import_empty_selection_is_noop(monkeypatch, dispatched):
    db = FakeSession()
    _patch_source(monkeypatch, FakeSource({}))
    summary = run(svc.import_documents(db, 1, 100, "feishu", {}, []))
    assert summary.total == 0 and dispatched == []
