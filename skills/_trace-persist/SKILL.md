---
name: _trace-persist
description: 内部 skill，不可直接调用。需求持久化底层引擎，由 /propose 和 /trace 调用。负责模块定位、ID 生成、文件写入、CSV 索引更新和收尾确认
---

# _trace-persist — 需求持久化引擎

你是需求持久化的底层工具。你不做任何分析、不问任何问题、不生成任何内容。你只执行上游 skill（`/propose` 或 `/trace`）传入的指令。

<HARD-GATE>
此 skill 不可直接由用户调用。它只接受来自 `/propose` 或 `/trace` 的调度。
如果用户直接运行 `/_trace-persist`，提示："请使用 `/propose`（产品需求）或 `/trace`（技术需求）提交需求。"
</HARD-GATE>

## 输入

上游 skill 调用时必须提供：

| 参数 | 说明 |
|------|------|
| `mode` | `pm` 或 `dev` — 标记需求来源角色 |
| `type` | `FEAT` / `BUG` / `REFACTOR` / `PATCH` |
| `title` | 需求标题（用于 ID 生成） |
| `module` | 受影响的产品模块名（从 PRODUCT-MAP 定位） |
| `component` | 受影响的组件名（可选，`/propose` 不传，`/trace` 传） |
| `content` | 完整的 Markdown 需求文档正文（由上游 skill 已起草完成） |

## 执行步骤

### Step 1：模块定位验证

读 `docs/product/PRODUCT-MAP.md`，验证上游传入的 `module` 在模块索引表中存在。

- 若存在：继续
- 若不存在：返回错误给上游，附上当前模块列表供修正
- 若 PRODUCT-MAP.md 不存在：降级检查 `docs/MAP.md`。如也不存在，返回错误建议运行 `/origin`

### Step 2：生成 FEAT-ID

```bash
python3 {ray_plugin_path}/scripts/search.py --generate-id --type {type} --title "{title}" --date {当天日期，YYYY-MM-DD 格式}
```

输出格式：`{TYPE}-{4hex}-{slug}`（例：`FEAT-a3f7-realtime-price`）。

### Step 3：计算 Baseline 哈希

解析 `content` 中的 `## Baseline` 章节，找到 Markdown 表格中列出的文件路径。对每个文件：
- 读取文件内容，计算 SHA256，取前 8 位十六进制字符
- 替换表格中对应行的占位符（如 `{由 /_trace-persist 填充}`）为实际哈希值
- 如文件不存在，填 `N/A`

### Step 4：写入 trace 文件

1. 若 `docs/traces/index.csv` 不存在，先初始化：
   ```bash
   python3 {ray_plugin_path}/scripts/search.py --init --project-dir {project_root}
   ```

2. 将 `content` 写入 `docs/traces/{FEAT-ID}.md`。
   - 文档为纯 Markdown，**不含 YAML frontmatter**
   - 在文档头部插入 `> mode: {mode}`，标记来源角色

3. 向 `docs/traces/index.csv` 追加一行：
   ```
   id,type,phase,module,component,title,keywords,status,author,date,file,depends_on,depended_by
   ```
   - `component`：填入上游传入的 `component`，未传则留空（由 `/pipeline` Phase 0 补充）
   - `author`：`mode=pm` 时填 `pm`，`mode=dev` 时填 `dev`
   - `status`：`confirmed`
   - `phase`：`trace`
   - `depends_on` / `depended_by`：初始留空，由 `/pipeline` 或 `/update-map` 后续填充

### Step 5：收尾确认

向用户展示：

```
需求已确认，注册为 {FEAT-ID}。

请选择执行方式：
  A) 在 worktree 中执行（推荐）— 创建隔离分支，不影响当前工作区
  B) 在当前工作区执行 — 直接在当前分支开发

选择 A 或 B？
```

若用户选 A：提示运行 `/pipeline --worktree`
若用户选 B：提示运行 `/pipeline`

## 规则

1. **不做分析** — 不读组件文件，不判断影响范围
2. **不问问题** — 不向用户澄清需求内容
3. **不生成内容** — 不写场景、不写验收标准
4. **只做持久化** — 定位、编号、写文件、更新索引
5. **幂等** — 相同输入 + 相同日期产生相同 FEAT-ID（日期参与哈希）。重复调用不会创建重复文件
