from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus
# 加载环境变量
load_dotenv()

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从环境变量构建数据库 URL
# 注意：不使用 config.set_main_option() 设置 URL，因为底层 configparser
# 会把 % 当作插值语法（如 %40、%21），导致 ValueError
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")
db_name = os.getenv("DB_NAME", "minworkbuddy")
# 密码中可能包含特殊字符（如 @! 等），需要 URL 编码
_database_url = f"postgresql://{db_user}:{quote_plus(db_password)}@{db_host}:{db_port}/{db_name}"

# add your model's MetaData object here
# for 'autogenerate' support
from app.db.database import Base
# 触发所有 ORM 模型注册到 Base.metadata，否则 autogenerate 会漏表。
# （此前依赖 main.py 的 F401 副作用导入，alembic 不启动 FastAPI，故此必须显式导入。）
import app.db.init_models  # noqa: F401
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # 直接使用 _database_url，绕过 configparser 的 % 插值问题
    context.configure(
        url=_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 直接使用 create_engine(_database_url)，绕过 configparser 的 % 插值问题
    connectable = create_engine(_database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
