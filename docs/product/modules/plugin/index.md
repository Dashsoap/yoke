# plugin 模块

> Yoke 框架的 3 平台分发配置。

## 组件索引

| 组件 | 描述 |
|---|---|
| `.claude-plugin/` | Claude Code marketplace + plugin 配置 |
| `.cursor-plugin/` | Cursor 平台配置(symlink skills/) |
| `.codex/INSTALL.md` | Codex 平台手动安装指南 |

## 已知限制

- 三平台共享同一份 skills/，通过文件系统约定而非平台 API
