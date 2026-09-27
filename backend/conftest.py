"""backend conftest — 注入项目根目录到 sys.path,保证 `app.*` 可导入。"""
import os
import sys

# 让 pytest 可以找到 `app` 包:测试在 backend/ 下运行,但 app 在 backend/app/ 下
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

# 优先:把 backend 目录加入 sys.path,这样 `app` 就能被解析
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)