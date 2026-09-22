# Skill 文件树展示与按技能执行 — 设计文档

日期：2026-09-21
状态：已确认（用户批准）

## 背景与问题

1. **管理页只显示脚本**：`SkillManagement.vue` 详情页的"脚本列表"仅展示 `ai_skill_script` 表内容。以文件为主体提供的技能（如 `tupian-shipin-shengcheng` 的 `scripts/*.py`、`buffett` 的 `references/*.md`）无法查看，无法确认 references 是否装全。
2. **对话技能选择以脚本为单位**：`SkillSelector.vue` 必须选中某个脚本（`script-change` 事件携带 `scriptId`），无脚本技能（buffett、dyp-ask）完全不可选（`v-if="pkg.scripts?.length"`）。
3. **隐藏 bug**：前端发送 `skill: {package_id, ...}`，但 `SkillAgent`（`agent_factory.py:56`）读取 `skill_config.get("name", "general")`，键不匹配 → 对话技能模式实际执行 `"general"` → "技能不存在"。
4. **定时任务强制选脚本**：`ScheduledTaskManage.vue` 要求 `skillScriptId` 必填，但后端校验与执行均只使用 `package_id`。

关键事实：后端执行（`SkillExecutionService.execute`）**本来就是整技能执行**——加载完整 SKILL.md 作为 system prompt，toolkit 挂载工具，agent 自主决定调用哪些脚本、读取哪些 references。`script_id` 在执行链路中从未被使用。

## 决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 文件登记方式 | B：不建表，按需扫描文件系统 | 磁盘是唯一事实源，零失同步，老技能无需重装 |
| 文件操作范围 | B：查看 + 文本预览 | 便于确认 references 齐全、查看脚本代码；编辑走现有 SKILL.md 入口（YAGNI） |
| SkillSelector 交互 | A：完全按技能选择 | 后端执行单位本就是整技能；无脚本技能可选 |
| 定时任务 | 放开脚本必填 | 后端校验只查 package_id |

## 设计

### 1. 后端：技能文件树接口（`routers/ai/ai_skill.py` + `ai_skill_admin_service.py`）

- `GET /ai-skills/{package_id}/files`
  - 扫描 `SKILLS_BASE_DIR/<package_id>/`（递归），排除 `SKILL.md`（已有专属接口）。
  - 返回 `{ package_id, files: [{ path, size, ext, type }], total_count, total_size }`。
  - `type` 判定：`scripts/*.py` → `script`；`references/` 目录下 → `reference`；其余 → `other`。
  - 目录不存在 → 空列表（不报错）。
- `GET /ai-skills/{package_id}/files/content?path=<相对路径>`
  - 安全约束：
    - `resolve()` 后必须仍位于 `SKILLS_BASE_DIR/<package_id>/` 内（拒绝 `..` / 绝对路径穿越）；
    - 文本扩展名白名单（`.md .txt .py .json .yaml .yml .toml .csv .sh .bat .cfg .ini`）+ 内容 null-byte 检测拒绝二进制；
    - 单文件 1MB 上限；
  - 返回 `{ path, size, content }`；越界/超限/二进制 → HTTP 400。
- 现有脚本 CRUD / 启停接口不变（`ai_skill_script` 仍是脚本管理事实源）。

### 2. 前端：`SkillManagement.vue`

- 详情页"脚本列表"区块改为"**文件列表**"：
  - 列出全部文件：相对路径、大小（人性化格式）、类型 Tag（脚本/参考/其他）；
  - `type=script` 行保留现有 启用开关/删除 按钮（数据仍来自 `ai_skill_script`，按 `script_id` 对应 `scripts/<id>.py`）;
  - 点击任意文件行 → 弹窗预览内容（调新接口；二进制/超限时展示后端错误信息）；
  - 保留"新增脚本"等既有管理功能。
- 新增文案走 `t('skillHub.*')`，四语言（en-US / zh-CN / zh-TW / ja-JP）同步补齐。

### 3. 前端：`SkillSelector.vue`（按技能选择）

- 移除脚本二级列表；**点击包名即选中并高亮**；
- 保留 `script-change` 事件名（父组件 `SessionSidebar` → `AssistantPanel` 链路零改动）；
- `SkillSelectInfo` 的 `scriptId` / `scriptName` 置空串；`supportsFileParam` / `isSelected` 等脚本相关逻辑随脚本列表一并移除或简化；
- `AssistantPanel.vue` 提交时 `script_id: ''`、`script_name: ''`（后端不使用）；
- 无脚本技能从此可选、可执行。

### 4. 后端修复：`SkillAgent`（`agent_factory.py`）

```python
skill_name = (
    (self._skill_config or {}).get("name")
    or (self._skill_config or {}).get("package_id")
    or "general"
)
```

- 兼容 `name`（潜在旧调用方）与 `package_id`（当前前端载荷）两种键；
- 定时任务网关路径（`payload["skill"] = pkg_id` 字符串）不受影响。

### 5. 前端：`ScheduledTaskManage.vue`

- `skillScriptId` 必填校验移除；表单中"技能脚本"标注（可选）；
- 提交的 `skill_info` 允许 `script_id` 为空；编辑回填时 `skillScriptId` 可能为空，下拉框允许清空；
- 后端 `_validate_target` 无需改动（本就只查 `package_id`）。

## 数据流（改造后）

```
[管理页] GET /files → 磁盘扫描 → 文件列表 + 类型Tag + 预览弹窗
         scripts 管理仍走 ai_skill_script CRUD

[对话]  SkillSelector 点击包 → skill-change{packageId, scriptId:''}
        → AssistantPanel: session_type=skill, skill={package_id, script_id:''}
        → ai_agent.py config["skill"]
        → SkillAgent: name || package_id → SkillExecutionService.execute(package_id)
        → SKILL.md 全文 prompt + 工具 toolkit → agent 循环（读 references / 跑脚本）
```

## 错误处理

- 文件树：目录缺失 → 空列表；扫描 OSError 逐项跳过并记日志。
- 预览：路径穿越 / 二进制 / 超限 → 400 + 明确 detail；前端弹窗内展示。
- SkillSelector：`getSkills()` 失败沿用现有重试 UI。
- SkillAgent：`package_id` 缺失时维持原 `"general"` 兜底并记 warning。

## 测试要点

1. `GET /files`：buffett（references 8 个 md）、tupian-shipin-shengcheng（5 py）、dyp-ask（空 scripts）三类技能的 type 标记与数量正确；SKILL.md 不出现。
2. `GET /files/content`：正常 md/py 可读；`path=../../config.py` 拒绝；二进制（png）拒绝；>1MB 拒绝。
3. 管理页：脚本行启停/删除仍生效；预览弹窗内容正确。
4. 对话：选择无脚本技能 buffett 发消息 → 会话 session_type=skill，执行不再报"技能不存在：general"，agent 能按 SKILL.md 读取 references 回答。
5. 定时任务：只选技能包不选脚本可保存并触发执行。

## 不做的事（YAGNI）

- 不新建 `ai_skill_file` 表；
- 不做在线编辑/删除/下载任意文件；
- 不改动导出 zip、SKILL.md 编辑、技能仓库安装链路；
- 不改动 ReAct 适配器 / Pipeline 执行路径。
