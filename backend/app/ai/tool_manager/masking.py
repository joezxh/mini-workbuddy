"""列级脱敏引擎。

按 ``config_value.masking`` 规则与当前用户角色，对结果集中的敏感字段执行
掩码 / 哈希 / 隐藏 / 截断。脱敏在结果返回前的最后阶段执行，是与行级兜底
过滤并列的真实安全边界。

规范：脱敏前的原始值**禁止**写入任何日志。
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.ai.tool_manager.sqlbot_tool_config import MaskingConfig, MaskingRule, MaskStrategy
from app.ai.tool_manager.tool_context import ToolUserContext

logger = logging.getLogger(__name__)

__all__ = ["apply_masking", "mask_value", "guess_strategy_for_field"]

# 常用敏感字段的默认掩码参数（字段名小写匹配）
_BUILTIN_PRESETS: Dict[str, Tuple[int, int]] = {
    "id_card": (6, 4),
    "idcard": (6, 4),
    "identity_card": (6, 4),
    "id_number": (6, 4),
    "phone": (3, 4),
    "mobile": (3, 4),
    "tel": (3, 4),
    "telephone": (3, 4),
    "contact_phone": (3, 4),
    "name": (1, 0),
    "real_name": (1, 0),
    "person_name": (1, 0),
    "bank_card": (4, 4),
    "email": (2, 0),
}

_SENSITIVE_HINTS = re.compile(
    r"(id_?card|identity|phone|mobile|tel|bank_?card|address|email|real_?name)", re.I
)


def guess_strategy_for_field(field: str) -> Tuple[int, int]:
    """依据字段名推测掩码保留位数，未命中返回 (0, 0)（全掩码）。"""
    return _BUILTIN_PRESETS.get(str(field).lower(), (0, 0))


def _hash_value(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def mask_value(value: Any, rule: MaskingRule) -> Any:
    """对单个值执行脱敏。"""
    if value is None:
        return None

    if rule.strategy == MaskStrategy.HASH:
        return _hash_value(str(value))

    text = str(value)

    if rule.strategy == MaskStrategy.TRUNCATE:
        limit = rule.max_length if rule.max_length and rule.max_length > 0 else 6
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    # MASK
    keep_prefix = rule.keep_prefix
    keep_suffix = rule.keep_suffix
    if keep_prefix == 0 and keep_suffix == 0:
        keep_prefix, keep_suffix = guess_strategy_for_field(rule.field)

    mask_char = rule.mask_char or "*"
    length = len(text)
    if length <= keep_prefix + keep_suffix:
        # 太短无法保留两端，整体掩码但保留长度信息
        return mask_char * max(length, 1)

    masked_len = length - keep_prefix - keep_suffix
    prefix = text[:keep_prefix] if keep_prefix else ""
    suffix = text[length - keep_suffix:] if keep_suffix else ""
    return f"{prefix}{mask_char * masked_len}{suffix}"


def _resolve_field_key(row: Dict[str, Any], field: str) -> Optional[str]:
    """在行中定位字段（兼容大小写差异）。"""
    if field in row:
        return field
    lowered = {str(k).lower(): k for k in row}
    return lowered.get(field.lower())


def apply_masking(
    rows: List[Dict[str, Any]],
    masking: MaskingConfig,
    user: Optional[ToolUserContext],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """对结果集执行列级脱敏。

    :return: ``(rows, applied_fields)``，``applied_fields`` 为实际生效的字段名
    """
    if not masking.enabled or not masking.rules or not rows:
        return rows, []

    # 计算生效规则（剔除当前用户免脱敏的）
    effective: List[MaskingRule] = []
    for rule in masking.rules:
        if user is not None and user.is_admin and rule.exempt_roles:
            # admin 仅在规则显式配置了豁免角色时才免脱敏，避免默认过度放权
            pass
        if user is not None and rule.exempt_roles and user.has_any_role(rule.exempt_roles):
            continue
        effective.append(rule)

    if not effective:
        return rows, []

    applied: set[str] = set()
    result: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            result.append(row)
            continue
        new_row = dict(row)
        for rule in effective:
            key = _resolve_field_key(new_row, rule.field)
            if key is None:
                continue
            if rule.strategy == MaskStrategy.DROP:
                new_row.pop(key, None)
            else:
                new_row[key] = mask_value(new_row[key], rule)
            applied.add(rule.field)
        result.append(new_row)

    if applied:
        # 只记录字段名，绝不记录原始值
        logger.info("列级脱敏生效字段: %s", sorted(applied))

    return result, sorted(applied)


def detect_unmasked_sensitive_fields(
    rows: List[Dict[str, Any]], masking: MaskingConfig
) -> List[str]:
    """检测结果集中疑似敏感但未配置脱敏的字段（配置期/审计告警用）。"""
    if not rows:
        return []
    sample = next((r for r in rows if isinstance(r, dict)), None)
    if not sample:
        return []
    configured = {r.field.lower() for r in masking.rules} if masking.enabled else set()
    suspects = [
        str(k)
        for k in sample
        if _SENSITIVE_HINTS.search(str(k)) and str(k).lower() not in configured
    ]
    return sorted(suspects)
