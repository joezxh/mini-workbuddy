from datetime import datetime, timedelta
import bcrypt
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.sys.sys_user import SysUser


class AuthService:
    """认证服务"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """获取密码哈希"""
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def create_access_token(self, user_id: int, tenant_id: int = 0) -> str:
        """创建访问令牌"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),  # 转换为字符串存储在 JWT 中
            "tenant_id": tenant_id,
            "exp": expire
        }
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    async def login(self, username: str, password: str, tenant_id: int = 0) -> dict:
        """用户登录（含租户校验）"""
        from app.models.sys.sys_tenant import SysTenant

        # 1. 校验租户
        tenant = self.db.query(SysTenant).filter(
            SysTenant.tenant_id == tenant_id,
            SysTenant.status == "active",
        ).first()
        if not tenant:
            raise ValueError("租户不存在或已禁用")
        if tenant.expire_time and tenant.expire_time < datetime.now():
            raise ValueError("租户已过期")

        # 2. 校验用户（绑定租户）
        user = self.db.query(SysUser).filter(
            SysUser.username == username,
            SysUser.tenant_id == tenant_id,
        ).first()
        if not user:
            raise ValueError("用户名或密码错误")
        
        if not self.verify_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        
        if user.status != "active":
            raise ValueError("账号已被禁用")
        
        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        
        # 3. 生成 token（含 tenant_id）
        token = self.create_access_token(user.user_id, tenant_id=tenant_id)
        
        return {
            "token": token,
            "userId": user.user_id,
            "username": user.username,
            "realName": user.real_name,
            "tenantId": tenant_id,
        }

