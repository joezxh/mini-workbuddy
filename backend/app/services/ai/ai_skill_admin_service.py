"""AI Skill 注册管理服务(CRUD + 文件系统镜像 + ZIP 导入导出)"""
import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai.ai_skill_package import AiSkillPackage
from app.models.ai.ai_skill_script import AiSkillScript
from app.models.sys.sys_dictionary import SysDictionaryItem
from app.ai.skills.categories import SkillCategory


class AiSkillAdminService:
    """Skill 注册表管理服务"""

    SKILLS_BASE_DIR = settings.resolved_skills_base_dir

    # ── Package CRUD ────────────────────────────────────────────────

    def list_packages(
        self, db: Session, category: Optional[str] = None, enabled: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        # 1. 获取字典排序映射（skill_category 的 sort_order）
        dict_items = db.scalars(
            select(SysDictionaryItem).where(
                SysDictionaryItem.dict_code == 'skill_category',
                SysDictionaryItem.is_active == True,  # noqa: E712
                SysDictionaryItem.is_deleted == False,  # noqa: E712
            )
        ).all()
        cat_sort = {item.item_code: item.sort_order for item in dict_items}

        # 2. 查询技能包
        q = select(AiSkillPackage)
        if category:
            q = q.where(AiSkillPackage.category == category)
        if enabled is not None:
            q = q.where(AiSkillPackage.enabled == enabled)
        rows = db.scalars(q).all()

        # 3. 按字典 sort_order 排序（未在字典中定义的分类排在最后）
        rows.sort(key=lambda p: (cat_sort.get(p.category or '', 9999), p.id))

        result = []
        for pkg in rows:
            scripts = db.scalars(
                select(AiSkillScript)
                .where(AiSkillScript.package_id == pkg.package_id)
                .order_by(AiSkillScript.sort_order, AiSkillScript.id)
            ).all()
            result.append(self._pkg_to_dict(pkg, scripts))
        return result

    def get_package(self, db: Session, package_id: str) -> Optional[Dict[str, Any]]:
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            return None
        scripts = db.scalars(
            select(AiSkillScript)
            .where(AiSkillScript.package_id == package_id)
            .order_by(AiSkillScript.sort_order)
        ).all()
        return self._pkg_to_dict(pkg, scripts)

    def save_skill_markdown(
        self, db: Session, package_id: str, content: str,
    ) -> Dict[str, Any]:
        """保存 SKILL.md 内容：同步写入数据库(skill_markdown)与文件系统(SKILL.md)。

        保存后，技能执行时将以数据库内容优先（见 SkillExecutionService._load_skill）。

        Args:
            db: 数据库 session
            package_id: 技能包 ID
            content: SKILL.md 完整文本

        Returns:
            更新后的技能包字典

        Raises:
            ValueError: package_id 不存在
        """
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            raise ValueError(f"package_id '{package_id}' 不存在")

        # 1. 写入数据库（执行优先来源）
        pkg.skill_markdown = content
        db.commit()
        db.refresh(pkg)

        # 2. 同步镜像到文件系统（保持与 workspace / 备份一致）
        md_path = self.SKILLS_BASE_DIR / package_id / "SKILL.md"
        try:
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.warning("SKILL.md 文件系统同步失败(%s): %s", md_path, e)

        scripts = db.scalars(
            select(AiSkillScript)
            .where(AiSkillScript.package_id == package_id)
            .order_by(AiSkillScript.sort_order)
        ).all()
        return self._pkg_to_dict(pkg, scripts)

    def get_skill_markdown(self, db: Session, package_id: str) -> Optional[str]:
        """获取 SKILL.md 内容（数据库 skill_markdown 优先，fallback 文件系统）。"""
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            return None
        if getattr(pkg, "skill_markdown", None):
            return pkg.skill_markdown
        # fallback 文件系统
        md_path = self.SKILLS_BASE_DIR / package_id / "SKILL.md"
        if md_path.exists():
            try:
                return md_path.read_text(encoding="utf-8")
            except OSError:
                return None
        return None

    def create_package(
        self,
        db: Session,
        package_id: str,
        name: str,
        category: str = None,  # 默认从字典获取
        description: Optional[str] = None,
        icon: str = "tool",
        version: str = "1.0.0",
        created_by: Optional[int] = None,
        upsert: bool = False,
        skill_markdown: Optional[str] = None,
    ) -> AiSkillPackage:
        # 如果未指定分类，使用默认分类（从字典获取）
        if category is None:
            category = SkillCategory.get_default()
        
        # 验证分类有效性
        SkillCategory.validate(category)
        
        existing = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if existing:
            if upsert:
                return existing
            raise ValueError(f"package_id '{package_id}' 已存在")

        pkg_dir = self.SKILLS_BASE_DIR / package_id
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "scripts").mkdir(exist_ok=True)

        pkg = AiSkillPackage(
            package_id=package_id,
            name=name,
            description=description,
            icon=icon,
            category=category,
            version=version,
            file_path=package_id,
            created_by=created_by,
            skill_markdown=skill_markdown,
        )
        db.add(pkg)
        db.commit()
        db.refresh(pkg)
        return pkg

    def update_package(
        self,
        db: Session,
        package_id: str,
        **fields,
    ) -> Optional[AiSkillPackage]:
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            return None
        for k, v in fields.items():
            if hasattr(pkg, k) and v is not NotImplemented:
                setattr(pkg, k, v)
        db.commit()
        db.refresh(pkg)
        return pkg

    def delete_package(self, db: Session, package_id: str) -> bool:
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            return False
        db.delete(pkg)
        db.commit()
        pkg_dir = self.SKILLS_BASE_DIR / package_id
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
        return True

    # ── Script CRUD ────────────────────────────────────────────────

    def create_script(
        self,
        db: Session,
        package_id: str,
        script_id: str,
        name: str,
        command: str,
        description: Optional[str] = None,
        params: Optional[List[Dict]] = None,
        sort_order: int = 0,
        upsert: bool = False,
    ) -> AiSkillScript:
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            raise ValueError(f"package_id '{package_id}' 不存在")

        existing = db.scalars(
            select(AiSkillScript).where(
                AiSkillScript.package_id == package_id,
                AiSkillScript.script_id == script_id,
            )
        ).first()
        if existing:
            if upsert:
                # 更新 command / name / description 等可变字段
                existing.name = name
                existing.command = command
                if description is not None:
                    existing.description = description
                if params is not None:
                    existing.params = params
                existing.sort_order = sort_order
                db.commit()
                db.refresh(existing)
                return existing
            raise ValueError(f"script_id '{script_id}' 已存在于包 '{package_id}'")

        script_dir = self.SKILLS_BASE_DIR / package_id / "scripts"
        script_path = script_dir / f"{script_id}.py"
        if not script_path.exists():
            placeholder = (
                "#!/usr/bin/env python3\n"
                f'"""{name} - {description or ""}"""\n'
                f"# Skill: {package_id}\n"
                f"# Script: {script_id}\n\n"
                "def main():\n"
                '    print(\'{"output": "TODO: implement your skill logic here"}\')\n\n'
                'if __name__ == "__main__":\n'
                "    main()\n"
            )
            script_path.write_text(placeholder, encoding="utf-8")

        script = AiSkillScript(
            package_id=package_id,
            script_id=script_id,
            name=name,
            description=description,
            command=command,
            params=params or [],
            sort_order=sort_order,
        )
        db.add(script)
        db.commit()
        db.refresh(script)
        return script

    def update_script(
        self, db: Session, package_id: str, script_id: str, **fields
    ) -> Optional[AiSkillScript]:
        script = db.scalars(
            select(AiSkillScript).where(
                AiSkillScript.package_id == package_id,
                AiSkillScript.script_id == script_id,
            )
        ).first()
        if not script:
            return None
        for k, v in fields.items():
            if hasattr(script, k) and v is not NotImplemented:
                setattr(script, k, v)
        db.commit()
        db.refresh(script)
        return script

    def delete_script(self, db: Session, package_id: str, script_id: str) -> bool:
        script = db.scalars(
            select(AiSkillScript).where(
                AiSkillScript.package_id == package_id,
                AiSkillScript.script_id == script_id,
            )
        ).first()
        if not script:
            return False
        db.delete(script)
        db.commit()
        script_path = self.SKILLS_BASE_DIR / package_id / "scripts" / f"{script_id}.py"
        if script_path.exists():
            script_path.unlink()
        return True

    # ── ZIP 导入导出 ─────────────────────────────────────────────────

    def import_zip(self, db: Session, zip_bytes: bytes) -> Dict[str, Any]:
        zip_buffer = io.BytesIO(zip_bytes)
        pkg_dir = None
        try:
            zf = zipfile.ZipFile(zip_buffer, "r")
        except zipfile.BadZipFile:
            raise ValueError("无效的 ZIP 文件")
        try:
            names = zf.namelist()

            skill_json_name = next((n for n in names if n.endswith("SKILL.json")), None)
            if not skill_json_name:
                raise ValueError("ZIP 内必须包含 SKILL.json")

            try:
                skill_data = json.loads(zf.read(skill_json_name).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise ValueError(f"SKILL.json 解析失败: {e}")

            pkg_id = skill_data.get("id")
            if not pkg_id:
                raise ValueError("SKILL.json 中缺少 'id' 字段")

            existing = db.scalars(
                select(AiSkillPackage).where(AiSkillPackage.package_id == pkg_id)
            ).first()
            if existing:
                raise ValueError(f"package_id '{pkg_id}' 已存在，请先删除再导入")

            pkg_dir = self.SKILLS_BASE_DIR / pkg_id
            # 统一剥掉首个 SKILL.json 所在目录前缀（顶层无前缀则保持）
            extracted_dir_prefix = str(Path(skill_json_name).parent)
            if extracted_dir_prefix == ".":
                extracted_dir_prefix = ""

            pkg_dir.mkdir(parents=True, exist_ok=True)
            extracted_skill_md = None
            for name in names:
                if not name or name.endswith("/"):
                    continue
                if name == skill_json_name:
                    continue
                # 剥前缀
                target_name = name
                if extracted_dir_prefix and name.startswith(extracted_dir_prefix):
                    target_name = name[len(extracted_dir_prefix):].lstrip("/\\")
                if not target_name:
                    continue
                target_path = (pkg_dir / target_name).resolve()
                # 路径穿越防护：落点必须在 pkg_dir 内
                if target_path != pkg_dir and pkg_dir not in target_path.parents:
                    logger.warning("跳过疑似路径穿越的成员: %s", name)
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target_path.write_bytes(zf.read(name))
                except OSError:
                    logger.warning("写入成员失败，跳过: %s", name)
                    continue
                if target_path.name == "SKILL.md":
                    try:
                        extracted_skill_md = target_path.read_text(encoding="utf-8")
                    except OSError:
                        extracted_skill_md = None

            # 验证分类有效性
            category = skill_data.get("category")
            if category is None:
                category = SkillCategory.get_default()
            else:
                SkillCategory.validate(category)

            pkg = self.create_package(
                db,
                package_id=pkg_id,
                name=skill_data.get("name", pkg_id),
                category=category,
                description=skill_data.get("description"),
                icon=skill_data.get("icon", "tool"),
                version=skill_data.get("version", "1.0.0"),
                skill_markdown=extracted_skill_md,
            )

            for s in skill_data.get("scripts", []):
                try:
                    self.create_script(
                        db,
                        package_id=pkg.package_id,
                        script_id=s["id"],
                        name=s.get("name", s["id"]),
                        command=s.get("command", ""),
                        description=s.get("description"),
                        params=s.get("params"),
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(f"跳过脚本 {s.get('id')}: {e}")

            return {
                "package_id": pkg.package_id,
                "name": pkg.name,
                "scripts_count": len(skill_data.get("scripts", [])),
            }
        except ValueError:
            # 业务校验错误（缺 SKILL.json / 缺 id / 已存在等）直接抛出，保留原信息
            if pkg_dir is not None and pkg_dir.exists():
                shutil.rmtree(pkg_dir)
            raise
        except Exception as e:
            if pkg_dir is not None and pkg_dir.exists():
                shutil.rmtree(pkg_dir)
            raise ValueError(f"导入失败: {e}")
        finally:
            zf.close()

    def export_zip(self, db: Session, package_id: str) -> bytes:
        pkg = db.scalars(
            select(AiSkillPackage).where(AiSkillPackage.package_id == package_id)
        ).first()
        if not pkg:
            raise ValueError(f"package '{package_id}' 不存在")

        pkg_dir = self.SKILLS_BASE_DIR / package_id
        if not pkg_dir.exists():
            raise ValueError(f"目录不存在: {pkg_dir}")

        scripts = db.scalars(
            select(AiSkillScript).where(AiSkillScript.package_id == package_id)
        ).all()

        skill_json = {
            "id": pkg.package_id,
            "name": pkg.name,
            "version": pkg.version,
            "description": pkg.description,
            "icon": pkg.icon,
            "category": pkg.category,
            "scripts": [
                {
                    "id": s.script_id,
                    "name": s.name,
                    "description": s.description,
                    "command": s.command,
                    "params": s.params,
                }
                for s in scripts
            ],
        }

        buffer = io.BytesIO()
        missing_scripts: List[str] = []
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                f"{package_id}/SKILL.json",
                json.dumps(skill_json, ensure_ascii=False, indent=2),
            )

            # SKILL.md：本地缺失时回退 DB 中的 skill_markdown
            skill_md_file = pkg_dir / "SKILL.md"
            if skill_md_file.exists():
                zf.writestr(f"{package_id}/SKILL.md", skill_md_file.read_bytes())
            elif pkg.skill_markdown:
                zf.writestr(
                    f"{package_id}/SKILL.md",
                    pkg.skill_markdown.encode("utf-8"),
                )
            else:
                missing_scripts.append("SKILL.md")

            # 脚本：本地文件缺失时仅记录，不影响导出
            for script in scripts:
                script_file = pkg_dir / "scripts" / f"{script.script_id}.py"
                rel = f"{package_id}/scripts/{script.script_id}.py"
                if script_file.exists():
                    zf.writestr(rel, script_file.read_bytes())
                else:
                    missing_scripts.append(f"scripts/{script.script_id}.py")

            # .env 默认排除（含密钥）
            env_file = pkg_dir / ".env"
            if env_file.exists():
                zf.writestr(f"{package_id}/.env", env_file.read_bytes())

            # 递归遍历，保留 data/、skill/ 等所有子目录
            for root, _dirs, files in os.walk(pkg_dir):
                for fname in files:
                    abs_path = Path(root) / fname
                    rel_parts = abs_path.relative_to(pkg_dir).parts
                    if rel_parts[0] in (".env", "SKILL.json", "SKILL.md"):
                        continue
                    if len(rel_parts) >= 2 and rel_parts[0] == "scripts":
                        continue
                    arcname = f"{package_id}/" + "/".join(rel_parts)
                    zf.writestr(arcname, abs_path.read_bytes())

            # 缺失脚本/文件说明
            if missing_scripts:
                note = (
                    "# 导出说明\n\n"
                    "以下源文件未在本地文件系统中找到，未包含在本导出包中：\n\n"
                    + "\n".join(f"- {m}" for m in missing_scripts)
                    + "\n\nSKILL.json 中仍保留了这些脚本的元数据；"
                    "如需完整执行，请补充对应源文件后重新导出。\n"
                )
                zf.writestr(f"{package_id}/IMPORT_NOTE.md", note.encode("utf-8"))

        return buffer.getvalue()

    # ── 辅助 ────────────────────────────────────────────────────────

    def _pkg_to_dict(self, pkg: AiSkillPackage, scripts: List[AiSkillScript]) -> Dict[str, Any]:
        return {
            "id": pkg.id,
            "package_id": pkg.package_id,
            "name": pkg.name,
            "description": pkg.description,
            "icon": pkg.icon,
            "category": pkg.category,
            "version": pkg.version,
            "enabled": pkg.enabled,
            "file_path": pkg.file_path,
            "created_by": pkg.created_by,
            "created_at": str(pkg.created_at) if pkg.created_at else None,
            "updated_at": str(pkg.updated_at) if pkg.updated_at else None,
            "skill_markdown": getattr(pkg, "skill_markdown", None),
            "scripts": [
                {
                    "id": s.id,
                    "script_id": s.script_id,
                    "name": s.name,
                    "description": s.description,
                    "command": s.command,
                    "params": s.params or [],
                    "sort_order": s.sort_order,
                    "enabled": s.enabled,
                    "created_at": str(s.created_at) if s.created_at else None,
                }
                for s in scripts
            ],
        }
