"""租户管理核心业务逻辑。"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.sys.sys_tenant import SysTenant, SysTenantPackage
from app.models.sys.sys_user import SysUser
from app.services.auth_service import AuthService
from app.schemas.sys.sys_tenant import SysTenantCreate, SysTenantUpdate, TenantPageQuery

logger = logging.getLogger(__name__)


class TenantService:
    """租户管理核心业务逻辑"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _refresh_domain_cache() -> None:
        """通知域名解析中间件刷新缓存"""
        try:
            from app.middleware.tenant_resolver import get_tenant_resolver
            resolver = get_tenant_resolver()
            if resolver:
                resolver.refresh_domain_map()
        except Exception as e:
            logger.warning(f"刷新域名缓存失败(可忽略): {e}")

    # ── 租户管理 ─────────────────────────────────────────────────────────

    def create_tenant(self, req: SysTenantCreate) -> SysTenant:
        """创建租户 + 管理员账号"""
        # 1. 检查租户名唯一性
        existing = self.db.query(SysTenant).filter(SysTenant.name == req.name).first()
        if existing:
            raise ValueError(f"租户名 '{req.name}' 已存在")

        # 2. 检查用户名唯一性
        existing_user = self.db.query(SysUser).filter(SysUser.username == req.username).first()
        if existing_user:
            raise ValueError(f"用户名 '{req.username}' 已存在")

        # 3. 创建租户
        tenant = SysTenant(
            name=req.name,
            contact_name=req.contact_name,
            contact_mobile=req.contact_mobile,
            status=req.status,
            package_id=req.package_id,
            expire_time=req.expire_time,
            account_count=req.account_count,
            websites=req.websites,
        )
        self.db.add(tenant)
        self.db.flush()

        # 4. 创建管理员用户
        admin_user = SysUser(
            username=req.username,
            password_hash=AuthService.get_password_hash(req.password),
            real_name=req.username,
            tenant_id=tenant.tenant_id,
            is_admin=True,
            status="active",
        )
        self.db.add(admin_user)
        self.db.commit()
        self.db.refresh(tenant)
        self._refresh_domain_cache()
        return tenant

    def update_tenant(self, req: SysTenantUpdate) -> SysTenant:
        """更新租户信息"""
        tenant = self.db.query(SysTenant).filter(
            SysTenant.tenant_id == req.tenant_id
        ).first()
        if not tenant:
            raise ValueError("租户不存在")

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tenant, key, value)

        self.db.commit()
        self.db.refresh(tenant)
        self._refresh_domain_cache()
        return tenant

    def delete_tenant(self, tenant_id: int) -> None:
        """删除租户（软删除：禁用所有用户 + 标记租户为 disabled）"""
        tenant = self.db.query(SysTenant).filter(
            SysTenant.tenant_id == tenant_id
        ).first()
        if not tenant:
            raise ValueError("租户不存在")

        if tenant.tenant_id == 0:
            raise ValueError("系统默认租户不可删除")

        # 禁用该租户下所有用户
        self.db.query(SysUser).filter(
            SysUser.tenant_id == tenant_id,
        ).update({"status": "disabled"})

        tenant.status = "disabled"
        self.db.commit()
        self._refresh_domain_cache()

    def get_tenant(self, tenant_id: int) -> Optional[SysTenant]:
        return self.db.query(SysTenant).filter(
            SysTenant.tenant_id == tenant_id
        ).first()

    def get_tenant_page(self, query: TenantPageQuery) -> tuple[list[SysTenant], int]:
        """分页查询租户列表"""
        q = self.db.query(SysTenant)
        if query.name:
            q = q.filter(SysTenant.name.ilike(f"%{query.name}%"))
        if query.contact_name:
            q = q.filter(SysTenant.contact_name.ilike(f"%{query.contact_name}%"))
        if query.contact_mobile:
            q = q.filter(SysTenant.contact_mobile.ilike(f"%{query.contact_mobile}%"))
        if query.status:
            q = q.filter(SysTenant.status == query.status)

        total = q.count()
        items = q.order_by(SysTenant.tenant_id.desc()).offset(
            (query.page_no - 1) * query.page_size
        ).limit(query.page_size).all()
        return items, total

    def get_simple_list(self) -> list[SysTenant]:
        """获取活跃租户精简列表（登录页下拉用）"""
        return self.db.query(SysTenant).filter(
            SysTenant.status == "active"
        ).order_by(SysTenant.tenant_id.asc()).all()

    def valid_tenant(self, tenant_id: int) -> SysTenant:
        """校验租户合法性"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")
        if tenant.status != "active":
            raise ValueError("租户已被禁用")
        if tenant.expire_time and tenant.expire_time < datetime.now():
            raise ValueError("租户已过期")
        return tenant

    # ── 套餐管理 ─────────────────────────────────────────────────────────

    def create_package(self, name: str, status: str = "active",
                       remark: str = None, menu_ids: list = None) -> SysTenantPackage:
        existing = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.name == name
        ).first()
        if existing:
            raise ValueError(f"套餐名 '{name}' 已存在")
        package = SysTenantPackage(
            name=name, status=status, remark=remark, menu_ids=menu_ids
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def update_package(self, package_id: int, **kwargs) -> SysTenantPackage:
        package = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()
        if not package:
            raise ValueError("套餐不存在")
        for key, value in kwargs.items():
            if value is not None:
                setattr(package, key, value)
        self.db.commit()
        self.db.refresh(package)
        return package

    def delete_package(self, package_id: int) -> None:
        package = self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()
        if not package:
            raise ValueError("套餐不存在")
        # 检查是否有租户使用该套餐
        tenant_count = self.db.query(SysTenant).filter(
            SysTenant.package_id == package_id
        ).count()
        if tenant_count > 0:
            raise ValueError(f"该套餐正在被 {tenant_count} 个租户使用，无法删除")
        self.db.delete(package)
        self.db.commit()

    def get_package(self, package_id: int) -> Optional[SysTenantPackage]:
        return self.db.query(SysTenantPackage).filter(
            SysTenantPackage.package_id == package_id
        ).first()

    def get_package_page(self, name: str = None, status: str = None,
                         page_no: int = 1, page_size: int = 10) -> tuple[list, int]:
        q = self.db.query(SysTenantPackage)
        if name:
            q = q.filter(SysTenantPackage.name.ilike(f"%{name}%"))
        if status:
            q = q.filter(SysTenantPackage.status == status)
        total = q.count()
        items = q.order_by(SysTenantPackage.package_id.desc()).offset(
            (page_no - 1) * page_size
        ).limit(page_size).all()
        return items, total

    def get_package_simple_list(self) -> list[SysTenantPackage]:
        return self.db.query(SysTenantPackage).filter(
            SysTenantPackage.status == "active"
        ).order_by(SysTenantPackage.package_id.asc()).all()
