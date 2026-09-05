"""Dify API Key 认证中间件"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


class DifyApiKeyAuth(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/dify/"):
            return await call_next(request)
        api_key = request.headers.get("X-Dify-Api-Key", "")
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API Key")
        if api_key != settings.DIFY_API_KEY:
            raise HTTPException(status_code=403, detail="Invalid API Key")
        return await call_next(request)
