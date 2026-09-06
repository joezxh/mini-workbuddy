"""Tool 管理器 - 基于 AgentScope 2.0.4 ToolBase + ToolGroup，并支持从 DB 加载。

职责:
- 内存持有 tool_name -> ToolBase 实例（AgentScope 原生 Tool）
- 内存缓存 tool_key -> AiToolDefinition（DB 持久化的工具元数据，即「缓存」）
- 提供 register / list / build_tool_group / load_all(reload) 等接口
- 作为单例挂载在 app.state，供「刷新缓存」接口重新装载
"""
from __future__ import annotations
import importlib
import inspect
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from agentscope.tool import ToolBase, ToolGroup, Toolkit
from app.ai.tool_manager.models import ToolType
from app.models.ai.ai_tool_definition import AiToolDefinition

logger = logging.getLogger(__name__)


class ToolManager:
    """Tool 管理器 - 注册 ToolBase 实例并组装 ToolGroup，同时缓存 DB 元数据。"""

    def __init__(self, toolkit: Optional[Toolkit] = None) -> None:
        self.tools: Dict[str, ToolBase] = {}
        self.groups: Dict[str, ToolGroup] = {}
        self.definitions: Dict[str, AiToolDefinition] = {}
        # SDK 2.0.4: Toolkit(tools=[...], tool_groups=[...]) 一次构造
        self.toolkit: Toolkit = toolkit or Toolkit(tools=[])

    # ---------- AgentScope ToolBase 管理 ----------

    def register(self, tool: ToolBase, type_hint: Optional[str] = None) -> str:
        """注册一个 ToolBase 实例。返回 tool_name。"""
        name = getattr(tool, "name", None) or tool.__class__.__name__
        if not name:
            raise ValueError(f"tool {tool!r} has no name")
        self.tools[name] = tool
        self._rebuild_toolkit()
        logger.info("registered tool: %s (%s)", name, type_hint or tool.__class__.__name__)
        return name

    def unregister(self, tool_name: str) -> bool:
        removed = self.tools.pop(tool_name, None) is not None
        if removed:
            self._rebuild_toolkit()
        return removed

    def get(self, tool_name: str) -> Optional[ToolBase]:
        return self.tools.get(tool_name)

    def list_tools(self, tool_type: Optional[str] = None) -> List[str]:
        """列出 Tool 名。tool_type 在 v2 自定义场景下为 'custom'。"""
        if tool_type is None or tool_type == ToolType.CUSTOM.value:
            return list(self.tools.keys())
        return []

    def build_tool_group(
        self,
        name: str,
        description: str,
        tool_names: Optional[List[str]] = None,
        instructions: Optional[str] = None,
    ) -> ToolGroup:
        """按 tool_names 组装 agentscope 2.0.4 ToolGroup。"""
        if tool_names is None:
            tool_names = list(self.tools.keys())
        picked: List[ToolBase] = []
        for tn in tool_names:
            inst = self.tools.get(tn)
            if inst is None:
                logger.warning("tool %s not found, skip", tn)
                continue
            picked.append(inst)
        group = ToolGroup(
            name=name,
            description=description,
            instructions=instructions,
            tools=picked,
        )
        self.groups[name] = group
        self._rebuild_toolkit()
        return group

    def _rebuild_toolkit(self) -> None:
        try:
            self.toolkit = Toolkit(
                tools=list(self.tools.values()),
                tool_groups=list(self.groups.values()) or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("toolkit rebuild skipped: %s", exc)

    # ---------- DB 元数据缓存管理 ----------

    def load_all(self, db: Session) -> int:
        """从 DB 加载全部工具元数据到内存缓存。返回加载数量。"""
        rows = db.query(AiToolDefinition).all()
        self.definitions = {r.tool_key: r for r in rows}
        logger.info("tool cache loaded from DB: %d tools", len(self.definitions))
        return len(self.definitions)

    def reload(self, db: Session) -> int:
        """刷新缓存（重新从 DB 加载）。"""
        return self.load_all(db)

    def get_definition(self, tool_key: str) -> Optional[AiToolDefinition]:
        return self.definitions.get(tool_key)

    def list_definitions(self) -> List[AiToolDefinition]:
        return list(self.definitions.values())

    def cache_model(self, model: AiToolDefinition) -> None:
        """将单个（新建/更新后的）模型写入缓存。"""
        self.definitions[model.tool_key] = model

    def evict(self, tool_key: str) -> None:
        """从缓存移除。"""
        self.definitions.pop(tool_key, None)

    async def call_tool(self, tool_name: str, **inputs: Any) -> Any:
        """统一调用入口 - 供 Skill 之外的业务模块调用任意已注册工具。

        与 AgentScope agent 内部 ``tool_manager.tools`` 调用路径不同，业务模块
        （如 research pipeline、调度任务）无需了解 ToolBase 协议，直接通过本方法
        以 ``name + 关键字参数`` 调用，返回的 python 对象（非 ToolChunk）可直接使用。

        Args:
            tool_name: 工具名（如 ``"web_search"``）
            **inputs: 传给工具的入参（如 ``query="..."``）

        Returns:
            工具 call 返回的 python 对象；失败返回 ``{"error": str}``。

        Raises:
            KeyError: 工具未注册时抛出，便于调用方感知配置缺失。
        """
        tool = self.tools.get(tool_name)
        if tool is None:
            raise KeyError(f"tool not registered: {tool_name}")
        chunk = await tool.call(**inputs)
        # ToolChunk -> python 对象（优先取首个 text block 的 JSON）
        for block in getattr(chunk, "content", []) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    return text
        return chunk


# ---------------------------------------------------------------------------
# Toolkit 装配：把 agent_config.tools（tool_key 列表）实例化为 AgentScope 工具
# ---------------------------------------------------------------------------


def _normalize_tool_keys(raw: Any) -> List[str]:
    """把 agent_config.tools 的历史形态归一化为 tool_key 列表。

    主流形态是扁平的 ``List[str]``；兼容早期写入的 ``{"tools": [...]}`` 字典与单个字符串。
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = raw.get("tools") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _import_tool_class(class_name: Optional[str]):
    """按 ``module.Class`` 动态导入 ToolBase 子类，失败返回 None。"""
    if not class_name:
        return None
    try:
        module_name, _, cls_name = str(class_name).rpartition(".")
        if not module_name or not cls_name:
            return None
        module = importlib.import_module(module_name)
        cls = getattr(module, cls_name, None)
        if not isinstance(cls, type) or not issubclass(cls, ToolBase):
            logger.warning("工具类 %s 不是 ToolBase 子类", class_name)
            return None
        return cls
    except Exception as e:  # noqa: BLE001 单个工具不可用不应影响整体
        logger.warning("导入工具类 %s 失败: %s", class_name, e)
        return None


def _instantiate_tool(defn: AiToolDefinition, db: Session) -> Optional[ToolBase]:
    """按定义实例化工具：优先带 config_value，参数不匹配时退化为无参构造。"""
    cls = _import_tool_class(defn.class_name)
    if cls is None:
        return None

    config = defn.config_value if isinstance(defn.config_value, dict) else {}

    def _inject_db(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """构造器声明了 ``db`` 参数时注入当前 Session。"""
        try:
            params = inspect.signature(cls.__init__).parameters
            if "db" in params and "db" not in kwargs:
                return {**kwargs, "db": db}
        except (TypeError, ValueError):
            pass
        return kwargs

    attempts: List[Dict[str, Any]] = [config] if config else []
    if {} not in attempts:
        attempts.append({})

    for base in attempts:
        try:
            return cls(**_inject_db(base))
        except TypeError as e:
            logger.debug("工具 %s 构造参数不匹配(%s)，尝试下一组", defn.tool_key, e)
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("工具 %s 实例化失败: %s", defn.tool_key, e)
            return None
    return None


def _resolve_tool(db: Session, key: str) -> Optional[ToolBase]:
    """按 tool_key 解析出可用工具实例。"""
    # 1) 复用 ToolManager 中已注册的实例（避免重复构造）
    try:
        registered = get_tool_manager().get(key)
        if registered is not None:
            return registered
    except Exception:  # noqa: BLE001
        pass

    # 2) 按 DB 定义动态实例化
    try:
        query = db.query(AiToolDefinition).filter(AiToolDefinition.tool_key == key)
        if key.isdigit():  # 兼容存了主键 id 的历史数据
            query = db.query(AiToolDefinition).filter(
                or_(AiToolDefinition.tool_key == key, AiToolDefinition.id == int(key))
            )
        defn = query.first()
    except Exception as e:  # noqa: BLE001
        logger.warning("查询工具 %s 失败: %s", key, e)
        return None

    if defn is None:
        return None
    if (defn.status or "") != "enabled":
        logger.warning("工具 %s 未启用(status=%s)，已跳过", key, defn.status)
        return None
    return _instantiate_tool(defn, db)


def build_toolkit(db: Session, tool_keys: Any) -> Toolkit:
    """按 tool_key 列表构建 Toolkit，供 Agent 注入工具。

    设计要点：
    - **不缓存、不写回单例**：每次构建全新实例，避免并发运行共享同一工具实例造成状态污染；
    - 单个工具失败只跳过并记录告警，绝不阻断整个 Agent 的构建。

    Args:
        db: SQLAlchemy Session。
        tool_keys: tool_key 列表（兼容 dict / 单字符串等历史形态）。

    Returns:
        已装配可用工具的 Toolkit（无可用工具时返回空 Toolkit）。
    """
    tools: List[ToolBase] = []
    for key in _normalize_tool_keys(tool_keys):
        tool = _resolve_tool(db, key)
        if tool is None:
            logger.warning("工具 %s 不可用，未注入", key)
            continue
        tools.append(tool)
    return Toolkit(tools=tools)


# ---------------------------------------------------------------------------
# 单例访问器（供 app.state.tool_manager 与「刷新缓存」接口使用）
# ---------------------------------------------------------------------------

_MANAGER: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """返回进程级 ToolManager 单例。"""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ToolManager()
    return _MANAGER
