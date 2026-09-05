"""行级数据权限：区域范围解析、受控参数生成与兜底行过滤。

在 NL2SQL 路径下无法像手写 SQL 那样安全地拼接 ``WHERE``，因此设计三重保障：

1. **参数层** —— 将用户辖区解析为受控占位符文本，注入提问模板；
2. **约束层** —— 将区域限制写入提问的约束说明，提高 SQL 正确率；
3. **兜底层** —— 对返回结果做强制行过滤。**这一层才是真正的安全边界**，
   即使 SQLBot 生成的 SQL 越权，越权数据也不会返回给调用方。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.ai.tool_manager.sqlbot_tool_config import RowScopeConfig
from app.ai.tool_manager.tool_context import ToolUserContext

logger = logging.getLogger(__name__)

__all__ = [
    "ScopeDecision",
    "resolve_scope",
    "build_scope_text",
    "filter_rows",
]

# 单次提问中最多列举的区域码个数，超出则改用概括描述
_MAX_LISTED_REGIONS = 20


@dataclass(frozen=True)
class ScopeDecision:
    """区域范围裁决结果。"""

    # 是否需要施加区域限制
    enforced: bool
    # 允许的区域码集合（enforced=False 时无意义）
    region_codes: tuple[str, ...]
    # 注入提问的区域描述文本
    scope_text: str
    # 是否应直接拒绝执行（无上下文 / 无任何辖区）
    denied: bool = False
    reason: str = ""


def resolve_scope(
    scope_cfg: RowScopeConfig,
    user: Optional[ToolUserContext],
    allow_anonymous: bool = False,
) -> ScopeDecision:
    """裁决当前用户的区域数据范围。

    安全约定：取不到用户上下文时**不默认放行**。
    """
    if not scope_cfg.enabled:
        return ScopeDecision(enforced=False, region_codes=(), scope_text="")

    if user is None:
        if allow_anonymous:
            logger.warning("行级权限：无用户上下文，但配置允许匿名执行，跳过区域限制")
            return ScopeDecision(enforced=False, region_codes=(), scope_text="")
        return ScopeDecision(
            enforced=True,
            region_codes=(),
            scope_text="",
            denied=True,
            reason="无法获取当前用户上下文，已按最严格策略拒绝执行",
        )

    if user.is_admin or user.is_global_scope:
        return ScopeDecision(enforced=False, region_codes=(), scope_text="")

    if scope_cfg.bypass_roles and user.has_any_role(scope_cfg.bypass_roles):
        return ScopeDecision(enforced=False, region_codes=(), scope_text="")

    if not user.region_codes:
        return ScopeDecision(
            enforced=True,
            region_codes=(),
            scope_text="",
            denied=True,
            reason="当前用户未配置任何辖区，无数据查看权限",
        )

    codes = tuple(user.region_codes)
    return ScopeDecision(
        enforced=True,
        region_codes=codes,
        scope_text=build_scope_text(codes, scope_cfg.region_field),
    )


def build_scope_text(region_codes: Sequence[str], region_field: str = "region_code") -> str:
    """将区域码集合转为可嵌入提问的自然语言描述。"""
    codes = [c for c in region_codes if c]
    if not codes:
        return ""
    if len(codes) <= _MAX_LISTED_REGIONS:
        listed = "、".join(codes)
        return f"{region_field} 属于 [{listed}] 的数据"
    head = "、".join(codes[:_MAX_LISTED_REGIONS])
    return (
        f"{region_field} 属于 [{head}] 等共 {len(codes)} 个区域的数据"
    )


def _row_region(row: Dict[str, Any], region_field: str) -> Tuple[bool, Optional[str]]:
    """从结果行中取区域值，兼容字段大小写与常见别名。"""
    if region_field in row:
        return True, row[region_field]
    lowered = {str(k).lower(): k for k in row}
    key = lowered.get(region_field.lower())
    if key is not None:
        return True, row[key]
    return False, None


def filter_rows(
    rows: List[Dict[str, Any]],
    decision: ScopeDecision,
    scope_cfg: RowScopeConfig,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    """对结果集执行兜底强制行过滤。

    :return: ``(kept_rows, filtered_count, field_missing)``
    """
    if not decision.enforced or not rows:
        return rows, 0, False

    allowed = set(decision.region_codes)
    if not allowed:
        # 无任何辖区 → 全部丢弃
        return [], len(rows), False

    region_field = scope_cfg.region_field
    kept: List[Dict[str, Any]] = []
    filtered = 0
    missing_count = 0

    for row in rows:
        if not isinstance(row, dict):
            # 非字典行无法判定归属，按严格策略丢弃
            filtered += 1
            continue
        found, value = _row_region(row, region_field)
        if not found:
            missing_count += 1
            continue
        if value is None:
            filtered += 1
            continue
        if str(value) in allowed:
            kept.append(row)
        else:
            filtered += 1

    field_missing = missing_count == len(rows) and missing_count > 0

    if field_missing:
        # 整个结果集都没有区域字段（典型：聚合统计结果）
        if scope_cfg.on_missing_field == "strict":
            logger.warning(
                "行级权限：结果集缺少区域字段 %s，strict 模式下已清空结果", region_field
            )
            return [], len(rows), True
        logger.info(
            "行级权限：结果集缺少区域字段 %s，lenient 模式下放行（已在提问中施加区域约束）",
            region_field,
        )
        return rows, 0, True

    if missing_count:
        # 部分行缺字段：按严格策略计入过滤
        filtered += missing_count

    if filtered:
        logger.warning(
            "行级权限兜底过滤生效：丢弃 %s 行越权数据（字段=%s）", filtered, region_field
        )
    return kept, filtered, False
