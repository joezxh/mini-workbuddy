"""文件存储路径与 MIME 工具（对齐 Java FileTypeUtils / FileUtils）。"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

_EXT_WHITELIST = re.compile(r"^[A-Za-z0-9]{1,16}$")
_UNSAFE = re.compile(r"[^0-9A-Za-z._\-一-龥]+")
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
]
_MAGIC_EXT = {
    "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
    "application/pdf": "pdf", "application/zip": "zip",
}


def safe_filename(name: str, max_len: int = 120) -> str:
    """剥离路径成分并折叠危险字符，用于目录段。"""
    base = Path(name or "").name or "unnamed"
    cleaned = _UNSAFE.sub("_", base).lstrip(".")
    return (cleaned or "unnamed")[:max_len]


def normalize_dir(directory: str | None) -> str:
    """规范化业务目录段：去首尾斜杠、反斜杠转正斜杠、阻断穿越。"""
    if not directory:
        return ""
    parts = [p for p in str(directory).replace("\\", "/").split("/")
             if p and p not in (".", "..")]
    return "/".join(safe_filename(p) for p in parts)


def detect_mime(content: bytes, filename: str | None = None, declared: str | None = None) -> str:
    """按魔数 > 声明 content-type > 扩展名顺序推断 MIME。"""
    for magic, mime in _MAGIC:
        if content[:8].startswith(magic):
            return mime
    if declared and declared != "application/octet-stream":
        return declared
    mime = mimetypes.guess_type(filename or "")[0]
    return mime or "application/octet-stream"


def detect_extension(content: bytes, filename: str | None = None) -> str:
    """取文件名扩展；非法则按内容魔数推断，最终兜底 bin。"""
    ext = Path(filename or "").suffix.lstrip(".").lower()
    if _EXT_WHITELIST.fullmatch(ext):
        return ext
    mime = detect_mime(content, filename)
    return _MAGIC_EXT.get(mime, "bin")


def generate_path(content: bytes, filename: str, directory: str | None = None) -> str:
    """内容寻址存储路径：{dir}/sha256.{ext}（纯 ASCII，避免中文 URL 编码问题）。"""
    digest = hashlib.sha256(content).hexdigest()
    ext = detect_extension(content, filename)
    path = f"{digest}.{ext}"
    prefix = normalize_dir(directory)
    return f"{prefix}/{path}" if prefix else path


def generate_upload_path(filename: str, directory: str | None = None,
                         date_prefix: bool = True, suffix_timestamp: bool = True) -> str:
    """预签名直传路径：yyyyMMdd/{safe_name}[_ts].{ext}（Java generateUploadPath 等价）。"""
    safe = safe_filename(filename)
    stem, dot, ext = safe.rpartition(".")
    if not dot:
        stem, ext = safe, ""
    if suffix_timestamp:
        stem = f"{stem}_{int(datetime.now().timestamp() * 1000)}"
    name = f"{stem}.{ext}" if ext else stem
    prefix = normalize_dir(directory)
    if date_prefix:
        date_seg = datetime.now().strftime("%Y%m%d")
        prefix = f"{prefix}/{date_seg}" if prefix else date_seg
    return f"{prefix}/{name}" if prefix else name


def strip_query(url: str | None) -> str:
    """去掉 URL 查询串（私有桶预签名参数不落库）。"""
    if not url:
        return ""
    return url.split("?", 1)[0].split("#", 1)[0]


def format_file_url(domain: str | None, config_id: int, path: str) -> str:
    """拼装下载 URL；domain 为空时返回相对路径。"""
    encoded = quote(path, safe="/")
    return f"{(domain or '').rstrip('/')}/api/v1/system/file/{config_id}/get/{encoded}"


def join_path(*parts: str | None) -> str:
    return "/".join(p.strip("/") for p in parts if p)
