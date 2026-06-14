# skills 模块

> Yoke 框架核心 — 19 个 SKILL.md,每个是一个 Agent 的指令书。

## 用户旅程

用户在 Claude Code / Cursor / Codex 里跑 `/{skill-name}` → Claude 读取对应 `skills/{name}/SKILL.md` → 按指令执行。

## 组件索引

| 组件 | 分组 | 描述 |
|---|---|---|
| `propose` | Intake | PM 视角需求入口 |
| `trace` | Intake | Dev 视角需求入口 |
| `_trace-persist` | Intake | 内部 — ID 生成 + CSV 索引(由 propose/trace 调用) |
| `pipeline` | Core | 编排器 — 根据复杂度自适应调度 |
| `architect` | Core | 合约设计 — spec.md + 类型契约 |
| `qa` | Core | TDD 测试套件 + API mock |
| `coder` | Core | 自愈循环 + 自适应升级 + STUCK 协议 |
| `audit` | Core | 七维评分 + 置信度 + 攻击路径 |
| `update-map` | Core | MAP / 模块 / 双向关系 + CSV 同步 |
| `ship` | Core | PR/MR + changelog + 审查就绪看板 |
| `post-trace` | Core | 内部 hook(trace 后处理) |
| `guard` | Safety | 编辑范围限制 + 危险命令拦截 |
| `learn` | Safety | JSONL 经验库 + 置信度演化 |
| `anchor` | Safety | **新加 v7.3** — 文档锚定代码 + 内容哈希过时检测(stale/missing) |
| `init` | Docs | **新加 v7.2** — 空目录骨架引导(IMP-01 解法) |
| `origin` | Docs | 引导活文档(代码反推) + 校准 |
| `migrate` | Docs | 文档迁移 + 索引迁移 |
| `digest` | Docs | 归纳碎片 trace + 清理过时 |
| `explore` | Docs | 项目全貌速览 |

## 已知限制

- IMP-02 P0:架构师 / 测试基础设施缺位(scaffold check 未做)
- IMP-05 P1:client/server 边界守门(node:* 进 client bundle 已发生 2 次)
- 部分 skill 还没接入运行时反馈(guard 拦截记录 / digest 归并历史)
