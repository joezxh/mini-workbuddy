"""DB 文件客户端：内容存入 sys_infra_file_content（BYTEA）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.framework.file.client.base import FileClient
from app.models.sys.sys_infra_file import SysInfraFileContent


class DBFileClient(FileClient):
    def upload(self, content: bytes, path: str, db: Session | None = None, content_type: str | None = None) -> str:
        assert db is not None, "DBFileClient 需要 Service 注入 Session"
        existing = db.execute(
            select(SysInfraFileContent).where(
                SysInfraFileContent.config_id == self.config_id,
                SysInfraFileContent.path == path,
                SysInfraFileContent.deleted == "0",
            ).order_by(SysInfraFileContent.id.desc())
        ).scalars().first()
        if existing:
            existing.content = content
        else:
            db.add(SysInfraFileContent(
                config_id=self.config_id, path=path, content=content, deleted="0",
            ))
        return self.format_url(path)

    def delete(self, path: str, db: Session | None = None) -> None:
        assert db is not None
        for row in db.execute(
            select(SysInfraFileContent).where(
                SysInfraFileContent.config_id == self.config_id,
                SysInfraFileContent.path == path,
            )
        ).scalars().all():
            db.delete(row)

    def get_content(self, path: str, db: Session | None = None) -> Optional[bytes]:
        assert db is not None
        row = db.execute(
            select(SysInfraFileContent).where(
                SysInfraFileContent.config_id == self.config_id,
                SysInfraFileContent.path == path,
                SysInfraFileContent.deleted == "0",
            ).order_by(SysInfraFileContent.id.desc())
        ).scalars().first()
        if row is None or row.content is None:
            return None
        return bytes(row.content) if not isinstance(row.content, bytes) else row.content

    def get_files(self, prefix: str = "", db: Session | None = None) -> list[dict]:
        assert db is not None
        stmt = select(SysInfraFileContent.path).where(
            SysInfraFileContent.config_id == self.config_id,
            SysInfraFileContent.deleted == "0",
        )
        if prefix:
            stmt = stmt.where(SysInfraFileContent.path.like(f"{prefix}%"))
        return [{"path": p} for p in db.execute(stmt).scalars().all()]
