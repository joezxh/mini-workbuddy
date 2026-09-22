"""技能文件树扫描（list_files）与安全文本预览（read_file_content）单测。

覆盖 spec `2026-09-21-skill-file-tree-and-skill-mode-execution-design.md` 测试要点 1、2：
- type 标记（script / reference / other）与 SKILL.md 排除；
- 目录缺失返回空列表；
- 路径穿越 / 二进制 / 超限 / 非 UTF-8 拒绝。
"""
from pathlib import Path

import pytest

from app.ai.agent_factory import resolve_skill_name
from app.services.ai.ai_skill_admin_service import AiSkillAdminService


@pytest.fixture()
def svc(tmp_path: Path) -> AiSkillAdminService:
    s = AiSkillAdminService()
    s.SKILLS_BASE_DIR = tmp_path
    return s


def _build_pkg(tmp_path: Path, package_id: str = "demo") -> Path:
    pkg = tmp_path / package_id
    (pkg / "scripts").mkdir(parents=True)
    (pkg / "references").mkdir(parents=True)
    (pkg / "assets").mkdir(parents=True)
    (pkg / "SKILL.md").write_text("# demo", encoding="utf-8")
    (pkg / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
    (pkg / "references" / "guide.md").write_text("hello", encoding="utf-8")
    (pkg / "assets" / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    (pkg / "notes.txt").write_text("note", encoding="utf-8")
    return pkg


# ── list_files ──────────────────────────────────────────────────────────


def test_list_files_types_and_excludes_skill_md(svc, tmp_path):
    _build_pkg(tmp_path)
    res = svc.list_files("demo")
    paths = [f["path"] for f in res["files"]]

    assert res["package_id"] == "demo"
    assert "SKILL.md" not in paths

    types = {f["path"]: f["type"] for f in res["files"]}
    assert types["scripts/run.py"] == "script"
    assert types["references/guide.md"] == "reference"
    assert types["notes.txt"] == "other"
    assert types["assets/logo.png"] == "other"

    assert res["total_count"] == len(res["files"])
    assert res["total_size"] == sum(f["size"] for f in res["files"])
    assert paths == sorted(paths)


def test_list_files_ext_without_dot(svc, tmp_path):
    _build_pkg(tmp_path)
    exts = {f["path"]: f["ext"] for f in svc.list_files("demo")["files"]}
    assert exts["scripts/run.py"] == "py"
    assert exts["references/guide.md"] == "md"


def test_list_files_missing_dir_returns_empty(svc):
    res = svc.list_files("nope")
    assert res["files"] == []
    assert res["total_count"] == 0
    assert res["total_size"] == 0


def test_list_files_nested_script_dir_is_not_script(svc, tmp_path):
    """references/ 下即使有同名目录也不算 script；scripts 下非 .py 不算 script。"""
    pkg = tmp_path / "demo"
    (pkg / "scripts").mkdir(parents=True)
    (pkg / "references" / "sub").mkdir(parents=True)
    (pkg / "scripts" / "data.json").write_text("{}", encoding="utf-8")
    (pkg / "references" / "sub" / "deep.py").write_text("x = 1\n", encoding="utf-8")

    types = {f["path"]: f["type"] for f in svc.list_files("demo")["files"]}
    assert types["scripts/data.json"] == "other"
    assert types["references/sub/deep.py"] == "reference"


# ── read_file_content ───────────────────────────────────────────────────


def test_read_file_content_ok(svc, tmp_path):
    _build_pkg(tmp_path)
    res = svc.read_file_content("demo", "references/guide.md")
    assert res["content"] == "hello"
    assert res["size"] == 5
    assert res["path"] == "references/guide.md"


@pytest.mark.parametrize(
    "bad",
    ["../SKILL.md", "../../outside.py", "/etc/hosts", "..\\SKILL.md", "scripts/../../SKILL.md"],
)
def test_read_file_content_rejects_traversal(svc, tmp_path, bad):
    _build_pkg(tmp_path)
    with pytest.raises(ValueError):
        svc.read_file_content("demo", bad)


def test_read_file_content_rejects_binary(svc, tmp_path):
    _build_pkg(tmp_path)
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "assets/logo.png")


def test_read_file_content_rejects_disallowed_extension(svc, tmp_path):
    pkg = tmp_path / "demo"
    pkg.mkdir(parents=True)
    (pkg / "blob.bin").write_bytes(b"plain-ascii")
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "blob.bin")


def test_read_file_content_rejects_oversize(svc, tmp_path):
    pkg = tmp_path / "demo"
    pkg.mkdir(parents=True)
    (pkg / "big.txt").write_bytes(b"a" * (1024 * 1024 + 1))
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "big.txt")


def test_read_file_content_rejects_missing_file(svc, tmp_path):
    _build_pkg(tmp_path)
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "references/absent.md")


def test_read_file_content_rejects_non_utf8(svc, tmp_path):
    pkg = tmp_path / "demo"
    pkg.mkdir(parents=True)
    (pkg / "latin.txt").write_bytes("caf\u00e9".encode("latin-1"))
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "latin.txt")


# ── SkillAgent 技能标识解析 ─────────────────────────────────────────────


def test_resolve_skill_name_prefers_name_then_package_id():
    assert resolve_skill_name({"name": "a", "package_id": "b"}) == "a"
    assert resolve_skill_name({"package_id": "buffett"}) == "buffett"


def test_resolve_skill_name_falls_back_to_general():
    assert resolve_skill_name({}) == "general"
    assert resolve_skill_name(None) == "general"
