"""PP-StructureV3 版面解析服务（CPU 推理）。

与 app.py 的对偶版本，只在 infer pipeline 上不同：
  - GET  /health       -> {"status":"ok"}
  - POST /api/parse    (multipart file "image")
                       -> {"status":"success","data":[{"markdown":"...","blocks":[...]}]}

CPU 下单页耗时可达数秒，生产环境建议改用 GPU 侧的 PaddleOCR-VL。
"""
import asyncio
import io
import os
import threading

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="PP-StructureV3 Parsing Service")

_lock = threading.Lock()
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        with _lock:
            if _pipeline is None:
                from paddleocr import PPStructureV3
                _pipeline = PPStructureV3()
    return _pipeline


def _to_blocks(result):
    blocks = []
    for r in result:
        j = r.json if hasattr(r, "json") else r
        if isinstance(j, dict):
            blocks.append({
                "type": j.get("block_label"),
                "text": "\n".join(str(x) for x in (j.get("rec_texts") or [])),
                "bbox": j.get("block_bbox"),
            })
        else:
            blocks.append({"type": None, "text": str(j), "bbox": None})
    return blocks


@app.get("/health")
def health():
    return {"status": "ok", "gpu_available": False}


@app.post("/api/parse")
async def api_parse(image: UploadFile = File(...)):
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        pipeline = get_pipeline()
        result = await asyncio.to_thread(pipeline.predict, io.BytesIO(data))
        blocks = _to_blocks(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"parse failed: {e}")
    markdown = "\n\n".join(b.get("text") or "" for b in blocks).strip()
    return {"status": "success", "data": [{"markdown": markdown, "blocks": blocks}]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
