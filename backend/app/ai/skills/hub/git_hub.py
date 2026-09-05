"""Git 仓库型 Skill Hub 适配器。

实现 SkillHubAdapter 接口：
- ensure_cloned：首次访问把 git 仓库 clone 到本地缓存目录；
- list_remote：读取缓存中的 category_index.json（降级扫描 skills/*/SKILL.md）；
- fetch：把 skills/<id>/ 目录打包为 zip，并注入兼容 import_zip 的 SKILL.json。

官方/第三方 Git 仓库（如 tianque-skills、anbeime/skill）均为源码仓库，
其目录结构为 skills/<id>/（含 SKILL.md + manifest.json + 子目录）。
import_zip 要求 zip 内含 SKILL.json，因此 fetch 时做格式转换。
"""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.config import settings

logger = logging.getLogger(__name__)

# Hub 七大类 → 本工程 skill_category 字典表代码（best-effort 映射）
_HUB_CATEGORY_MAP = {
    "key_person": "risk-assessment",
    "mediation": "other",
    "legal": "legal-reasoning",
    "evidence": "argumentation",
    "compliance": "other",
    "risk_event": "risk-assessment",
    "general": "other",
}


class GitHubAdapter(SkillHubAdapter):
    """基于 git clone 的 Skill Hub 适配器。"""

    name = "git"

    def __init__(
        self,
        repo_id: int,
        url: str,
        branch: str = "main",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.repo_id = repo_id
        self.url = url
        self.branch = branch or "main"
        self.username = username
        self.password = password

    # ── 缓存管理 ──────────────────────────────────────────────
    @property
    def cache_dir(self) -> Path:
        return settings.hub_cache_path / str(self.repo_id)

    def _clone_url(self) -> str:
        """返回注入凭据的 clone 地址（仅当配置了 username/password）。

        凭据中的 @ / : / / 等保留字符会被 URL 编码，避免破坏地址结构
        （例如账号含 @ 时导致 git 解析 host:port 失败）。

        协议兜底：私有化 GitLab 常通过反代在 HTTP 下剥离 Basic Auth 头，
        导致 git clone 报 "HTTP Basic: Access denied"。此处强制将 http 升级为
        https（与 GitLab 实际可克隆协议保持一致），repo 记录填 http/https 均可工作。
        """
        base = self.url
        if base.startswith("http://"):
            base = "https://" + base[len("http://"):]

        if not (self.username and self.password):
            return base
        from urllib.parse import quote, urlparse, urlunparse

        user = quote(self.username, safe="")
        pwd = quote(self.password, safe="")
        parsed = urlparse(base)
        netloc = f"{user}:{pwd}@{parsed.netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def _safe_url(self) -> str:
        """脱敏后的地址，用于日志（隐藏密码）。"""
        if not (self.username and self.password):
            return self.url
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(self.url)
        netloc = f"{self.username}:***@{parsed.netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def _is_valid_clone(self, cache: Path) -> bool:
        """判断缓存目录是否为一次有效 clone（含 .git 且非空）。

        避免「目录已存在但内容为空/克隆中途失败」时误判为已克隆，
        从而永久返回空列表。
        """
        if not cache.is_dir():
            return False
        if not (cache / ".git").exists():
            return False
        return any(cache.iterdir())

    def ensure_cloned(self, force: bool = False) -> Path:
        """确保仓库已 clone 到缓存目录；force=True 时重新 clone。

        若缓存目录存在但非有效 clone（如空目录/克隆中途失败残留），
        同样视为未克隆并重新克隆。
        """
        cache = self.cache_dir
        if cache.exists() and not force and self._is_valid_clone(cache):
            return cache
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)

        cache.parent.mkdir(parents=True, exist_ok=True)
        clone_url = self._clone_url()
        logger.info("克隆 skill hub 仓库 %s -> %s", self._safe_url(), cache)
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "-b",
                    self.branch,
                    clone_url,
                    str(cache),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"克隆仓库失败: {e.stderr or e.stdout or e}"
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError("未找到 git 命令，请确认运行环境已安装 git") from e
        return cache

    # ── 列表 ──────────────────────────────────────────────────
    def list_remote(self) -> list[SkillHubEntry]:
        cache = self.ensure_cloned()
        index_path = cache / "category_index.json"
        if index_path.exists():
            try:
                return self._list_from_index(index_path)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("category_index.json 解析失败，降级扫描: %s", e)

        return self._list_from_scan(cache)

    def _list_from_index(self, index_path: Path) -> list[SkillHubEntry]:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        entries: list[SkillHubEntry] = []
        for cat in data.get("categories", []):
            cat_key = cat.get("key", "general")
            for s in cat.get("skills", []):
                entries.append(
                    SkillHubEntry(
                        id=s["id"],
                        name=s.get("name", s["id"]),
                        version=s.get("version"),
                        description=s.get("description"),
                        meta={
                            "category": cat_key,
                            "category_name": cat.get("name"),
                            "tags": s.get("tags", []),
                            "path": s.get("path", f"skills/{s['id']}"),
                        },
                    )
                )
        return entries

    def _list_from_scan(self, cache: Path) -> list[SkillHubEntry]:
        """递归扫描 skills/ 下任意层级的子目录，定位含 SKILL.md 的目录。

        适用于未提供 category_index.json 的自定义仓库：
        目录内存在 SKILL.md 即确认为一个 skill，读取 frontmatter 的
        name/version/description；不产生分类（category 留空），
        meta.path 记录相对仓库根的完整路径（如 skills/engineering/ask-matt）
        供 fetch 定位。
        """
        skills_dir = cache / "skills"
        entries: list[SkillHubEntry] = []
        if not skills_dir.is_dir():
            return entries
        seen_ids: set[str] = set()
        for md in sorted(skills_dir.rglob("SKILL.md")):
            skill_dir = md.parent
            rel = skill_dir.relative_to(cache)
            # skills/ 根目录自身的 SKILL.md 不算独立 skill
            if len(rel.parts) < 2:
                continue
            fm = self._parse_frontmatter(md)
            skill_id = skill_dir.name
            if skill_id in seen_ids:
                # 跨分组同名目录消歧：id 不能含 /（会破坏安装 URL 路径参数）
                parent_name = rel.parts[-2]
                skill_id = f"{parent_name}-{skill_id}"
                if skill_id in seen_ids:
                    continue
            seen_ids.add(skill_id)
            entries.append(
                SkillHubEntry(
                    id=skill_id,
                    name=fm.get("name") or skill_id,
                    version=fm.get("version"),
                    description=fm.get("description"),
                    meta={"path": rel.as_posix()},
                )
            )
        return entries

    # ── 拉取 ──────────────────────────────────────────────────
    def fetch(self, entry: SkillHubEntry) -> bytes:
        cache = self.ensure_cloned()
        skill_id = entry.id
        # 优先用扫描时记录的完整相对路径（支持嵌套目录如 skills/engineering/ask-matt）
        rel_path = entry.meta.get("path") or f"skills/{skill_id}"
        skill_dir = cache / rel_path
        if not skill_dir.is_dir():
            raise RuntimeError(f"仓库中不存在 skill 目录: {rel_path}")

        skill_json = self._build_skill_json(skill_dir, entry)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                f"{skill_id}/SKILL.json",
                json.dumps(skill_json, ensure_ascii=False, indent=2),
            )
            # os.walk 兼容 Python 3.11（Path.walk 为 3.12+ API）
            for root, _dirs, files in os.walk(skill_dir):
                for fname in files:
                    abs_path = Path(root) / fname
                    rel = abs_path.relative_to(skill_dir)
                    if rel.name == "SKILL.json":
                        continue
                    zf.write(abs_path, f"{skill_id}/{rel.as_posix()}")
        buffer.seek(0)
        return buffer.read()

    # ── 工具 ──────────────────────────────────────────────────
    def _build_skill_json(self, skill_dir: Path, entry: SkillHubEntry) -> dict:
        md = skill_dir / "SKILL.md"
        fm = self._parse_frontmatter(md) if md.exists() else {}
        category = entry.meta.get("category", "general")
        mapped = _HUB_CATEGORY_MAP.get(category, "other")

        manifest: dict = {}
        mpath = skill_dir / "manifest.json"
        if mpath.exists():
            try:
                manifest = json.loads(mpath.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {}

        scripts = []
        for sc in manifest.get("scripts", []):
            if isinstance(sc, dict) and sc.get("id"):
                scripts.append(
                    {
                        "id": sc["id"],
                        "name": sc.get("name", sc["id"]),
                        "command": sc.get("command", ""),
                        "description": sc.get("description"),
                        "params": sc.get("params"),
                    }
                )

        return {
            "id": entry.id,
            "name": fm.get("name") or manifest.get("name") or entry.id,
            "category": mapped,
            "description": fm.get("description") or manifest.get("description"),
            "icon": fm.get("icon", "tool"),
            "version": fm.get("version") or manifest.get("version", "1.0.0"),
            "type": fm.get("type", manifest.get("type", "prompt")),
            "entry": fm.get("entry", manifest.get("entry")),
            "scripts": scripts,
        }

    @staticmethod
    def _parse_frontmatter(md_path: Path) -> dict:
        import re

        text = md_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        block = text[3:end].strip("\n")
        fields: dict = {}
        for line in block.splitlines():
            m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                fields[key] = val
        return fields
