"""SOP 模板服务测试 —— 用 SQLite 内存库验证播种幂等与 CRUD（不依赖 Postgres）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.sop.schemas import SOPDefinition, SOPStepDef
from app.models.sop import SOPTemplate
from app.services.sop_service import SOPTemplateService


@pytest.fixture()
def db():
    """每个用例一个干净的内存库，只建 sop_templates 表。"""
    engine = create_engine("sqlite:///:memory:")
    SOPTemplate.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _custom_definition() -> dict:
    return SOPDefinition(
        name="自定义流程",
        steps=[SOPStepDef(subject="一步", description="完成")],
    ).model_dump(mode="json")


def test_seed_creates_all_registry_templates(db):
    """播种应落地全部 14 个注册表模板。"""
    result = SOPTemplateService(db).seed()

    assert result["created"] == 14
    assert db.query(SOPTemplate).count() == 14


def test_seed_is_idempotent_and_only_refreshes_builtin(db):
    """重复播种不重复插入；仅内置模板（2 个）被刷新，预设跳过以保留用户改动。"""
    service = SOPTemplateService(db)
    service.seed()
    second = service.seed()

    assert second["created"] == 0
    assert second["updated"] == 2
    assert second["skipped"] == 12
    assert db.query(SOPTemplate).count() == 14


def test_seed_persists_definition_as_json_serializable(db):
    """definition 落库后仍是纯 JSON（枚举已转成字符串），可被前端直接使用。"""
    service = SOPTemplateService(db)
    service.seed()

    row = service.get_by_key("builtin_thinking")
    assert row is not None
    assert row.builtin is True
    first_step = row.definition["steps"][0]
    assert first_step["subject"] == "理解问题"
    assert first_step["verifier_type"] == "ai"  # 枚举已序列化为字符串


def test_list_templates_filters_by_keyword(db):
    service = SOPTemplateService(db)
    service.seed()

    assert len(service.list_templates()) == 14
    assert len(service.list_templates(keyword="巴菲特")) == 1
    assert service.list_templates(keyword="不存在的关键词") == []


def test_create_update_and_delete_custom_template(db):
    service = SOPTemplateService(db)

    row = service.create(
        {
            "template_key": "custom_x",
            "name": "自定义流程",
            "description": "我的流程",
            "tags": ["自定义"],
            "definition": _custom_definition(),
            "builtin": False,
            "enabled": True,
        }
    )
    assert row.id is not None
    assert service.get_by_key("custom_x") is not None

    service.update(row, {"name": "改过的名字", "enabled": False})
    assert service.get(row.id).name == "改过的名字"
    # 停用后默认列表不可见
    assert service.get(row.id) not in service.list_templates()
    assert service.get(row.id) in service.list_templates(include_disabled=True)

    service.delete(row)
    assert service.get_by_key("custom_x") is None
