"""共享基础常量和路径计算"""
import os
from pathlib import Path


# 项目根目录（backend/ 上一级），避免 settings.BASE_DIR 未定义崩溃。
# 支持通过环境变量 APP_BASE_DIR 显式覆盖，以适配 Docker 容器：
# WORKDIR=/app 且 COPY app ./app 时，__file__ 三级上溯会算成 / 而非 /app，
# 导致所有 _BASE_DIR/"backend"/... 路径与挂载卷（/app/data/...）对不上。
_BASE_DIR = Path(os.environ.get("APP_BASE_DIR", Path(__file__).resolve().parent.parent.parent.parent))
