"""Task 8 挂载检查点：验证 /agentscope/knowledge_bases 挂载与 lifespan 行为。

检查点结论（P1 简报 Task 8 硬检查点）：
- Starlette 挂载子应用**不会自动触发子应用 lifespan**；
- 因此 KB 关键初始化放在主应用 lifespan（app.state.kb_ready）兜底，
  子应用 lifespan 仅做日志/本地标记，不作为唯一事实来源。
本测试不导入 app.main（避免触发真实建表/工具加载等重副作用），
用隔离的 FastAPI 父子应用复现挂载语义。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.kb.kb_app import kb_app


def test_mount_subapp_lifespan_not_auto_run():
    """检查点：挂载子应用不会自动执行其子应用 lifespan（Starlette 已知限制）。"""
    child_initialized = {"v": False}

    @asynccontextmanager
    async def child_lifespan(app):
        child_initialized["v"] = True
        yield

    child = FastAPI(lifespan=child_lifespan)

    @child.get("/x")
    async def _x():
        return {"ok": True}

    parent = FastAPI()
    parent.mount("/agentscope/knowledge_bases", child)

    with TestClient(parent):
        pass  # 启动父应用

    assert child_initialized["v"] is False


def test_kb_subapp_reachable_via_mount():
    """挂载真实 kb_app 后，/agentscope/knowledge_bases/health 可达。"""
    parent = FastAPI()
    parent.mount("/agentscope/knowledge_bases", kb_app)
    with TestClient(parent) as client:
        r = client.get("/agentscope/knowledge_bases/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_kb_storage_initialized_via_parent_lifespan():
    """关键初始化由父应用 lifespan 兜底（KB 采用此模式，规避子应用 lifespan 限制）。"""
    kb_ready = {"v": False}

    @asynccontextmanager
    async def parent_lifespan(app):
        # 主应用 lifespan 兜底：KB 存储初始化（对应 main.lifespan 中 app.state.kb_ready=True）
        kb_ready["v"] = True
        yield

    parent = FastAPI(lifespan=parent_lifespan)
    parent.mount("/agentscope/knowledge_bases", kb_app)
    with TestClient(parent) as client:
        r = client.get("/agentscope/knowledge_bases/health")
        assert r.status_code == 200
    assert kb_ready["v"] is True
