"""SQLBot 业务 Tool 的声明式配置模型。

业务线无需编写代码：在管理后台填写一份 JSON 配置，存入
``tool_definition.config_value``，即可发布一个新的数据查询 Tool。

本模块定义该配置的契约（Pydantic v2），并提供：
- :func:`validate_config` —— 配置校验（配置期使用）
- :meth:`SqlBotToolConfig.build_input_schema` —— 由参数声明自动生成标准
  JSON Schema，写回 ``tool_definition.input_schema`` 供 Agent 识别与前端渲染
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "CONFIG_VERSION",
    "ParamType",
    "MaskStrategy",
    "ParameterDef",
    "RowScopeConfig",
    "MaskingRule",
    "MaskingConfig",
    "OrderByItem",
    "ResultFormatConfig",
    "PermissionConfig",
    "SqlBotToolConfig",
    "validate_config",
    "PLACEHOLDER_PATTERN",
]

CONFIG_VERSION = "1.0"

# 模板占位符：{param_name}，仅允许字母/数字/下划线
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

_PARAM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")

# 行数上限的硬性天花板（配置不得超过）
HARD_MAX_ROWS = 1000
DEFAULT_MAX_ROWS = 200


class ParamType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"


class MaskStrategy(str, Enum):
    MASK = "mask"
    HASH = "hash"
    DROP = "drop"
    TRUNCATE = "truncate"


class ParameterDef(BaseModel):
    """单个业务参数声明。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = Field(..., description="参数名，需与提问模板占位符一致")
    label: str = Field(default="", description="中文显示名")
    type: ParamType = Field(default=ParamType.STRING)
    required: bool = Field(default=False)
    default: Any = Field(default=None)
    enum: Optional[List[Any]] = Field(default=None, description="type=enum 时的候选值")
    minimum: Optional[float] = Field(default=None)
    maximum: Optional[float] = Field(default=None)
    max_length: Optional[int] = Field(default=128, alias="maxLength")
    description: str = Field(default="")

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not _PARAM_NAME_PATTERN.match(v or ""):
            raise ValueError(f"参数名非法（仅允许字母/数字/下划线且不以数字开头）: {v}")
        return v

    @model_validator(mode="after")
    def _check_enum(self) -> "ParameterDef":
        if self.type == ParamType.ENUM and not self.enum:
            raise ValueError(f"参数 {self.name} 声明为 enum 但未提供候选值 enum")
        return self

    def json_schema_fragment(self) -> Dict[str, Any]:
        """转为 JSON Schema 片段。"""
        if self.type == ParamType.ENUM:
            frag: Dict[str, Any] = {"type": "string", "enum": list(self.enum or [])}
        elif self.type == ParamType.DATE:
            frag = {"type": "string", "format": "date"}
        elif self.type == ParamType.INTEGER:
            frag = {"type": "integer"}
        elif self.type == ParamType.NUMBER:
            frag = {"type": "number"}
        elif self.type == ParamType.BOOLEAN:
            frag = {"type": "boolean"}
        else:
            frag = {"type": "string"}

        desc = self.description or self.label
        if desc:
            frag["description"] = desc
        if self.default is not None:
            frag["default"] = self.default
        if self.minimum is not None:
            frag["minimum"] = self.minimum
        if self.maximum is not None:
            frag["maximum"] = self.maximum
        if self.type in (ParamType.STRING, ParamType.DATE) and self.max_length:
            frag["maxLength"] = int(self.max_length)
        return frag


class RowScopeConfig(BaseModel):
    """行级数据权限配置。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    enabled: bool = Field(default=True)
    region_field: str = Field(default="region_code", alias="regionField",
                              description="结果集中用于兜底过滤的区域字段名")
    scope_placeholder: str = Field(default="__region_scope__", alias="scopePlaceholder",
                                   description="提问模板中的受控区域占位符名")
    bypass_roles: List[str] = Field(default_factory=list, alias="bypassRoles",
                                    description="可跳过行级过滤的角色码")
    # 结果集中不含区域字段时的处置：strict=清空并告警，lenient=放行
    on_missing_field: Literal["strict", "lenient"] = Field(
        default="lenient", alias="onMissingField"
    )


class MaskingRule(BaseModel):
    """单条列级脱敏规则。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    field: str = Field(..., description="需脱敏的结果字段名")
    strategy: MaskStrategy = Field(default=MaskStrategy.MASK)
    keep_prefix: int = Field(default=0, alias="keepPrefix", ge=0)
    keep_suffix: int = Field(default=0, alias="keepSuffix", ge=0)
    mask_char: str = Field(default="*", alias="maskChar", max_length=1)
    max_length: Optional[int] = Field(default=None, alias="maxLength",
                                      description="strategy=truncate 时保留长度")
    exempt_roles: List[str] = Field(default_factory=list, alias="exemptRoles",
                                    description="免脱敏的角色码")

    @field_validator("field")
    @classmethod
    def _check_field(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("脱敏规则的 field 不能为空")
        return v.strip()


class MaskingConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    enabled: bool = Field(default=False)
    rules: List[MaskingRule] = Field(default_factory=list)


class OrderByItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    field: str
    desc: bool = Field(default=False)


class ResultFormatConfig(BaseModel):
    """结果格式化配置。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    max_rows: int = Field(default=DEFAULT_MAX_ROWS, alias="maxRows", ge=1)
    field_alias: Dict[str, str] = Field(default_factory=dict, alias="fieldAlias")
    include_fields: Optional[List[str]] = Field(default=None, alias="includeFields",
                                                description="None 表示全部字段")
    exclude_fields: List[str] = Field(default_factory=list, alias="excludeFields")
    order_by: List[OrderByItem] = Field(default_factory=list, alias="orderBy")
    number_precision: Optional[int] = Field(default=None, alias="numberPrecision", ge=0, le=10)

    @field_validator("max_rows")
    @classmethod
    def _cap_max_rows(cls, v: int) -> int:
        return min(int(v), HARD_MAX_ROWS)


class PermissionConfig(BaseModel):
    """Tool 级权限配置。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    permission_code: Optional[str] = Field(default=None, alias="permissionCode")
    allow_roles: List[str] = Field(default_factory=list, alias="allowRoles",
                                   description="空表示不做角色白名单限制")
    deny_roles: List[str] = Field(default_factory=list, alias="denyRoles")
    # 取不到用户上下文时是否允许执行（默认否，最严策略）
    allow_anonymous: bool = Field(default=False, alias="allowAnonymous")


class SqlBotToolConfig(BaseModel):
    """SQLBot 业务 Tool 的完整声明式配置。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    config_version: str = Field(default=CONFIG_VERSION, alias="configVersion")
    datasource_id: int = Field(..., alias="datasourceId", description="固定绑定的数据源，调用方不可覆盖")
    business_line: str = Field(default="", alias="businessLine", description="所属业务线标识")
    allowed_tables: List[str] = Field(default_factory=list, alias="allowedTables")
    parameters: List[ParameterDef] = Field(default_factory=list)
    question_template: str = Field(..., alias="questionTemplate")
    extra_rules: List[str] = Field(default_factory=list, alias="extraRules",
                                   description="附加到提问的业务约束语句")
    row_scope: RowScopeConfig = Field(default_factory=RowScopeConfig, alias="rowScope")
    masking: MaskingConfig = Field(default_factory=MaskingConfig)
    result_format: ResultFormatConfig = Field(default_factory=ResultFormatConfig, alias="resultFormat")
    permission: PermissionConfig = Field(default_factory=PermissionConfig)

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    @field_validator("datasource_id")
    @classmethod
    def _check_ds(cls, v: int) -> int:
        if int(v) <= 0:
            raise ValueError("datasourceId 必须为正整数")
        return int(v)

    @field_validator("question_template")
    @classmethod
    def _check_template(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("questionTemplate 不能为空")
        return v

    @field_validator("allowed_tables")
    @classmethod
    def _check_tables(cls, v: List[str]) -> List[str]:
        cleaned: List[str] = []
        for t in v or []:
            t = (t or "").strip()
            if not t:
                continue
            if not _TABLE_NAME_PATTERN.match(t):
                raise ValueError(f"表名非法: {t}")
            cleaned.append(t)
        return cleaned

    @model_validator(mode="after")
    def _cross_check(self) -> "SqlBotToolConfig":
        names = [p.name for p in self.parameters]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            raise ValueError(f"参数名重复: {sorted(dup)}")

        scope_name = self.row_scope.scope_placeholder
        if scope_name in names:
            raise ValueError(f"参数名不得与受控区域占位符同名: {scope_name}")

        declared = set(names) | {scope_name}
        used = set(PLACEHOLDER_PATTERN.findall(self.question_template))
        unknown = used - declared
        if unknown:
            raise ValueError(
                f"提问模板中存在未声明的占位符: {sorted(unknown)}（已声明: {sorted(declared)}）"
            )

        if self.row_scope.enabled and scope_name not in used:
            # 非致命：允许模板不含区域占位符，此时仅依赖兜底行过滤
            pass
        return self

    # ------------------------------------------------------------------
    # 派生能力
    # ------------------------------------------------------------------
    def build_input_schema(self) -> Dict[str, Any]:
        """由参数声明自动生成标准 JSON Schema。"""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            properties[p.name] = p.json_schema_fragment()
            if p.required:
                required.append(p.name)
        schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def get_parameter(self, name: str) -> Optional[ParameterDef]:
        for p in self.parameters:
            if p.name == name:
                return p
        return None

    def unused_parameters(self) -> List[str]:
        """声明了但未在模板中使用的参数（配置期告警用）。"""
        used = set(PLACEHOLDER_PATTERN.findall(self.question_template))
        return [p.name for p in self.parameters if p.name not in used]

    def to_config_value(self) -> Dict[str, Any]:
        """序列化为存库用的 camelCase dict。"""
        return self.model_dump(by_alias=True, mode="json")


def validate_config(raw: Any) -> tuple[Optional[SqlBotToolConfig], List[str], List[str]]:
    """校验配置。

    :return: ``(config, errors, warnings)``；解析失败时 config 为 None。
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(raw, dict):
        return None, ["config_value 必须为 JSON 对象"], warnings

    try:
        cfg = SqlBotToolConfig.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - pydantic ValidationError 亦在内
        return None, [str(exc)], warnings

    if cfg.config_version != CONFIG_VERSION:
        warnings.append(
            f"configVersion={cfg.config_version} 与当前支持版本 {CONFIG_VERSION} 不一致"
        )
    if not cfg.allowed_tables:
        warnings.append("未声明 allowedTables，SQLBot 可能触达该数据源的任意表")
    unused = cfg.unused_parameters()
    if unused:
        warnings.append(f"以下参数已声明但未在提问模板中使用: {unused}")
    if cfg.row_scope.enabled and cfg.row_scope.scope_placeholder not in PLACEHOLDER_PATTERN.findall(
        cfg.question_template
    ):
        warnings.append(
            f"已启用行级权限但模板未使用占位符 {{{cfg.row_scope.scope_placeholder}}}，"
            "将仅依赖返回结果的兜底行过滤"
        )
    if cfg.masking.enabled and not cfg.masking.rules:
        warnings.append("已启用列级脱敏但未配置任何规则")
    if not cfg.permission.permission_code and not cfg.permission.allow_roles:
        warnings.append("未配置 permissionCode 与 allowRoles，该 Tool 对所有登录用户可用")

    return cfg, errors, warnings
