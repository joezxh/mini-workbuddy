from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging


# 配置 SQLAlchemy 日志
if settings.DATABASE_ECHO:
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    echo_pool=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    # TCP keepalive：长任务中单个连接在多次 LLM await 期间会长时间空闲，
    # 远端 PostgreSQL / 网络中间件可能丢弃空闲连接，导致后续同步读阻塞并冻结整个
    # asyncio 事件循环。开启 keepalive 探活可在空闲期保活连接，connect_timeout
    # 防止建连阶段无限挂起。（仅对 psycopg2/PostgreSQL 生效）
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 15,
        "keepalives_interval": 5,
        "keepalives_count": 5,
        "connect_timeout": 10,
    },
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # 提交后不过期对象，适合只读查询
)

# 创建基类
Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
        # 如果会话中有未提交的事务且没有修改，自动提交以避免ROLLBACK
        if db.is_active and not db.dirty and not db.new and not db.deleted:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        from app.core.tenant_context import clear
        clear()
        db.close()

