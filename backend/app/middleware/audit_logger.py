import time
import json
import asyncio
import threading
from typing import Callable, Optional
from collections import OrderedDict
from fastapi import Request, Response, HTTPException
from fastapi.routing import APIRoute
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from loguru import logger

from app.db.database import SessionLocal
from app.models.sys.sys_user import SysAuditLog, SysUser, SysUserRole, SysRoleMenu, SysMenu
from app.config import settings

# ──────────────────── 异步批量写入队列 ────────────────────

_audit_queue: asyncio.Queue = asyncio.Queue()
_audit_writer_task: Optional[asyncio.Task] = None


class _AuditWriter:
    """后台协程：从队列取日志，攒批后批量写入数据库"""

    def __init__(self, batch_size: int, flush_interval: float):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._running = False

    async def run(self):
        self._running = True
        logger.info(f"审计日志写入协程启动 batch_size={self.batch_size} flush_interval={self.flush_interval}s")
        while self._running or not _audit_queue.empty():
            batch: list = []
            try:
                # 等待第一条（最多等 flush_interval 秒）
                try:
                    item = await asyncio.wait_for(_audit_queue.get(), timeout=self.flush_interval)
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass

                # 非阻塞地尽可能多取
                while len(batch) < self.batch_size:
                    try:
                        item = _audit_queue.get_nowait()
                        batch.append(item)
                    except asyncio.QueueEmpty:
                        break

                if batch:
                    await asyncio.to_thread(self._flush_batch, batch)

            except Exception as e:
                logger.error(f"审计日志批量写入异常: {e}")

        logger.info("审计日志写入协程已停止")

    def _flush_batch(self, batch: list):
        """同步批量写入"""
        db: Session = SessionLocal()
        try:
            db.add_all(batch)
            db.commit()
        except Exception as e:
            logger.error(f"审计日志批量写入失败: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

    def stop(self):
        self._running = False


def start_audit_writer() -> asyncio.Task:
    """在 lifespan 启动时调用，返回后台 Task"""
    global _audit_writer_task
    writer = _AuditWriter(
        batch_size=settings.AUDIT_LOG_BATCH_SIZE,
        flush_interval=settings.AUDIT_LOG_FLUSH_INTERVAL,
    )
    _audit_writer_task = asyncio.create_task(writer.run())
    _audit_writer_task._writer = writer  # 挂载引用以便关闭
    return _audit_writer_task


async def stop_audit_writer():
    """在 lifespan 关闭时调用，刷盘剩余日志"""
    global _audit_writer_task
    if _audit_writer_task and hasattr(_audit_writer_task, '_writer'):
        _audit_writer_task._writer.stop()
        # 等待协程处理完队列中剩余项
        try:
            await asyncio.wait_for(_audit_writer_task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("审计日志写入协程关闭超时，强制取消")
            _audit_writer_task.cancel()
    _audit_writer_task = None


# ──────────────────── 权限缓存（线程安全 LRU + TTL） ────────────────────

class _TTLCache:
    """简单的线程安全 TTL 缓存"""

    def __init__(self, maxsize: int = 256, ttl: float = 60.0):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    self._cache.move_to_end(key)
                    return value
                else:
                    del self._cache[key]
            return None

    def set(self, key, value):
        with self._lock:
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


_perm_cache = _TTLCache(maxsize=256, ttl=60.0)


# ──────────────────── 权限 & 用户信息合并查询 ────────────────────

def _query_user_and_perms(uid: int, required_perms: list) -> dict:
    """一次 DB 查询获取 username + 权限检查结果，减少连接开销"""
    db = SessionLocal()
    try:
        user = db.query(SysUser).filter(SysUser.user_id == uid).first()
        username = user.username if user else None

        if not required_perms:
            return {"username": username, "has_perm": True}

        if not user or user.status != 'active':
            return {"username": username, "has_perm": False}
        if user.is_admin:
            return {"username": username, "has_perm": True}

        role_ids = [ur.role_id for ur in db.query(SysUserRole.role_id).filter(SysUserRole.user_id == uid).all()]
        if not role_ids:
            return {"username": username, "has_perm": False}

        menu_ids = [rm.menu_id for rm in db.query(SysRoleMenu.menu_id).filter(SysRoleMenu.role_id.in_(role_ids)).all()]
        if not menu_ids:
            return {"username": username, "has_perm": False}

        db_perms = [m.permission for m in db.query(SysMenu.permission).filter(SysMenu.id.in_(menu_ids), SysMenu.permission.isnot(None)).all()]

        for required in required_perms:
            if required not in db_perms:
                return {"username": username, "has_perm": False}
        return {"username": username, "has_perm": True}
    finally:
        db.close()


# ──────────────────── 辅助函数 ────────────────────

def _get_skip_methods() -> set:
    """解析配置中的跳过方法"""
    raw = getattr(settings, 'AUDIT_LOG_SKIP_METHODS', '')
    if not raw:
        return set()
    return {m.strip().upper() for m in raw.split(',') if m.strip()}


def _get_mask_fields() -> set:
    """解析配置中的敏感字段列表"""
    raw = getattr(settings, 'AUDIT_LOG_MASK_FIELDS', 'password,oldPassword,newPassword')
    if not raw:
        return {"password", "oldPassword", "newPassword"}
    return {f.strip() for f in raw.split(',') if f.strip()}


def _determine_op_type(method: str, path: str, route_audit_type: Optional[str] = None) -> str:
    """判断操作类型，支持路由级覆盖"""
    if route_audit_type:
        return route_audit_type
    if method == "POST":
        if "login" in path:
            return "login"
        elif "logout" in path:
            return "logout"
        else:
            return "create"
    elif method in ["PUT", "PATCH"]:
        return "update"
    elif method == "DELETE":
        return "delete"
    return "query"


def _derive_module(path: str) -> str:
    """从 URL 路径推导模块名"""
    parts = path.strip("/").split("/")
    return parts[2] if len(parts) >= 3 else (parts[1] if parts else "unknown")


def _mask_body(body: dict, mask_fields: set) -> dict:
    """脱敏请求体中的敏感字段"""
    if not body or not isinstance(body, dict):
        return body
    masked = dict(body)
    for k in mask_fields:
        if k in masked:
            masked[k] = "********"
    # 防止附件字段过长（截断到最多 20 个 ID，附 _truncated 标记）
    for k in ('file_ids', 'file_db_ids'):
        if k in masked and isinstance(masked[k], list) and len(masked[k]) > 20:
            count = len(masked[k])
            masked[k] = masked[k][:20] + [f"... (共 {count} 个，已截断)"]
    return masked


def _extract_attachment_info(body: dict) -> Optional[dict]:
    """
    从请求体中提取附件信息（用于审计日志）。
    支持以下字段：
      - file_ids: List[str]  （UUID 列表）
      - file_db_ids: List[int]（infra_file.id 列表）
      - file_id: int | str   （单文件关联）
      - upload: Multipart    （文件上传请求）
    """
    if not body or not isinstance(body, dict):
        return None

    info: dict = {}
    has_attach = False

    # file_db_ids（精确关联，优先）
    db_ids = body.get('file_db_ids')
    if isinstance(db_ids, list) and db_ids:
        info['file_db_ids'] = [int(x) for x in db_ids if str(x).isdigit()]
        info['file_db_id_count'] = len(info['file_db_ids'])
        has_attach = True

    # file_ids（UUID 列表）
    file_ids = body.get('file_ids')
    if isinstance(file_ids, list) and file_ids:
        info['file_ids'] = [str(x) for x in file_ids]
        info['file_id_count'] = len(info['file_ids'])
        has_attach = True

    # 单文件关联
    file_id = body.get('file_id')
    if file_id is not None:
        info['file_id'] = str(file_id)
        has_attach = True

    return info if has_attach else None


# ──────────────────── AuditLogRoute ────────────────────

class AuditLogRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        required_permissions = self.openapi_extra.get("permissions", []) if self.openapi_extra else []
        route_audit_type = self.openapi_extra.get("audit_type", None) if self.openapi_extra else None
        route_mask_fields = self.openapi_extra.get("audit_mask_fields", []) if self.openapi_extra else []
        skip_methods = _get_skip_methods()
        global_mask_fields = _get_mask_fields()

        async def custom_route_handler(request: Request) -> Response:
            start_time = time.time()

            # --- Extract JWT for User ID ---
            user_id = None
            username = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                    uid_str = payload.get("sub")
                    if uid_str:
                        user_id = int(uid_str)
                except (JWTError, ValueError):
                    pass

            # --- 合并查询 username + 权限（优先走缓存） ---
            if user_id:
                cache_key = (user_id, tuple(sorted(required_permissions)))
                cached = _perm_cache.get(cache_key)
                if cached is not None:
                    username = cached["username"]
                    has_perm = cached["has_perm"]
                else:
                    result = await asyncio.to_thread(_query_user_and_perms, user_id, required_permissions)
                    username = result["username"]
                    has_perm = result["has_perm"]
                    _perm_cache.set(cache_key, result)

                # --- Permission Check（始终执行，不受审计日志开关影响） ---
                if required_permissions and not has_perm:
                    raise HTTPException(status_code=403, detail="没有足够的权限访问此接口")
            elif required_permissions:
                raise HTTPException(status_code=401, detail="请提供有效的 JWT Token 进行鉴权")

            # --- 审计日志开关：关闭时直接执行路由并返回 ---
            audit_enabled = getattr(settings, 'AUDIT_LOG_ENABLED', True)
            if not audit_enabled:
                return await original_route_handler(request)

            # --- 跳过指定 HTTP 方法的审计日志 ---
            if request.method.upper() in skip_methods:
                return await original_route_handler(request)

            # --- Extract Request Body Safely ---
            body = None
            try:
                content_type = request.headers.get("content-type", "")
                if request.method in ["POST", "PUT", "PATCH"] and "application/json" in content_type:
                    byte_body = await request.body()
                    if byte_body:
                        body = json.loads(byte_body.decode('utf-8'))
                elif request.method in ["POST", "PUT", "PATCH"] and "multipart/form-data" in content_type:
                    # 文件上传场景：仅记录文件名/大小，不读取文件内容
                    byte_body = await request.body()
                    body = {
                        "_upload": True,
                        "content_length": len(byte_body) if byte_body else 0,
                    }
                    # 尝试从 boundary 后的 Header 部分提取 filename
                    if byte_body:
                        try:
                            head = byte_body[:512].decode('utf-8', errors='ignore')
                            import re as _re
                            m = _re.search(r'filename="([^"]+)"', head)
                            if m:
                                body['filename'] = m.group(1)
                        except Exception:
                            pass
            except Exception:
                pass

            # --- 合并脱敏字段列表 ---
            effective_mask = global_mask_fields | set(route_mask_fields)

            response: Response = None
            status_code = 500

            try:
                response = await original_route_handler(request)
                status_code = response.status_code
            except HTTPException as e:
                status_code = e.status_code
                raise
            except Exception as e:
                status_code = 500
                raise
            finally:
                process_time = int((time.time() - start_time) * 1000)

                method = request.method
                path = request.url.path

                op_type = _determine_op_type(method, path, route_audit_type)
                module = _derive_module(path)
                desc = f"Invoke API {path}"

                masked_body = _mask_body(body, effective_mask)

                # 提取附件信息，写入 new_data JSON 字段（便于审计追溯附件上传/关联行为）
                attachment_info = _extract_attachment_info(body)

                log_entry = SysAuditLog(
                    user_id=user_id,
                    username=username,
                    operation_type=op_type,
                    operation_module=module,
                    operation_desc=desc,
                    request_method=method,
                    request_url=str(request.url),
                    request_params=masked_body,
                    request_ip=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", ""),
                    response_status=status_code,
                    response_time_ms=process_time,
                    # 附件详情保存到 new_data 字段
                    new_data={"attachment_info": attachment_info} if attachment_info else None,
                )

                # 入队（纯内存操作，微秒级）
                try:
                    _audit_queue.put_nowait(log_entry)
                except Exception as e:
                    # 队列满或异常时，降级打印日志，不阻塞请求
                    logger.warning(f"审计日志入队失败: {e}")

            return response

        return custom_route_handler
