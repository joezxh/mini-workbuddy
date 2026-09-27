"""9 种会话模式的跨模式上下文策略常量。

约束(Global Constraints):
- scheduled 不写 Mem0(后台调度非永久记忆)
- shared 不写 Mem0(共享层数据非用户偏好)
- 8 种交互模式(general/react/thinking/deep_research/skill/agent/team/shared_excluded)
  写本地私有化 Mem0 作为永久记忆。

与 risk_control 工程 4 共有模式(general/skill/scheduled/shared)值对齐;
其余模式按 MinWorkBuddy 业务设定。
"""
from __future__ import annotations

from typing import Dict, List, Set


# 数字越小优先级越高(压缩保护时优先保留)
PRIORITY_MAP: Dict[str, int] = {
    "general":       3,
    "react":         3,
    "thinking":      4,
    "deep_research": 4,
    "skill":         2,
    "agent":         2,
    "team":          2,
    "data":          2,
    "scheduled":     4,
    "shared":        5,
}


# 默认 TTL(小时)。agent 720h = 30 天,因为 agent 是用户投资最重的执行结果
DEFAULT_TTL_HOURS: Dict[str, int] = {
    "general":       168,   # 7 天
    "react":         168,
    "thinking":      168,
    "deep_research": 336,   # 14 天(深度调研价值高,延长)
    "skill":         168,
    "agent":         720,   # 30 天
    "team":          168,
    "data":          48,    # 2 天(查询结果时效性短)
    "scheduled":     720,   # 30 天(调度任务可追溯)
    "shared":        168,
}


# 受保护模式(自动压缩时不删除)
DEFAULT_PROTECTED_MODES: List[str] = [
    "agent", "team", "deep_research",
]


# 写本地私有化 Mem0 的模式白名单
# scheduled 不写(后台调度非永久记忆)
# shared 不写(共享层数据非用户偏好)
MEM0_ENABLED_MODES: Set[str] = {
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "data",
}


# 9 种会话模式的权威清单(与前端 AssistantPanel fallback 映射 + 字典表对齐)。
# 会话内切换模式(PUT session_type)以此为唯一校验源。
SESSION_MODES: List[str] = [
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "data", "scheduled",
]

# 存储层兜底 source_mode(非会话模式):L2 记录默认标记,
# 无法归类到具体会话模式时使用。
STORAGE_FALLBACK_MODE: str = "shared"