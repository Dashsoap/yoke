> **语言**: [English](README.md) · **中文**

# Yoke

**会自己说自己过时的 AI 开发流水线。**

Yoke 把开发拆成一组专业化 agent，做事和审查强制分开，内置三层活文档系统。它最关键的一点：文档锚定在真实代码上——代码一改，过时的文档会自己标红，不靠人记得去看。100% 本地，零依赖。

[落地页](https://dashsoap.github.io/yoke/) · [GitHub](https://github.com/Dashsoap/yoke) · 三端：Claude Code · Cursor · Codex

---

## 30 秒看懂杀手锏：改代码 → 文档标红

活文档最大的问题不是写得不好，而是写完之后悄悄过时——你不知道哪句话已经失效。Yoke 用内容哈希把每条文档钉在它描述的那段代码（函数/类）上。代码一改，锚点哈希就变，对应文档立刻翻成 `stale`，在代码移动的那一刻，而不是等某个 agent 后来碰巧发现文档不对。

不用安装、不碰你的仓库，一条命令亲眼看一遍（在隔离临时目录里跑，纯 `python3`，零依赖）：

```bash
bash scripts/anchor-demo.sh
```

它会走完整个闭环：

```
$ anchor add ... --symbol-name make_token      # 把一条 learning 锚到函数上 → FRESH
$ anchor scan                                  # 在文件顶部插 3 行注释 → 仍 FRESH（符号模式抗行号位移）
$ anchor report                                # 把 token 从 8 位改成 12 位 → STALE！文档自己报警
$ anchor verify --anchor-id A-xxxx             # 更新文档后重定基线 → 回到 FRESH
```

关键设计：**符号模式优于行号模式**。锚定按符号名重新定位再哈希函数体，所以在上方插入无关代码不会误报 stale——只有真正改动被锚函数的内容才会触发。这是让"文档健康度看板"不被假阳性淹没、从而值得信任的前提。

在你自己的项目里启用：

```bash
python3 scripts/anchor.py add --doc-kind learning --doc-ref <key> --code-file <f> --symbol-name <fn>
python3 scripts/anchor.py report                       # 给人/agent 看的过时报告
python3 scripts/anchor.py dashboard                    # 生成单文件 HTML 健康度看板
```

> 为什么这是差异点：代码图谱工具精确但不懂设计意图；LLM 文档工具可读但会幻觉、会悄悄过时。Yoke 两头都占，并让"过时"第一次变得机器可检——audit 阶段会把未处理的过时文档计入扣分，成为硬闸门。

---

## 工作原理

需求进，生产级代码 + 活文档出。产品经理用 `/propose`，开发者用 `/trace`，两个入口共享同一条流水线。

```
propose (PM) ──┐
               ├──→ _trace-persist → pipeline → architect → qa + coder → audit → update-map → ship
trace   (Dev) ─┘                        │                      │           │
                                      guard                  learn ←─── learn
                                    (保护编辑范围)      (经验捕获 + anchor 过时检测)
```

确认后 `/pipeline` 会根据复杂度自动调度后续阶段：生成类型合约、编写测试、实现代码、质量审计、更新文档、创建 PR——全程自治。

## 安装

### Claude Code

```bash
# 1. 添加 marketplace（在终端中执行）
claude plugin marketplace add https://github.com/Dashsoap/yoke.git

# 2. 安装（全局，所有项目可用）
claude plugin install yoke

# 或仅为当前项目安装
claude plugin install yoke --scope project
```

安装后重启 Claude Code 会话生效。

### Cursor

```bash
# 1. 克隆仓库
git clone https://github.com/Dashsoap/yoke.git ~/.cursor/yoke

# 2. 复制 skills 到项目
mkdir -p .cursor/skills
cp -r ~/.cursor/yoke/skills .cursor/skills/yoke
```

### Codex

```bash
# 1. 克隆仓库
git clone https://github.com/Dashsoap/yoke.git ~/.codex/yoke

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
| `/anchor` | **杀手锏**：文档锚定代码 + 内容哈希过时检测。/coder 收尾扫描、/audit 扣分、/update-map 局部复核 |

### Docs — 文档管理

| Skill | 职责 |
|-------|------|
| `/init` | **新项目骨架引导**（空目录跑 origin 会失败 → 用 init，问 2 个问题、写最小 PRODUCT-MAP + 5 CSV） |
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

# 查看活文档健康度（哪些文档因代码改动而过时）
python3 scripts/anchor.py report

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
