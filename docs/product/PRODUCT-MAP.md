# PRODUCT-MAP — Yoke 框架本身

> 由 `/init` 等价产出 · 2026-05-25 · 用于"用 Yoke 改 Yoke" meta-dogfood

## 项目定位

Yoke 是一个 Agent 驱动的开发流水线 + 活文档系统,以 plugin 形态分发给 Claude Code / Cursor / Codex。
本 PRODUCT-MAP 文档化 **Yoke 框架自身**的结构,让 Yoke 流水线能改造自己(meta-dogfood)。

## 模块索引

| 模块 | 描述 | 状态 |
|---|---|---|
| `skills` | 18 个 SKILL.md (propose/trace/architect/qa/coder/audit/update-map/ship/guard/learn/origin/init/migrate/digest/explore/pipeline/post-trace/_trace-persist) | 主体 |
| `scripts` | search.py — FEAT-ID 生成 / BM25 trace 搜索 | 工具 |
| `plugin` | 3 个分发配置 (.claude-plugin / .cursor-plugin / .codex/) | 配置 |

## Open Issues

- IMP-02 P0(scaffold check)仍未修
- IMP-05 P1(client/server 边界守门 3 件套)未修
- IMP-08 候选:Worker 上下文压缩(qa/coder/audit prompt > 6K 在 alicepan 网关卡死)
- IMPROVEMENTS.md 全量 backlog 见 `docs/IMPROVEMENTS.md`
