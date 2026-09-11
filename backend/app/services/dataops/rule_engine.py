"""规则标注引擎 —— 置信度分层常量（单一事实来源）。

⚠️ 归属与边界（P2 计划 Task 12 / P4 计划 Task 5 的共同约定）
----------------------------------------------------------
本文件属于 **P2（业务数据集成）Task 12「规则标注引擎 + 置信度分层」**。
P2 实施时规则标注本体（PII 识别 / join key 判定 / 标准项绑定等）在本文件扩展。

当前仅包含 P4（本体层）与 P2 **共用**的置信度阈值常量——P4 Task 5 的
候选生成按此分层（`0.90 → accepted`、`0.70 → suggested`、`0.50 → 丢弃`
即对应这两条分界线），**两侧都不得另行定义**：
"""
from __future__ import annotations

#: 自动接受阈值：置信度 ≥ 此值的候选/标注直接落为 accepted（无需人工评审）。
CONF_AUTO_ACCEPT = 0.85

#: 建议阈值：置信度 ∈ [CONF_SUGGEST_MIN, CONF_AUTO_ACCEPT) 的落为 suggested
#: （进入人工评审队列）；低于此值不生成候选。
CONF_SUGGEST_MIN = 0.65

__all__ = ["CONF_AUTO_ACCEPT", "CONF_SUGGEST_MIN"]
