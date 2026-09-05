"""共享的通用辅助函数，消除各 service/router 中重复定义的小工具。

此前 _get_beijing_now / get_beijing_now / _coerce_bool / _safe_bool 在多个文件重复定义。
统一在此提供，业务模块通过 `from app.utils.common import ...` 复用。
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


def get_beijing_now() -> datetime:
    """获取当前北京时间（带时区信息，UTC+8）。"""
    return datetime.now(timezone(timedelta(hours=8)))


def get_beijing_now_naive() -> datetime:
    """获取当前北京时间（不带时区，tzinfo=None），用于写入 naive 字段。"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    except Exception:
        return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


def coerce_bool(v: Any) -> Optional[bool]:
    """宽松布尔解析：None/非布尔返回 None，字符串 true/1/yes/on 视为真。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return None
