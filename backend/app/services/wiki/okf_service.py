"""OKF v0.2 合规层（spec §9.3）：DB 事实源 ↔ 文件 Bundle 的序列化/反序列化。

frontmatter 键序遵循规范推荐：type→resource→title→description→tags→sources→
generated→verified→status→stale_after。宽容消费（§11.3）：缺可选字段/未知
type/未知键/断链一律接受，退化为通用文档继续读取。

状态映射（spec §9.2）：``0→draft``、``1→stable``、``-1→deprecated``；
未知值宽容落 ``stable``。
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

import yaml

_STATUS_MAP = {0: "draft", 1: "stable", -1: "deprecated"}
_STATUS_REVERSE = {"draft": 0, "stable": 1, "deprecated": -1}

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """宽容解析：无 frontmatter/YAML 失败 → type=concept 退化消费（§11.3）。"""
    m = _FM_RE.match(text or "")
    if not m:
        return {"type": "concept"}, text or ""
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {"type": "concept"}, text
    if not isinstance(data, dict):
        data = {"type": "concept"}
    data.setdefault("type", "concept")
    return data, text[m.end():]


def _status_to_okf(status) -> str:
    try:
        return _STATUS_MAP.get(int(status), "stable")
    except (TypeError, ValueError):
        return "stable"


def _format_stale_after(value) -> str:
    """统一 ISO 8601 UTC（spec §11 风险表：时序往返不丢失）。"""
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return text if text.endswith("Z") else text + "Z"


def serialize_article(article, author_actor: str, generated_at: str) -> str:
    """单文章 → concept.md；仅非空字段写入（缺可选即合规，§2.1）。"""
    meta: Dict = {"type": article.okf_type or "concept"}
    if getattr(article, "resource", None):
        meta["resource"] = article.resource
    meta["title"] = article.title
    if article.summary:
        meta["description"] = article.summary
    if article.tags:
        meta["tags"] = list(article.tags)
    if article.sources:
        meta["sources"] = article.sources
    meta["generated"] = {"by": author_actor, "at": generated_at}
    if article.verified:
        meta["verified"] = article.verified
    meta["status"] = _status_to_okf(article.status)
    if article.stale_after is not None:
        meta["stale_after"] = _format_stale_after(article.stale_after)
    body = article.content or ""
    return f"---\n{yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)}---\n{body}"


# ── Bundle 级导出/导入（spec §9.3；DB 仍为事实源，文件即互操作面） ───────────

def _category_dir_map(categories) -> Dict[int, str]:
    """category_id → bundle 相对目录（'.'=根；父链自上而下拼接 slug）。"""
    by_id = {c.id: c for c in categories}
    cache: Dict[int, str] = {}

    def _dir(cid: int) -> str:
        if cid in cache:
            return cache[cid]
        cat = by_id.get(cid)
        if cat is None:
            cache[cid] = "."
            return "."
        parent_dir = _dir(cat.parent_id) if cat.parent_id else "."
        cache[cid] = f"{parent_dir}/{cat.slug}" if parent_dir != "." else cat.slug
        return cache[cid]

    for cid in by_id:
        _dir(cid)
    return cache


def export_bundle(db, knowledge_id: int) -> Dict[str, str]:
    """知识库 → 合规 Bundle：{相对路径: 文件内容}（spec §9.3）。

    * 文章 = ``<目录>/<slug>.md``（含 frontmatter）；
    * 每层目录 ``index.md``（条目含 description，渐进披露 §8）；
    * 根 ``index.md`` 携带 ``okf_version: "0.2"``（唯一允许处）；
    * ``log.md`` 由 ``kms_article_version`` 生成（ISO 日期分组、最新在前 §9）。
    """
    from sqlalchemy import select

    from app.models.kb.kb_category import KbCategory
    from app.models.wiki.wiki_article import WikiArticle
    from app.models.wiki.wiki_article_version import WikiArticleVersion
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    knowledge = db.get(WikiKnowledge, knowledge_id)
    if knowledge is None:
        raise ValueError(f"知识库不存在: {knowledge_id}")

    articles = db.execute(
        select(WikiArticle).where(WikiArticle.knowledge_id == knowledge_id)
    ).scalars().all()
    cat_ids = {a.category_id for a in articles if a.category_id}
    categories = (
        db.execute(select(KbCategory).where(KbCategory.id.in_(cat_ids))).scalars().all()
        if cat_ids
        else []
    )
    dir_of = _category_dir_map(categories)

    articles = db.execute(
        select(WikiArticle).where(WikiArticle.knowledge_id == knowledge_id)
    ).scalars().all()

    files: Dict[str, str] = {}
    # 目录 → 条目列表（index.md 用）
    entries: Dict[str, list] = {}

    for art in articles:
        sub = dir_of.get(art.category_id, ".") if art.category_id else "."
        path = f"{sub}/{art.slug}.md" if sub != "." else f"{art.slug}.md"
        files[path] = serialize_article(
            art, author_actor="process:minworkbuddy-wiki",
            generated_at=art.updated_at.isoformat() + "Z"
            if art.updated_at else "1970-01-01T00:00:00Z",
        )
        entries.setdefault(sub, []).append((art.slug, art.title, art.summary or ""))

    # index.md（每层，§8）：条目含 description；根 index.md 携带 okf_version
    def _index_md(sub: str, is_root: bool) -> str:
        lines = []
        if is_root:
            lines.append("---")
            lines.append('okf_version: "0.2"')
            lines.append("---")
            lines.append("")
        lines.append(f"# {knowledge.name}")
        lines.append("")
        for slug, title, desc in sorted(entries.get(sub, [])):
            lines.append(f"* [{title}]({slug}.md) - {desc}")
        return "\n".join(lines) + "\n"

    all_dirs = {".", *{p.rsplit("/", 1)[0] for p in files if "/" in p}}
    for sub in sorted(all_dirs):
        files[f"{sub}/index.md" if sub != "." else "index.md"] = _index_md(sub, sub == ".")

    # log.md（§9）：按日期分组、最新在前
    versions = db.execute(
        select(WikiArticleVersion)
        .where(WikiArticleVersion.article_id.in_([a.id for a in articles] or [0]))
        .order_by(WikiArticleVersion.id.desc())
    ).scalars().all()
    by_date: Dict[str, list] = {}
    for v in versions:
        day = str(v.created_at)[:10] if v.created_at else "1970-01-01"
        by_date.setdefault(day, []).append(
            f"**Update** {v.title}（v{v.version}）：{v.change_note or ''}".rstrip()
        )
    log_lines = ["# 更新历史", ""]
    for day in sorted(by_date, reverse=True):
        log_lines.append(f"## {day}")
        log_lines.append("")
        log_lines.extend(by_date[day])
        log_lines.append("")
    if articles or versions:
        files["log.md"] = "\n".join(log_lines)
    return files


def import_bundle(db, knowledge_id: int, files: Dict[str, str], user) -> dict:
    """宽容导入（spec §9.3）：按 slug upsert 文章；返回导入报告。

    * 断链/缺可选字段/未知 type 一律接受；
    * 分类路径不存在的目录挂为未归类（knowledge_id 直挂）；
    * slug 冲突（跨知识库）自动加 ``-2`` 后缀并记入 warnings。
    """
    from sqlalchemy import select

    from app.models.wiki.wiki_article import WikiArticle

    imported, skipped, warnings = 0, 0, []
    for path, text in sorted(files.items()):
        if path.endswith("index.md") or path.endswith("log.md"):
            skipped += 1  # 保留文件（§3.1）不作为概念导入
            continue
        if not path.endswith(".md"):
            skipped += 1
            continue
        meta, body = parse_frontmatter(text)
        slug = path.rsplit("/", 1)[-1][:-3]
        existing = db.execute(
            select(WikiArticle).where(WikiArticle.slug == slug)
        ).scalar_one_or_none()
        if existing is None:
            base_slug = slug
            n = 2
            while db.execute(
                select(WikiArticle.id).where(WikiArticle.slug == slug)
            ).scalar_one_or_none() is not None:
                slug = f"{base_slug}-{n}"
                n += 1
                if n > 2:
                    warnings.append(f"slug 冲突：{base_slug} → {slug}")
            article = WikiArticle(
                tenant_id=None, slug=slug, title=meta.get("title", slug),
                content=body, summary=meta.get("description"),
                tags=meta.get("tags") or [], knowledge_id=knowledge_id,
                status=_STATUS_REVERSE.get(meta.get("status"), 1), version=1,
            )
            db.add(article)
            imported += 1
        else:
            existing.title = meta.get("title", existing.title)
            existing.content = body
            existing.summary = meta.get("description", existing.summary)
            existing.tags = meta.get("tags") or existing.tags
            existing.status = _STATUS_REVERSE.get(meta.get("status"), 1)
            imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped, "warnings": warnings}

