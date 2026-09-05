"""LLM 调用工具 — 提供通用的 GPUStack 对话接口调用"""
import json
import re
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 800,
             timeout: float = 180.0) -> Optional[dict]:
    """调用 GPUStack 对话接口, 解析返回 JSON。失败返回 None。

    timeout 默认 180s, 覆盖长正文抽取场景；
    trust_env=False: GPUStack 为内网地址, 禁用系统代理环境变量。
    """
    url = settings.GPUSTACK_API_URL.rstrip('/') + '/chat/completions'
    headers = {
        'Authorization': f'Bearer {settings.GPUSTACK_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': settings.GPUSTACK_CHAT_MODEL,
        'temperature': 0.2,
        'max_tokens': max_tokens,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data['choices'][0]['message']['content']
    except httpx.HTTPError as e:
        logger.error('LLM 网络调用失败 (url=%s, model=%s, timeout=%ss): %s: %s',
                     url, settings.GPUSTACK_CHAT_MODEL, timeout, type(e).__name__, e)
        return None
    except Exception as e:  # noqa: BLE001
        logger.error('LLM 调用失败 (url=%s, model=%s, timeout=%ss): %s',
                     url, settings.GPUSTACK_CHAT_MODEL, timeout, e)
        return None
    # 提取 JSON (去除 ```json 代码块)
    m = re.search(r'\{.*\}', content, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
