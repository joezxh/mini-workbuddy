"""Wiki RAG 写入路径（G1）。

在文章创建/更新后由 ``WikiArticleService._enqueue_index`` 触发（后台线程，不阻塞主链路）。
复用全局 ``EmbeddingClient``（与 kb 模块一致），将 ``WikiArticle.content`` 向量化并写入
``content_vector``。任何异常（embedding 未配置 / PGVector 不可用 / 网络）均被捕获并降级，
绝不抛回写请求。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from app.ai.embedding_client import get_embedding_client
from app.db.database import SessionLocal
from app.models.wiki.wiki_article import WikiArticle


logger = logging.getLogger(__name__)


class WikiRAGIngestor:
    """将单篇文章内容写入向量库。"""

    def index_article(self, article_id: int) -> None:
        """为指定文章生成 embedding 并写回 ``content_vector``。"""
        db = SessionLocal()
        try:
            article = db.get(WikiArticle, article_id)
            if not article or not article.content:
                return
            try:
                client = get_embedding_client()
                vector = client.embed_sync(article.content or "")
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"[WikiRAGIngestor] embedding 不可用，跳过索引 article={article_id}: {e}"
                )
                return
            if not vector:
                return
            article.content_vector = vector
            db.commit()
            logger.info(f"[WikiRAGIngestor] 已索引 article={article_id} dim={len(vector)}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WikiRAGIngestor] 索引失败 article={article_id}: {e}")
        finally:
            db.close()

    def reindex_all(self, batch_size: int = 200) -> int:
        """全量重建索引（运维脚本 / 数据修复用）。返回成功索引数。"""
        db = SessionLocal()
        ok = 0
        try:
            stmt = (
                select(WikiArticle.id)
                .where(WikiArticle.status >= 0)
                .where(WikiArticle.content.isnot(None))
                .order_by(WikiArticle.id)
            )
            ids = db.execute(stmt).scalars().all()
            for aid in ids:
                try:
                    self.index_article(aid)
                    ok += 1
                except Exception:  # noqa: BLE001
                    continue
        finally:
            db.close()
        return ok
