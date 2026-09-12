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
import stat
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Optional

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.config import settings

logger = logging.getLogger(__name__)


def _force_unlink(func, path: str, exc_info) -> None:  # noqa: ANN001
    """shutil.rmtree 的纠错回调：清掉只读属性后再删一次。

    git 的 `.git/objects/**` 权限是 444（只读），Windows 下 rmtree 会抛
    PermissionError；此时若用 ignore_errors=True，会**静默留下残骸**，
    随后 git clone 就报
    "destination path already exists and is not an empty directory"。
    """
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass
    try:
        func(path)
    except OSError:
        pass


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
        """判断缓存目录是否为一次**完整**的 clone。

        三个条件缺一不可：
          1. 目录存在且含 .git；
          2. 工作树含 .git 之外的文件（rmtree 半失败会留下「.git 完好 + 工作树空」的空壳）；
          3. HEAD 能解析出有效提交（clone 被中断会留下 refs/heads/.invalid）。

        只检查前两条会把半成品当成有效克隆，从而陷入
        「pull 失败 → reset 失败 → 重克隆又被中断」的死循环，并永久返回空列表。
        """
        if not cache.is_dir():
            return False
        if not (cache / ".git").exists():
            return False
        if not self._worktree_has_content(cache):
            return False
        return self._head_ok(cache)

    @staticmethod
    def _worktree_has_content(cache: Path) -> bool:
        """工作树是否含 .git 之外的文件。"""
        try:
            return any(p.name != ".git" for p in cache.iterdir())
        except OSError:
            return False

    @staticmethod
    def _head_ok(cache: Path) -> bool:
        """HEAD 是否指向一个可解析的提交。"""
        try:
            r = subprocess.run(
                ["git", "-C", str(cache), "rev-parse", "--verify", "-q", "HEAD"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
        return r.returncode == 0

    def ensure_cloned(self, force: bool = False) -> Path:
        """确保仓库已 clone 到缓存目录。

        刷新策略（force=True）：目录已存在且为**完整**克隆时，执行 git pull
        增量刷新，而**不再删除重建**——目录常被 IDE / uvicorn 监视器 / 杀软占用，
        rmtree 会静默失败并残留非空目录，导致 git clone 报
        "destination path already exists and is not an empty directory"。

        目录存在但非完整克隆（空目录、克隆中途失败、HEAD 损坏）时，清理后重新克隆。
        若清理失败（目录被占用），回退为克隆到临时兄弟目录，成功后原子替换——
        避免对非空目录直接 clone 必然 128 的问题。
        """
        cache = self.cache_dir

        if cache.exists() and self._is_valid_clone(cache):
            if not force:
                return cache
            if self._try_pull(cache):
                return cache
            logger.warning("git pull 刷新失败，将尝试重新克隆: %s", cache)

        if cache.exists():
            self._remove_cache(cache)

        cache.parent.mkdir(parents=True, exist_ok=True)

        # 删除失败仍非空时，git clone 进原目录必报 "already exists"；
        # 此时改克隆到临时目录，成功后再尝试替换回正式路径。
        target = cache
        if self._dir_not_empty(cache):
            target = cache.with_name(cache.name + ".clone-tmp")
            self._remove_cache(target)
            logger.warning(
                "缓存目录被占用无法清空，改用临时目录克隆: %s -> %s", cache, target
            )

        clone_url = self._clone_url()
        logger.info("克隆 skill hub 仓库 %s -> %s", self._safe_url(), target)

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                # 前两次按仓库配置的分支克隆；仍失败时第三次退回克隆远端默认分支，
                # 兼容远端把 master 改成 main（或反之）而未同步更新仓库记录的情况。
                branch = self.branch if attempt < 2 else None
                if branch is None:
                    logger.warning(
                        "按分支 %s 克隆失败，退回克隆远端默认分支: %s",
                        self.branch,
                        self._safe_url(),
                    )
                self._run_clone(target, clone_url, branch)
                if self._is_valid_clone(target):
                    if target != cache:
                        self._remove_cache(cache)
                        if cache.exists():
                            # 正式路径仍被占用，无法替换；保留 tmp 供下次直接 pull
                            self._remove_cache(target)
                            raise RuntimeError(
                                f"缓存目录被占用无法替换: {cache}；"
                                "请关闭占用该目录的进程（IDE/杀软/索引器）后重试"
                            )
                        target.rename(cache)
                    return cache
                # clone 退出码为 0 但工作树不完整（极罕见）：清掉重来
                logger.warning("克隆结束但工作树不完整，重试: %s", target)
                self._remove_cache(target)
                last_err = RuntimeError("克隆后工作树校验失败")
                continue
            except subprocess.CalledProcessError as e:
                last_err = e
                logger.warning(
                    "git clone 失败(尝试 %d/3): %s",
                    attempt + 1,
                    (e.stderr or e.stdout or str(e)).strip().splitlines()[-1:],
                )
                # .git 已就绪但工作树 checkout 失败 → 就地重建工作树
                if (target / ".git").exists() and self._recover_checkout(target):
                    if target != cache:
                        return self._promote_tmp(target, cache)
                    return target
                self._remove_cache(target)
                time.sleep(0.5 * (attempt + 1))
            except subprocess.TimeoutExpired as e:
                last_err = e
                logger.warning("git clone 超时(尝试 %d/3)", attempt + 1)
                self._remove_cache(target)
            except FileNotFoundError as e:
                raise RuntimeError("未找到 git 命令，请确认运行环境已安装 git") from e

        raise RuntimeError(
            "克隆仓库失败: "
            + (getattr(last_err, "stderr", "") or getattr(last_err, "stdout", "") or str(last_err))
        ) from last_err

    def _promote_tmp(self, target: Path, cache: Path) -> Path:
        """把临时目录克隆结果替换到正式缓存路径；替换失败时返回 tmp 路径兜底。"""
        self._remove_cache(cache)
        if cache.exists():
            logger.warning("正式缓存目录仍被占用，暂用临时目录: %s", target)
            return target
        target.rename(cache)
        return cache

    @staticmethod
    def _dir_not_empty(path: Path) -> bool:
        """目录是否存在且包含任何条目（路径不存在视为空）。"""
        try:
            return any(path.iterdir())
        except OSError:
            return False

    def _run_clone(self, cache: Path, clone_url: str, branch: Optional[str] = None) -> None:
        """执行 git clone（启用 core.longpaths 规避 Windows 长路径 checkout 失败）。

        branch 为 None 时不带 -b，克隆远端默认分支。
        """
        cmd = ["git", "-c", "core.longpaths=true", "clone", "--depth", "1"]
        if branch:
            cmd += ["-b", branch]
        cmd += [clone_url, str(cache)]
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def _try_pull(self, cache: Path) -> bool:
        """对已存在的克隆执行增量刷新。

        顺序：pull --ff-only → fetch --all --prune + checkout -B。

        为什么最后一步用 `checkout -B <branch> <ref>` 而不是 `reset --hard origin/<branch>`：
          * 远端把分支改名（master→main）后 `origin/<branch>` 不存在，reset 直接 128；
          * HEAD 损坏时 reset 无法定位当前分支，而 checkout -B 能同时重建分支与 HEAD；
          * 因此先解析真实存在的远端 ref，再切换。
        """
        if not self._head_ok(cache):
            logger.warning("缓存仓库 HEAD 无效（上次克隆被中断），判定需重新克隆: %s", cache)
            return False

        try:
            subprocess.run(
                ["git", "-c", "core.longpaths=true", "pull", "--ff-only"],
                cwd=str(cache),
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("git pull 失败(%s)，尝试 fetch+checkout: %s", cache, e)

        try:
            subprocess.run(
                ["git", "-c", "core.longpaths=true", "fetch", "--all", "--prune"],
                cwd=str(cache),
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("git fetch 失败: %s | %s", cache, e)
            return False

        ref = self._resolve_remote_ref(cache)
        if not ref:
            logger.warning("远端不存在可用分支(branch=%s)，将重新克隆: %s", self.branch, cache)
            return False

        try:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.longpaths=true",
                    "-C",
                    str(cache),
                    "checkout",
                    "-B",
                    self.branch,
                    ref,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("checkout -B %s %s 失败: %s", self.branch, ref, e)
            return False

    def _resolve_remote_ref(self, cache: Path) -> Optional[str]:
        """挑选实际存在的远端分支 ref。

        优先 origin/<branch>，其次 origin/HEAD、origin/main、origin/master，
        最后退回第一个非 HEAD 的 origin/* 分支。
        """
        try:
            r = subprocess.run(
                ["git", "-C", str(cache), "branch", "-r", "--format", "%(refname:short)"],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None

        refs = [x.strip() for x in r.stdout.splitlines() if x.strip()]
        for wanted in (f"origin/{self.branch}", "origin/HEAD", "origin/main", "origin/master"):
            if wanted in refs:
                return wanted
        for ref in refs:
            if ref.startswith("origin/") and ref != "origin/HEAD":
                return ref
        return None

    def _recover_checkout(self, cache: Path) -> bool:
        """checkout 失败但 .git 已就绪时，强制重建工作树。

        对应 git 提示的 `git restore --source=HEAD :/`，等价于 `git checkout -f`。
        """
        try:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.longpaths=true",
                    "-C",
                    str(cache),
                    "checkout",
                    "-f",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("工作树恢复失败: %s | %s", cache, e)
            return False
        return self._is_valid_clone(cache)

    @staticmethod
    def _remove_cache(cache: Path) -> None:
        """删除缓存目录；被占用 / 只读时重试若干次。

        Windows 上常被杀软 / 索引器 / IDE 短暂占用，且 git 对象文件是只读的，
        单次 rmtree 会静默失败并残留目录，让随后的 git clone 报
        "destination path already exists and is not an empty directory"。
        """
        for i in range(3):
            shutil.rmtree(cache, onerror=_force_unlink)
            if not cache.exists():
                return
            time.sleep(0.5 * (i + 1))
        if cache.exists():
            logger.warning("缓存目录无法完全删除（可能被占用）: %s", cache)

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
        cache = index_path.parent
        entries: list[SkillHubEntry] = []
        missing: list[str] = []
        for cat in data.get("categories", []):
            cat_key = cat.get("key", "general")
            for s in cat.get("skills", []):
                path = self._normalize_skill_path(s.get("path"), s["id"])
                # 索引里列了但工作树中没有对应目录的条目（典型场景：仓库用了 git
                # 子模块而克隆时未初始化，目录为空）直接跳过，避免「列表有、安装 500」。
                if not (cache / path).is_dir():
                    missing.append(s["id"])
                    continue
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
                            "path": path,
                        },
                    )
                )
        if missing:
            logger.warning(
                "category_index.json 中有 %d 个技能缺少对应目录（多为未初始化的 git 子模块），已跳过: %s%s",
                len(missing),
                missing[:5],
                " …" if len(missing) > 5 else "",
            )
        return entries

    @staticmethod
    def _normalize_skill_path(raw: Optional[str], skill_id: str) -> str:
        """把索引里的 path 规整为**技能目录**的相对路径。

        category_index.json 的 path 常直接指向 SKILL.md
        （如 `buffett-skills/skills/buffett/SKILL.md`），
        而 fetch 需要的是它所在的目录；否则 `cache / rel_path` 会拼成
        `.../buffett/SKILL.md` 并报「仓库中不存在 skill 目录」。
        """
        p = (raw or "").replace("\\", "/").strip().strip("/")
        if p.endswith("/SKILL.md"):
            p = p[: -len("/SKILL.md")]
        elif p.endswith("SKILL.md"):
            p = p[: -len("SKILL.md")]
        return p.strip("/") or f"skills/{skill_id}"

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
        # 优先用扫描/索引时记录的完整相对路径（支持嵌套目录如 buffett-skills/skills/buffett）
        # 历史索引里的 path 可能直接指向 SKILL.md，这里统一收敛到所在目录
        rel_path = self._normalize_skill_path(entry.meta.get("path"), skill_id)
        skill_dir = cache / rel_path
        if not skill_dir.is_dir():
            # 兜底：按 skill_id 在 skills/ 下定位，再退化到全仓同名目录
            fallback = cache / "skills" / skill_id
            if fallback.is_dir():
                skill_dir = fallback
            else:
                for cand in cache.rglob(skill_id):
                    if cand.is_dir() and (cand / "SKILL.md").exists():
                        skill_dir = cand
                        break
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
