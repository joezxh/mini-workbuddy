from app.db.database import SessionLocal
from app.models.sys.sys_user import SysUser
from app.models.sys.sys_tenant import SysTenant
from app.services.auth_service import AuthService

db = SessionLocal()
try:
    u = db.query(SysUser).filter(SysUser.username == 'admin').first()
    print(f'hash: {u.password_hash}')
    print(f'verify admin123: {AuthService.verify_password("admin123", u.password_hash)}')

    tenant = db.query(SysTenant).filter(SysTenant.tenant_id == 0, SysTenant.status == 'active').first()
    print(f'tenant: {tenant}')
    print(f'tenant expire: {tenant.expire_time}')

    user = db.query(SysUser).filter(SysUser.username == 'admin', SysUser.tenant_id == 0).first()
    print(f'user found: {user is not None}')
    if user:
        print(f'user tenant: {user.tenant_id}')
        print(f'verify: {AuthService.verify_password("admin123", user.password_hash)}')

    svc = AuthService(db)
    try:
        result = svc.login('admin', 'admin123', 0)
        print(f'login success: {result}')
    except ValueError as e:
        print(f'login ValueError: {e}')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()