from typing import Optional
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader, APIKeyQuery
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.database import get_db
from app.config import settings
from app.models.sys.sys_user import SysUser

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Open API Key 认证（用于外部系统通过固定 API Key 访问开放接口）
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def verify_api_key(
    key_header: Optional[str] = Security(_api_key_header),
    key_query: Optional[str] = Security(_api_key_query),
) -> str:
    """
    验证 Open API Key。
    支持两种传入方式：
      - HTTP Header：X-API-Key: <key>
      - Query 参数：?api_key=<key>
    """
    if not settings.OPEN_API_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Open API 访问未启用",
        )
    key = key_header or key_query
    if not key or key != settings.OPEN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key


def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    key_header: Optional[str] = Security(_api_key_header),
    key_query: Optional[str] = Security(_api_key_query),
    db: Session = Depends(get_db),
) -> Optional[SysUser]:
    """
    双模式认证：优先验证 JWT Token，失败则验证 API Key。
    JWT 认证成功返回 SysUser 对象；API Key 认证成功返回 None。
    两者均失败则抛出 401。
    """
    # 1. 尝试 JWT
    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            user_id_str = payload.get("sub")
            if user_id_str:
                user = db.query(SysUser).filter(SysUser.user_id == int(user_id_str)).first()
                if user and user.status == "active":
                    # 设置租户上下文
                    if hasattr(user, 'tenant_id') and user.tenant_id is not None:
                        from app.core.tenant_context import set_tenant_id
                        set_tenant_id(user.tenant_id)
                    return user
        except (JWTError, ValueError):
            pass

    # 2. 尝试 API Key
    if settings.OPEN_API_ENABLED:
        key = key_header or key_query
        if key and key == settings.OPEN_API_KEY:
            return None  # API Key 认证通过，无用户对象

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请提供有效的 JWT Token 或 API Key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> SysUser:
    """获取当前登录用户"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证"
            )
        user_id = int(user_id_str)  # 转换为整数
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用"
        )
    
    # 设置租户上下文
    if hasattr(user, 'tenant_id') and user.tenant_id is not None:
        from app.core.tenant_context import set_tenant_id
        set_tenant_id(user.tenant_id)
    
    return user


def get_current_active_user(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """获取当前活跃用户"""
    return current_user


def require_admin(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """要求管理员权限"""
    # 检查用户是否是管理员
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return current_user


def require_admin_or_backend_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> Optional[SysUser]:
    """
    双模式管理员认证：
      1. 优先验证 JWT Token（要求 is_admin=True）
      2. 若 JWT 无效，验证 OPEN_API_KEY（供 Dify 工作流内部调用）
    两者均失败则抛出 401。
    """
    token = credentials.credentials if credentials else None

    # 1. 尝试 JWT 管理员认证
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id_str = payload.get("sub")
            if user_id_str:
                user = db.query(SysUser).filter(SysUser.user_id == int(user_id_str)).first()
                if user and user.status == "active" and user.is_admin:
                    return user
        except (JWTError, ValueError):
            pass

    # 2. 尝试 OPEN_API_KEY 认证
    if token and settings.OPEN_API_ENABLED and token == settings.OPEN_API_KEY:
        # 构造虚拟管理员对象，满足下游代码对 SysUser 属性的访问
        fake_admin = SysUser()
        fake_admin.is_admin = True
        fake_admin.status = "active"
        return fake_admin

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请提供有效的 JWT Token 或 API Key",
        headers={"WWW-Authenticate": "Bearer"},
    )