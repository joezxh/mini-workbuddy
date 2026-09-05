"""MCP 服务管理 Schemas - API Key / Client / Square。"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ============= AiMcpApiKey Schemas =============

class AiMcpApiKeyCreate(BaseModel):
    """创建 MCP API Key"""
    name: str = Field(..., description="密钥名称")
    service_type: str = Field(..., description="服务类型")
    platform: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    service_url: Optional[str] = None
    service_name: Optional[str] = None
    api_key: Optional[str] = None
    namespace: Optional[str] = None
    group_key: Optional[str] = None
    access_path: Optional[str] = None
    properties: Optional[dict] = None
    capabilities: Optional[List[str]] = None
    remark: Optional[str] = None


class AiMcpApiKeyUpdate(BaseModel):
    """更新 MCP API Key"""
    id: int = Field(..., description="ID")
    name: Optional[str] = None
    service_type: Optional[str] = None
    platform: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    service_url: Optional[str] = None
    service_name: Optional[str] = None
    api_key: Optional[str] = None
    namespace: Optional[str] = None
    group_key: Optional[str] = None
    access_path: Optional[str] = None
    properties: Optional[dict] = None
    capabilities: Optional[List[str]] = None
    remark: Optional[str] = None
    status: Optional[int] = None
    sort: Optional[int] = None


class AiMcpApiKeyPageResp(BaseModel):
    """MCP API Key 分页响应"""
    id: int
    name: str
    service_type: str
    platform: Optional[str] = None
    protocol_type: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    status: int
    sort: int
    template_id: int = 0
    health_status: str = "unknown"
    last_check_at: Optional[datetime] = None
    creator: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AiMcpApiKeyDetailResp(AiMcpApiKeyPageResp):
    """MCP API Key 详情响应"""
    service_url: Optional[str] = None
    service_name: Optional[str] = None
    api_key: Optional[str] = None
    namespace: Optional[str] = None
    group_key: Optional[str] = None
    access_path: Optional[str] = None
    properties: Optional[dict] = None
    capabilities: Optional[List[str]] = None
    remark: Optional[str] = None
    updater: Optional[str] = None


class AiMcpApiKeySimpleResp(BaseModel):
    """MCP API Key 简易响应（用于下拉选择）"""
    id: int
    name: str
    service_type: str

    model_config = ConfigDict(from_attributes=True)


# ============= McpClient Schemas =============

class AiMcpClientCreate(BaseModel):
    """创建 MCP Client"""
    name: str = Field(..., description="客户端名称")
    api_key_id: int = Field(..., description="关联API Key ID")
    client_type: str = Field(..., description="客户端类型")
    mcp_type: str = Field(..., description="应用类别")
    version: Optional[str] = None
    description: Optional[str] = None
    tools_config: Optional[dict] = None
    remark: Optional[str] = None


class AiMcpClientUpdate(BaseModel):
    """更新 MCP Client"""
    id: int = Field(..., description="ID")
    name: Optional[str] = None
    client_type: Optional[str] = None
    mcp_type: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    tools_config: Optional[dict] = None
    remark: Optional[str] = None
    status: Optional[int] = None


class AiMcpClientPageResp(BaseModel):
    """MCP Client 分页响应"""
    id: int
    name: str
    api_key_id: int
    client_type: str
    mcp_type: str
    version: Optional[str] = None
    description: Optional[str] = None
    status: int
    creator: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============= McpSquare Schemas =============

class McpSquareInstallReq(BaseModel):
    """MCP 广场安装请求 - 模板ID + 用户自定义参数"""
    template_id: int = Field(..., description="模板ID")
    name: Optional[str] = Field(None, description="自定义名称（默认用模板名）")
    service_url: Optional[str] = Field(None, description="用户自定义服务地址")
    api_key: Optional[str] = Field(None, description="用户鉴权密钥")
    access_path: Optional[str] = Field(None, description="自定义访问路径")
    service_name: Optional[str] = Field(None, description="Nacos服务名")
    namespace: Optional[str] = Field(None, description="Nacos命名空间")
    group_key: Optional[str] = Field(None, description="Nacos分组")


class McpSquareCreate(BaseModel):
    """创建 MCP 广场模板"""
    name: str = Field(..., max_length=100, description="模板名称")
    icon: Optional[str] = Field(None, max_length=200, description="图标标识")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    platform: Optional[str] = Field(None, max_length=50, description="平台类型")
    description: Optional[str] = Field(None, description="描述")
    service_type: str = Field(..., max_length=20, description="服务类型")
    service_url: Optional[str] = Field(None, max_length=500, description="服务地址模板")
    access_path: Optional[str] = Field(None, max_length=500, description="访问路径")
    version: Optional[str] = Field(None, max_length=20, description="协议版本")
    capabilities: Optional[List[str]] = None
    default_client_config: Optional[dict] = None
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="1=启用,0=禁用")


class McpSquareUpdate(BaseModel):
    """更新 MCP 广场模板"""
    id: int = Field(..., description="ID")
    name: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    platform: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    service_type: Optional[str] = Field(None, max_length=20)
    service_url: Optional[str] = Field(None, max_length=500)
    access_path: Optional[str] = Field(None, max_length=500)
    version: Optional[str] = Field(None, max_length=20)
    capabilities: Optional[List[str]] = None
    default_client_config: Optional[dict] = None
    sort: Optional[int] = None
    status: Optional[int] = None


class McpSquarePageResp(BaseModel):
    """MCP 广场模板分页响应"""
    id: int
    name: str
    icon: Optional[str] = None
    category: Optional[str] = None
    platform: Optional[str] = None
    description: Optional[str] = None
    service_type: str
    service_url: Optional[str] = None
    access_path: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[List[str]] = None
    default_client_config: Optional[dict] = None
    sort: int
    status: int = 1
    is_installed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
