"""kb_format 二级形态校验（spec §10.2）：合法性矩阵 + 创建后不可切换。

矩阵（Dify 对齐「选定数据源后不可切换」）：
    type=1 llm-wiki    → kb_format 必须为 NULL
    type=2 general-kb  → document | table | qa（multimodal 是 document 上的开关，非形态）
    type=3 external-kb → connector | proxy
"""
from fastapi import HTTPException

VALID_KB_FORMATS: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("document", "table", "qa"),
    3: ("connector", "proxy"),
}


def validate_kb_format(kb_type: int, kb_format: str | None) -> str | None:
    """校验 (type, kb_format) 合法性；type=2 时 kb_format 必填。返回规整后的值。"""
    allowed = VALID_KB_FORMATS.get(kb_type)
    if allowed is None:
        raise HTTPException(status_code=422, detail=f"未知知识库类型: {kb_type}")
    if kb_type == 1:
        if kb_format is not None:
            raise HTTPException(status_code=422, detail="llm-wiki 容器不使用 kb_format")
        return None
    if not kb_format:
        raise HTTPException(status_code=422, detail=f"type={kb_type} 必须选择 kb_format")
    if kb_format not in allowed:
        raise HTTPException(
            status_code=422, detail=f"kb_format={kb_format!r} 不合法，允许: {allowed}"
        )
    return kb_format


def assert_format_unchanged(old: str | None, new: str | None) -> None:
    """创建后不可切换：old 为 None 表示初次设置；new 为 None 表示本次未传，放行。"""
    if new is None or new == old:
        return
    if old is not None:
        raise HTTPException(
            status_code=409, detail="知识库数据源形态创建后不可切换（Dify 对齐）"
        )
