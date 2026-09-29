"""SOP 模板库单元测试 —— 校验注册表完整性（离线，不依赖 DB）。"""
from __future__ import annotations

from app.ai.sop.templates import (
    ALL_TEMPLATES,
    get_template,
    match_templates,
    resolve_source,
    template_ids,
)
from app.ai.sop.schemas import SOPDefinition


def test_registry_has_expected_templates():
    """注册表应含 2 内置 + 7 金融 + 5 营销/自媒体 = 14 个模板。"""
    assert len(ALL_TEMPLATES) == 14
    assert len(set(template_ids())) == 14


def test_every_template_definition_is_executable():
    """每个模板的每一步都要有可验收的终点描述与合法的重试配置。"""
    for template in ALL_TEMPLATES:
        assert isinstance(template.definition, SOPDefinition), template.id
        assert template.definition.steps, f"{template.id} 无步骤"
        for step in template.definition.steps:
            assert step.subject.strip(), f"{template.id} 存在空步骤名"
            assert step.description.strip(), f"{template.id}/{step.subject} 缺终点描述"
            assert step.max_attempts >= 1
            if step.loop == "goal":
                assert step.goal_max_iters >= 1


def test_finance_templates_require_human_signoff():
    """涉及真金白银的金融模板必须至少有一道人工把关步骤。"""
    finance = [t for t in ALL_TEMPLATES if "金融" in t.tags]
    assert len(finance) == 7
    for template in finance:
        assert any(
            s.verifier_type == "human" for s in template.definition.steps
        ), f"{template.id} 缺少人工验收步骤"


def test_match_templates_by_keyword():
    """关键词命中 id/名称/描述/标签。"""
    assert any(t.id == "buffett_value_investing" for t in match_templates("巴菲特"))
    assert any(t.id == "uzi_dragon_head" for t in match_templates("游资"))
    assert any(t.id == "selfmedia_content_ops" for t in match_templates("自媒体"))
    assert match_templates("完全不存在的关键词") == []
    assert len(match_templates("")) == 14


def test_builtin_sources_resolve_to_templates():
    """thinking / deep_research 模式可解析到内置骨架。"""
    assert resolve_source("builtin:thinking").id == "builtin_thinking"
    assert resolve_source("builtin:research").id == "builtin_research"
    assert resolve_source("builtin:unknown") is None
    assert get_template("nope") is None


def test_builtin_research_uses_parallel_search_group():
    """研究模板的检索步应为并行组，且产出 research* 产物键（§4.6）。"""
    research = resolve_source("builtin:research")
    search_step = next(
        s for s in research.definition.steps if s.subject == "拆分子问题并行检索"
    )
    assert search_step.exec_mode == "parallel"
    assert search_step.group_id == "subq"
    keys = {s.artifact_key for s in research.definition.steps if s.artifact_key}
    assert {"researchPlan", "researchSources", "researchReport"} <= keys
