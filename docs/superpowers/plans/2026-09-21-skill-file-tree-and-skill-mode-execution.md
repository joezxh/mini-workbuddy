# Skill 文件树展示与按技能执行 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:executing-plans 逐任务实施，checkbox（`- [ ]`）跟踪进度。

**Goal:** 管理页可查看技能包内全部文件（含 references/），对话侧与定时任务侧改为「按整技能」选择与执行，并修复前端 `skill` 载荷与 `SkillAgent` 键名不匹配导致的 "技能不存在：general"。

**Architecture:** 后端不建表，直接扫描 `SKILLS_BASE_DIR/<package_id>/` 作为唯一事实源（只读 + 文本预览）；执行链路（`SkillExecutionService.execute`）本就以整技能为执行单位，故前端只需把「选脚本」降级为「选包」，并把 `skill` 载荷统一为 `package_id` 标识；`SkillAgent` 兼容 `name` / `package_id` 两种键。

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy；Vue3 + TypeScript + Ant Design Vue + vue-i18n。

**Spec:** `docs/superpowers/specs/2026-09-21-skill-file-tree-and-skill-mode-execution-design.md`

**命令约定**（Windows PowerShell）：
- 后端测试：`cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit/test_ai_skill_files.py -v`
- 前端类型检查：`cd d:\projects\MinWorkBuddy\frontend; npx vue-tsc --noEmit`
- 前端 lint：`cd d:\projects\MinWorkBuddy\frontend; npm run lint`

**已验证的关键事实**（实施时直接引用，勿凭记忆改写）：
- 技能路由前缀：`app.routers.ai.ai_skill` 挂载于 `/api/v1/ai-assistant/skills`（`backend/app/core/router_registry.py`）。
- `AiSkillAdminService.SKILLS_BASE_DIR = settings.resolved_skills_base_dir`，为 `Path`（`backend/app/services/ai/ai_skill_admin_service.py:24`）。
- `SkillAgent.__init__` 收 `skill_config`；`reply_stream` 内 `skill_name = (self._skill_config or {}).get("name", "general")`（`backend/app/ai/agent_factory.py:56`）→ 与前端 `{package_id, script_id}` 载荷键不匹配。
- 前端载荷：`AssistantPanel.vue` 提交 `skill: {package_id, package_name, script_id, script_name, params}`（`frontend/src/views/assistant/components/AssistantPanel.vue:935`）。
- `SkillSelector` 事件链：`SkillSelector` `script-change` → `SessionSidebar` `skill-change` → `AssistantPanel.handleSkillScriptChange`（事件名保持不变，链路零改动）。
- 定时任务校验只查 `package_id`：`_validate_target`（`backend/app/services/agent/agent_scheduled_task_service.py:98-101`）；执行 payload 用 `payload["skill"] = pkg_id`（同文件 `_build_payload`）。
- 现有 `scripts` 管理事实源为 `ai_skill_script` 表，接口 `/ai-assistant/skills/{package_id}/scripts` 不变。

---

## Task 1: 后端 — 技能文件树扫描与文本预览服务

**Files:**
- Modify: `backend/app/services/ai/ai_skill_admin_service.py`
- Test: `backend/tests/unit/test_ai_skill_files.py`

**接口契约（服务层）：**
- `list_files(package_id) -> {package_id, files: [{path, size, ext, type}], total_count, total_size}`
  - 递归扫描 `SKILLS_BASE_DIR/<package_id>/`，跳过目录与文件名 `SKILL.md`；
  - 路径以 POSIX 相对路径输出（`scripts/x.py`、`references/y.md`）；
  - `type`：首段为 `scripts` 且扩展名 `.py` → `script`；首段为 `references` → `reference`；其余 → `other`；
  - 目录不存在 → 空列表；单个文件 `OSError` → 跳过并 `logger.warning`；
  - 结果按 `path` 升序。
- `read_file_content(package_id, rel_path) -> {path, size, content}`
  - `resolve()` 后必须位于 `SKILLS_BASE_DIR/<package_id>/` 内，否则 `ValueError`；
  - 文本扩展名白名单 `.md .txt .py .json .yaml .yml .toml .csv .sh .bat .cfg .ini`；
  - 单文件上限 1MB（`MAX_PREVIEW_BYTES = 1024 * 1024`）；
  - `b"\x00"` 检测为二进制 → `ValueError`；非 UTF-8 → `ValueError`；
  - 文件不存在 / 非普通文件 → `ValueError`。

- [x] **Step 1: 写失败测试**

```python
"""技能文件树扫描与安全预览单测。"""
from pathlib import Path

import pytest

from app.services.ai.ai_skill_admin_service import AiSkillAdminService


@pytest.fixture()
def svc(tmp_path: Path) -> AiSkillAdminService:
    s = AiSkillAdminService()
    s.SKILLS_BASE_DIR = tmp_path
    return s


def _build_pkg(tmp_path: Path, package_id: str = "demo") -> Path:
    pkg = tmp_path / package_id
    (pkg / "scripts").mkdir(parents=True)
    (pkg / "references").mkdir(parents=True)
    (pkg / "assets").mkdir(parents=True)
    (pkg / "SKILL.md").write_text("# demo", encoding="utf-8")
    (pkg / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
    (pkg / "references" / "guide.md").write_text("hello", encoding="utf-8")
    (pkg / "assets" / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    (pkg / "notes.txt").write_text("note", encoding="utf-8")
    return pkg


def test_list_files_types_and_excludes_skill_md(svc, tmp_path):
    _build_pkg(tmp_path)
    res = svc.list_files("demo")
    paths = [f["path"] for f in res["files"]]
    assert "SKILL.md" not in paths
    types = {f["path"]: f["type"] for f in res["files"]}
    assert types["scripts/run.py"] == "script"
    assert types["references/guide.md"] == "reference"
    assert types["notes.txt"] == "other"
    assert types["assets/logo.png"] == "other"
    assert res["total_count"] == len(res["files"])
    assert res["total_size"] == sum(f["size"] for f in res["files"])
    assert paths == sorted(paths)


def test_list_files_missing_dir_returns_empty(svc):
    res = svc.list_files("nope")
    assert res["files"] == []
    assert res["total_count"] == 0
    assert res["total_size"] == 0


def test_read_file_content_ok(svc, tmp_path):
    _build_pkg(tmp_path)
    res = svc.read_file_content("demo", "references/guide.md")
    assert res["content"] == "hello"
    assert res["size"] == 5


@pytest.mark.parametrize("bad", ["../SKILL.md", "../../x.py", "/etc/hosts", "..\\SKILL.md"])
def test_read_file_content_rejects_traversal(svc, tmp_path, bad):
    _build_pkg(tmp_path)
    with pytest.raises(ValueError):
        svc.read_file_content("demo", bad)


def test_read_file_content_rejects_binary_and_oversize(svc, tmp_path):
    _build_pkg(tmp_path)
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "assets/logo.png")
    big = tmp_path / "demo" / "big.txt"
    big.write_bytes(b"a" * (1024 * 1024 + 1))
    with pytest.raises(ValueError):
        svc.read_file_content("demo", "big.txt")
```

- [x] **Step 2: 运行测试确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit/test_ai_skill_files.py -v`
Expected: FAIL（`AttributeError: 'AiSkillAdminService' object has no attribute 'list_files'`）

- [x] **Step 3: 实现服务方法**

在 `AiSkillAdminService` 的「辅助」区块前新增：

```python
    # ── 文件树（只读扫描，不建表）────────────────────────────────────

    MAX_PREVIEW_BYTES = 1024 * 1024
    TEXT_EXTENSIONS = {
        ".md", ".txt", ".py", ".json", ".yaml", ".yml",
        ".toml", ".csv", ".sh", ".bat", ".cfg", ".ini",
    }

    @classmethod
    def _classify_file(cls, rel_parts: tuple, ext: str) -> str:
        head = rel_parts[0] if rel_parts else ""
        if head == "scripts" and ext == ".py":
            return "script"
        if head == "references":
            return "reference"
        return "other"

    def list_files(self, package_id: str) -> Dict[str, Any]:
        """扫描技能包目录，返回全部文件的相对路径/大小/类型（不建表）。"""
        pkg_dir = self.SKILLS_BASE_DIR / package_id
        files: List[Dict[str, Any]] = []
        if not pkg_dir.is_dir():
            return {"package_id": package_id, "files": files, "total_count": 0, "total_size": 0}

        def _on_error(err: OSError) -> None:
            logger.warning("技能文件扫描失败(%s): %s", package_id, err)

        for root, _dirs, names in os.walk(pkg_dir, onerror=_on_error):
            for fname in names:
                if fname == "SKILL.md":
                    continue
                abs_path = Path(root) / fname
                rel_parts = abs_path.relative_to(pkg_dir).parts
                ext = abs_path.suffix.lower()
                try:
                    size = abs_path.stat().st_size
                except OSError as e:
                    logger.warning("技能文件跳过(%s): %s", abs_path, e)
                    continue
                files.append({
                    "path": "/".join(rel_parts),
                    "size": size,
                    "ext": ext.lstrip("."),
                    "type": self._classify_file(rel_parts, ext),
                })

        files.sort(key=lambda f: f["path"])
        return {
            "package_id": package_id,
            "files": files,
            "total_count": len(files),
            "total_size": sum(f["size"] for f in files),
        }

    def read_file_content(self, package_id: str, rel_path: str) -> Dict[str, Any]:
        """读取技能包内单个文本文件（路径穿越/二进制/超限拒绝）。"""
        base = (self.SKILLS_BASE_DIR / package_id).resolve()
        target = (base / rel_path).resolve()
        if target != base and base not in target.parents:
            raise ValueError("非法的文件路径")
        if not target.is_file():
            raise ValueError("文件不存在")
        if target.suffix.lower() not in self.TEXT_EXTENSIONS:
            raise ValueError("该文件类型不支持预览")
        size = target.stat().st_size
        if size > self.MAX_PREVIEW_BYTES:
            raise ValueError("文件超过 1MB 上限，无法预览")
        try:
            raw = target.read_bytes()
        except OSError as e:
            raise ValueError(f"文件读取失败: {e}")
        if b"\x00" in raw:
            raise ValueError("二进制文件无法预览")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("非 UTF-8 文本，无法预览")
        return {"path": "/".join(target.relative_to(base).parts), "size": size, "content": content}
```

- [x] **Step 4: 运行测试确认通过**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit/test_ai_skill_files.py -v`
Expected: PASS（全部用例）

---

## Task 2: 后端 — 文件树 HTTP 端点

**Files:**
- Modify: `backend/app/routers/ai/ai_skill.py`

- [x] **Step 1: 新增两个 GET 端点**（挂在 SKILL.md 文档端点区块之前）

```python
@router.get("/{package_id}/files")
def list_skill_files(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出技能包内全部文件（磁盘扫描，SKILL.md 除外）。"""
    svc = AiSkillAdminService()
    if not svc.get_package(db, package_id):
        raise HTTPException(status_code=404, detail="技能包不存在")
    return svc.list_files(package_id)


@router.get("/{package_id}/files/content")
def get_skill_file_content(
    package_id: str,
    path: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """预览技能包内文本文件（越界/二进制/超限 → 400）。"""
    svc = AiSkillAdminService()
    if not svc.get_package(db, package_id):
        raise HTTPException(status_code=404, detail="技能包不存在")
    try:
        return svc.read_file_content(package_id, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [x] **Step 2: 校验路由注册无冲突**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -c "from app.main import app; print([r.path for r in app.routes if 'files' in getattr(r,'path','')])"`
Expected: 输出包含 `/api/v1/ai-assistant/skills/{package_id}/files` 与 `.../files/content`

---

## Task 3: 后端 — `SkillAgent` 技能标识解析修复

**Files:**
- Modify: `backend/app/ai/agent_factory.py`
- Test: `backend/tests/unit/test_ai_skill_files.py`（同一测试文件追加用例）

- [x] **Step 1: 追加失败测试**

```python
from app.ai.agent_factory import resolve_skill_name


def test_resolve_skill_name_prefers_name_then_package_id():
    assert resolve_skill_name({"name": "a", "package_id": "b"}) == "a"
    assert resolve_skill_name({"package_id": "buffett"}) == "buffett"
    assert resolve_skill_name({}) == "general"
    assert resolve_skill_name(None) == "general"
```

- [x] **Step 2: 运行确认失败**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit/test_ai_skill_files.py -v -k resolve_skill_name`
Expected: FAIL（ImportError）

- [x] **Step 3: 实现**

在 `agent_factory.py` 顶部加 `from loguru import logger`，并新增模块级函数：

```python
def resolve_skill_name(skill_config: Optional[dict]) -> str:
    """解析技能标识：兼容 name（旧调用方）与 package_id（当前前端载荷）。"""
    cfg = skill_config or {}
    name = cfg.get("name") or cfg.get("package_id")
    if not name:
        logger.warning("SkillAgent 未收到 skill 标识（name/package_id），回退 general")
        return "general"
    return str(name)
```

`SkillAgent.reply_stream` 中改为 `skill_name = resolve_skill_name(self._skill_config)`。

- [x] **Step 4: 运行测试**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit/test_ai_skill_files.py -v`
Expected: PASS

---

## Task 4: 前端 — 技能文件 API

**Files:**
- Modify: `frontend/src/api/skill.ts`

- [x] **Step 1: 新增类型与函数**

```ts
export type SkillFileType = 'script' | 'reference' | 'other'

export interface SkillFileItem {
  path: string
  size: number
  ext: string
  type: SkillFileType
}

export interface SkillFileListResp {
  package_id: string
  files: SkillFileItem[]
  total_count: number
  total_size: number
}

export function getSkillFiles(packageId: string): Promise<SkillFileListResp> {
  return request.get(`${BASE_URL}/ai-assistant/skills/${packageId}/files`)
}

export function getSkillFileContent(
  packageId: string,
  path: string,
): Promise<{ path: string; size: number; content: string }> {
  return request.get(`${BASE_URL}/ai-assistant/skills/${packageId}/files/content`, { params: { path } })
}
```

---

## Task 5: 前端 — `SkillManagement.vue` 文件列表 + 预览弹窗

**Files:**
- Modify: `frontend/src/views/admin/ai/skill/SkillManagement.vue`

- [x] **Step 1: 「脚本列表」区块替换为「文件列表」**

- 详情 Tab 中 `a-divider{{ t('skillHub.scriptList') }}` → `{{ t('skillHub.fileList') }}`，并在其后展示 `t('skillHub.fileCount', { count: files.length })`；
- 文件行：相对路径 + 人性化大小（`formatSize`）+ 类型 Tag（`script`→`t('skillHub.fileTypeScript')`，`reference`→`t('skillHub.fileTypeReference')`，其他→`t('skillHub.fileTypeOther')`）；
- 点击行 → `openFilePreview(file)`；`type==='script'` 且能按 `path` 的 stem 匹配到 `selected.scripts` 中的条目时，保留原有 启用开关 / 编辑 / 删除 按钮（`toggleScriptEnabled`、`openScriptForm`、`handleDeleteScript` 复用现有函数，数据仍来自 `ai_skill_script`）；匹配不到的脚本文件显示为只读行；
- 空列表提示改为 `t('skillHub.noFiles')`；「新增脚本」按钮保留。

- [x] **Step 2: 预览弹窗**

```vue
<a-modal
  v-model:open="previewVisible"
  :title="previewPath"
  width="820px"
  :footer="null"
>
  <a-spin :spinning="previewLoading">
    <a-alert v-if="previewError" type="error" show-icon :message="previewError" />
    <pre v-else class="file-preview-pre">{{ previewContent }}</pre>
  </a-spin>
</a-modal>
```

- [x] **Step 3: 脚本与文件数据联动**

- `watch(() => selected.value?.package_id, ...)` 内并行 `loadFiles()`；
- `loadFiles()` 调 `getSkillFiles(package_id)`，失败 `message.error(t('skillHub.loadFilesFailed') + detail)`，置 `files = []`；
- `reloadSelected()` / `handleDeleteScript` / `SkillScriptForm` `@success` 后同时刷新 `loadFiles()`；
- 打开「脚本」相关函数不新增 API，保持 `apiDeleteScript` / `updateScript`。

- [x] **Step 4: 样式**：新增 `.file-item` / `.file-preview-pre` 等（复用现有 `--bg-surface` / `--border` 变量），不改动既有区块样式。

---

## Task 6: 前端 — `SkillSelector.vue` 按技能选择

**Files:**
- Modify: `frontend/src/views/assistant/components/SkillSelector.vue`

- [x] **Step 1: 移除脚本二级列表**

- 删除包内 `.script-list` 渲染与 `.package-empty` 提示；
- 包行改为可点击选中：`<div class="package-item" :class="{ selected: isPackageSelected(pkg.package_id) }" @click="selectPackage(pkg)">`，含图标 + 名称；
- 选中态显示在头部 badge：`{{ selectedSkill?.packageName }}` + `clearSelection` 按钮。

- [x] **Step 2: 选中逻辑**

```ts
function selectPackage(pkg: SkillPackage) {
  const info: SkillSelectInfo = {
    packageId: pkg.package_id,
    packageName: pkg.name,
    packageIcon: pkg.icon || 'tool',
    scriptId: '',
    scriptName: '',
    scriptDescription: pkg.description || '',
  }
  selectedSkill.value = info
  emit('script-change', info)
}
function isPackageSelected(packageId: string) {
  return selectedSkill.value?.packageId === packageId
}
```

- 删除 `supportsFileParam` / `FILE_PARAM_NAMES` / `isSelected` / `SkillScript` 导入；`fileId` / `fileName` props 与文件提示条保留（已不再有 `file-badge`）。

---

## Task 7: 前端 — `AssistantPanel.vue` / `ChatInput.vue` 空脚本字段适配

**Files:**
- Modify: `frontend/src/views/assistant/components/AssistantPanel.vue`
- Modify: `frontend/src/views/assistant/components/ChatInput.vue`

- [x] **Step 1: 提交载荷置空脚本字段**

`AssistantPanel.vue` 的 `skill` 载荷改为：

```ts
skill: currentSkill.value ? {
  package_id: currentSkill.value.packageId, package_name: currentSkill.value.packageName,
  script_id: '', script_name: '',
  params: currentSkill.value.params || {},
} : null,
```

- [x] **Step 2: `ChatInput.vue` 徽标回退包名**

`skill.scriptName` 为空时显示 `skill.packageName`（tooltip 回退 `scriptDescription`）。

---

## Task 8: 前端 — `ScheduledTaskManage.vue` 脚本改为可选

**Files:**
- Modify: `frontend/src/views/assistant/ScheduledTaskManage.vue`

- [x] **Step 1: 放开必填**

- 表单 item label：`技能脚本` → `技能脚本（可选）`，移除 `required`；
- `onSave` 删除 `if (form.targetMode === 'skill' && !form.skillScriptId) { ... }` 校验；
- `skillInfo` 构造条件由「包 + 脚本都存在」改为「包存在」，`script_id` / `script_name` 允许为空串/undefined；
- 脚本 `a-select` 加 `allow-clear`，placeholder 为「可不选脚本，按整技能执行」。

---

## Task 9: i18n 四语言补文案

**Files:**
- Modify: `frontend/src/i18n/locales/{zh-CN,zh-TW,en-US,ja-JP}.ts`

- [x] **Step 1: 在 `skillHub` 段 `newScript` 后新增键**

| key | zh-CN | zh-TW | en-US | ja-JP |
|---|---|---|---|---|
| `fileList` | 文件列表 | 檔案列表 | File List | ファイル一覧 |
| `noFiles` | 该技能包暂无文件 | 此技能包暫無檔案 | No files in this package | このパッケージにファイルはありません |
| `fileCount` | 共 {count} 个文件 | 共 {count} 個檔案 | {count} file(s) | 全 {count} ファイル |
| `fileTypeScript` | 脚本 | 指令碼 | Script | スクリプト |
| `fileTypeReference` | 参考 | 參考 | Reference | リファレンス |
| `fileTypeOther` | 其他 | 其他 | Other | その他 |
| `previewLoading` | 加载中... | 載入中... | Loading... | 読み込み中... |
| `loadFilesFailed` | 加载文件列表失败： | 載入檔案列表失敗： | Failed to load files: | ファイル一覧の取得に失敗： |

（脚本标签兼容说明：`skillHub.scriptList` / `noScripts` 保留，避免其他引用失效。）

---

## Task 10: 验证

- [x] **Step 1: 后端测试全绿**

Run: `cd d:\projects\MinWorkBuddy\backend; .venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: 全部通过（含新增 `test_ai_skill_files.py`）

- [x] **Step 2: 前端类型检查**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx vue-tsc --noEmit`
Expected: 与改动前基线相比不新增错误

- [x] **Step 3: 前端 lint 改动文件**

Run: `cd d:\projects\MinWorkBuddy\frontend; npx eslint src/api/skill.ts src/views/admin/ai/skill/SkillManagement.vue src/views/assistant/components/SkillSelector.vue src/views/assistant/components/AssistantPanel.vue src/views/assistant/components/ChatInput.vue src/views/assistant/ScheduledTaskManage.vue`
Expected: 无 error

- [ ] **Step 4: 手工验收清单**（需运行环境，记录结论）
  1. buffett / tupian-shipin-shengcheng / dyp-ask 三类技能文件树数量与 type 标记正确，SKILL.md 不出现；
  2. 预览：正常 md/py 可读；二进制与超限返回 400 且弹窗展示 detail；
  3. 脚本行启停/删除仍生效；
  4. 对话选择无脚本技能（buffett）发消息 → 不再出现「技能不存在：general」；
  5. 定时任务只选技能包即可保存。

---

## 执行记录（2026-09-21）

已完成的验证：
- `pytest tests/unit -q` → **92 passed**（含新增 `tests/unit/test_ai_skill_files.py` 17 项）。
- `npx vue-tsc --noEmit` → 改动文件（`SkillManagement.vue` / `SkillSelector.vue` / `ScheduledTaskManage.vue` / `AssistantPanel.vue` / `ChatInput.vue` / `api/skill.ts`）**无新增错误**；仅剩仓库既有 TS6133（`SkillHubBrowser.vue` activeRepo、`AssistantPanel.vue` userTabSelected、`SkillExecutionPanel.vue` stepEvents）。
- 路由注册校验：`GET /api/v1/ai-assistant/skills/{package_id}/files` 与 `.../files/content` 已挂载。
- 真实磁盘数据校验（`backend/data/skills`）：
  - `buffett` → 8 个 `reference`（与 spec 一致），SKILL.md 未出现；
  - `arbor` → 1 个 `script`（scripts/tree.py）+ 4 个 `reference`，合计 5 个文件；
  - `references/01-thinking-frameworks.md` 预览成功（9751 字符）；
  - `../SKILL.md` / `/etc/hosts` / `scripts/../../SKILL.md` 一律 `非法的文件路径` 拒绝。
  - 说明：spec 中提到的 `tupian-shipin-shengcheng`、`dyp-ask` 在本机 `backend/data/skills` 下不存在（属 spec 作者环境），已用同类真实技能包替代验证。
- 未执行（需完整运行环境 + DB + 登录态）：HTTP 层 400 行为、管理页交互、对话端「无脚本技能可执行」、定时任务保存。ESLint 未执行：本仓库无 eslint 配置文件（`npm run lint` 在改动前即不可用）。

---

## 不做的事（与 spec 一致）

- 不新建 `ai_skill_file` 表；不做在线编辑/删除/下载任意文件；
- 不改动导出 zip、SKILL.md 编辑、技能仓库安装链路；
- 不改动 ReAct 适配器 / Pipeline 执行路径。
