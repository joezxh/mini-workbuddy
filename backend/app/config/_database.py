"""数据库配置"""
from pydantic import BaseModel
from urllib.parse import quote_plus


class DatabaseSettings(BaseModel):
    """数据库配置字段"""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "minworkbuddy"
    DATABASE_ECHO: bool = True  # 开发环境输出SQL语句

    # 数据库连接池配置
    DB_POOL_SIZE: int = 30           # 常驻连接数
    DB_MAX_OVERFLOW: int = 20        # 最大溢出连接数
    DB_POOL_TIMEOUT: int = 30        # 获取连接超时（秒）
    DB_POOL_RECYCLE: int = 1800      # 连接回收时间（30分钟）

    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接 URL（密码进行 URL 编码）"""
        password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
