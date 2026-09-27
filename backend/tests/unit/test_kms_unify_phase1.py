"""知识库统一化 Phase 1 回归测试（spec 2026-09-27，P0 六项）。

覆盖：
1. 统一容器类型枚举与 type/kb_format 列的向后兼容默认值；
2. kb_category 模型改造（表名/类名/冗余类型列）；
3. 连接器实例层模型落位（此前路由 import 崩溃的 P0-2）；
4. connectors / wiki_admin / ontology 三个路由已进注册清单（P0-2 / P0-6）；
5. 版本 diff / 回滚服务语义（P0-1 的三个端点依赖）；
6. job_runner 后台任务异常不回抛（P0-5）。
"""
import pytest

from app.core.router_registry import ROUTER_SPECS
from app.models.kb.kb_category import KbCategory
from app.models.kb.kb_collection import KbCollection
from app.models.connectors.connector_record import ConnectorInstance, ConnectorSyncLog
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_knowledge import KnowledgeType, WikiKnowledge


def test_knowledge_type_enum_values():
    assert (KnowledgeType.LLM_WIKI, KnowledgeType.GENERAL_KB, KnowledgeType.EXTERNAL_KB) == (1, 2, 3)


def test_knowledge_type_column_defaults_to_wiki():
    """存量行零迁移：type 列 server_default='1'，新增列均可为空。"""
    col = WikiKnowledge.__table__.c["type"]
    assert col.nullable is False
    assert "1" in str(col.server_default.arg if col.server_default else "")
    assert WikiKnowledge.__table__.c["kb_format"].nullable is True


def test_category_table_renamed_and_typed():
    assert KbCategory.__tablename__ == "kb_category"
    assert "kb_type" in KbCategory.__table__.c


def test_collection_has_knowledge_link():
    assert "knowledge_id" in KbCollection.__table__.c
    assert "schema_config" in KbCollection.__table__.c


def test_knowledge_index_mode_and_pipeline_config_columns():
    """spec §10.2：索引模式（economy 零 embedding）与摄取编排列。"""
    col = WikiKnowledge.__table__.c["index_mode"]
    assert col.nullable is False
    assert "high_quality" in str(col.server_default.arg if col.server_default else "")
    assert "pipeline_config" in WikiKnowledge.__table__.c


def test_connector_instance_and_log_models_exist():
    """路由此前 import 这两个类即崩，必须存在且字段齐备。"""
    assert ConnectorInstance.__tablename__ == "kms_connector_instance"
    assert ConnectorSyncLog.__tablename__ == "kms_connector_sync_log"
    for col in ("code", "connector_type", "target_collection", "sync_interval_min", "status"):
        assert col in ConnectorInstance.__table__.c
    for col in ("instance_id", "status", "added", "cursor_value", "duration_ms"):
        assert col in ConnectorSyncLog.__table__.c


@pytest.mark.parametrize(
    "module",
    ["app.routers.connectors.connector", "app.routers.wiki.wiki_admin", "app.routers.ontology.ontology"],
)
def test_routers_registered(module):
    """此前三个模块未进清单 → 前端请求 404 / routerMissing。"""
    assert any(spec.module == module and spec.enabled for spec in ROUTER_SPECS)


def test_article_okf_columns_added():
    for col in ("okf_type", "resource", "sources", "verified", "stale_after"):
        assert col in WikiArticle.__table__.c


class _FakeVersion:
    def __init__(self, article_id, version, content):
        self.id = version
        self.article_id = article_id
        self.version = version
        self.content = content
        self.title = f"t{version}"
        self.slug = f"s{version}"
        self.summary = None
        self.owl_class_uris = None


class _FakeDB:
    """最小替身：按主键返回预置对象。"""

    def __init__(self, objs):
        self._objs = objs
        self.added = []

    def get(self, model, pk):  # noqa: ANN001 - 测试替身
        return self._objs.get((model, pk))

    def add(self, obj):  # noqa: ANN001 - 测试替身
        self.added.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):  # noqa: ANN001 - 测试替身
        return None


def _fake_article(version: int, content: str):
    """构造具备 _serialize 所需字段的文章替身。"""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=1, slug="s", title=f"t{version}", content=content, summary=None,
        category_id=None, tags=[], owl_class_uris=[], wiki_links=[], backlinks=[],
        status=1, is_featured=False, view_count=0, version=version,
        creator_id=1, updater_id=1, created_at=None, updated_at=None,
    )


def test_version_diff_vs_current_and_between_versions():
    from app.models.wiki.wiki_article_version import WikiArticleVersion
    from app.services.wiki.version_service import WikiVersionService

    article = _fake_article(3, "new\nline")
    v1 = _FakeVersion(1, 1, "old\nline")
    v2 = _FakeVersion(1, 2, "mid\nline")
    db = _FakeDB({
        (WikiArticle, 1): article,
        (WikiArticleVersion, 1): v1,
        (WikiArticleVersion, 2): v2,
    })
    svc = WikiVersionService(db)

    # 缺省对照当前版本
    diff = svc.get_diff(1, 1)
    assert diff["base_version"] == 1 and diff["target_version"] == 3
    assert "-old" in diff["diff"] and "+new" in diff["diff"]

    # 指定 target 时为两历史版本互比
    diff2 = svc.get_diff(1, 1, target_version_id=2)
    assert diff2["target_version"] == 2
    assert "-old" in diff2["diff"] and "+mid" in diff2["diff"]


def test_rollback_creates_new_version_without_touching_history():
    from app.models.wiki.wiki_article_version import WikiArticleVersion
    from app.services.wiki.version_service import WikiVersionService

    article = _fake_article(3, "new\nline")
    v1 = _FakeVersion(1, 1, "old\nline")
    db = _FakeDB({(WikiArticle, 1): article, (WikiArticleVersion, 1): v1})
    svc = WikiVersionService(db)

    result = svc.rollback(1, 1, type("U", (), {"id": 9})())

    # 非破坏式：生成 max+1 新版本，正文回到历史内容，历史版本对象不变
    assert article.version == 4
    assert article.content == "old\nline"
    assert v1.version == 1 and v1.content == "old\nline"
    snapshot = db.added[-1]
    assert snapshot.version == 4 and snapshot.operation_type == "rollback"
    assert result["version"] == 4


def test_job_runner_swallows_exceptions():
    """后台任务失败不得回抛到请求链路（P0-5）。"""
    from app.core import job_runner

    def _boom():
        raise RuntimeError("boom")

    thread = job_runner.run_in_background(_boom, name="unit-boom")
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert job_runner.pending_tasks()["unit-boom"] is False
