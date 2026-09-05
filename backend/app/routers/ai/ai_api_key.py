"""AI API Key and ChatModel Router."""
import json
import logging
from typing import Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_api_key import AiApiKey, AiChatModel
from app.schemas.ai.ai_api_key import AiApiKeyCreate, AiApiKeyUpdate, AiChatModelCreate, AiChatModelUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/api-key", tags=["AI API Key"])


# ============= API Key CRUD =============

@router.get("/page")
def get_api_key_page(
    name: Optional[str] = Query(None, description="密钥名称搜索"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    status: Optional[int] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """分页获取 API Key 列表"""
    query = db.query(AiApiKey)
    
    if name:
        query = query.filter(AiApiKey.name.contains(name))
    if platform:
        query = query.filter(AiApiKey.platform == platform)
    if status is not None:
        query = query.filter(AiApiKey.status == status)
    
    total = query.count()
    items = query.order_by(AiApiKey.sort.desc(), AiApiKey.id.desc())\
                 .offset((page - 1) * pageSize)\
                 .limit(pageSize).all()
    
    return {
        "data": [_to_page_resp(item) for item in items],
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.get("/simple-list")
def get_api_key_simple_list(
    platform: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """获取 API Key 简易列表（用于下拉选择）"""
    query = db.query(AiApiKey).filter(AiApiKey.status == 1)
    
    if platform:
        query = query.filter(AiApiKey.platform == platform)
    
    items = query.order_by(AiApiKey.sort.desc(), AiApiKey.id.desc()).all()
    
    return [
        {"id": item.id, "name": item.name, "platform": item.platform}
        for item in items
    ]


@router.get("/{api_key_id}")
def get_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """获取 API Key 详情"""
    item = db.query(AiApiKey).filter(AiApiKey.id == api_key_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    return _to_resp(item)


@router.post("/create")
def create_api_key(
    data: AiApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """创建 API Key"""
    item = AiApiKey(
        name=data.name,
        api_key=data.api_key,
        platform=data.platform,
        url=data.url or "",
        app_id=data.app_id or "",
        property=data.property or {},
        status=data.status,
        sort=data.sort,
        creator=current_user.username if current_user else None
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "创建成功"}


@router.post("/update")
def update_api_key(
    data: AiApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """更新 API Key"""
    item = db.query(AiApiKey).filter(AiApiKey.id == data.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if k == "id":
            continue
        setattr(item, k, v)
    
    item.updater = current_user.username if current_user else None
    item.updated_at = datetime.now()
    db.commit()
    return {"id": item.id, "message": "更新成功"}


@router.delete("/delete")
def delete_api_key(
    id: int = Query(..., description="API Key ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """删除 API Key（如果有关联模型则不允许删除）"""
    # 检查是否有关联的模型
    model_count = db.query(AiChatModel).filter(AiChatModel.key_id == id).count()
    if model_count > 0:
        raise HTTPException(status_code=400, detail=f"该 API Key 关联了 {model_count} 个模型，请先删除关联模型")
    
    item = db.query(AiApiKey).filter(AiApiKey.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============= ChatModel CRUD =============

@router.get("/chat-model/available")
def get_available_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """获取所有可用的聊天模型（用于前端下拉选择）"""
    models = (
        db.query(AiChatModel, AiApiKey)
        .join(AiApiKey, AiChatModel.key_id == AiApiKey.id)
        .filter(AiChatModel.status == 1, AiApiKey.status == 1)
        .order_by(AiChatModel.sort.desc(), AiChatModel.id.asc())
        .all()
    )

    return [
        {
            "id": model.id,
            "name": model.name,
            "model": model.model,
            "platform": model.platform or api_key.platform,
            "key_name": api_key.name,
            "type": model.type,
        }
        for model, api_key in models
    ]


@router.get("/chat-model/page")
def get_chat_model_page(
    keyId: int = Query(..., description="API Key ID"),
    name: Optional[str] = Query(None, description="模型名称搜索"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """分页获取关联的 ChatModel 列表"""
    query = db.query(AiChatModel).filter(AiChatModel.key_id == keyId)
    
    if name:
        query = query.filter(AiChatModel.name.contains(name))
    
    total = query.count()
    items = query.order_by(AiChatModel.sort.desc(), AiChatModel.id.desc())\
                 .offset((page - 1) * pageSize)\
                 .limit(pageSize).all()
    
    return {
        "data": [_to_model_resp(item) for item in items],
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.get("/chat-model/{model_id}")
def get_chat_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """获取 ChatModel 详情"""
    item = db.query(AiChatModel).filter(AiChatModel.id == model_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="模型不存在")
    return _to_model_resp(item)


@router.post("/chat-model/create")
def create_chat_model(
    data: AiChatModelCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """创建 ChatModel"""
    # 验证 API Key 存在
    api_key = db.query(AiApiKey).filter(AiApiKey.id == data.key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="关联的 API Key 不存在")

    # code 唯一性校验（跨全表唯一）
    if data.code:
        dup = db.query(AiChatModel).filter(AiChatModel.code == data.code).first()
        if dup:
            raise HTTPException(status_code=400, detail="模型编码 code 已存在")
    
    item = AiChatModel(
        code=data.code,
        key_id=data.key_id,
        name=data.name,
        model=data.model,
        platform=data.platform or api_key.platform,
        sort=data.sort,
        status=data.status,
        type=data.type,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        top_k=data.top_k,
        top_p=data.top_p,
        seed=data.seed,
        max_contexts=data.max_contexts,
        max_turns=data.max_turns,
        dimensions=data.dimensions,
        retry=data.retry,
        timeout=data.timeout,
        stream_timeout=data.stream_timeout,
        enable_thinking=data.enable_thinking,
        enable_search=data.enable_search,
        is_default=data.is_default,
    )
    # 如果设为默认，清除同类型其他模型的默认状态
    if data.is_default and data.type is not None:
        db.query(AiChatModel).filter(
            AiChatModel.key_id == data.key_id,
            AiChatModel.type == data.type,
            AiChatModel.id != item.id
        ).update({"is_default": False}, synchronize_session=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "创建成功"}


@router.post("/chat-model/update")
def update_chat_model(
    data: AiChatModelUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """更新 ChatModel"""
    item = db.query(AiChatModel).filter(AiChatModel.id == data.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="模型不存在")

    # code 唯一性校验（排除自身）
    if data.code:
        dup = (
            db.query(AiChatModel)
            .filter(AiChatModel.code == data.code, AiChatModel.id != data.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="模型编码 code 已存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if k == "id":
            continue
        setattr(item, k, v)
    
    item.updated_at = datetime.now()
    db.commit()
    return {"id": item.id, "message": "更新成功"}


@router.delete("/chat-model/delete")
def delete_chat_model(
    id: int = Query(..., description="模型 ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """删除 ChatModel"""
    item = db.query(AiChatModel).filter(AiChatModel.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


class SetDefaultRequest(BaseModel):
    model_id: int


@router.post("/chat-model/set-default")
async def set_chat_model_default(
    req: SetDefaultRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """设置模型为默认模型（先检测连通性）"""
    model = db.query(AiChatModel).filter(AiChatModel.id == req.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    api_key = db.query(AiApiKey).filter(AiApiKey.id == model.key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="关联的 API Key 不存在")
    if api_key.status != 1:
        raise HTTPException(status_code=400, detail="API Key 已禁用，无法设为默认")

    # 检测模型连通性
    model_type = model.type or 1
    connectivity_ok = await _check_model_connectivity(model, api_key, model_type)
    if not connectivity_ok:
        raise HTTPException(status_code=400, detail="模型连通性检测失败，无法设为默认")

    # 连通性正常，清除同类型其他模型的默认状态
    if model.type is not None:
        db.query(AiChatModel).filter(
            AiChatModel.key_id == model.key_id,
            AiChatModel.type == model.type,
            AiChatModel.id != model.id
        ).update({"is_default": False}, synchronize_session=False)

    # 设置当前模型为默认
    model.is_default = True
    model.updated_at = datetime.now()
    db.commit()
    return {"id": model.id, "message": "已设为默认模型"}


async def _check_model_connectivity(model: AiChatModel, api_key: AiApiKey, model_type: int) -> bool:
    """检测模型连通性（发送最小请求）

    自动兼容 URL 是否包含 /v1 前缀：
    - 先尝试原始 URL
    - 若原始 URL 不以 /v1 结尾，再尝试追加 /v1
    """
    raw_url = (api_key.url or "").rstrip("/")
    # 构建候选 base_url 列表：优先原始 URL，再补充带 /v1 的变体
    candidates = [raw_url]
    if not raw_url.endswith("/v1"):
        candidates.append(f"{raw_url}/v1")

    headers = {
        "Authorization": f"Bearer {api_key.api_key}",
        "Content-Type": "application/json",
    }
    timeout = min(model.timeout or 15, 15)

    if model_type == 5:
        payload = {"model": model.model, "input": "test", "dimensions": 1}
        path = "/embeddings"
    else:
        payload = {
            "model": model.model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }
        path = "/chat/completions"

    for base_url in candidates:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base_url}{path}",
                    json=payload,
                    headers=headers,
                    timeout=float(timeout)
                )
                if resp.status_code == 200:
                    return True
                logger.debug(f"连通性检测 {base_url}{path} 返回 {resp.status_code}")
        except Exception as e:
            logger.debug(f"连通性检测 {base_url}{path} 异常: {e}")

    logger.warning(f"模型连通性检测失败: 所有候选 URL均不可达")
    return False


# ============= 模型测试 =============

class ModelTestRequest(BaseModel):
    model_id: int
    prompt: str
    system_prompt: Optional[str] = None
    stream: bool = True


@router.post("/chat-model/test")
async def test_chat_model(
    req: ModelTestRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """测试单个模型（流式 SSE 返回）"""
    model = db.query(AiChatModel).filter(AiChatModel.id == req.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    api_key = db.query(AiApiKey).filter(AiApiKey.id == model.key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="关联的 API Key 不存在")
    if api_key.status != 1:
        raise HTTPException(status_code=400, detail="API Key 已禁用")

    # Embedding 模型走单独逻辑
    model_type = model.type or 1
    if model_type == 5:
        return await _test_embedding(model, api_key, req.prompt)

    # 文本/对话模型 → SSE 流式
    if not req.stream:
        return await _test_chat_non_stream(model, api_key, req)

    return StreamingResponse(
        _stream_chat(model, api_key, req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


async def _stream_chat(model: AiChatModel, api_key: AiApiKey, req: ModelTestRequest):
    """SSE 流式调用 OpenAI 兼容 API"""
    base_url = (api_key.url or "").rstrip("/")
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})

    payload = {
        "model": model.model,
        "messages": messages,
        "stream": True,
    }
    if model.temperature is not None:
        payload["temperature"] = model.temperature
    if model.max_tokens:
        payload["max_tokens"] = model.max_tokens
    if model.top_p is not None:
        payload["top_p"] = model.top_p
    if model.top_k is not None:
        payload["top_k"] = model.top_k
    if model.seed is not None:
        payload["seed"] = model.seed
    if model.enable_thinking:
        payload["enable_thinking"] = True

    headers = {
        "Authorization": f"Bearer {api_key.api_key}",
        "Content-Type": "application/json",
    }

    timeout = model.stream_timeout or model.timeout or 120

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=float(timeout),
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    err_msg = body.decode("utf-8", errors="replace")[:500]
                    yield f"data: {json.dumps({'error': True, 'message': f'HTTP {resp.status_code}: {err_msg}'})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        yield "data: [DONE]\n\n"
                        return
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                        # 思考内容
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            yield f"data: {json.dumps({'reasoning': reasoning}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        continue

    except httpx.TimeoutException:
        yield f"data: {json.dumps({'error': True, 'message': f'请求超时 ({timeout}s)'})}\n\n"
    except Exception as e:
        logger.error(f"模型测试流式调用异常: {e}")
        yield f"data: {json.dumps({'error': True, 'message': str(e)})}\n\n"


async def _test_chat_non_stream(model: AiChatModel, api_key: AiApiKey, req: ModelTestRequest):
    """非流式调用"""
    base_url = (api_key.url or "").rstrip("/")
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})

    payload = {"model": model.model, "messages": messages}
    if model.temperature is not None:
        payload["temperature"] = model.temperature
    if model.max_tokens:
        payload["max_tokens"] = model.max_tokens

    headers = {
        "Authorization": f"Bearer {api_key.api_key}",
        "Content-Type": "application/json",
    }
    timeout = model.timeout or 120

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=float(timeout),
            )
            if resp.status_code != 200:
                return {"error": True, "message": f"HTTP {resp.status_code}: {resp.text[:500]}"}
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {"content": content, "usage": usage}
    except Exception as e:
        return {"error": True, "message": str(e)}


async def _test_embedding(model: AiChatModel, api_key: AiApiKey, prompt: str):
    """Embedding 模型测试"""
    base_url = (api_key.url or "").rstrip("/")
    payload = {"model": model.model, "input": prompt}
    if model.dimensions:
        payload["dimensions"] = model.dimensions

    headers = {
        "Authorization": f"Bearer {api_key.api_key}",
        "Content-Type": "application/json",
    }
    timeout = model.timeout or 60

    try:
        async with httpx.AsyncClient() as client:
            # 兼容 /embeddings 和 /chat/completions 两种端点
            url = f"{base_url}/embeddings"
            resp = await client.post(url, json=payload, headers=headers, timeout=float(timeout))
            if resp.status_code != 200:
                return {"error": True, "message": f"HTTP {resp.status_code}: {resp.text[:500]}"}
            data = resp.json()
            embedding = data.get("data", [{}])[0].get("embedding", [])
            usage = data.get("usage", {})
            # 只返回前 20 维用于展示
            preview = embedding[:20] if len(embedding) > 20 else embedding
            return {
                "type": "embedding",
                "dimensions": len(embedding),
                "preview": preview,
                "usage": usage,
            }
    except Exception as e:
        return {"error": True, "message": str(e)}


# ============= Helper Functions =============

def _to_resp(item: AiApiKey) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "api_key": item.api_key,
        "platform": item.platform,
        "url": item.url or "",
        "app_id": item.app_id or "",
        "property": item.property or {},
        "status": item.status,
        "sort": item.sort,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "creator": item.creator,
        "updater": item.updater,
    }


def _to_page_resp(item: AiApiKey) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "api_key": item.api_key,
        "platform": item.platform,
        "url": item.url or "",
        "app_id": item.app_id or "",
        "status": item.status,
        "sort": item.sort,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "creator": item.creator,
    }


def _to_model_resp(item: AiChatModel) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "key_id": item.key_id,
        "name": item.name,
        "model": item.model,
        "platform": item.platform,
        "sort": item.sort,
        "status": item.status,
        "type": item.type,
        "temperature": item.temperature,
        "max_tokens": item.max_tokens,
        "top_k": item.top_k,
        "top_p": item.top_p,
        "seed": item.seed,
        "max_contexts": item.max_contexts,
        "max_turns": item.max_turns,
        "dimensions": item.dimensions,
        "retry": item.retry,
        "timeout": item.timeout,
        "stream_timeout": item.stream_timeout,
        "enable_thinking": item.enable_thinking,
        "enable_search": item.enable_search,
        "is_default": item.is_default or False,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
