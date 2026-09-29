"""SOP 模板库 —— 内置模板与行业预设模板的统一注册表。

spec: docs/design/sop-assistant-mode-design.md §4.3 / §4.6

注册表是**代码侧的权威来源**：数据库 ``sop_templates`` 表由种子服务
按此播种；前端模板选择器经 API 读取；``thinking`` / ``deep_research``
两种内置模式经 ``SOURCE_TO_TEMPLATE`` 直接解析到对应骨架。
"""
from __future__ import annotations

from typing import List, Optional

from .builtin import BUILTIN_RESEARCH, BUILTIN_THINKING, BUILTIN_TEMPLATES
from .finance import FINANCE_TEMPLATES
from .growth import GROWTH_TEMPLATES
from .spec import SOPTemplateSpec

# 全部模板：2 个内置 + 7 个金融 + 5 个营销/自媒体
ALL_TEMPLATES: List[SOPTemplateSpec] = [
    *BUILTIN_TEMPLATES,
    *FINANCE_TEMPLATES,
    *GROWTH_TEMPLATES,
]

_BY_ID = {t.id: t for t in ALL_TEMPLATES}
if len(_BY_ID) != len(ALL_TEMPLATES):  # pragma: no cover - 启动期自检
    raise ValueError("SOP 模板 id 重复，注册表不可用")

# 模式 → 内置模板（供 AgentFactory 下沉 thinking / deep_research 使用）
SOURCE_TO_TEMPLATE = {
    "builtin:thinking": BUILTIN_THINKING.id,
    "builtin:research": BUILTIN_RESEARCH.id,
}


def get_template(template_id: str) -> Optional[SOPTemplateSpec]:
    """按 id 取模板；不存在返回 None（由调用方决定兜底）。"""
    return _BY_ID.get(template_id)


def resolve_source(source: str) -> Optional[SOPTemplateSpec]:
    """按内置模式标识（如 ``builtin:thinking``）取模板。"""
    template_id = SOURCE_TO_TEMPLATE.get(source)
    return _BY_ID.get(template_id) if template_id else None


def match_templates(keyword: str = "", limit: int = 50) -> List[SOPTemplateSpec]:
    """关键词匹配（id/名称/描述/标签子串），空关键词返回全部。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return ALL_TEMPLATES[:limit]
    return [t for t in ALL_TEMPLATES if kw in t.keywords.lower()][:limit]


def template_ids() -> List[str]:
    return [t.id for t in ALL_TEMPLATES]


__all__ = [
    "SOPTemplateSpec",
    "ALL_TEMPLATES",
    "BUILTIN_TEMPLATES",
    "FINANCE_TEMPLATES",
    "GROWTH_TEMPLATES",
    "BUILTIN_THINKING",
    "BUILTIN_RESEARCH",
    "SOURCE_TO_TEMPLATE",
    "get_template",
    "resolve_source",
    "match_templates",
    "template_ids",
]
