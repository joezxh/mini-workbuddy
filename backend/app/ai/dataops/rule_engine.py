"""规则标注引擎（P2 Task 12）。

⚠️ 归属与边界
-----------------------------------------------------------
本文件是 **P2（业务数据集成）Task 12「规则标注引擎 + 置信度分层」** 的归属地，
也是 P4（本体层）候选生成**共用**的阈值单一事实来源：
- `CONF_AUTO_ACCEPT` / `CONF_SUGGEST_MIN` 仅此一处定义（P4 Task 5 已 import 引用）。
- Task 12 在本文件扩展规则标注本体：PII 识别 / 语义类型判定 / 标准项匹配 /
  三方投票关系推断的置信度分层。

分层语义（P2/P4 共用，参数化测试为权威）
-----------------------------------------------------------
* `confidence >= CONF_AUTO_ACCEPT (0.85)` → accepted（自动接受）
* `CONF_SUGGEST_MIN (0.65) <= confidence` → suggested（进入人工评审）
* `confidence < CONF_SUGGEST_MIN`        → drop（不生成候选）
* `confidence is None`                   → suggested（未评分走人工兜底）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

#: 自动接受阈值：置信度 ≥ 此值的标注直接落为 accepted（无需人工评审）。
CONF_AUTO_ACCEPT = 0.85

#: 建议阈值：置信度 ∈ [CONF_SUGGEST_MIN, CONF_AUTO_ACCEPT) 的落为 suggested
#: （进入人工评审队列）；低于此值不生成候选。
CONF_SUGGEST_MIN = 0.65

#: 评审状态常量（与 meta_column_standard / 本体层 status 对齐）
TIER_ACCEPTED = "accepted"
TIER_SUGGESTED = "suggested"
TIER_DROP = "drop"

__all__ = [
    "CONF_AUTO_ACCEPT",
    "CONF_SUGGEST_MIN",
    "TIER_ACCEPTED",
    "TIER_SUGGESTED",
    "TIER_DROP",
    "tier",
    "AnnotationResult",
    "RuleEngine",
    "BUILTIN_STANDARDS",
]


def tier(confidence: Optional[float], *, none_means: str = TIER_SUGGESTED) -> str:
    """按置信度分层返回评审状态（P2/P4 共用语义）。

    None → ``none_means``（默认 suggested：未评分走人工兜底）。
    """
    if confidence is None:
        return none_means
    if confidence >= CONF_AUTO_ACCEPT:
        return TIER_ACCEPTED
    if confidence >= CONF_SUGGEST_MIN:
        return TIER_SUGGESTED
    return TIER_DROP


# ── PII / 语义类型识别规则 ──────────────────────────────────────────────────
# 每条规则：name 命中列名/注释 → 名称证据；value_regex 命中样本值 → 强证据。
# 列名命中给较高置信度，样本值命中给近满置信度（最具象证据）。
_PII_RULES: List[Dict] = [
    {
        "semantic_type": "phone", "pii_level": "L3", "name_conf": 0.9, "value_conf": 0.95,
        "name_regex": r"(?i)(phone|mobile|cellphone|telephone|手机|电话|手机号|座机)",
        "value_regex": r"^1[3-9]\d{9}$",
    },
    {
        "semantic_type": "email", "pii_level": "L3", "name_conf": 0.88, "value_conf": 0.95,
        "name_regex": r"(?i)(email|e_mail|mail|邮箱|电子邮件|邮件)",
        "value_regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    },
    {
        "semantic_type": "id_card", "pii_level": "L3", "name_conf": 0.9, "value_conf": 0.96,
        "name_regex": r"(?i)(id_?card|idcard|身份证|证件号|证件号码)",
        "value_regex": r"^\d{17}[\dXx]$",
    },
    {
        "semantic_type": "person_name", "pii_level": "L2", "name_conf": 0.8, "value_conf": 0.7,
        "name_regex": r"(?i)(user_?name|real_?name|full_?name|name|姓名|用户名|真实姓名)",
        "value_regex": None,
    },
    {
        "semantic_type": "user_id", "pii_level": "L1", "name_conf": 0.82, "value_conf": 0.6,
        "name_regex": r"(?i)(user_?id|uid|用户id|用户_?id|会员id)",
        "value_regex": None,
    },
    {
        "semantic_type": "address", "pii_level": "L2", "name_conf": 0.78, "value_conf": 0.6,
        "name_regex": r"(?i)(address|addr|地址|收货地址|居住地址)",
        "value_regex": None,
    },
    {
        "semantic_type": "gender", "pii_level": "L1", "name_conf": 0.75, "value_conf": 0.6,
        "name_regex": r"(?i)(gender|sex|性别)",
        "value_regex": None,
    },
    {
        "semantic_type": "amount", "pii_level": "L0", "name_conf": 0.7, "value_conf": 0.6,
        "name_regex": r"(?i)(amount|price|money|fee|cost|金额|价格|费用|余额|单价)",
        "data_type_hint": ("numeric", "decimal", "money", "double", "real", "integer", "bigint"),
    },
    {
        "semantic_type": "datetime", "pii_level": "L0", "name_conf": 0.72, "value_conf": 0.6,
        "name_regex": r"(?i)(created_?at|updated_?at|create_?time|update_?time|timestamp|时间|日期|时间戳)",
        "data_type_hint": ("timestamp", "date", "timestamptz", "time"),
    },
]


@dataclass
class AnnotationResult:
    """单条列的规则标注结果。"""

    semantic_type: Optional[str] = None
    pii_level: Optional[str] = None
    confidence: Optional[float] = None
    evidence: Dict = field(default_factory=dict)


class RuleEngine:
    """规则标注引擎（纯函数，无 DB 依赖，便于单测）。"""

    # pylint: disable=too-many-arguments
    @staticmethod
    def detect_semantic(
        column_name: str,
        data_type: Optional[str] = None,
        comment: Optional[str] = None,
        profile_top_values: Optional[List[Dict]] = None,
    ) -> AnnotationResult:
        """识别列的语义类型与 PII 等级。

        证据优先级：样本值命中 value_regex（最具体）→ 列名/注释命中 name_regex
        → 数据类型暗示。取最高分规则输出。
        """
        haystack = f"{column_name or ''} {(comment or '')}"
        dt = (data_type or "").lower()
        best: Optional[Dict] = None
        best_conf = 0.0
        best_evidence: Dict = {}

        for rule in _PII_RULES:
            conf = 0.0
            why: List[str] = []
            name_re = re.compile(rule["name_regex"])
            if name_re.search(haystack):
                conf = max(conf, float(rule["name_conf"]))
                why.append("name_match")
            if rule.get("data_type_hint") and any(h in dt for h in rule["data_type_hint"]):
                conf = max(conf, float(rule["name_conf"]) * 0.8)
                why.append("data_type_hint")
            value_re = rule.get("value_regex")
            if value_re and profile_top_values:
                compiled = re.compile(value_re)
                hits = sum(1 for v in profile_top_values if compiled.match(str(v.get("value", ""))))
                if hits:
                    conf = max(conf, float(rule["value_conf"]))
                    why.append(f"value_match(x{hits})")
            if conf > best_conf:
                best_conf = conf
                best = rule
                best_evidence = {"rule": rule["semantic_type"], "why": why, "score": round(conf, 4)}

        if best is None:
            return AnnotationResult(evidence={"note": "no_rule_matched"})
        return AnnotationResult(
            semantic_type=best["semantic_type"],
            pii_level=best["pii_level"],
            confidence=round(best_conf, 4),
            evidence=best_evidence,
        )

    @staticmethod
    def match_standard(
        column_name: str,
        comment: Optional[str],
        data_type: Optional[str],
        standards: List[Dict],
    ) -> "Optional[StandardMatch]":
        """把列匹配到标准项（按别名精确/子串命中 + 数据类型暗示）。

        :param standards: 形如 ``{code,name,aliases,semantic_type,security_level,
            data_type_expect}`` 的字典列表（来自 ``MetaStandard`` 行序列化）。
        :return: 最佳命中，无命返回 None。
        """
        haystack = f"{column_name or ''} {(comment or '')}".lower()
        dt = (data_type or "").lower()
        best: Optional[Dict] = None
        best_conf = 0.0
        best_why: List[str] = []
        for s in standards:
            conf = 0.0
            why: List[str] = []
            aliases = [str(s.get("code", "")), str(s.get("name", ""))]
            aliases += [str(a) for a in (s.get("aliases") or [])]
            for alias in aliases:
                a = (alias or "").lower().strip()
                if not a:
                    continue
                if a == haystack.strip():
                    conf = max(conf, 0.9)
                    why.append(f"alias_exact:{a}")
                elif a in haystack:
                    conf = max(conf, 0.72)
                    why.append(f"alias_substr:{a}")
            expect = (s.get("data_type_expect") or "").lower()
            if expect and expect in dt:
                conf = max(conf, 0.6)
                why.append("data_type_expect")
            if conf > best_conf:
                best_conf = conf
                best = s
                best_why = why
        if best is None or best_conf < CONF_SUGGEST_MIN:
            return None
        return StandardMatch(
            standard_code=best["code"],
            standard_id=best.get("id"),
            confidence=round(best_conf, 4),
            evidence={"why": best_why, "score": round(best_conf, 4)},
        )


@dataclass
class StandardMatch:
    """标准项匹配结果。"""

    standard_code: str
    standard_id: Optional[int]
    confidence: float
    evidence: Dict


#: 内置标准项（种子数据）：业务字段的命名/类型/安全口径。
BUILTIN_STANDARDS: List[Dict] = [
    {
        "code": "std_phone", "name": "手机号", "semantic_type": "phone", "security_level": "L3",
        "aliases": ["phone", "mobile", "cellphone", "手机", "电话", "手机号"],
        "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_email", "name": "邮箱", "semantic_type": "email", "security_level": "L3",
        "aliases": ["email", "mail", "邮箱", "电子邮件"], "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_id_card", "name": "身份证号", "semantic_type": "id_card", "security_level": "L3",
        "aliases": ["id_card", "idcard", "身份证", "证件号"], "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_person_name", "name": "姓名", "semantic_type": "person_name", "security_level": "L2",
        "aliases": ["name", "username", "realname", "姓名", "用户名", "真实姓名"],
        "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_user_id", "name": "用户ID", "semantic_type": "user_id", "security_level": "L1",
        "aliases": ["user_id", "uid", "用户id", "会员id"], "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_address", "name": "地址", "semantic_type": "address", "security_level": "L2",
        "aliases": ["address", "addr", "地址", "收货地址"], "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_gender", "name": "性别", "semantic_type": "gender", "security_level": "L1",
        "aliases": ["gender", "sex", "性别"], "data_type_expect": "", "domain": "客户",
    },
    {
        "code": "std_amount", "name": "金额", "semantic_type": "amount", "security_level": "L0",
        "aliases": ["amount", "price", "money", "fee", "金额", "价格", "费用"],
        "data_type_expect": "numeric", "domain": "交易",
    },
    {
        "code": "std_datetime", "name": "时间", "semantic_type": "datetime", "security_level": "L0",
        "aliases": ["created_at", "updated_at", "time", "date", "时间", "日期", "时间戳"],
        "data_type_expect": "timestamp", "domain": "交易",
    },
]
