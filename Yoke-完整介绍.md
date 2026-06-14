# Yoke — 团队 AI 工作流

> Agent 驱动的开发流水线，附带活文档系统
> 状态：MVP 已跑通，小范围试用中

---

## TL;DR

Yoke 是从 0 设计的 AI 自治开发流水线。**核心思路是分工**——把"AI 写代码"拆成 10 个专业化 agent，agent 之间用文件系统通信，做事的和审查的强制分开。目标是让 AI 的错误变得可控、可发现、可修复。适配 Claude Code / Cursor / Codex 三平台，以 plugin 形态分发。

**一句话**：Yoke = 分工 + 文件系统通信 + 做事和审查分开。

---

## 1. 背景：为什么要做 Yoke

裸用 AI 写代码遇到的四个典型问题，Anthropic 在 *Effective harnesses for long-running agents* 里把它们叫 failure modes：

1. **一次性吃太多上下文** — 上下文填充率超过 40% 后 AI 开始幻觉
2. **过早宣布完成** — AI 说"做完了"，编译都不过
3. **跨会话冷启动** — 每次新会话重新理解项目，token 预算被吃光
4. **AI 没法准确评估自己的产出** — Anthropic 反复验证过的硬限制

这四个问题的根源是同一个：**AI 缺少外部化的结构约束和反馈机制**。Yoke 就是给 AI 加一套这样的"工程外骨架"——这就是 Harness Engineering。

> "Every time you discover an agent has made a mistake, you take the time to engineer a solution so that it can never make that mistake again."
> — Mitchell Hashimoto

---

## 2. 设计原则（四条）

| 原则 | 含义 |
|---|---|
| **文件系统即记忆** | Agent 状态全部写在 `docs/` 里，跨会话能完整恢复 |
| **做事和审查分离** | Anthropic 强调的 powerful lever——不能让 AI 自己审自己 |
| **Spec-Driven Development** | 需求 → 合约 → 测试 → 实现，每一步靠机器可读合约衔接 |
| **任务分级自适应** | PATCH / FEATURE / REFACTOR 三档，小改动跳过 spec，新功能走完整 TDD |

---

## 3. 系统架构

```
propose (PM) ──┐
               ├──→ pipeline → architect → qa → coder → audit → update-map → ship
trace   (Dev) ─┘                  │                       │           │
                                guard                   learn ←──── learn
                              (安全护栏)              (经验沉淀，下次召回)
```

两个需求入口（PM 用 `/propose`，Dev 用 `/trace`）共享同一条流水线。`/pipeline` 是编排器，根据任务级别自适应调度后续阶段。

---

## 4. 10 个核心 Agent

| # | Agent | 职责 |
|---|---|---|
| 1 | **propose** | PM 视角需求入口，前提质疑 + 产品语言起草 |
| 2 | **trace** | Dev 视角需求入口，技术影响分析 + 组件级评估 |
| 3 | **architect** | 合约架构师，双产出（spec.md + 可 import 的类型文件） |
| 4 | **qa** | 测试工程师，按 spec 先写测试（TDD RED） |
| 5 | **coder** | 实现工程师，自愈循环 + 测试基线 + 自适应升级 |
| 6 | **audit** | 质量审计员，100 分制 + 置信度评分 + 攻击路径证据链 |
| 7 | **update-map** | 知识沉淀，更新三层活文档 + 双向原子关系更新 |
| 8 | **ship** | 发布工程师，自动 PR/MR + changelog + 审查看板 |
| 9 | **guard** | 安全护栏，编辑范围限制 + 危险命令拦截 |
| 10 | **learn** | 经验复利，JSONL 经验库 + 置信度演化 |

> 此外还有 7 个支撑工具（origin / migrate / digest / explore / post-trace / pipeline / _trace-persist），定位为编排器和文档工具，不算流水线主 agent。

---

## 5. 三层活文档网络

Yoke 把项目知识组织成三层，每层职责明确：

```
docs/product/
├── PRODUCT-MAP.md              ← 决策层（产品疆域、模块索引）
├── modules/{name}/
│   ├── index.md                ← 叙事层（用户旅程、组件索引）
│   └── {ComponentName}.md      ← 规约层（关系/交互/状态机/不变式）
```

| 层 | 职责 | 读者 |
|---|---|---|
| **决策层** | 模块划分、全局导航 | PM / 新人 |
| **叙事层** | 用户旅程、跨组件流程 | PM / QA |
| **规约层** | 单组件的硬约束 | 开发 / Agent |

**关键设计**：组件按复杂度分三级——轻量 / 标准 / 完整。完整级才有不变式、状态机、故障旅程，避免简单组件被过度文档化。

**双向原子关系更新**：组件间是图结构，A 依赖 B 时必须在同一次操作里 A 加 → B、B 加 ← A，禁止孤立链接。

---

## 6. 关键质量机制

### 6.1 docs/ 和代码物理隔离

`architect` 双产出：
- `docs/specs/{ID}.spec.md` — 给人看的合约文档
- 项目源码里的类型文件 — 给代码 import

HARD-GATE：**代码绝不能 import docs/**。这保证了文档区和代码区职责分离，重构互不影响。

### 6.2 自愈循环 + 自适应升级（coder）

- 最多 10 轮
- 连续 2 轮同类错误 → 警告
- 连续 3 轮同类错误 → 强制重读 spec 切换策略
- 连续 5 轮同类错误 → 提前中止进根因分析
- 通过测试数连续 3 轮没增加 → 触发升级

**测试基线机制**：coder 启动前跑一次全量测试记录 `PREEXISTING_FAILURES`，后续循环过滤掉这些不是它造成的失败，避免 agent 替别人擦屁股。

**STUCK 协议**：卡住时不强求自己解决，写一份根因分析报告（症状 / 回溯 / 3 个假设 / 建议）到 `docs/audit/`，体面把决策权交还给人。

### 6.3 100 分制评分 + 置信度（audit）

七维度评分：

| 维度 | 权重 |
|---|---|
| 需求一致性 | 25 |
| 安全性 | 20 |
| OpenSpec 合规 | 15 |
| 代码质量 | 15 |
| 分级合约合规 | 10 |
| 产品文档就绪度 | 10 |
| 治理合规 | 5 |

三档门槛：≥80 通过、60-79 软拒（重新调度 coder 最多 2 次）、<60 硬拒升级到人。

**置信度评分**：每条发现打 1-10 分。8-10 全权重扣，5-7 半权重扣并标"需确认"，1-4 进"待验证"附录不计分。

**攻击路径**：安全类发现必须附"输入来源 → 经过函数 → 到达危险操作"。**构造不出攻击路径的安全发现，置信度自动降到 4 不计分**。这是逼 agent 拿证据不是空喊狼来了。

### 6.4 HARD-GATE 一票否决

三种情况无视总分直接硬拒：
- 完整级组件不变式违反
- 置信度 ≥8 的 OWASP Top 10 漏洞
- AI 内容安全护栏未实施

### 6.5 learn 经验复利

每条 learning 是 JSONL 一行：

```json
{"type":"pitfall","key":"date-field-utc-string","insight":"这个项目的 date 字段是 UTC 字符串不是 Date 对象","confidence":8,"source":"audit/FEAT-a3f7","files":["src/models/"],"date":"2026-03-28"}
```

- audit 和 coder 执行前自动搜索相关 learnings 加入上下文
- 正反馈 +1（learning 帮助发现真实问题）
- 负反馈 -2（learning 引用后发现不再适用）
- 负反馈系数大于正反馈是故意的——**陈旧经验比缺失经验危害更大**

---

## 7. 多平台适配

Yoke 以 plugin 形态分发，适配三平台：

| 平台 | 入口 |
|---|---|
| **Claude Code** | `.claude-plugin/marketplace.json` + plugin install |
| **Cursor** | 克隆 + `.cursor/skills/` 软链 |
| **Codex** | `~/.agents/skills/` 软链 + 重启 |

**共享部分**：17 份 skill markdown 文件、scripts/search.py（CSV 索引 + MAP 生成）。
**平台特定部分**：安装脚本、marketplace 配置。

---

## 8. 已验证 / 待验证

### ✅ 已验证

- 完整流水线在多个真实需求上跑通（自用 + 小范围试用）
- coder 自愈循环累计 300+ 轮稳定运行（无死循环、无烧穿上下文）
- 三平台 plugin 安装路径全部跑通
- 三层活文档双向关系一致性

### ⚠️ 待验证 / 没做过

- **生产规模团队推广** — 当前是设计目标，实际还是小范围
- **AI 代码率量化指标** — 没接入自动采集，凭感觉提升明显但没硬数据
- **端到端浏览器自动化验证** — audit 目前只到静态检查，Anthropic 用 Puppeteer MCP 做 E2E 截图验证 Yoke 没做
- **大型存量代码库冷启动** — `/origin` 在 10w+ 行代码库还没充分实测

**承认这些缺口比硬撑更重要**——这是产品要继续做的方向。

---

## 9. 下一步规划

| 优先级 | 方向 | 参考 |
|---|---|---|
| P0 | 量化指标采集（AI 代码率 / 返工率 / 评审轮次） | 阿里 Harness 实践 |
| P0 | 真实团队小范围推广（先 3-5 人） | — |
| P1 | Entropy GC——后台 agent 自动扫违规并提修复 PR | OpenAI 百万行代码项目 |
| P1 | 端到端浏览器自动化验证集成（Puppeteer MCP） | Anthropic |
| P2 | Harness 自我进化——agent 自动分析失败案例提规范改进 | — |
| P2 | 跨项目 Harness 模板化（可参数化） | — |

---

## 10. 参考资料

- Anthropic. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Anthropic. [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- Anthropic. [2026 Agentic Coding Trends Report](https://resources.anthropic.com/2026-agentic-coding-trends-report)
- OpenAI. [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- Mitchell Hashimoto. *Harness Engineering 定义*

---

## 附录：核心叙事（用于讲解）

### 15 秒版
> Yoke 是我做的 AI 写代码工作流。核心思路是分工——把开发拆成几步，不同的 AI agent 负责不同的事，互相用文件交流。这样 AI 犯错能被另一个 agent 发现。

### 30 秒版
> Yoke 是我做的 AI 自治开发流水线。解决的问题是——一个 AI 干所有事容易出错。它会一次吃太多上下文然后开始幻觉，会写完代码说"完成了"但编译都不过。我的做法是分工——一个 agent 写需求、一个写测试、一个写实现、一个审代码。它们之间用文件交流。最关键的一条是——做事的 agent 和审代码的 agent 必须分开。

### 一句记忆口诀
> **分工 + 文件通信 + 做事和审查分开**
