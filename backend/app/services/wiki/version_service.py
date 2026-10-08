"""Wiki 版本服务（G2）：非破坏式回滚 + diff。

回滚语义：以目标历史版本的内容生成一个**新的当前版本**（version = max+1），
绝不删除历史，保证可恢复性。每条版本快照记录 ``operation_type`` 以区分
create / edit / rollback。
"""
from __future__ import annotations

import difflib
import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.job_runner import run_in_background
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_article_version import WikiArticleVersion
from app.services.wiki.article_service import _serialize, _serialize_version
from app.services.wiki.rag_ingestor import WikiRAGIngestor


logger = logging.getLogger(__name__)


class VersionNotFoundError(HTTPException):
    def __init__(self, version_id: int):
        super().__init__(status_code=404, detail=f"版本不存在: {version_id}")


class VersionMismatchError(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="目标版本不属于该文章")


class WikiVersionService:
    """版本管理与回滚。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_version(self, version_id: int) -> WikiArticleVersion:
        obj = self.db.get(WikiArticleVersion, version_id)
        if not obj:
            raise VersionNotFoundError(version_id)
        return obj

    def version_detail(self, article_id: int, version_id: int) -> dict:
        version = self.get_version(version_id)
        if version.article_id != article_id:
            raise VersionMismatchError()
        return _serialize_version(version)

    def rollback(self, article_id: int, version_id: int, user, change_note: Optional[str] = None) -> dict:
        """非破坏式回滚：以目标历史版本内容生成新的当前版本。"""
        article = self.db.get(WikiArticle, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        target = self.get_version(version_id)
        if target.article_id != article_id:
            raise VersionMismatchError()

        new_version_num = (article.version or 1) + 1
        snapshot = WikiArticleVersion(
            article_id=article.id,
            version=new_version_num,
            title=target.title,
            content=target.content,
            slug=target.slug,
            summary=getattr(target, "summary", None),
            owl_class_uris=getattr(target, "owl_class_uris", None),
            change_note=change_note
            or f"Rollback from v{article.version} to v{target.version}",
            editor_id=user.id,
            operation_type="rollback",
        )
        self.db.add(snapshot)

        article.title = target.title
        article.content = target.content
        article.summary = target.summary
        article.owl_class_uris = target.owl_class_uris
        article.slug = target.slug
        article.version = new_version_num
        article.updater_id = user.id
        self.db.commit()
        self.db.refresh(article)

        # 异步重建向量索引（经 job_runner，独立 Session）
        run_in_background(
            WikiRAGIngestor().index_article,
            article.id,
            name=f"wiki-index-{article.id}",
        )

        return _serialize(article, include_content=True)

    def get_diff(
        self,
        article_id: int,
        version_id: int,
        target_version_id: Optional[int] = None,
    ) -> dict:
        """返回版本 diff（unified diff，段落级）。

        :param version_id: 基线版本（diff 左侧）
        :param target_version_id: 对照版本；缺省为文章当前版本（diff 右侧）
        """
        article = self.db.get(WikiArticle, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        base = self.get_version(version_id)
        if base.article_id != article_id:
            raise VersionMismatchError()

        if target_version_id is None:
            other_label = f"v{article.version} (current)"
            other_lines = (article.content or "").splitlines(keepends=True)
            other_number = article.version
        else:
            other = self.get_version(target_version_id)
            if other.article_id != article_id:
                raise VersionMismatchError()
            other_label = f"v{other.version}"
            other_lines = (other.content or "").splitlines(keepends=True)
            other_number = other.version

        diff = list(
            difflib.unified_diff(
                (base.content or "").splitlines(keepends=True),
                other_lines,
                fromfile=f"v{base.version}",
                tofile=other_label,
                lineterm="",
            )
        )
        return {
            "article_id": article_id,
            "current_version": article.version,
            "base_version": base.version,
            "target_version": other_number,
            "diff": "".join(diff),
        }
