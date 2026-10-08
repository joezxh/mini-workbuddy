"""摄取编排执行器（spec §10.7 / D8）：dry-run 与真实 ingest 共用同一条链路。

断言点：
1. ``pipeline_config`` 的 parser/clean/chunker 段零转换生效；
2. dry-run 与真实摄取共用入口 → 同配置两次执行产物完全一致（预览即落库）；
3. 未知 parser/clean/chunker 显式失败且带步名（§10.7 单步可观测）；
4. 按 collection 名反查知识库编排配置。
"""
from __future__ import annotations

import pytest

from app.services.kb.pipeline_config import resolve_knowledge_pipeline_config
from app.services.kb.pipeline_runner import (
    PipelinePlan,
    PipelineStepError,
    run_pipeline_from_config,
)

MD = "# 标题\n\n第一段 https://example.com/a 内容。\n\n\n第二段 内容。\n"


class _Kn:
    def __init__(self, pc):
        self.pipeline_config = pc


class _FakeDB:
    """仅提供 ``get`` 的最小会话替身（避开真实 WikiKnowledge 建表）。"""

    def __init__(self, kn=None):
        self._kn = kn

    def get(self, model, pk):  # noqa: ARG002
        return self._kn if pk == 7 else None


def test_plan_chunk_segment_overrides_flat_params():
    plan = PipelinePlan.from_config(
        {"chunker": {"type": "qa", "params": {}}},
        chunker_type="approx_token",
        chunker_params={"chunk_size": 64},
    )
    assert plan.chunker_type == "qa"
    assert plan.chunker_params == {}


def test_plan_extracts_parser_and_clean():
    plan = PipelinePlan.from_config({
        "parser": {"type": "TextParser"},
        "clean": ["remove_urls"],
        "chunker": {"type": "approx_token", "params": {"chunk_size": 32}},
    })
    assert plan.parser_type == "TextParser"
    assert plan.clean == ["remove_urls"]
    assert plan.chunker_params == {"chunk_size": 32}


def test_pipeline_applies_clean_operators():
    run = run_pipeline_from_config(
        MD.encode("utf-8"), "a.md",
        pipeline_config={"clean": ["remove_urls", "remove_extra_spaces"]},
    )
    joined = "".join(s.content.text for s in run.sections)
    assert "example.com" not in joined
    assert "\n\n\n" not in joined
    assert run.steps[1]["step"] == "clean"


def test_pipeline_same_config_same_chunks_for_dryrun_and_ingest():
    """同一配置两次执行产物一致 → dry-run 预览即真实落库结果。"""
    cfg = {"chunker": {"type": "approx_token", "params": {"chunk_size": 64, "overlap": 8}}}
    a = run_pipeline_from_config(MD.encode("utf-8"), "a.md", pipeline_config=cfg)
    b = run_pipeline_from_config(MD.encode("utf-8"), "a.md", pipeline_config=cfg)
    assert [c.content.text for c in a.chunks] == [c.content.text for c in b.chunks]
    assert a.to_preview()["chunks"] == b.to_preview()["chunks"]


@pytest.mark.parametrize("cfg,step", [
    ({"clean": ["nope"]}, "clean"),
    ({"parser": {"type": "NopeParser"}}, "parse"),
])
def test_pipeline_unknown_type_raises_step_error(cfg, step):
    with pytest.raises(PipelineStepError) as ei:
        run_pipeline_from_config(MD.encode("utf-8"), "a.md", pipeline_config=cfg)
    assert ei.value.step == step


def test_pipeline_unknown_chunker_raises_step_error():
    with pytest.raises(PipelineStepError) as ei:
        run_pipeline_from_config(MD.encode("utf-8"), "a.md", chunker_type="nonexistent")
    assert ei.value.step == "chunk"


def test_resolve_knowledge_pipeline_config_by_collection():
    db = _FakeDB(_Kn({"chunker": {"type": "approx_token"}}))
    assert resolve_knowledge_pipeline_config(db, "kb_7") == {
        "chunker": {"type": "approx_token"}
    }
    assert resolve_knowledge_pipeline_config(db, "kb_8") is None
    assert resolve_knowledge_pipeline_config(db, "other") is None


def test_resolve_knowledge_pipeline_config_rejects_unknown_key():
    with pytest.raises(ValueError):
        resolve_knowledge_pipeline_config(_FakeDB(_Kn({"bogus": {}})), "kb_7")
