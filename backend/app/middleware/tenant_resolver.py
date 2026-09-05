"""域名→租户解析中间件。

从请求 Host 头解析租户，支持域名绑定。
当用户通过绑定域名访问时，自动设置租户上下文。
"""
import logging

logger = logging.getLogger(__name__)

# 模块级单例引用，供外部刷新缓存使用
_instance: "TenantResolverMiddleware | None" = None


def get_tenant_resolver() -> "TenantResolverMiddleware | None":
    """获取当前运行的 TenantResolverMiddleware 实例"""
    return _instance


class TenantResolverMiddleware:
    """从请求 Host 头解析租户，支持域名绑定。

    首次请求时自动从数据库加载域名映射（懒加载），
    后续通过 ``refresh_domain_map`` 手动刷新。
    """

    def __init__(self, app):
        self.app = app
        self._domain_tenant_map: dict[str, int] = {}
        self._loaded: bool = False
        global _instance
        _instance = self

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            # 懒加载：首次请求时从数据库初始化域名映射
            if not self._loaded:
                self._init_from_db()
                self._loaded = True

            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"").decode()
            domain = host.split(":")[0]
            if domain:
                tenant_id = self._domain_tenant_map.get(domain)
                if tenant_id is not None:
                    from app.core.tenant_context import set_tenant_id
                    set_tenant_id(tenant_id)
        return await self.app(scope, receive, send)

    def _init_from_db(self) -> None:
        """从数据库加载所有租户的域名映射"""
        try:
            from app.db.database import SessionLocal
            from app.models.sys.sys_tenant import SysTenant

            db = SessionLocal()
            try:
                tenants = db.query(SysTenant).filter(
                    SysTenant.status == "active",
                    SysTenant.websites.isnot(None),
                ).all()
                domain_map: dict[str, int] = {}
                for tenant in tenants:
                    websites = tenant.websites or []
                    for domain in websites:
                        domain_map[domain] = tenant.tenant_id
                self._domain_tenant_map = domain_map
                if domain_map:
                    logger.info(f"域名→租户映射已加载: {len(domain_map)} 条")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"加载域名→租户映射失败(可忽略): {e}")

    def refresh_domain_map(self, domain_map: dict[str, int] | None = None) -> None:
        """刷新域名→租户映射表。

        如果传入 *domain_map* 则直接使用，否则从数据库重新加载。
        """
        if domain_map is not None:
            self._domain_tenant_map = domain_map
        else:
            self._init_from_db()
        self._loaded = True
