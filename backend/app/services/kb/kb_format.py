"""kb_format 二级形态校验（spec §10.2）：合法性矩阵 + 创建后不可切换。

矩阵（Dify 对齐「选定数据源后不可切换」）：
    type=1 llm-wiki    → kb_format 必须为 NULL
    type=2 general-kb  → document | table | qa（multimodal 是 document 上的开关，非形态）
    type=3 external-kb → connector | proxy
    type=4 graph-kb    → graph（唯一形态，缺省自动补齐；其它值一律 422）
"""
from fastapi import HTTPException

# 图谱知识库（type=4）常量：唯一形态 + 强制约束
GRAPH_KB_TYPE = 4
GRAPH_KB_FORMAT = "graph"

VALID_KB_FORMATS: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("document", "table", "qa"),
    3: ("connector", "proxy"),
    4: (GRAPH_KB_FORMAT,),
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
    # 图谱知识库：形态唯一且固定，缺省自动补齐（客户端无需记忆 magic 字符串）
    if kb_type == GRAPH_KB_TYPE:
        if kb_format in (None, GRAPH_KB_FORMAT):
            return GRAPH_KB_FORMAT
        raise HTTPException(
            status_code=422,
            detail=f"图谱知识库（type=4）仅支持 kb_format={GRAPH_KB_FORMAT!r}",
        )
    if not kb_format:
        raise HTTPException(status_code=422, detail=f"type={kb_type} 必须选择 kb_format")
    if kb_format not in allowed:
        raise HTTPException(
            status_code=422, detail=f"kb_format={kb_format!r} 不合法，允许: {allowed}"
        )
    return kb_format


def normalize_graph_kb(kb_type: int, data: dict) -> dict:
    """type=4 强制约束（原地修改并返回 ``data``）；非 type=4 不做任何改动。

    - ``kb_format`` 固定为 ``graph``
    - ``index_mode`` 强制 ``high_quality``（economy 不产向量，实体/关系无法召回）
    - ``multimodal_enabled`` 恒 False（图谱库无「图片独立向量化」语义）

    ``external_type`` 必须为 NULL —— 由 ``validate_external_type`` 的 type≠3 分支
    既有拒绝逻辑保证，无需在此重复实现。
    """
    if kb_type != GRAPH_KB_TYPE:
        return data
    data["kb_format"] = GRAPH_KB_FORMAT
    data["index_mode"] = "high_quality"
    data["multimodal_enabled"] = False
    return data


def validate_external_type(
    kb_type: int, kb_format: str | None, external_type: str | None
) -> str | None:
    """校验外部类型（spec 知识库管理「外部类型」下拉）。

    - type≠3                       → 必须为 NULL
    - type=3 / kb_format=proxy     → 必须为 NULL（proxy 仅配置检索端点，无平台）
    - type=3 / kb_format=connector → 必填，且必须命中已注册的文档源平台
                                     （feishu|lark|feishu_drive|lark_drive|yuque|
                                      dingtalk|wecom|notion|gitlab|ima|rss|confluence|
                                      seafile|github|google_drive|onedrive|web_crawler|
                                      slack|imap）

    返回规整后的 external_type（connector 路径）或 None。
    """
    # 非外部知识库：不允许携带外部类型
    if kb_type != 3:
        if external_type is not None:
            raise HTTPException(
                status_code=422, detail="仅外部知识库（type=3）可设置 external_type"
            )
        return None
    # type=3 但选择的是 proxy（仅检索代理）：无平台概念
    if kb_format == "proxy":
        if external_type is not None:
            raise HTTPException(
                status_code=422, detail="proxy 形态的外部知识库无需设置 external_type"
            )
        return None
    # type=3 / connector：外部类型必填且必须命中已注册平台
    if not external_type:
        raise HTTPException(
            status_code=422, detail="connector 形态的外部知识库必须选择外部类型（平台）"
        )
    from app.connectors.doc_sources import supported_source_types

    supported = supported_source_types()
    if external_type not in supported:
        raise HTTPException(
            status_code=422,
            detail=f"external_type={external_type!r} 不合法，允许: {supported}",
        )
    return external_type


def assert_format_unchanged(old: str | None, new: str | None) -> None:
    """创建后不可切换：old 为 None 表示初次设置；new 为 None 表示本次未传，放行。"""
    if new is None or new == old:
        return
    if old is not None:
        raise HTTPException(
            status_code=409, detail="知识库数据源形态创建后不可切换（Dify 对齐）"
        )
