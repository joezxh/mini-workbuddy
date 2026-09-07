"""SkillHub 云市场适配器。

通过 SkillHub 开放 API（https://api.skillhub.cn）检索并下载技能，复用
SkillHubAdapter 抽象，使技能仓库服务可像 Git 仓库一样检索 / 安装。

鉴权：服务端环境变量 SKILLHUB_API_KEY（请求头 X-API-Key）。
参考端点（docs/api/README.md）：
- GET /api/skills?keyword=&pageSize=&page           列表 / 检索
- GET /api/v1/categories                          一级分类
- GET /api/v1/skills/{slug}                       技能详情
- GET /api/v1/download?slug=                      下载 zip（302 跳转对象存储）

本适配器把 SkillHub 的 SKILL.md 包重新打包为内部 import_zip 兼容格式
（注入 SKILL.json），因此 fetch 返回的 zip 可被 AiSkillAdminService.import_zip 直接消费。
"""
from __future__ import annotations

import io
import json
import logging
import re
import urllib.parse
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional

from app.ai.skills.hub.base import SkillHubAdapter, SkillHubEntry
from app.config import settings

logger = logging.getLogger(__name__)


class SkillHubCloudAdapter(SkillHubAdapter):
    """SkillHub 云市场适配器（api.skillhub.cn）。"""

    name = "skillhub"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = (api_key or settings.SKILLHUB_API_KEY or "").strip()
        self.base_url = (
            base_url or settings.SKILLHUB_BASE_URL or "https://api.skillhub.cn"
        ).rstrip("/")

    # ── 内部 HTTP 辅助 ───────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_url + path
        if params:
            params = {k: v for k, v in params.items() if v is not None}
            if params:
                url += "?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_bytes(self, path: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        url = self.base_url + path
        if params:
            params = {k: v for k, v in params.items() if v is not None}
            if params:
                url += "?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    # ── 字段映射 ─────────────────────────────────────────────
    @staticmethod
    def _normalize_category(skill: Dict[str, Any]) -> (str, str):
        cat = skill.get("category")
        if isinstance(cat, dict):
            return str(cat.get("id") or ""), str(cat.get("name") or cat.get("id") or "")
        cat = cat or ""
        return str(cat), str(cat)

    @staticmethod
    def _entry_from_skill(skill: Dict[str, Any]) -> SkillHubEntry:
        slug = str(skill.get("slug") or skill.get("id") or "")
        name = skill.get("name") or skill.get("title") or slug
        version = str(skill.get("version") or "")
        description = skill.get("description") or ""
        cat_id, cat_name = SkillHubCloudAdapter._normalize_category(skill)
        tags = skill.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        return SkillHubEntry(
            id=slug,
            name=name,
            version=version,
            description=description,
            meta={
                "slug": slug,
                "category": cat_id,
                "category_name": cat_name,
                "tags": tags,
                "path": skill.get("readme_url") or skill.get("url") or "",
            },
        )

    @staticmethod
    def _entry_to_dict(e: "SkillHubEntry") -> Dict[str, Any]:
        return {
            "id": e.id,
            "name": e.name,
            "version": e.version,
            "description": e.description,
            "category": e.meta.get("category"),
            "category_name": e.meta.get("category_name"),
            "tags": e.meta.get("tags", []),
            "path": e.meta.get("path"),
            "slug": e.meta.get("slug"),
        }

    # ── SkillHubAdapter 接口实现 ─────────────────────────────
    def list_remote(self) -> List[SkillHubEntry]:
        """默认取首页（大规模来源实际通过 search 服务端分页）。"""
        data = self._get_json("/api/skills", {"pageSize": 20, "page": 1})
        skills = (data.get("data") or {}).get("skills") or []
        return [self._entry_from_skill(s) for s in skills]

    def search(
        self,
        *,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "keyword": keyword,
            "pageSize": page_size,
            "page": page,
        }
        data = self._get_json("/api/skills", params)
        payload = data.get("data") or {}
        skills = payload.get("skills") or []
        total = int(payload.get("total") or len(skills))
        items = [
            self._entry_to_dict(self._entry_from_skill(s)) for s in skills
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def list_categories(self) -> List[Dict[str, Any]]:
        try:
            data = self._get_json("/api/v1/categories")
        except Exception as e:  # 分类仅为展示增强，失败不影响主流程
            logger.warning("SkillHub 分类加载失败: %s", e)
            return []
        cats: Any = data.get("data") or data.get("categories") or []
        if isinstance(cats, dict):
            cats = cats.get("categories") or []
        result: List[Dict[str, Any]] = []
        for c in cats:
            key = str(c.get("id") or c.get("key") or c.get("name") or "")
            name = str(c.get("name") or key)
            result.append({"key": key, "name": name, "count": 0})
        return result

    def get_entry(self, skill_id: str) -> Optional[SkillHubEntry]:
        try:
            data = self._get_json(f"/api/v1/skills/{skill_id}")
        except Exception:
            return None
        skill = data.get("data") or data.get("skill") or data
        if not isinstance(skill, dict) or not skill:
            return None
        return self._entry_from_skill(skill)

    def fetch(self, entry: SkillHubEntry) -> bytes:
        slug = entry.meta.get("slug") or entry.id
        raw = self._get_bytes("/api/v1/download", {"slug": slug})
        return self._repack_to_internal_zip(raw, entry)

    # ── 下载包 -> 内部 SKILL.json 结构 ────────────────────────
    @staticmethod
    def _parse_frontmatter(text: str) -> Dict[str, Any]:
        if not text.startswith("---"):
            return {}
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        block = text[3:end].strip("\n")
        fields: Dict[str, Any] = {}
        block_key: Optional[str] = None
        block_lines: List[str] = []
        for line in block.splitlines():
            if line[:1] in (" ", "\t"):
                if block_key is not None:
                    block_lines.append(line.strip())
                continue
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
            if m:
                block_key = m.group(1)
                val = m.group(2).strip()
                if val in ("|", ">"):
                    block_lines = []
                    fields[block_key] = block_lines
                else:
                    fields[block_key] = val.strip('"').strip("'")
        for k, v in list(fields.items()):
            if isinstance(v, list):
                fields[k] = " ".join(v)
        # 提取 metadata.tags（缩进块中的 tags: [...]）
        meta = fields.get("metadata")
        if isinstance(meta, str):
            tm = re.search(r"tags:\s*\[(.*?)\]", meta)
            if tm:
                fields["tags"] = [
                    t.strip().strip('"').strip("'")
                    for t in tm.group(1).split(",")
                    if t.strip()
                ]
        return fields

    def _repack_to_internal_zip(self, raw_zip: bytes, entry: SkillHubEntry) -> bytes:
        skill_id = entry.id or entry.meta.get("slug") or "skill"
        with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zin:
            names = zin.namelist()
            skill_md_name = next(
                (n for n in names if n.upper().endswith("SKILL.MD")), None
            )
            fm = (
                self._parse_frontmatter(zin.read(skill_md_name).decode("utf-8", "ignore"))
                if skill_md_name
                else {}
            )
            skill_json = {
                "id": skill_id,
                "name": fm.get("name") or entry.name or skill_id,
                "description": fm.get("description") or entry.description or "",
                "version": fm.get("version") or entry.version or "1.0.0",
                "category": "other",
                "type": "prompt",
                "icon": "tool",
                "tags": entry.meta.get("tags") or fm.get("tags") or [],
            }
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zout:
                zout.writestr(
                    f"{skill_id}/SKILL.json",
                    json.dumps(skill_json, ensure_ascii=False, indent=2),
                )
                for name in names:
                    if not name or name.endswith("/"):
                        continue
                    data = zin.read(name)
                    # 统一放到 <skill_id>/ 前缀下，与 SKILL.json 同级
                    target = (
                        f"{skill_id}/{name}"
                        if not name.startswith(skill_id + "/")
                        else name
                    )
                    zout.writestr(target, data)
            return buffer.getvalue()
