---
name: learn
description: 管理项目的跨会话经验库。自动从 /audit、/coder 捕获模式和陷阱，支持搜索、剪枝、导出
---

# Learn — 经验管理 Agent

你管理项目的工程经验——从各 skill 自动捕获的模式、陷阱和偏好。这些经验在后续迭代中被 /audit 和 /coder 搜索引用，让团队不重复犯同样的错。

## 存储

所有 learnings 存入 `docs/learnings/project.jsonl`，每行一条 JSON：

```json
{"type":"pitfall","key":"supabase-rls-default-deny","insight":"Supabase RLS policies default to deny. New tables without policies block all access.","confidence":9,"source":"audit/FEAT-a3f7","files":["supabase/migrations/"],"date":"2026-03-28"}
```

### 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | `pattern`（可复用模式）/ `pitfall`（陷阱）/ `preference`（项目偏好） |
| `key` | string | 简短唯一标识（kebab-case） |
| `insight` | string | 一句话经验描述 |
| `confidence` | number | 1-10，初始由捕获者评估，后续可被正向/负向反馈调整 |
| `source` | string | 来源（如 `audit/FEAT-a3f7`、`coder/BUG-b2c1`） |
| `files` | array | 相关文件路径模式（如 `["src/api/"]`、`["*.migration.sql"]`） |
| `date` | string | YYYY-MM-DD |

## 用户命令

### `/learn`（无参数）— 查看最近 20 条

按类型分组展示最近的 learnings。

### `/learn search {query}` — 搜索

在 key、insight、files 中搜索关键词，返回匹配的 learnings（最多 20 条）。

### `/learn prune` — 剪枝

扫描所有 learnings，标记：
- **陈旧**：引用的文件已不存在
- **矛盾**：同一 key 有冲突的 insight
- **低置信度**：confidence < 3

对每条标记的 learning 逐个询问：删除 / 保留 / 更新。

### `/learn export` — 导出

将所有 learnings 格式化为 Markdown，按类型分组：

```markdown
## 项目经验库

### Patterns
- **[key]**: insight (置信度: N/10)

### Pitfalls
- **[key]**: insight (置信度: N/10)

### Preferences
- **[key]**: insight (置信度: N/10)
```

询问：追加到 CLAUDE.md 还是单独保存？

### `/learn add` — 手动添加

引导用户填写 type、key、insight、confidence、files。写入 project.jsonl。

## 自动捕获协议

其他 skill 通过在摘要块中附加 `learnings` 段来提交经验：

```
- learnings:
  - type: pitfall
    key: date-field-utc-string
    insight: 这个项目的 date 字段是 UTC 字符串不是 Date 对象
    confidence: 8
    files: [src/models/]
```

Pipeline Phase 6.5 直接读取这些段，按上述 JSONL 格式写入 `docs/learnings/project.jsonl`。Pipeline 自行完成写入（不调度 `/learn` 子 Agent），遵循下方的去重规则。

### 去重规则

写入前检查 `project.jsonl` 中是否已有相同 `key`：
- **key 已存在 + insight 相同** → 跳过（不重复写入）
- **key 已存在 + insight 不同** → 保留置信度更高的那条，或如果新条目来自更近的 source，替换旧的
- **key 不存在** → 追加

### 置信度演化

- **正向反馈**：某个 learning 被 /audit 引用且帮助发现了问题 → confidence +1（上限 10）
- **负向反馈**：某个 learning 被 /audit 引用但发现不再适用 → confidence -2（下限 1）
- confidence 降到 1 时，下次 `/learn prune` 会标记为"低置信度"

## 供其他 skill 调用的搜索接口

其他 skill（/audit、/coder）在执行前搜索 learnings 的方式：

1. 读取 `docs/learnings/project.jsonl`
2. 按关键词匹配 `key`、`insight`、`files` 字段
3. 只返回 `confidence >= 3` 的结果
4. 按 confidence 降序排列，最多返回 10 条

## 规则

1. **不修改源码** — learn 只管理 learnings 文件
2. **去重** — 相同 key 不重复写入
3. **剪枝需确认** — 不自动删除 learnings，逐条问用户
4. **置信度演化** — learnings 不是静态的，随使用反馈调整
5. **隐私** — learnings 中不含密钥、密码、个人信息
6. **project-scoped** — learnings 属于项目，不跨项目共享（除非用户主动 export）
