"""PP-OCRv6 文本识别服务（Medium 34.5M，CPU 推理）。

端点：
  - GET  /health      -> {"status":"ok","gpu_available":false}
  - POST /api/ocr     (multipart file "image" + 可选 "prompt")
                      -> {"status":"success","data":[{"text":"..."}]}

客户端契约（Java PaddleOcrClient）：POST multipart image，解析 data 数组中的 text 字段。
模型在首次请求时惰性加载；构建阶段已把权重预热进 PADDLEX_HOME，因此这里几乎是瞬时返回。
"""
import asyncio
import io
import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="PP-OCRv6 (Medium) OCR Service")

_lock = threading.Lock()
_ocr_model = None


def get_ocr():
    """惰性加载 PP-OCRv6（默认即 Medium 34.5M 服务端高精度模型）。"""
    global _ocr_model
    if _ocr_model is None:
        with _lock:
            if _ocr_model is None:
                from paddleocr import PaddleOCR
                _ocr_model = PaddleOCR()  # ocr_version 默认 PP-OCRv6 Medium
    return _ocr_model


def _ocr_text(result) -> str:
    parts = []
    for r in result:
        j = r.json if hasattr(r, "json") else r
        if isinstance(j, dict):
            rec = j.get("rec_texts")
            if isinstance(rec, list) and rec:
                parts.append("\n".join(str(x) for x in rec))
                continue
        parts.append(str(j))
    return "\n".join(p for p in parts if p).strip()


@app.get("/health")
def health():
    return {"status": "ok", "gpu_available": False}


@app.post("/api/ocr")
async def api_ocr(image: UploadFile = File(...), prompt: Optional[str] = Form(None)):
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        ocr = get_ocr()
        result = await asyncio.to_thread(ocr.predict, io.BytesIO(data))
        text = _ocr_text(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ocr failed: {e}")
    return {"status": "success", "data": [{"text": text}]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
