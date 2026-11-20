# -*- coding: utf-8 -*-
"""org_patterns 测试共享配置：注入 examples 路径 + 数字开头模块加载器。"""
import importlib.util
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parents[2] / "examples" / "org_patterns"
sys.path.insert(0, str(EXAMPLES_DIR))


def load_example(filename: str):
    """按文件路径加载数字开头的范例模块（如 01_supervisor_worker.py）。"""
    path = EXAMPLES_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod