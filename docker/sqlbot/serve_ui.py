"""SQLBot 生产入口 —— 在 main:app 之上挂载前端 SPA 静态资源。

官方镜像 main.py 只注册 API 路由，不服务前端。
本模块在 deploy 侧把前端 dist 挂载到 "/"，使页面与 API 同源共用 8000 端口。

要点:
1. import main 会执行 main.py 的模块级逻辑（注册 api_router、MCP 等），
   "/" 挂载在所有 API 路由之后，不会遮蔽 /api/v1/* 等路径。
2. 路由为 hash 模式，URL 恒为 "/"，相对 API 路径 ./api/v1 始终正确。
3. ResponseMiddleware 只包装 JSON 响应，静态文件原样透传。
"""

import os
import logging

from fastapi.staticfiles import StaticFiles
from main import app, mcp_app  # noqa: F401  mcp_app 供 uvicorn serve_ui:mcp_app 复用

UI_DIST = os.environ.get("SQLBOT_UI_DIST", "/opt/sqlbot/frontend/dist")

if os.path.isdir(UI_DIST):
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
else:
    logging.getLogger(__name__).warning(
        "前端静态目录不存在, 跳过 SPA 挂载: %s", UI_DIST
    )
