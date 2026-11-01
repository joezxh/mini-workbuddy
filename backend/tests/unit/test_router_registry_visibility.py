"""router_registry 失败可见性回归测试。

背景（线上事故）：后端启动时 `app.routers.kb.kb` 导入失败，52 条接口
（含 GET /api/v1/kb/chunkers）整组未注册，但服务仍打印「启动成功」，
前端只看到莫名 404。此处固化三点：

1. 加载失败的模块必须进 `app.state.router_failures`；
2. 未注册的模块不得中断启动，但置 ROUTER_STRICT=1 时必须直接失败；
3. `app.routers.kb.kb` 能正常注册，/api/v1/kb/chunkers 必须在路由表中。
"""
import pytest
from fastapi import FastAPI

from app.core.router_registry import RouterSpec, register_routers


def _paths(app: FastAPI) -> set:
    return {getattr(r, "path", "") for r in app.routes}


def test_failed_module_is_recorded_not_fatal():
    app = FastAPI()
    specs = [
        RouterSpec("app.routers.not_exist_module", tags=["坏模块"]),
        RouterSpec("app.routers.kb.kb", tags=["通用知识库"]),
    ]

    registered = register_routers(app, specs=specs, strict=False)

    assert "app.routers.not_exist_module:router" not in registered
    assert "app.routers.kb.kb:router" in registered
    assert [f["module"] for f in app.state.router_failures] == ["app.routers.not_exist_module"]
    # 坏模块不影响其它模块的路由落地
    assert "/api/v1/kb/chunkers" in _paths(app)


def test_strict_mode_raises_on_failed_module():
    app = FastAPI()
    specs = [RouterSpec("app.routers.not_exist_module")]

    with pytest.raises(ImportError):
        register_routers(app, specs=specs, strict=True)


def test_missing_router_attr_is_recorded():
    app = FastAPI()
    # 模块存在但没有 APIRouter 属性 `no_such_router`
    specs = [RouterSpec("app.core.router_registry", attr="no_such_router")]

    register_routers(app, specs=specs, strict=False)

    assert app.state.router_failures
    assert "no_such_router" in app.state.router_failures[0]["error"]


def test_kb_chunkers_route_registered():
    """GET /api/v1/kb/chunkers 必须能被注册（防止整组 kb 路由再次丢失）。"""
    app = FastAPI()
    registered = register_routers(app, specs=[RouterSpec("app.routers.kb.kb")], strict=True)

    assert registered == ["app.routers.kb.kb:router"]
    assert "/api/v1/kb/chunkers" in _paths(app)
    assert not app.state.router_failures
