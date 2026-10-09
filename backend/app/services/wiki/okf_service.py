"""OKF v0.2 合规层（spec §9.3）：DB 事实源 ↔ 文件 Bundle 的序列化/反序列化。

frontmatter 键序遵循规范推荐：type→resource→title→description→tags→sources→
generated→verified→status→stale_after。宽容消费（§11.3）：缺可选字段/未知
type/未知键/断链一律接受，退化为通用文档继续读取。

状态映射（spec §9.2）：``0→draft``、``1→stable``、``-1→deprecated``；
未知值宽容落 ``stable``。

写入路径统一走 ``WikiArticleService``（版本快照 / 反向链接 / 异步向量索引只有一处实现）。
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
import zipfile
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

_STATUS_MAP = {0: "draft", 1: "stable", -1: "deprecated"}
_STATUS_REVERSE = {"draft": 0, "stable": 1, "deprecated": -1}

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

# ── zip 解包安全上限（spec §11 风险表：外部输入不可信）──────────────────────
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_ENTRY_BYTES = 5 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 50 * 1024 * 1024

# 允许的 frontmatter 顶层键（§2.2 / §5.x / §10）；未知键不拒绝，只计入报告
_KNOWN_META_KEYS = {
    "type", "resource", "title", "description", "tags", "sources",
    "generated", "verified", "status", "stale_after",
    # §10 Attested Computation 契约字段（仅该 type 必填 runtime）
    "runtime", "parameters", "computation", "executor", "attester",
}

# §10 Attested Computation 契约字段（top-level frontmatter 键）
_ATTESTED_KEYS = ("runtime", "parameters", "computation", "executor", "attester")

_WIKI_LINK_RE = re.compile(r"\]\(/wiki/([A-Za-z0-9_\-]+)(#[^)\s]*)?\)")
_MD_LINK_RE = re.compile(r"\]\((\.{0,2}/)?([A-Za-z0-9_\-/\.]+\.md)(#[^)\s]*)?\)")


# ── 基础解析/格式化 ────────────────────────────────────────────────────────

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


def _has_explicit_type(text: str) -> bool:
    """原始文本是否显式声明了 frontmatter ``type``（§11.2 非空唯一必填）。

    ``parse_frontmatter`` 会把缺失的 type 缺省为 ``concept``，无法据此判断是否缺失，
    所以要回看原始 frontmatter。
    """
    m = _FM_RE.match(text or "")
    if not m:
        return False
    try:
        raw = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return False
    return isinstance(raw, dict) and raw.get("type") is not None


def _status_to_okf(status) -> str:
    try:
        return _STATUS_MAP.get(int(status), "stable")
    except (TypeError, ValueError):
        return "stable"


def _status_from_okf(value) -> int:
    """反向映射；未知值宽容落 stable（1）。"""
    return _STATUS_REVERSE.get(str(value).strip().lower(), 1)


def _to_utc_iso(value) -> str:
    """统一 ISO 8601 UTC（spec §11 风险表：时序往返不丢失）。

    naive datetime 视为 UTC 后标注 ``Z``；date 补零时刻。不再对本地时间谎称 UTC。
    """
    if value is None:
        return "1970-01-01T00:00:00Z"
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00Z"
    return _to_utc_iso(_parse_datetime(value))


def _parse_datetime(value):
    """宽容解析时间；失败返回 None（§11.3 不得拒绝）。"""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_stale_after(value) -> str:
    """``stale_after`` 导出为 ISO 8601 UTC（§5.5）。"""
    return _to_utc_iso(value)


def _parse_stale_after(value):
    """``stale_after`` 导入解析；不可解析返回 None 并由调用方计入警告。"""
    return _parse_datetime(value)


def _actor_for(article, db=None) -> str:
    """§7 actor 命名：``human:<username>``，无创建者时 ``process:minworkbuddy-wiki``。"""
    creator_id = getattr(article, "creator_id", None)
    if creator_id and db is not None:
        try:
            from app.models.sys.sys_user import SysUser

            user = db.get(SysUser, creator_id)
            username = getattr(user, "username", None) if user else None
            if username:
                return f"human:{username}"
        except Exception:  # noqa: BLE001 actor 解析失败不得中断导出
            logger.warning("[OKF] 解析创建者 actor 失败 article=%s", getattr(article, "id", None))
    return "process:minworkbuddy-wiki"


# ── 链接重写（§6.1）────────────────────────────────────────────────────────

def _relative_md_link(current_path: str, target_path: str) -> str:
    """从当前概念文件到目标概念文件的 bundle 相对路径。"""
    current_dir = os.path.dirname(current_path) or "."
    rel = os.path.relpath(target_path, start=current_dir)
    return rel.replace(os.sep, "/")


def rewrite_links_out(body: str, current_path: str, slug_to_path: Dict[str, str]) -> str:
    """导出方向：``/wiki/<slug>`` → bundle 相对路径。断链原样保留（§6.1 容忍）。"""

    def _sub(m: "re.Match[str]") -> str:
        slug, anchor = m.group(1), m.group(2) or ""
        target = slug_to_path.get(slug)
        if not target:
            return m.group(0)
        return f"]({_relative_md_link(current_path, target)}{anchor})"

    return _WIKI_LINK_RE.sub(_sub, body or "")


def rewrite_links_in(body: str) -> str:
    """导入方向：``<path>.md`` → ``/wiki/<slug>``（slug 取路径末段的干名）。"""

    def _sub(m: "re.Match[str]") -> str:
        prefix, path, anchor = m.group(1) or "", m.group(2), m.group(3) or ""
        slug = path.rsplit("/", 1)[-1][:-3]
        if not slug:
            return m.group(0)
        return f"](/wiki/{slug}{anchor})"

    return _MD_LINK_RE.sub(_sub, body or "")


def missing_body_headings(body: str) -> list:
    """§4.2 body 约定 heading 检查（``# Schema`` / ``# Examples`` / ``# Computation``）。

    约定不是强制项：缺失只报告，不拒绝（§11.3 宽容消费）。
    """
    present = {
        m.group(1).strip().lower()
        for m in re.finditer(r"^#\s+(.+?)\s*$", body or "", re.MULTILINE)
    }
    return [h for h in ("schema", "examples", "computation") if h not in present]


def find_broken_links(body: str, known_slugs) -> list:
    """导出后仍指向未知 slug 的 wiki 链接（§6.1：容忍但需报告）。"""
    broken = []
    for m in _WIKI_LINK_RE.finditer(body or ""):
        if m.group(1) not in known_slugs:
            broken.append(m.group(1))
    return sorted(set(broken))


# ── 单篇文章序列化 ─────────────────────────────────────────────────────────

def serialize_article(article, author_actor: Optional[str] = None,
                      generated_at: Optional[str] = None, db=None) -> str:
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
    meta["generated"] = {
        "by": author_actor or _actor_for(article, db),
        "at": generated_at or _to_utc_iso(article.updated_at),
    }
    if article.verified:
        meta["verified"] = article.verified
    meta["status"] = _status_to_okf(article.status)
    if article.stale_after is not None:
        meta["stale_after"] = _format_stale_after(article.stale_after)
    # §10 Attested Computation：仅该 type 才把契约字段写出为 top-level frontmatter（保证往返保真，
    # 且避免非该 type 的文章误带 runtime/executor/attester 等契约键）
    ac = getattr(article, "attested_computation", None)
    if ac and (article.okf_type or "concept") == "Attested Computation":
        for key in _ATTESTED_KEYS:
            if ac.get(key) is not None:
                meta[key] = ac[key]
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


def export_bundle(db, knowledge_id: int, tenant_id: Optional[int] = None) -> Dict[str, str]:
    """知识库 → 合规 Bundle：{相对路径: 文件内容}（spec §9.3）。

    * 文章 = ``<目录>/<slug>.md``（含 frontmatter）；
    * 每层目录 ``index.md``（条目含 description，渐进披露 §8）；
    * 根 ``index.md`` 携带 ``okf_version: "0.2"``（唯一允许处）；
    * ``log.md`` 由 ``kms_article_version`` 生成（ISO 日期分组、最新在前 §9）；
    * ``references/`` 惯例目录（§3）：汇总各文章的 ``resource`` 与 ``sources``。
    """
    from sqlalchemy import select

    from app.models.kb.kb_category import KbCategory
    from app.models.wiki.wiki_article import WikiArticle
    from app.models.wiki.wiki_article_version import WikiArticleVersion
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    knowledge = db.get(WikiKnowledge, knowledge_id)
    if knowledge is None:
        raise ValueError(f"知识库不存在: {knowledge_id}")

    stmt = select(WikiArticle).where(WikiArticle.knowledge_id == knowledge_id)
    if tenant_id is not None:
        stmt = stmt.where(WikiArticle.tenant_id == tenant_id)
    articles = db.execute(stmt).scalars().all()

    cat_ids = {a.category_id for a in articles if a.category_id}
    categories = (
        db.execute(select(KbCategory).where(KbCategory.id.in_(cat_ids))).scalars().all()
        if cat_ids
        else []
    )
    dir_of = _category_dir_map(categories)

    files: Dict[str, str] = {}
    entries: Dict[str, list] = {}
    # slug → bundle 路径（链接重写用）
    slug_to_path: Dict[str, str] = {}
    references: list = []

    for art in articles:
        sub = dir_of.get(art.category_id, ".") if art.category_id else "."
        path = f"{sub}/{art.slug}.md" if sub != "." else f"{art.slug}.md"
        slug_to_path[art.slug] = path
        files[path] = serialize_article(
            art, author_actor=_actor_for(art, db), db=db,
        )
        entries.setdefault(sub, []).append((art.slug, art.title, art.summary or ""))
        if art.resource:
            references.append(f"* [{art.title}]({art.resource}) — `{art.slug}`")
        for src in art.sources or []:
            uri = src.get("resource") if isinstance(src, dict) else None
            ident = src.get("id") if isinstance(src, dict) else None
            if uri:
                suffix = f"（sources id={ident}）" if ident else ""
                references.append(f"* {uri}{suffix} — `{art.slug}`")

    # 链接重写（导出方向）：需要全部路径先就位
    for path, content in list(files.items()):
        meta, body = parse_frontmatter(content)
        new_body = rewrite_links_out(body, path, slug_to_path)
        broken = find_broken_links(body, slug_to_path.keys())
        if broken:
            logger.info("[OKF] 导出断链（原样保留 §6.1）%s → %s", path, broken)
        files[path] = (
            f"---\n{yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)}---\n{new_body}"
        )

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

    # references/ 惯例目录（§3）
    if references:
        files["references/index.md"] = "\n".join(
            ["# References", "", "*本目录汇总各概念文件引用的外部资产（OKF §3 惯例目录）。*", ""]
            + sorted(set(references))
        ) + "\n"

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


def import_bundle(db, knowledge_id: int, files: Dict[str, str], user,
                  tenant_id: Optional[int] = None) -> dict:
    """宽容导入（spec §9.3）：按 slug upsert 文章；返回导入报告。

    * 断链 / 缺可选字段 / 未知 type / 未知键一律接受（§11.3）；
    * 作用域严格限定在 ``tenant_id + knowledge_id``：跨知识库同名 slug 不再覆盖，
      而是加 ``-2`` / ``-3`` 后缀新建并计入报告；
    * frontmatter 全字段往返（type / resource / sources / verified / stale_after），
      不再只写 title / description / tags / status；
    * 写入统一走 ``WikiArticleService``，因此版本快照、反向链接与异步向量索引都会触发。
    """
    from sqlalchemy import select

    from app.core.tenant_context import get_tenant_id
    from app.models.wiki.wiki_article import WikiArticle
    from app.services.wiki.article_service import WikiArticleService

    svc = WikiArticleService(db)
    tenant = tenant_id if tenant_id is not None else getattr(user, "tenant_id", None)
    if tenant is None:
        tenant = get_tenant_id()

    imported, skipped = 0, 0
    warnings: list = []
    details = {
        "unknown_type": 0,
        "unknown_keys": 0,
        "broken_links": 0,
        "slug_conflicts": 0,
        "stale_after_unparsed": 0,
        "missing_headings": 0,
        # §10 Attested Computation：type=Attested Computation 却缺必填 runtime
        "attested_missing_runtime": 0,
    }
    # 逐源细分统计（§11.3 报告化）：每篇概念文件的动作 / 耗时 / 正文行数
    per_file: list = []
    total_duration_ms = 0.0
    total_body_lines = 0

    # 先建立 slug 集合，供链接还原与断链检测使用
    concept_paths = [
        p for p in files
        if p.endswith(".md")
        and not p.endswith("index.md")
        and not p.endswith("log.md")
    ]
    known_slugs = {p.rsplit("/", 1)[-1][:-3] for p in concept_paths}

    for path, text in sorted(files.items()):
        if not path.endswith(".md"):
            skipped += 1
            continue
        if path.endswith("index.md") or path.endswith("log.md"):
            skipped += 1  # 保留文件（§3.1）不作为概念导入
            continue

        file_warnings: list = []
        t0 = time.monotonic()

        meta, body = parse_frontmatter(text)
        slug = path.rsplit("/", 1)[-1][:-3]

        unknown_keys = sorted(set(meta.keys()) - _KNOWN_META_KEYS)
        if unknown_keys:
            details["unknown_keys"] += 1
            file_warnings.append(f"未知 frontmatter 键（已保留并忽略）：{path} → {unknown_keys}")
        # type 是非空唯一必填项（§11.2）。parse_frontmatter 会把它缺省为 concept，
        # 因此"原始 frontmatter 是否显式声明了 type"要单独判断，才能报告出来。
        okf_type = meta.get("type")
        if not _has_explicit_type(text):
            details["unknown_type"] += 1
            file_warnings.append(f"缺少 type，退化为 concept（§11.3）：{path}")
            okf_type = okf_type or "concept"

        # 链接还原（导入方向）+ 断链检测
        body = rewrite_links_in(body)
        broken = find_broken_links(body, known_slugs)
        if broken:
            details["broken_links"] += len(broken)
            file_warnings.append(f"断链（已原样保留 §6.1）：{path} → {broken}")

        missing = missing_body_headings(body)
        if missing:
            details["missing_headings"] += 1
            file_warnings.append(
                f"缺少推荐标题（§4.2，已接受）：{path} → {', '.join(missing)}"
            )

        stale_after = _parse_stale_after(meta.get("stale_after"))
        if meta.get("stale_after") is not None and stale_after is None:
            details["stale_after_unparsed"] += 1
            file_warnings.append(f"stale_after 无法解析，已忽略：{path}")

        # §10 Attested Computation：契约字段解析 + 必填校验（宽容，不拒绝）
        ac: dict = {}
        for key in _ATTESTED_KEYS:
            if meta.get(key) is not None:
                ac[key] = meta[key]
        if okf_type == "Attested Computation" and not ac.get("runtime"):
            details["attested_missing_runtime"] += 1
            file_warnings.append(f"Attested Computation 缺少必填 runtime（§10.2）：{path}")
        ac = ac or None

        # slug 作用域：本租户 + 本知识库内命中才算同一篇
        existing = svc.find_scoped(slug, tenant, knowledge_id)
        final_slug = slug
        if existing is None and svc.slug_exists(slug):
            n = 2
            while svc.slug_exists(f"{slug}-{n}"):
                n += 1
            final_slug = f"{slug}-{n}"
            details["slug_conflicts"] += 1
            file_warnings.append(f"slug 冲突（跨知识库，不覆盖）：{slug} → {final_slug}")

        data = {
            "slug": final_slug,
            "title": meta.get("title", slug),
            "content": body,
            "summary": meta.get("description"),
            "tags": meta.get("tags") or [],
            "status": _status_from_okf(meta.get("status")),
            "knowledge_id": knowledge_id,
            # OKF 全字段往返（此前这五个字段在导入时被整体丢弃）
            "okf_type": okf_type,
            "resource": meta.get("resource"),
            "sources": meta.get("sources") or [],
            "verified": meta.get("verified") or [],
            "stale_after": stale_after,
            # §10 Attested Computation 契约字段往返
            "attested_computation": ac,
        }

        if existing is not None:
            svc.update(existing.id, data, change_note="OKF 导入", user=user)
            action = "updated"
        else:
            svc.create(data, user, tenant_id=tenant)
            action = "created"
        imported += 1

        # 逐源细分统计
        dt_ms = (time.monotonic() - t0) * 1000
        body_lines = len(body.splitlines())
        per_file.append({
            "path": path,
            "slug": final_slug,
            "okf_type": okf_type,
            "action": action,
            "duration_ms": round(dt_ms, 1),
            "body_lines": body_lines,
            "warnings": list(file_warnings),
        })
        total_duration_ms += dt_ms
        total_body_lines += body_lines
        warnings.extend(file_warnings)

    return {
        "imported": imported,
        "skipped": skipped,
        "warnings": warnings,
        "details": details,
        "per_file": per_file,
        "totals": {
            "duration_ms": round(total_duration_ms, 1),
            "body_lines": total_body_lines,
            "imported": imported,
            "skipped": skipped,
        },
    }


# ── zip 解包（§9.4 端点契约：服务端收 zip）─────────────────────────────────

def extract_zip(data: bytes) -> Dict[str, str]:
    """安全解包 zip → {相对路径: 文本}。

    限制条目总数、单条目与解压后总体积；拒绝绝对路径、``..`` 路径穿越与符号链接，
    避免 zip bomb / path traversal（§11 风险表）。
    """
    if not data:
        raise ValueError("上传内容为空")

    files: Dict[str, str] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ValueError(
                f"Bundle 条目过多：{len(entries)} > {MAX_ZIP_ENTRIES}"
            )
        for info in entries:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                raise ValueError(f"非法条目路径（绝对路径）：{name}")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if ".." in parts:
                raise ValueError(f"非法条目路径（路径穿越）：{name}")
            # 符号链接（外部属性高 16 位为 Unix 模式）
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"非法条目（符号链接）：{name}")
            if info.file_size > MAX_ZIP_ENTRY_BYTES:
                raise ValueError(
                    f"单文件过大：{name}（{info.file_size} > {MAX_ZIP_ENTRY_BYTES}）"
                )
            total += info.file_size
            if total > MAX_ZIP_TOTAL_BYTES:
                raise ValueError(f"Bundle 解压后体积超限：> {MAX_ZIP_TOTAL_BYTES} 字节")
            raw = zf.read(info)
            files["/".join(parts)] = raw.decode("utf-8", errors="replace")
    return files
