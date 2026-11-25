"""一次性：登记 GPUStack（192.168.40.30）的 qwen3-32b 到模型管理（幂等）。

key 复用 backend/.env 的 NVIDIA_API_KEY（该 key 实际指向内网 GPUStack，
见 llm_tokens.py 对 GPUStack qwen3-32b 的注释）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.ai.ai_api_key import AiApiKey, AiChatModel  # noqa: E402

KEY_NAME = "GPUStack 192.168.40.30"
MODEL_NAME = "GPUStack Qwen3-32B"

with SessionLocal() as db:
    key = db.execute(
        select(AiApiKey).where(AiApiKey.name == KEY_NAME)
    ).scalars().first()
    if key is None:
        key = AiApiKey(
            name=KEY_NAME,
            api_key=settings.NVIDIA_API_KEY,
            platform="openai",
            url="http://192.168.40.30/v1",
            status=1,
        )
        db.add(key)
        db.flush()
        print(f"[key] 新建 ai_api_key id={key.id}")
    else:
        print(f"[key] 已存在 id={key.id}")

    model = db.execute(
        select(AiChatModel).where(AiChatModel.model == "qwen3-32b",
                                  AiChatModel.platform == "openai")
    ).scalars().first()
    if model is None:
        model = AiChatModel(
            code="qwen3-32b",
            key_id=key.id,
            name=MODEL_NAME,
            model="qwen3-32b",
            platform="openai",
            type=1,
            status=1,
            sort=1,
            max_tokens=8192,
            enable_thinking=False,
            is_default=False,
        )
        db.add(model)
        db.flush()
        print(f"[model] 新建 ai_chat_model id={model.id}")
    else:
        print(f"[model] 已存在 id={model.id}")
    db.commit()
