# -*- coding: utf-8 -*-
"""写路径统一与向量化触发回归测试。

针对差距分析 §2.2 / §3.3 第 1、2 条：
- 创建 / 更新 / 导入三条入口此前都不触发 `_enqueue_index`，`content_vector` 恒为 NULL；
- `reindex_all` 此前没有任何 HTTP 入口。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.wiki.wiki_article import WikiArticle
from app.routers.wiki import wiki as wiki_router
from app.routers.wiki.wiki import ArticleCreateRequest, ArticleUpdateRequest


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
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self.added = []
        self.committed = 0

    def execute(self, stmt):
        return _Result(self._rows)

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
def indexed(monkeypatch):
    """拦截异步索引提交，记录被调用的 article id（不真的打 embedding）。"""
    calls = []

    def _fake_run_in_background(fn, *args, name=None, **kwargs):
        calls.append((fn, args, kwargs, name))
        return None

    monkeypatch.setattr(
        "app.core.job_runner.run_in_background", _fake_run_in_background,
    )
    return calls


def _user():
    return SimpleNamespace(user_id=1, username="alice", tenant_id=42)


# ── 路由委托到唯一写路径 ───────────────────────────────────────────────────

def test_create_article_route_enqueues_index(indexed):
    """内联实现曾经完全不触发索引；改为 service 后必须触发。"""
    result = wiki_router.create_article(
        body=ArticleCreateRequest(title="标题", content="正文"),
        db=FakeSession(),
        current_user=_user(),
    )
    assert result["okf_type"] is None
    assert result["verified"] == []
    assert len(indexed) == 1
    fn, args, kwargs, name = indexed[0]
    assert fn.__name__ == "index_article"
    assert str(name).startswith("wiki-index-")


def test_create_article_route_persists_okf_fields(indexed):
    result = wiki_router.create_article(
        body=ArticleCreateRequest(
            title="标题",
            okf_type="howto",
            resource="https://e.com/s",
            sources=[],
            verified=[{"by": "human:carol", "at": "2026-01-01T00:00:00Z"}],
            stale_after="2026-12-31T00:00:00Z",
        ),
        db=FakeSession(),
        current_user=_user(),
    )
    assert result["okf_type"] == "howto"
    assert result["resource"] == "https://e.com/s"
    assert result["verified"][0]["by"] == "human:carol"
    assert result["stale_after"].startswith("2026-12-31")


def test_update_article_route_enqueues_index(monkeypatch, indexed):
    article = WikiArticle(id=5, slug="s", title="旧", content="旧正文", version=1)
    monkeypatch.setattr(
        "app.repositories.wiki.article_repo.WikiArticleRepository.get_by_id",
        lambda self, article_id: article,
    )
    monkeypatch.setattr(
        "app.repositories.wiki.article_repo.WikiArticleRepository.get_by_slug",
        lambda self, slug: None,
    )

    result = wiki_router.update_article(
        article_id=5,
        body=ArticleUpdateRequest(okf_type="reference", content="新正文"),
        db=FakeSession(),
        current_user=_user(),
    )
    assert result["okf_type"] == "reference"
    assert article.content == "新正文"
    assert len(indexed) == 1


# ── service 自身 ───────────────────────────────────────────────────────────

def test_service_create_sets_tenant_and_knowledge(indexed):
    from app.services.wiki.article_service import WikiArticleService

    db = FakeSession()
    WikiArticleService(db).create(
        {"title": "T", "knowledge_id": 3, "okf_type": "metric"},
        _user(),
        tenant_id=42,
    )
    article = [o for o in db.added if isinstance(o, WikiArticle)][0]
    assert article.tenant_id == 42
    assert article.knowledge_id == 3
    assert article.okf_type == "metric"


def test_service_update_triggers_index(indexed):
    from app.services.wiki.article_service import WikiArticleService

    article = WikiArticle(id=6, slug="s", title="T", content="C", version=1)
    svc = WikiArticleService(FakeSession())
    svc.repo = SimpleNamespace(get_by_id=lambda i: article, get_by_slug=lambda s: None)
    svc.update(6, {"okf_type": "decision"}, "改类型", _user())
    assert article.okf_type == "decision"
    assert len(indexed) == 1


# ── 重建索引入口 ───────────────────────────────────────────────────────────

def test_reindex_endpoint_submits_background_job(indexed):
    resp = wiki_router.reindex_articles(
        knowledge_id=7, db=FakeSession(), current_user=_user(),
    )
    assert resp["started"] is True
    assert resp["knowledge_id"] == 7
    assert len(indexed) == 1
    fn, args, kwargs, name = indexed[0]
    assert fn.__name__ == "reindex_all"
    assert kwargs["tenant_id"] == 42
    assert kwargs["knowledge_id"] == 7
