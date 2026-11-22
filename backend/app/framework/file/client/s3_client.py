"""S3 兼容文件客户端：boto3 一套代码覆盖 MinIO / 阿里云 OSS / 七牛 / 腾讯云 / 华为 / 火山。"""
from __future__ import annotations

import re
from typing import Optional

from loguru import logger

from app.framework.file.client.base import FileClient

_REGION_RE = re.compile(r"([a-z]{2}-[a-z]+-\d+)")


class S3FileClient(FileClient):
    def __init__(self, config_id: int, code: str, config: dict):
        super().__init__(config_id, code, config)
        self.endpoint = (config.get("endpoint") or "").rstrip("/")
        self.bucket = config.get("bucket") or ""
        self.public = bool(config.get("enablePublicAccess", False))
        self.path_style = bool(config.get("enablePathStyleAccess", True))
        self.region = config.get("region") or self._infer_region()

    def _infer_region(self) -> str:
        match = _REGION_RE.search(self.endpoint)
        return match.group(1) if match else "us-east-1"

    def _client(self):
        if getattr(self, "_client_obj", None) is not None:
            return self._client_obj
        import boto3
        from botocore.config import Config as BotoConfig

        self._client_obj = boto3.client(
            "s3",
            endpoint_url=self.endpoint or None,
            aws_access_key_id=self.config.get("accessKey") or "",
            aws_secret_access_key=self.config.get("accessSecret") or "",
            region_name=self.region,
            # 自定义 endpoint 下 boto3 的 "auto" 会退化为 path-style；
            # 腾讯云 COS 等厂商强制虚拟主机式，须显式指定（MinIO 两种皆支持，IP 端点 boto3 会自动回退 path-style）
            config=BotoConfig(s3={"addressing_style": "path" if self.path_style else "virtual"}),
        )
        return self._client_obj

    def _public_url(self, path: str) -> str:
        if self.domain:
            return f"{self.domain.rstrip('/')}/{path}"
        return f"{self.endpoint}/{self.bucket}/{path}"

    def upload(self, content: bytes, path: str, db=None, content_type: str | None = None) -> str:
        try:
            self._client().put_object(
                Bucket=self.bucket, Key=path, Body=content,
                **({"ContentType": content_type} if content_type else {}),
            )
        except Exception as exc:  # noqa: BLE001 - path-style 被厂商拒绝时自动降级 virtual-hosted 重试
            if self._is_path_style_forbidden(exc) and self.path_style:
                logger.warning(f"[S3FileClient] path-style 被拒绝，自动降级 virtual-hosted: {self.endpoint}")
                self.path_style = False
                self._client_obj = None  # 强制重建 client
                self._client().put_object(Bucket=self.bucket, Key=path, Body=content)
            else:
                raise
        if self.public:
            return self._public_url(path)
        return self.presign_get_url(path, expires=86400)

    @staticmethod
    def _is_path_style_forbidden(exc: Exception) -> bool:
        """腾讯云 COS 等厂商对 path-style 返回 PathStyleDomainForbidden。"""
        code = getattr(getattr(exc, "response", None), "get", lambda *_: None)("Error", {}).get("Code")
        return code == "PathStyleDomainForbidden" or "PathStyleDomainForbidden" in str(exc)

    def delete(self, path: str, db=None) -> None:
        self._client().delete_object(Bucket=self.bucket, Key=path)

    def get_content(self, path: str, db=None) -> Optional[bytes]:
        try:
            resp = self._client().get_object(Bucket=self.bucket, Key=path)
            return resp["Body"].read()
        except Exception as exc:  # NoSuchKey 等统一视为不存在
            logger.warning(f"[S3FileClient] 读取失败 {path}: {exc}")
            return None

    def presign_put_url(self, path: str, expires: int = 3600) -> str:
        return self._client().generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": path}, ExpiresIn=expires,
        )

    def presign_get_url(self, path: str, expires: int = 3600) -> str:
        if self.public:
            return self._public_url(path)
        return self._client().generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": path}, ExpiresIn=expires,
        )

    def rename(self, path: str, new_name: str, db=None) -> str | None:
        new_path = "/".join([*path.split("/")[:-1], new_name])
        if new_path == path:
            return None
        client = self._client()
        client.copy_object(
            Bucket=self.bucket, CopySource={"Bucket": self.bucket, "Key": path}, Key=new_path,
        )
        client.delete_object(Bucket=self.bucket, Key=path)
        return new_path

    def get_files(self, prefix: str = "", db=None) -> list[dict]:
        client = self._client()
        paginator = client.get_paginator("list_objects_v2")
        result: list[dict] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                result.append({"path": obj["Key"], "size": obj.get("Size", 0)})
        return result

    def test(self) -> str:
        """连通性测试：列举 bucket（不写对象）。"""
        self._client().list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        return self._public_url("test-connectivity.txt")
