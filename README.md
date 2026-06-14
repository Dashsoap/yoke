# Yoke

Agent 驱动的开发流水线，内置活文档系统。

## 工作原理

需求进，生产级代码 + 活文档出。产品经理用 `/propose`，开发者用 `/trace`，两个入口共享同一条流水线。

```
propose (PM) ──┐
               ├──→ _trace-persist → pipeline → architect → qa + coder → audit → update-map → ship
trace   (Dev) ─┘                        │                      │           │
                                      guard                  learn ←─── learn
                                    (保护编辑范围)           (捕获经验，供后续迭代搜索)
```

确认后 `/pipeline` 会根据复杂度自动调度后续阶段：生成类型合约、编写测试、实现代码、质量审计、更新文档、创建 PR——全程自治。

## 安装

### Claude Code

```bash
# 1. 添加 marketplace（在终端中执行）
claude plugin marketplace add https://github.com/<your-org>/yoke.git

# 2. 安装（全局，所有项目可用）
claude plugin install yoke

# 或仅为当前项目安装
claude plugin install yoke --scope project
```

安装后重启 Claude Code 会话生效。

### Cursor

```bash
# 1. 克隆仓库
git clone https://github.com/<your-org>/yoke.git ~/.cursor/yoke

# 2. 复制 skills 到项目
mkdir -p .cursor/skills
cp -r ~/.cursor/yoke/skills .cursor/skills/yoke
```

### Codex

```bash
# 1. 克隆仓库
git clone https://github.com/<your-org>/yoke.git ~/.codex/yoke

# 2. 创建 skills 符号链接
mkdir -p ~/.agents/skills
ln -s ~/.codex/yoke/skills ~/.agents/skills/yoke

# 3. 重启 Codex
```

## Skills

### Intake — 需求入口

| Skill | 使用者 | 职责 |
|-------|--------|------|
| `/propose` | 产品经理 | 前提质疑 + 产品语言需求描述，输出含替代方案的产品简报 |
| `/trace` | 开发者 | 技术影响分析、组件级评估、治理合规双源、完整 trace |
| `_trace-persist` | 内部 | 持久化引擎（ID 生成、文件写入、CSV 索引），由 propose/trace 调用 |

### Core — 开发流水线

| Skill | 触发时机 | 职责 |
|-------|---------|------|
| `/pipeline` | trace 确认后 | 根据复杂度自适应调度后续阶段 |
| `/architect` | pipeline 调度 | OpenSpec 类型合约、不变式、FSM、故障旅程 |
| `/qa` | 合约就绪 | TDD 测试套件 + API mock，先于实现 |
| `/coder` | 测试 RED | 自愈循环 + 测试基线 + 自适应升级 + 根因分析 |
| `/audit` | 测试通过 | 置信度评分 + 证据链审计，不变式违反 = 一票否决 |
| `/update-map` | 审计通过 | 更新 MAP.md、需求追溯、产品手册、技术债 |
| `/ship` | update-map 后 | 创建 PR/MR、生成 changelog、审查就绪看板 |

### Safety — 安全与经验

| Skill | 职责 |
|-------|------|
| `/guard` | 编辑范围限制 + 危险命令拦截，pipeline worktree 模式自动激活 |
| `/learn` | 跨会话经验捕获（模式/陷阱/偏好），/audit 和 /coder 自动贡献 |

### Docs — 文档管理

| Skill | 职责 |
|-------|------|
| `/init` | **新项目骨架引导**（空目录跑 origin 会失败 → 用 init,问 2 个问题、写最小 PRODUCT-MAP + 5 CSV） |
| `/origin` | 引导活文档系统（Genesis）、校准现有文档（Reconcile） |
| `/migrate` | 产品文档迁移（--docs）、索引迁移（--index） |
| `/digest` | 归纳碎片 trace 进产品模块文件，清理过时、合并重复 |
| `/explore` | 快速了解项目全貌、架构和功能模块 |

## 快速开始

```bash
# 产品经理提需求
/propose 用户希望在首页看到实时通知

# 开发者提需求（含技术分析）
/trace 用户希望在首页看到实时通知

# 确认需求后，启动流水线
/pipeline

# 流水线完成后，创建 PR
/ship

# 查看项目经验库
/learn

# 或者只想了解项目
/explore
```

## 更新

```bash
# Claude Code
claude plugin update yoke

# Codex
cd ~/.codex/yoke && git pull
```
