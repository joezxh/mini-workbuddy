"""ToolExecutor - 基于反射的工具执行器。

根据 tool 的 className（Python module.Class 或 module.func）+ methodName，
动态加载并调用，返回结构化结果，供「工具测试」接口使用。
"""
from __future__ import annotations
import asyncio
import importlib
import inspect
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

# 可注入构造函数的关键字参数名
_INJECTABLE_KWARGS = ("config", "context")


class ToolExecutor:
    """反射式工具执行器。"""

    async def execute(
        self,
        *,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        config: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """执行工具。

        :param class_name: Python 路径，形如 ``app.ai.tool_manager.builtin.EchoTool``
                           或 ``app.ai.tool_manager.builtin.demo_add``
        :param method_name: 类方法名（当 class_name 指向类时必填，指向函数时可省略）
        :param inputs: 调用参数
        :param config: 可选。若目标类的构造函数接受 ``config`` 形参，则注入。
                       用于配置化工具（如 SqlBotTemplateTool）。
        :param context: 可选。若目标类的构造函数接受 ``context`` 形参，则注入。
                        用于传递当前用户上下文。
        :return: {"success": bool, "output": Any, "error": str|None, "target": str}

        .. note:: 不传 ``config`` / ``context`` 时，行为与改造前完全一致。
        """
        inputs = inputs or {}
        target = class_name or ""
        if method_name:
            target = f"{target}.{method_name}" if target else method_name

        if not class_name:
            return {
                "success": False,
                "output": None,
                "error": "工具未配置 className，无法执行测试",
                "target": target,
            }

        try:
            obj = self._resolve(class_name, method_name, config=config, context=context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("resolve tool failed: %s -> %s", target, exc)
            return {
                "success": False,
                "output": None,
                "error": f"加载工具失败: {exc}",
                "target": target,
            }

        try:
            if asyncio.iscoroutinefunction(obj):
                result = await asyncio.wait_for(obj(**inputs), timeout=timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(obj, **inputs), timeout=timeout
                )
            # 防御：个别情况下 obj 被包装为同步方法却返回协程，确保不向外泄漏协程
            if inspect.iscoroutine(result):
                result = await result
            # 防御：AgentScope ToolChunk / pydantic 模型在裸 dict 响应中序列化可能失败，
            # 统一转为可 JSON 序列化的 dict，避免 'coroutine'/'vars()' 序列化异常
            if hasattr(result, "model_dump"):
                try:
                    result = result.model_dump()
                except Exception:  # noqa: BLE001
                    pass
            return {
                "success": True,
                "output": result,
                "error": None,
                "target": target,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("execute tool error: %s -> %s", target, exc)
            return {
                "success": False,
                "output": None,
                "error": f"执行工具出错: {exc}",
                "target": target,
            }

    @staticmethod
    def _instantiate(
        cls: type,
        config: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
    ):
        """实例化目标类，按需注入 config / context。

        用 :func:`inspect.signature` 探测构造函数形参：仅当构造函数显式接受
        ``config`` / ``context`` 且调用方传入了对应值时才注入；探测失败或不接受
        时退回无参实例化，保证既有工具行为不变。
        """
        kwargs: Dict[str, Any] = {}
        supplied = {"config": config, "context": context}

        if any(v is not None for v in supplied.values()):
            try:
                params = inspect.signature(cls.__init__).parameters
                accepts_var_kw = any(
                    p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
                )
                for key in _INJECTABLE_KWARGS:
                    value = supplied.get(key)
                    if value is None:
                        continue
                    if key in params or accepts_var_kw:
                        kwargs[key] = value
            except (TypeError, ValueError) as exc:
                logger.debug("inspect signature failed for %s: %s", cls, exc)
                kwargs = {}

        if kwargs:
            try:
                return cls(**kwargs)
            except TypeError as exc:
                logger.warning(
                    "inject config/context into %s failed, fallback to no-arg: %s",
                    cls,
                    exc,
                )
        return cls()

    def _resolve(
        self,
        class_name: str,
        method_name: Optional[str],
        config: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
    ):
        """解析 class_name / method_name 为可调用对象。"""
        if "." not in class_name:
            raise ValueError(f"className 格式应为 module.Class 或 module.func，得到: {class_name}")
        module_path, attr = class_name.rsplit(".", 1)

        # 优先复用 ToolManager 单例中已注册的内置工具实例。
        # 内置工具（如 knowledge_tools 中 RiskEventSearch 等）构造需 db_session_factory，
        # 由 register_builtin_tools 预构建并注册；此处按类名（attr）直接取实例，
        # 避免反射无参实例化因缺少依赖而失败。
        registered = self._lookup_registered(attr)
        if registered is not None:
            if method_name:
                method = getattr(registered, method_name, None)
                if method is None:
                    raise ValueError(f"工具 {attr} 不存在方法 {method_name}")
                return method
            # AgentScope ToolBase 工具以 ``call(**input_schema)`` 为统一入口，
            # 其入参与工具的 input_schema 一致（无需 session 等 Hidden 参数）。
            if hasattr(registered, "call") and callable(getattr(registered, "call")):
                return getattr(registered, "call")
            if callable(registered):
                return registered
            if hasattr(registered, "execute"):
                return getattr(registered, "execute")
            raise ValueError(f"工具 {attr} 既无 methodName，也不可调用")

        module = importlib.import_module(module_path)
        obj = getattr(module, attr)

        # 指向函数：直接调用
        if callable(obj) and not isinstance(obj, type):
            return obj

        # 指向类
        if isinstance(obj, type):
            if method_name:
                method = getattr(obj, method_name, None)
                if method is None:
                    raise ValueError(f"类 {class_name} 不存在方法 {method_name}")
                # 类方法 / 静态方法：直接调用；实例方法：实例化后调用
                if isinstance(method, (classmethod, staticmethod)) or getattr(method, "__self__", None) is not None:
                    return method
                instance = self._instantiate(obj, config, context)
                return getattr(instance, method_name)
            # 无 methodName：若实例可调用则实例化返回，否则尝试 execute
            instance = self._instantiate(obj, config, context)
            if callable(instance):
                return instance
            if hasattr(instance, "execute"):
                return getattr(instance, "execute")
            raise ValueError(f"类 {class_name} 既无 methodName，也不可调用")

        # 其它可调用对象
        if callable(obj):
            return obj
        raise ValueError(f"{class_name} 不是可调用对象")

    @staticmethod
    def _lookup_registered(attr: str) -> Optional[Any]:
        """按类名（attr）在 ToolManager 单例中查找已注册的内置工具实例。

        注意：ToolManager 以 ``tool.name``（如 ``risk_event_search``）为键注册，
        而非 Python 类名；故此处遍历实例，按 ``type(obj).__name__ == attr`` 匹配，
        使工具测试可复用已预构建（注入 db_session_factory 等）的内置工具实例。
        """
        try:
            from app.ai.tool_manager import get_tool_manager
        except Exception:  # noqa: BLE001
            return None
        try:
            manager = get_tool_manager()
        except Exception:  # noqa: BLE001
            return None
        # 直接键命中（如测试传入 tool.name 而非类名）
        direct = manager.get(attr)
        if direct is not None:
            return direct
        # 按类名匹配已注册实例
        for tool in manager.tools.values():
            if getattr(type(tool), "__name__", None) == attr:
                return tool
        return None
