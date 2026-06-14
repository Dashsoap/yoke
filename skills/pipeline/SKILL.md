---
name: pipeline
description: 需求经 /propose 或 /trace 确认后，根据任务复杂度自适应执行开发流水线
---

# Pipeline — 总调度器

你是自治开发流水线的总调度器。根据任务复杂度选择合适的流程深度。目标："确认的需求进 → 生产级代码 + 活文档出。"

## 核心原则

1. 活文档即真相 — 产品地图 + MAP.md + traces。
2. **按需执行** — 不是每个任务都需要走全套流水线。改个颜色不需要 OpenSpec。
3. 文件系统即记忆 — Agent 通过仓库文件通信。
4. 不猜意图。有疑问就问。

## 任务分级（Phase 0 确定）

<HARD-GATE>
Phase 0 必须先确定任务级别。级别决定跳过哪些 Phase。绝不对所有任务走全套。
</HARD-GATE>

| 级别 | 触发条件 | 执行 Phase | 跳过 Phase |
|------|---------|-----------|-----------|
| **PATCH** | bug 修复、样式调整、≤ 5 文件、无新 API、无新状态 | -1 → 0 → 4 → 5(轻量) → 6 → 6.5 → 7 → 7.5 → 8 | 1, 2, 3 |
| **FEATURE** | 新功能、新 API、新组件、新状态机 | -1 → 0 → 1? → 2 → 3 → 4 → 5 → 6 → 6.5 → 7 → 7.5 → 8 | 无 |
| **REFACTOR** | 结构变更、不改行为、迁移 | -1 → 0 → 4 → 5(轻量) → 6 → 6.5 → 7 → 7.5 → 8 | 1, 2, 3 |

### PATCH 级别的测试策略

PATCH 不预写新测试（Phase 3 跳过），而是：
1. **跑现有测试** — 确保修改不破坏现有功能
2. **按需补测试** — 如果 coder 修复的 bug 没有被现有测试覆盖，在实现完成后补一个回归测试
3. **只跑受影响包的测试** — 不全量跑，只 `{测试命令} -- {受影响文件}`

### FEATURE 级别的测试策略

FEATURE 走完整 TDD：
1. Phase 2 生成合约（类型文件）
2. Phase 3 预写测试（验证 RED，最多跑 2 次）
3. Phase 4 实现（自愈循环，每轮只跑相关测试）
4. 最终全量跑一次确认无回归

## 子 Agent 调度协议

<HARD-GATE>
每次调度子 Agent 时，必须在 prompt 中传递标准化上下文块，并要求子 Agent 在完成时返回标准化摘要。
</HARD-GATE>

### 调度时传递（写入 Agent tool 的 prompt 参数）

```
## Pipeline 上下文
- FEAT-ID: {FEAT-ID}
- 任务级别: {PATCH | FEATURE | REFACTOR}
- 受影响组件: {ComponentName}（模板级别：{轻量/标准/完整}）
- Trace 文件: docs/traces/{FEAT-ID}.md
- CLAUDE.md 关键配置:
  - 测试命令: {从 CLAUDE.md 读取}
  - 类型目录: {从 CLAUDE.md 读取}
  - 项目语言: {从 CLAUDE.md 读取}
```

### 子 Agent 返回要求

每个子 Agent 完成时，在最终输出的**末尾**附加结构化摘要块：

```
## Skill 完成摘要
- skill: {architect | qa | coder | audit}
- status: {done | stuck | rejected}
- artifacts:
  - {文件路径 1}
  - {文件路径 2}
- notes: {一句话关键信息，如 coder 迭代次数、audit 得分}
```

Pipeline 读取此摘要块，写入 execution-log，并传递给下一个 phase。

## Execution-Log 记录规则

每个 Phase 完成后，向 `docs/traces/execution-logs/{FEAT-ID}-run.json` 的 `phases` 数组追加一条记录：

```json
{
  "phase": 0,
  "skill": "{skill name}",
  "decision": "{该 phase 的关键决策，一句话}",
  "artifacts": ["{文件路径}"],
  "notes": "{从子 agent 摘要的 notes 字段复制}"
}
```

**best-effort**：写入失败不阻塞流水线。如果文件操作出错，在 Phase 7 报告中注明。

## 执行流程

### Phase -1：环境隔离（Worktree）

**触发条件**：用户在 `/trace` 确认时选择了 worktree 模式，或使用了 `--worktree` 参数。

若需要 worktree 隔离：
1. 基于当前 main 分支创建 worktree 和功能分支
2. 切换到 worktree 目录
3. 安装依赖（如需要）
4. **激活 `/guard`**：根据 trace 的受影响组件，自动激活编辑范围限制 + 危险命令拦截
5. 向用户确认后继续

若不需要 worktree：
- 创建功能分支
- 向用户确认分支名后继续

### Phase 0：加载上下文 + 分级

1. 从 `docs/traces/` 读取已确认的需求
2. **检测 trace 模式**：如文档头部含 `> mode: pm`（由 `/propose` 创建），执行技术补充。如为 `> mode: full` 或 `> mode: dev`，跳过此步。
   - 读受影响模块的组件文件（交互表、状态机、不变式）
   - 填充 trace 中所有"待补充"的技术章节：当前产品状态 — 技术视图、受影响的组件、不变式影响、模式、API 交互、治理合规研发补充、产品地图更新要求
   - 将 `mode: pm` 改为 `mode: full`
   - 回填 `docs/traces/index.csv` 中该 trace 行的 `component` 列（PM 模式初始为空）
   - 向用户展示补充内容，确认后继续
3. 读 `CLAUDE.md` 获取项目约定
4. 若产品文档网络存在：读 `docs/product/PRODUCT-MAP.md` → `modules/{module}/index.md` → `modules/{module}/{ComponentName}.md`
5. **识别受影响组件的模板级别**（轻量/标准/完整）— 从组件文件读取。级别信息将传递给下游 skill。读组件的 `## 关系` 表了解依赖影响范围。
6. **确定任务级别**（PATCH / FEATURE / REFACTOR），向用户确认：
   ```
   任务分析：
   - 级别：PATCH（bug 修复，≤ 5 文件，无新 API）
   - 受影响组件：{ComponentName}（完整级）
   - 将跳过：合约架构、预写测试
   - 将执行：直接实现 → 跑现有测试 → 轻量审计 → 知识沉淀

   确认此级别？或升级为 FEATURE？
   ```
7. **创建 execution-log**：
   ```
   docs/traces/execution-logs/{FEAT-ID}-run.json
   ```
   初始内容：
   ```json
   {
     "feat_id": "{FEAT-ID}",
     "task_level": "{PATCH | FEATURE | REFACTOR}",
     "started_at": "{ISO 8601 时间戳}",
     "baseline_hashes": "{从 trace 文档 Baseline 段读取}",
     "phases": []
   }
   ```
   如 `docs/traces/execution-logs/` 目录不存在则创建。

### Phase 1：Spike（可选，仅 FEATURE）

触发条件：需求涉及探索性或未知 API/行为。
- 最小概念验证（最多 20 行）→ 测试假设 → 删除 → 将发现输入 Phase 2

### Phase 2：合约架构（仅 FEATURE）

按调度协议调度 `/architect`。额外传递：
- Spike 发现（如 Phase 1 执行了）
- 产出：`docs/specs/{TYPE}-{4hex}-{slug}.spec.md`（合约文档，FEAT-ID 格式为 `{TYPE}-{4hex}-{slug}`，如 `FEAT-a3f7-trace-naming`）+ 项目源码中的类型文件
- 完整级组件：spec 须包含不变式、状态机定义、故障旅程
- 验证两个产出都存在

### Phase 3：测试生成（仅 FEATURE）

按调度协议调度 `/qa`。额外传递：
- Spec 文件路径（从 architect 摘要的 artifacts 获取）
- 类型文件路径（从 architect 摘要的 artifacts 获取）
- 产出：测试文件 + mock 文件
- 完整级组件：测试须覆盖不变式验证、状态机转换、故障旅程场景
- **验证 RED：只跑 1 次**，确认测试失败即可。最多 2 次。
- 不启动 watch 模式，不循环跑

### Phase 4：实现

**PATCH/REFACTOR 模式**：
- 不调度 coder 子 Agent，直接在当前 Agent 中实现
- 修改后跑一次受影响包的测试
- 如测试失败，修复后再跑一次（最多 3 轮）

**FEATURE 模式**：
- 按调度协议调度 `/coder`。额外传递：
  - Spec 文件路径
  - 测试文件路径（从 qa 摘要的 artifacts 获取）
  - 指示 coder 在自愈循环前建立测试基线
- coder 自愈循环（最多 10 轮，或连续 5 次同类错误提前中止）
- **每轮只跑相关测试文件**，不全量跑：
  ```
  {测试命令} {具体测试文件路径}
  ```
- 全部通过后，跑一次全量确认无回归
- **处理 coder stuck**：如 coder 返回 `status: stuck`，读取根因分析报告 `docs/audit/STUCK-{FEAT-ID}.md`，向用户展示假设和建议，等待用户决策（调整 spec？修改测试？手动介入？）

### Phase 5：质量审计

**PATCH/REFACTOR 模式（轻量审计）**：
- 不调度 /audit 子 Agent
- 在当前 Agent 中快速检查：
  - [ ] 修改是否与需求一致？
  - [ ] 有无安全问题？（XSS、注入等）
  - [ ] 现有测试全部通过？
  - [ ] 无调试代码残留？
  - [ ] 完整级组件：不变式是否被保持？
- 输出简短审计备注（非完整报告）

**FEATURE 模式（完整审计）**：
- 按调度协议调度 `/audit`。额外传递：
  - Spec 文件路径
  - 测试文件路径
  - Coder 迭代次数（从 coder 摘要的 notes 获取）
- 完整 100 分制评分，按组件模板级别检查合规性
- 得分 >= 80 通过；60-79 软拒（最多 2 次重试）；< 60 硬拒

### Phase 6：知识沉淀

**所有级别都执行**（知识沉淀不可省略）：
- 按调度协议调度 `/update-map`。额外传递：
  - Coder 迭代次数（从 coder 摘要）
  - 审计得分（从 audit 摘要）
  - 所有 phase 产出的 artifacts 列表
- 验证受影响的组件文件 `modules/{module}/{ComponentName}.md` 已更新
- 验证关系表双向一致

### Phase 6.5：经验捕获

**所有级别都执行**：
- 收集 coder 和 audit 摘要中的 `learnings` 段
- 如有 learnings，写入 `docs/learnings/` 目录（由 `/learn` skill 格式定义）
- 如 `docs/learnings/` 不存在，创建目录和 `project.jsonl` 文件
- best-effort：写入失败不阻塞流水线

### Phase 7：报告

读取 `docs/traces/execution-logs/{FEAT-ID}-run.json`，补充 `ended_at` 时间戳，向用户呈现结构化报告：

```
## Pipeline 完成报告

**FEAT-ID**: {FEAT-ID}
**任务级别**: {PATCH | FEATURE | REFACTOR}
**耗时**: {started_at → ended_at}

### Phase 执行记录
| Phase | Skill | 决策 | 产出 |
|-------|-------|------|------|
| 0 | pipeline | {决策} | - |
| 2 | architect | {决策} | {artifacts} |
| ... | | | |

### 关键数据
- Coder 迭代次数: {N}（从 coder phase notes 提取）
- 审计得分: {score}/100
- 产出文件总数: {count}

### 产品文档更新
- {ComponentName}.md: {更新内容摘要}
```

### Phase 7.5：发布（可选）

Phase 7 报告完成后，提示用户：

```
Pipeline 完成。下一步：
  A) 运行 /ship — 自动创建 PR，含 changelog 和审查就绪看板
  B) 稍后手动处理
```

如用户选 A 或直接运行 `/ship`，由 /ship skill 接管。

### Phase 8：Worktree 收尾（仅 worktree 模式）

1. **解除 `/guard`**（如 Phase -1 激活了）
2. 向用户确认处置方式：
   - A) 合并到 main 并清理 worktree
   - B) 创建 MR/PR（保留 worktree 供 review）— 可直接运行 `/ship`
   - C) 仅保留，稍后手动处理

**绝不自动合并或推送** — 始终等待用户明确选择。

---

## 测试执行原则

<HARD-GATE>
测试执行必须遵循以下原则，避免资源浪费：
</HARD-GATE>

1. **强制 run 模式，禁止 watch** — vitest 必须加 `--run`，jest 不加 `--watch`/`--watchAll`。测试跑完必须自动退出进程。示例：
   - vitest: `pnpm vitest run {file}` 或 `pnpm --filter {pkg} test -- --run`
   - jest: `pnpm jest --no-watchAll {file}`
   - pytest: `pytest {file}`（默认就是 run 模式）
   - go test: `go test ./...`（默认就是 run 模式）
2. **优先跑单文件** — `{测试命令} {具体文件}` 而非全量
3. **全量只跑一次** — 在最终确认阶段跑一次全量回归
4. **QA 验证 RED 最多 2 次** — 不循环
5. **Coder 自愈最多 10 轮** — 每轮只跑相关测试
6. **PATCH 不预写测试** — 跑现有测试，按需补回归测试
7. **测试进程必须退出** — 如果测试命令执行后进程未退出（卡在 watch），立即 Ctrl+C 终止，检查是否遗漏了 `--run` 参数

---

## 错误处理

| 情况 | 动作 |
|------|------|
| 任务级别判断有疑问 | 向用户确认，不猜 |
| Coder 卡住（> 10 轮或 5 次同类错误） | 读取根因分析报告，展示假设和建议，请用户决策 |
| 测试超时 / OOM | 缩小测试范围（单文件），报告资源问题 |
| 审计两次拒绝 | 升级至用户 |
| 逻辑矛盾 | 中止，请用户澄清需求 |
| 产品文档网络未更新 | 阻止 Phase 7 |

## 并发规则

- Phase 3（FEATURE）：前端 QA + 后端 QA = 并行
- Phase 4（FEATURE）：前端 Coder + 后端 Coder = 并行
- 其余：顺序执行
