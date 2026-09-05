from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse
import json
import asyncio


async def sse_generator(data_stream: AsyncGenerator[Dict[str, Any], None]) -> AsyncGenerator[str, None]:
    """
    SSE 数据生成器
    
    Args:
        data_stream: 数据流
        
    Yields:
        SSE 格式的数据
    """
    try:
        async for data in data_stream:
            # 将数据转换为 SSE 格式
            sse_data = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            yield sse_data
            
            # 短暂延迟，避免过快推送
            await asyncio.sleep(0.01)
    except Exception as e:
        error_data = {"error": str(e)}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    finally:
        # 发送结束标记
        yield "data: [DONE]\n\n"


def create_sse_response(data_stream: AsyncGenerator[Dict[str, Any], None]) -> StreamingResponse:
    """
    创建 SSE 响应
    
    Args:
        data_stream: 数据流
        
    Returns:
        StreamingResponse
    """
    return StreamingResponse(
        sse_generator(data_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def mock_deduction_stream() -> AsyncGenerator[Dict[str, Any], None]:
    """
    模拟推演流式输出（用于测试）
    """
    stages = [
        {"stage": "数据加载", "progress": 10, "message": "正在加载事件数据..."},
        {"stage": "相似事件检索", "progress": 30, "message": "检索历史相似事件..."},
        {"stage": "要素抽取", "progress": 50, "message": "提取事件关键要素..."},
        {"stage": "演化预测", "progress": 70, "message": "预测事件演化路径..."},
        {"stage": "风险评估", "progress": 90, "message": "评估各路径风险..."},
        {"stage": "完成", "progress": 100, "message": "推演完成", "result": {
            "scenarios": [
                {"strategy": "当前措施不变", "risk_score": 85},
                {"strategy": "强化调解", "risk_score": 40},
                {"strategy": "法律途径", "risk_score": 55}
            ]
        }}
    ]
    
    for stage in stages:
        yield stage
        await asyncio.sleep(1)

