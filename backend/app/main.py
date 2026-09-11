from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from loguru import logger
import sys
import logging

# Windows 控制台默认 GBK 编码，LLM 输出的特殊字符(•等)会导致 UnicodeEncodeError。
# 强制 stdout/stderr 使用 UTF-8，避免 worker 输出含特殊字符时崩溃。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 配置 APScheduler 日志输出到 stdout
apscheduler_logger = logging.getLogger('apscheduler')
apscheduler_logger.setLevel(logging.INFO)
if not apscheduler_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    apscheduler_logger.addHandler(handler)

from app.config import settings

# 集中登记所有 ORM 模型（建表单一事实来源）
from app.db import init_models  # noqa: F401 触发模型注册
from app.db.database import SessionLocal
from app.middleware.audit_logger import start_audit_writer, stop_audit_writer
from app.middleware.tenant_resolver import TenantResolverMiddleware

# 注册租户隔离拦截器（do_orm_execute 事件）
from app.core.tenant_interceptor import setup_tenant_interceptor
setup_tenant_interceptor(SessionLocal)

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL
)
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL
)


# 生命周期事件处理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    import time as _time
    _startup_t0 = _time.monotonic()

    # 启动事件
    logger.info(f"{settings.APP_NAME} 启动成功")
    logger.info(f"版本：{settings.APP_VERSION}")
    logger.info(f"文档地址：http://localhost:8000/docs")

    # 显式设置 asyncio 全局线程池
    import asyncio as _asyncio
    from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
    _loop = _asyncio.get_event_loop()
    _executor = _ThreadPoolExecutor(
        max_workers=settings.THREAD_POOL_MAX_WORKERS,
        thread_name_prefix="app_worker"
    )
    _loop.set_default_executor(_executor)
    logger.info(f"已设置全局线程池 max_workers={settings.THREAD_POOL_MAX_WORKERS} [{_time.monotonic()-_startup_t0:.2f}s]")

    # 表名迁移：重命名旧表以匹配新的模型命名规范（仅在旧表存在且新表不存在时执行）
    if settings.AUTO_CREATE_TABLES:
        try:
            from sqlalchemy import text as _text, inspect as _inspect
            from app.db.database import engine as _engine
            _insp = _inspect(_engine)
            _existing = set(_insp.get_table_names())
            _rename_map = {
                # sys_ 前缀：用户与权限
                'user': 'sys_user',
                'role': 'sys_role',
                'user_role': 'sys_user_role',
                'region': 'sys_region',
                'menu': 'sys_menu',
                'role_menu': 'sys_role_menu',
                'audit_log': 'sys_audit_log',
                'user_notification': 'sys_user_notification',
                # sys_ 前缀：字典
                'dictionary': 'sys_dictionary',
                'dictionary_item': 'sys_dictionary_item',
                # ai_ 前缀
                'workspace': 'ai_workspace',
                'web_search': 'ai_web_search',
                'web_search_log': 'ai_web_search_log',
                # sys_ 前缀：基础设施文件
                'infra_file': 'sys_infra_file',
                'infra_file_content': 'sys_infra_file_content',
                # ai_ 前缀：MCP / Tool
                'mcp_api_key': 'ai_mcp_api_key',
                'mcp_client': 'ai_mcp_client',
                'mcp_square_template': 'ai_mcp_square_template',
                'tool_definition': 'ai_tool_definition',
                'tool_group': 'ai_tool_group',
                'tool_group_member': 'ai_tool_group_member',
            }
            with _engine.begin() as _conn:
                for _old, _new in _rename_map.items():
                    if _old in _existing and _new not in _existing:
                        _conn.execute(_text(f'ALTER TABLE {_old} RENAME TO {_new}'))
                        logger.info(f'已重命名表: {_old} → {_new}')
            if any(o in _existing for o in _rename_map):
                logger.info("表名迁移完成")
        except Exception as _rename_err:
            logger.warning(f"表名迁移异常(可忽略): {_rename_err}")

    # 建表：开发/小环境用 create_all（controlled by AUTO_CREATE_TABLES）
    if settings.AUTO_CREATE_TABLES:
        from app.db.database import Base, engine
        # 基础表由 create_all 负责；kb_* 三表交由迁移 006 独占（建表+索引+pg_trgm 扩展），
        # 避免 create_all 与 alembic 重复建表导致索引/扩展缺失或冲突（见 P1 简报 Task 1）。
        non_kb = [t for t in Base.metadata.tables.values() if not t.name.startswith("kb_")]
        Base.metadata.create_all(bind=engine, tables=non_kb)
        logger.info("已通过 Base.metadata.create_all 完成基础表建表（kb_* 交由迁移 006）")

        # 确保 kb 表（迁移 006）存在：基础表已由 create_all 建好，故仅跑 006。
        app.state.kb_ready = False
        try:
            from app.db.migrate import ensure_kb_schema
            ensure_kb_schema(engine)
            app.state.kb_ready = True
            logger.info("kb 表（迁移 006）已确保存在")
        except Exception as _kb_err:
            logger.error(f"确保 kb 表失败（迁移 006 未执行或 pg_trgm 异常？）: {_kb_err}")

        # 轻量列迁移：补齐后加列
        try:
            from sqlalchemy import text as _text
            with engine.begin() as _conn:
                _conn.execute(_text(
                    "ALTER TABLE agent_async_task ADD COLUMN IF NOT EXISTS execution_id VARCHAR(100)"
                ))
                _conn.execute(_text(
                    "CREATE INDEX IF NOT EXISTS ix_agent_async_task_execution_id "
                    "ON agent_async_task (execution_id)"
                ))
                _conn.execute(_text(
                    "ALTER TABLE agent_scheduled_task ADD COLUMN IF NOT EXISTS skill_info TEXT"
                ))
                _conn.execute(_text(
                    "ALTER TABLE sys_menu ADD COLUMN IF NOT EXISTS i18n_key VARCHAR(100)"
                ))
        except Exception as _col_err:
            logger.warning(f"补齐新列失败(忽略): {_col_err}")

    # 启动审计日志批量写入协程
    try:
        start_audit_writer()
        logger.info("审计日志写入协程已启动")
    except Exception as e:
        logger.error(f"启动审计日志写入协程失败: {e}")

    # 初始化工具管理缓存（ToolManager 单例）
    _t5 = _time.monotonic()
    try:
        from app.ai.tool_manager import get_tool_manager
        mgr = get_tool_manager()
        app.state.tool_manager = mgr
        startup_db = SessionLocal()
        try:
            # 先幂等登记系统内置工具（web_search + 三个本体工具），再加载缓存
            from app.ai.tool_manager.seed_tools import register_builtin_tools
            register_builtin_tools(startup_db)
            mgr.load_all(startup_db)
        finally:
            startup_db.close()
        logger.info(f"工具管理缓存已加载 [{_time.monotonic()-_t5:.2f}s]")
    except Exception as e:
        logger.warning(f"加载工具管理缓存失败 [{_time.monotonic()-_t5:.2f}s]: {e}")

    # 初始化 OpenTelemetry 链路追踪
    _t4 = _time.monotonic()
    try:
        from app.ai.telemetry.exporter import setup_telemetry
        setup_telemetry()
        logger.info(f"OpenTelemetry 链路追踪已初始化 [{_time.monotonic()-_t4:.2f}s]")
    except Exception as e:
        logger.warning(f"初始化 OpenTelemetry 失败 [{_time.monotonic()-_t4:.2f}s]: {e}")

    logger.info(f"▶ 启动流程全部完成，总耗时 {_time.monotonic()-_startup_t0:.2f}s")
    yield

    # 关闭审计日志批量写入协程
    try:
        await stop_audit_writer()
        logger.info("审计日志写入协程已关闭")
    except Exception as e:
        logger.error(f"关闭审计日志写入协程失败: {e}")

    logger.info(f"{settings.APP_NAME} 关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="MinWorkBuddy AI 工作台 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册域名→租户解析中间件（ASGI 层）
app.add_middleware(TenantResolverMiddleware)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "服务器内部错误", "detail": str(exc)}
    )


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


# 注册路由（声明式清单：新增/下线模块只需改 app/core/router_registry.py，无需改动本文件）
from app.core.router_registry import register_routers

register_routers(app)



# 挂载 MCP Server SSE/Streamable HTTP 端点（供外部 MCP Client 连接）
try:
    from app.ai.mcp.server import get_mcp_server
    _mcp_srv = get_mcp_server()
    if _mcp_srv:
        try:
            mcp_http_app = _mcp_srv.streamable_http_app()
            app.mount("/mcp", mcp_http_app)
            logger.info("MCP Streamable HTTP 端点已挂载: /mcp")
        except AttributeError:
            mcp_sse_app = _mcp_srv.sse_app()
            app.mount("/mcp", mcp_sse_app)
            logger.info("MCP SSE 端点已挂载: /mcp")
except Exception as e:
    logger.warning(f"MCP Server 端点挂载失败: {e}")


# 挂载知识库 RAG Service 子应用（AgentScope RAG Service 内核）
# 检查点（P1 简报 Task 8）：Starlette 不会自动触发挂载子应用的 lifespan，
# 因此 KB 初始化由主应用 lifespan 兜底（app.state.kb_ready），详见 tests/kb/test_mount_checkpoint.py
try:
    from app.services.kb.kb_app import kb_app
    app.mount("/agentscope/knowledge_bases", kb_app)
    logger.info("知识库 RAG Service 已挂载: /agentscope/knowledge_bases")
except Exception as e:
    logger.warning(f"知识库 RAG Service 挂载失败: {e}")


if __name__ == "__main__":
    import os
    import uvicorn
    reload_env = os.getenv("UVICORN_RELOAD")
    reload_flag = settings.DEBUG if reload_env is None else (reload_env.lower() in ("1", "true", "yes", "on"))
    uvicorn.run(
        "app.main:app",
        host=settings.HOST if hasattr(settings, 'HOST') else "0.0.0.0",
        port=settings.PORT if hasattr(settings, 'PORT') else 8000,
        reload=reload_flag
    )
