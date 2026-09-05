"""安全的提问模板渲染 + 参数校验。

安全红线：**禁止使用 ``str.format()`` / f-string / eval 渲染模板**。
``"{x.__class__}".format(x=obj)`` 可触发属性遍历，导致对象内部信息泄露。
本模块只做白名单占位符的正则替换，且仅替换配置中显式声明的参数名。
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.ai.tool_manager.sqlbot_tool_config import (
    PLACEHOLDER_PATTERN,
    ParamType,
    ParameterDef,
    SqlBotToolConfig,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ParamValidationError",
    "validate_inputs",
    "render_question",
    "sanitize_value",
]

# 控制字符 + 换行 —— 防止提问被截断或注入额外指令
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DEFAULT_MAX_LENGTH = 128


class ParamValidationError(ValueError):
    """参数校验失败。"""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def sanitize_value(value: Any, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """将参数值清洗为可安全嵌入自然语言提问的字符串。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        parts = [sanitize_value(v, max_length) for v in value]
        text = "、".join(p for p in parts if p)
    else:
        text = str(value)

    text = _CONTROL_CHARS.sub(" ", text)
    # 花括号会干扰后续占位符识别，一律剔除
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    limit = max_length if max_length and max_length > 0 else _DEFAULT_MAX_LENGTH
    if len(text) > limit:
        text = text[:limit]
    return text


def _coerce(param: ParameterDef, raw: Any) -> Tuple[Any, Optional[str]]:
    """按声明类型转换并校验单个参数值。返回 ``(value, error)``。"""
    name = param.name
    if param.type == ParamType.INTEGER:
        try:
            if isinstance(raw, bool):
                raise ValueError
            return int(raw), None
        except (TypeError, ValueError):
            return None, f"参数 {name} 应为整数，得到: {raw!r}"

    if param.type == ParamType.NUMBER:
        try:
            if isinstance(raw, bool):
                raise ValueError
            return float(raw), None
        except (TypeError, ValueError):
            return None, f"参数 {name} 应为数字，得到: {raw!r}"

    if param.type == ParamType.BOOLEAN:
        if isinstance(raw, bool):
            return raw, None
        if isinstance(raw, str) and raw.lower() in ("true", "false", "1", "0", "是", "否"):
            return raw.lower() in ("true", "1", "是"), None
        return None, f"参数 {name} 应为布尔值，得到: {raw!r}"

    if param.type == ParamType.ENUM:
        candidates = param.enum or []
        if raw in candidates:
            return raw, None
        if str(raw) in [str(c) for c in candidates]:
            return str(raw), None
        return None, f"参数 {name} 取值非法，应为 {candidates} 之一，得到: {raw!r}"

    if param.type == ParamType.DATE:
        if isinstance(raw, (datetime, date)):
            return raw.isoformat()[:10], None
        text = str(raw).strip()
        if not _DATE_PATTERN.match(text):
            return None, f"参数 {name} 应为 YYYY-MM-DD 格式日期，得到: {raw!r}"
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None, f"参数 {name} 不是合法日期: {raw!r}"
        return text, None

    # string
    text = str(raw)
    if param.max_length and len(text) > int(param.max_length):
        return None, f"参数 {name} 长度超过上限 {param.max_length}"
    return text, None


def validate_inputs(
    config: SqlBotToolConfig, inputs: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """校验并归一化调用方传入的参数。

    - 未声明的参数一律丢弃（不透传给 SQLBot）
    - 缺失必填参数、类型/枚举/范围不符 → 抛 :class:`ParamValidationError`
    - 未传且有默认值的参数自动填充默认值

    :raises ParamValidationError: 校验失败
    """
    inputs = inputs or {}
    errors: List[str] = []
    resolved: Dict[str, Any] = {}

    declared_names = {p.name for p in config.parameters}
    unknown = set(inputs) - declared_names
    if unknown:
        logger.info("忽略未声明参数: %s", sorted(unknown))

    for param in config.parameters:
        if param.name in inputs and inputs[param.name] is not None:
            raw = inputs[param.name]
        elif param.default is not None:
            raw = param.default
        elif param.required:
            errors.append(f"缺少必填参数: {param.name}({param.label or param.name})")
            continue
        else:
            resolved[param.name] = None
            continue

        value, err = _coerce(param, raw)
        if err:
            errors.append(err)
            continue

        if param.minimum is not None and isinstance(value, (int, float)):
            if value < param.minimum:
                errors.append(f"参数 {param.name} 不得小于 {param.minimum}")
                continue
        if param.maximum is not None and isinstance(value, (int, float)):
            if value > param.maximum:
                errors.append(f"参数 {param.name} 不得大于 {param.maximum}")
                continue

        resolved[param.name] = value

    if errors:
        raise ParamValidationError(errors)
    return resolved


def render_question(
    config: SqlBotToolConfig,
    values: Dict[str, Any],
    scope_text: str = "",
) -> str:
    """渲染提问模板。

    :param values: 已通过 :func:`validate_inputs` 校验的参数
    :param scope_text: 受控区域描述文本，填充 ``rowScope.scopePlaceholder``；
                       该值由系统生成，**强制覆盖**用户同名输入
    """
    replacements: Dict[str, str] = {}
    for param in config.parameters:
        value = values.get(param.name)
        replacements[param.name] = sanitize_value(
            value, param.max_length or _DEFAULT_MAX_LENGTH
        )

    # 受控占位符最后写入，确保不被用户参数覆盖
    scope_name = config.row_scope.scope_placeholder
    replacements[scope_name] = sanitize_value(scope_text, 512)

    unknown_used: List[str] = []

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key in replacements:
            return replacements[key]
        unknown_used.append(key)
        return match.group(0)  # 未声明占位符原样保留

    question = PLACEHOLDER_PATTERN.sub(_replace, config.question_template)

    if unknown_used:
        logger.warning(
            "提问模板存在未声明占位符（已原样保留）: %s", sorted(set(unknown_used))
        )

    # 清理因空参数留下的多余空白
    question = re.sub(r"[ \t]+", " ", question).strip()
    return question


def build_constraint_text(
    config: SqlBotToolConfig, scope_text: str = "", max_rows: int = 0
) -> str:
    """组装追加到提问后的约束说明（表白名单 / 区域 / 行数）。

    注意：这是**提示层**约束，用于提高 NL2SQL 正确率，
    不具备强制阻断能力。真实安全边界是返回结果的兜底行过滤与列脱敏。
    """
    clauses: List[str] = []
    if config.allowed_tables:
        clauses.append(
            "只允许查询以下数据表：" + "、".join(config.allowed_tables) + "，不得访问其他表"
        )
    if scope_text:
        clauses.append(f"数据范围限定为{scope_text}")
    if max_rows > 0:
        clauses.append(f"返回结果不超过 {max_rows} 行")
    for rule in config.extra_rules:
        text = sanitize_value(rule, 256)
        if text:
            clauses.append(text)
    if not clauses:
        return ""
    return "（约束：" + "；".join(clauses) + "）"
