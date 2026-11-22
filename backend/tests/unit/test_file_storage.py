"""统一文件存储单元测试：路径工具、LOCAL 客户端、工厂、压缩包安全过滤。

不依赖真实数据库 / Redis / boto3，可在任意环境运行。
"""
from __future__ import annotations

import pytest

from app.framework.file.enums import FileStorageEnum
from app.framework.file.client.factory import FileClientFactory
from app.framework.file.client.local_client import LocalFileClient
from app.framework.file.utils import (
    detect_extension, detect_mime, format_file_url, generate_path,
    generate_upload_path, normalize_dir, safe_filename, strip_query,
)
from app.services.file.archive_extract_service import _is_ignored, _safe_rel_path


# ── 路径工具 ────────────────────────────────────────────────────────────────

def test_generate_path_is_content_addressed():
    content = b"hello file storage"
    path = generate_path(content, "中文名.pdf", directory="知识库/子目录")
    # 文件名（含中文）不进路径，仅保留 sha256 + 扩展名；目录段允许 CJK
    assert "中文名" not in path
    assert path.endswith(".pdf")
    assert path.startswith("知识库/子目录/")
    assert generate_path(content, "x.pdf", directory="知识库/子目录") == path
    assert generate_path(b"other", "x.pdf") != path


def test_generate_path_invalid_extension_falls_back_to_magic():
    png = b"\x89PNG\r\n\x1a\n" + b"rest"
    assert generate_path(png, "image.weird$ext").endswith(".png")


def test_detect_mime_and_extension():
    assert detect_mime(b"%PDF-1.7 rest", "x.bin") == "application/pdf"
    assert detect_mime(b"plain", "x.txt", declared="text/plain") == "text/plain"
    assert detect_extension(b"plain", "a.JSON") == "json"
    assert detect_extension(b"plain", "a.bad$ext") == "bin"


def test_safe_filename_and_normalize_dir():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("a" * 200) == "a" * 120
    assert normalize_dir("a/../b//c") == "a/b/c"
    assert normalize_dir(None) == ""


def test_generate_upload_path_shape():
    path = generate_upload_path("报告.pdf", directory="kb")
    assert path.startswith("kb/")
    assert "/报告_" in path and path.endswith(".pdf")


def test_url_helpers():
    assert format_file_url("https://cdn.example.com", 7, "dir/a b.pdf") == \
        "https://cdn.example.com/api/v1/system/file/7/get/dir/a%20b.pdf"
    assert strip_query("https://x/y?sig=abc#f") == "https://x/y"


# ── 存储枚举与工厂 ──────────────────────────────────────────────────────────

def test_storage_enum_supported():
    assert FileStorageEnum.is_supported(FileStorageEnum.LOCAL)
    assert FileStorageEnum.is_supported(int(FileStorageEnum.DB))
    assert not FileStorageEnum.is_supported(FileStorageEnum.FTP)
    assert not FileStorageEnum.is_supported(999)


class _FakeConfig:
    def __init__(self, id, code, storage, config):
        self.id, self.code, self.storage, self.config = id, code, storage, config


def test_factory_builds_local_client_and_caches(tmp_path):
    cfg = _FakeConfig(1, "kms", int(FileStorageEnum.LOCAL), {"basePath": str(tmp_path), "domain": ""})
    FileClientFactory.invalidate()
    c1 = FileClientFactory.get_client(cfg)
    c2 = FileClientFactory.get_client(cfg)
    assert isinstance(c1, LocalFileClient)
    assert c1 is c2
    assert c1.config_id == 1 and c1.code == "kms"
    FileClientFactory.invalidate(code="kms")
    c3 = FileClientFactory.get_client(cfg)
    assert c3 is not c1


def test_factory_rejects_unimplemented_storage(tmp_path):
    cfg = _FakeConfig(2, "ftp", int(FileStorageEnum.FTP), {})
    with pytest.raises(ValueError, match="未实现"):
        FileClientFactory.get_client(cfg)


# ── LOCAL 客户端 ────────────────────────────────────────────────────────────

def test_local_client_upload_download_delete(tmp_path):
    client = LocalFileClient(1, "kms", {"basePath": str(tmp_path), "domain": ""})
    path = "kb/abc.pdf"
    url = client.upload(b"payload", path)
    assert url == "/api/v1/system/file/1/get/kb/abc.pdf"
    assert client.get_content(path) == b"payload"
    assert client.get_files("kb")[0]["path"] == path
    client.delete(path)
    assert client.get_content(path) is None


def test_local_client_blocks_path_traversal(tmp_path):
    client = LocalFileClient(1, "kms", {"basePath": str(tmp_path)})
    with pytest.raises(ValueError):
        client.get_content("../../etc/passwd")


# ── 压缩包安全过滤 ──────────────────────────────────────────────────────────

def test_archive_safe_rel_path():
    assert _safe_rel_path("folder/a.txt") == "folder/a.txt"
    assert _safe_rel_path("/abs/a.txt") == "abs/a.txt"
    assert _safe_rel_path("../a.txt") is None
    assert _safe_rel_path("a/../../b.txt") is None


def test_archive_ignored_names():
    assert _is_ignored("__MACOSX/foo")
    assert _is_ignored("photo/.DS_Store")
    assert _is_ignored("~$doc.docx")
    assert not _is_ignored("folder/report.pdf")


# ── 目录树构建 ──────────────────────────────────────────────────────────────

class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDb:
    """只实现 get_directories 需要的 execute().scalars().all() 链。"""

    def __init__(self, paths):
        self._paths = paths

    def execute(self, *args, **kwargs):
        return _FakeScalarResult(self._paths)


def test_get_directories_builds_nested_tree():
    from app.services.file.file_service import get_directories

    db = _FakeDb([
        "kb/2026/a.pdf",
        "kb/2026/b.png",
        "kb/2027/c.pdf",
        "kb/2026/sub/d.txt",
    ])
    tree = get_directories(db)

    assert [d["name"] for d in tree] == ["kb"]
    kb = tree[0]
    assert kb["path"] == "kb"
    assert kb["hasChildren"] is True

    # 同层按名称排序
    assert [c["name"] for c in kb["children"]] == ["2026", "2027"]

    y2026 = kb["children"][0]
    assert y2026["path"] == "kb/2026"
    assert y2026["hasChildren"] is True

    sub = y2026["children"][0]
    assert sub["name"] == "sub"
    assert sub["path"] == "kb/2026/sub"
    assert sub["hasChildren"] is False
    assert sub["children"] == []

    y2027 = kb["children"][1]
    assert y2027["path"] == "kb/2027"
    assert y2027["hasChildren"] is False
    assert y2027["children"] == []


def test_get_directories_ignores_root_level_files():
    """单段路径（根目录下的文件）不构成目录，不应出现在目录树里。"""
    from app.services.file.file_service import get_directories

    tree = get_directories(_FakeDb(["abc123.pdf", "kb/x.pdf"]))
    assert [d["name"] for d in tree] == ["kb"]


def test_get_directories_empty_database():
    from app.services.file.file_service import get_directories

    assert get_directories(_FakeDb([])) == []
