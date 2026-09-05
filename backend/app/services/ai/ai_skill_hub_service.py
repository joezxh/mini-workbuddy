"""技能仓库（Skill Hub）业务逻辑。

职责：
- Hub 仓库配置的增删改查（官方仓库不可删除）；
- 首次访问确保官方仓库记录存在；
- 基于 git_hub.GitHubAdapter 列举 / 检索 / 分页 / 安装 skill；
- 安装复用 AiSkillAdminService.import_zip（落盘到 backend/data/skills/）。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.skills.hub.git_hub import GitHubAdapter
from app.models.ai.ai_skill_hub_repo import AiSkillHubRepo
from app.services.ai.ai_skill_admin_service import AiSkillAdminService

logger = logging.getLogger(__name__)


class AiSkillHubService:
    """技能仓库服务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 官方仓库初始化 ────────────────────────────────────────
    def ensure_official(self) -> AiSkillHubRepo:
        """确保官方仓库记录在库（不存在则创建）。"""
        existing = self.db.scalars(
            select(AiSkillHubRepo).where(AiSkillHubRepo.is_official == True)  # noqa: E712
        ).first()
        if existing:
            return existing
        from app.config import settings

        repo = AiSkillHubRepo(
            name="官方仓库",
            url=settings.OFFICIAL_HUB_URL,
            branch=settings.OFFICIAL_HUB_BRANCH,
            is_official=True,
            sort_order=0,
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)
        logger.info("已创建官方 skill hub 仓库: %s", repo.url)
        return repo

    # ── 仓库 CRUD ─────────────────────────────────────────────
    def list_repos(self) -> list[AiSkillHubRepo]:
        self.ensure_official()
        return list(
            self.db.scalars(
                select(AiSkillHubRepo).order_by(
                    AiSkillHubRepo.is_official.desc(), AiSkillHubRepo.sort_order, AiSkillHubRepo.id
                )
            ).all()
        )

    def get_repo(self, repo_id: int) -> Optional[AiSkillHubRepo]:
        return self.db.get(AiSkillHubRepo, repo_id)

    def create_repo(
        self,
        name: str,
        url: str,
        branch: str = "main",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> AiSkillHubRepo:
        url = url.strip()
        dup = self.db.scalars(
            select(AiSkillHubRepo).where(AiSkillHubRepo.url == url)
        ).first()
        if dup:
            raise ValueError(f"仓库地址已存在: {url}")
        max_order = self.db.scalar(
            select(func.max(AiSkillHubRepo.sort_order)).select_from(AiSkillHubRepo)
        ) or 0
        repo = AiSkillHubRepo(
            name=name.strip(),
            url=url,
            branch=branch or "main",
            is_official=False,
            sort_order=max_order + 1,
            username=username or None,
            password=password or None,
        )
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)
        return repo

    def update_repo(
        self,
        repo_id: int,
        name: str,
        url: str,
        branch: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> AiSkillHubRepo:
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        if repo.is_official:
            raise ValueError("官方仓库不可修改地址/名称")
        repo.name = name.strip()
        repo.url = url.strip()
        repo.branch = branch or "main"
        repo.username = username or None
        repo.password = password or None
        self.db.commit()
        self.db.refresh(repo)
        return repo

    def delete_repo(self, repo_id: int) -> None:
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        if repo.is_official:
            raise ValueError("官方仓库不可删除")
        self.db.delete(repo)
        self.db.commit()

    def refresh_repo(self, repo_id: int) -> AiSkillHubRepo:
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        self._build_adapter(repo).ensure_cloned(force=True)
        self.db.commit()
        return repo

    # ── 分类 / 列表 / 检索 / 分页 ─────────────────────────────
    def _build_adapter(self, repo: AiSkillHubRepo) -> "GitHubAdapter":
        """构造 git 适配器。

        凭据优先级：仓库自有账号密码 > 全局配置（OFFICIAL_HUB_USERNAME/PASSWORD）。
        仓库未配置凭据时（含官方仓库）自动回退到全局配置。
        """
        from app.config import settings

        username = repo.username or settings.OFFICIAL_HUB_USERNAME or None
        password = repo.password or settings.OFFICIAL_HUB_PASSWORD or None
        return GitHubAdapter(repo.id, repo.url, repo.branch, username, password)

    def list_skills(
        self,
        repo_id: int,
        category: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        adapter = self._build_adapter(repo)
        try:
            entries = adapter.list_remote()
        except RuntimeError as e:
            # 仓库克隆/拉取失败时降级为空列表，避免接口 500
            logger.warning("技能仓库 %s 加载失败，返回空列表: %s", repo_id, e)
            entries = []

        if category:
            entries = [e for e in entries if e.meta.get("category") == category]
        if q:
            ql = q.strip().lower()
            entries = [
                e
                for e in entries
                if ql in (e.id or "").lower()
                or ql in (e.name or "").lower()
                or ql in (e.description or "").lower()
                or any(ql in str(t).lower() for t in e.meta.get("tags", []))
            ]

        total = len(entries)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        start = (page - 1) * page_size
        page_items = entries[start : start + page_size]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": e.id,
                    "name": e.name,
                    "version": e.version,
                    "description": e.description,
                    "category": e.meta.get("category"),
                    "category_name": e.meta.get("category_name"),
                    "tags": e.meta.get("tags", []),
                    "path": e.meta.get("path"),
                }
                for e in page_items
            ],
        }

    def list_categories(self, repo_id: int) -> list[dict]:
        """返回该仓库的分类聚合（来自 category_index.json）。

        递归扫描型仓库（无 category_index.json）的条目不带分类，
        跳过后返回空列表——前端侧仅展示「全部」入口。
        """
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        adapter = self._build_adapter(repo)
        try:
            entries = adapter.list_remote()
        except RuntimeError as e:
            # 仓库克隆/拉取失败时降级为空分类，避免接口 500
            logger.warning("技能仓库 %s 加载失败，返回空分类: %s", repo_id, e)
            entries = []
        agg: dict[str, dict] = {}
        for e in entries:
            key = e.meta.get("category")
            if not key:
                # 无 category_index.json 的自定义仓库：不产生分类
                continue
            item = agg.setdefault(
                key,
                {"key": key, "name": e.meta.get("category_name", key), "count": 0},
            )
            item["count"] += 1
        return [agg[k] for k in sorted(agg)]

    # ── 安装 ──────────────────────────────────────────────────
    def install_skill(self, repo_id: int, skill_id: str) -> dict:
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError("仓库不存在")
        adapter = self._build_adapter(repo)
        entry = next((e for e in adapter.list_remote() if e.id == skill_id), None)
        if not entry:
            raise ValueError(f"仓库中不存在 skill: {skill_id}")
        zip_bytes = adapter.fetch(entry)
        admin = AiSkillAdminService()
        result = admin.import_zip(self.db, zip_bytes)
        logger.info("已从仓库 %s 安装 skill %s", repo.name, skill_id)
        return result
