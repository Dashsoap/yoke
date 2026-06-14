---
name: post-trace
description: >-
  代码已写完后的逆向 trace 流水线。分析 git diff，反推生成符合 /trace 格式的需求文档、更新 CSV 索引、补测试、质量审查，并通过
  /update-map 完成知识沉淀——全部事后执行。适用于代码改动已完成但跳过了 trace、测试和文档的场景。
  触发词：'post-trace'、'补文档'、'补 trace'、'事后 trace'、'retroactive trace'，或用户想补齐已有改动的正式文档时。
---

# Post-Trace — 事后补全流水线

代码已写完，现在补齐 trace 流程中缺失的需求文档、测试、审查和知识沉淀。

## 核心理念

正向 trace 流程：需求 → trace → 实现 → 审查 → 沉淀
Post-Trace 逆向：**已有实现** → 反推 trace → 补测试 → 审查 → 沉淀

## 与 /trace 的关系

`/trace` 是正向需求入口，在实现前起草文档。`/post-trace` 是逆向补全，在实现后补写相同格式的文档。两者产出物格式完全一致，可被后续 `/pipeline` 和 `/update-map` 正常处理。

## 交互模型

**仅在 Phase 0 结束时暂停一次，等待用户确认变更摘要。** 确认后，Phase 1 → 5 全自动执行，中间不再暂停。最终 Phase 6 输出完成报告。

---

## 执行流程

### Phase 0: 变更分析 ⏸️ 唯一确认点

1. **收集变更范围** — 运行 git diff 获取本次改动：
   ```bash
   git diff main --stat
   git diff main --name-only
   git diff main
   ```
   如果用户指定了特定 commit range 或 branch，使用用户指定的范围。

2. **阅读产品地图** — 读 `docs/product/PRODUCT-MAP.md`，扫描模块索引，确定受影响的模块和组件。
   - 若 `docs/product/PRODUCT-MAP.md` 不存在：降级读 `docs/MAP.md` 做技术级影响分析，并建议用户运行 `/origin` 引导产品地图。

3. **阅读变更文件** — 逐个阅读关键变更文件，理解改动意图和实现细节。

4. **输出变更摘要** 并等待用户确认：
   ```
   ## 变更分析
   - 涉及模块：{module}
   - 受影响组件：{ComponentName}（{轻量/标准/完整}）
   - 改动文件：{N} 个
   - 新增/修改/删除行数：+{add} / -{del}
   - 改动类型：[新功能 | 增强 | 修复 | 重构 | 补丁]
   - 建议 ID 类型：{FEAT / BUG / REFACTOR / PATCH}

   确认后将自动执行：trace 文档生成 → 测试补充 → 质量审查(含自动修复) → 知识沉淀
   ```

**用户确认后，以下所有 Phase 自动顺序执行，不再暂停。**

---

### Phase 1: Trace 文档反推

从已有代码反推需求文档，格式与 `/trace` 输出完全一致。

#### 1a. 生成 FEAT-ID

```bash
python3 {ray_plugin_path}/scripts/search.py --generate-id --type {type} --title "{title}" --date {今天日期，YYYY-MM-DD}
```

输出格式：`{TYPE}-{4hex}-{slug}`（例：`FEAT-a3f7-realtime-price`）。

#### 1b. 读取受影响组件文件

按三层路径加载：`PRODUCT-MAP.md` → `modules/{module}/index.md` → `modules/{module}/{ComponentName}.md`

重点阅读：交互表、状态机、不变式（完整级）、边界情况、Non-Goals。这是"改之前的状态"。

#### 1c. 计算 Baseline 哈希

对以下文件计算 SHA256 前 8 位：
- `docs/product/PRODUCT-MAP.md`
- `docs/product/modules/{module}/index.md`
- `docs/product/modules/{module}/{ComponentName}.md`

注意：post-trace 的 Baseline 反映的是**实现后**的产品文档状态（而非实现前）。

#### 1d. 起草 Trace 文档

内容从已有代码和产品地图反推，格式与 `/trace` 输出一致：

```markdown
# {FEAT/BUG/REFACTOR/PATCH}-{4hex}-{slug}: {功能名称}

> mode: dev

## 当前产品状态（Before）
> 来源：docs/product/modules/{module}/{ComponentName}.md
> 组件模板级别：{轻量 | 标准 | 完整}

{2-3 句描述与本次变更相关的实现前行为。如适用，粘贴交互表/状态机中的相关行。}

## 场景
{用叙事故事描述本次改动解决的问题。给用户取一个名字，描述他的背景和目标。}

> {用户名} 想要 {目标}，在改动前遇到 {问题}。
> 变更后：{改动如何改善了体验}。

## 关键规则
- [从代码中提取的业务约束 1]
- [从代码中提取的业务约束 2]

## 不变式影响（完整级组件必填）
- {列出本次变更涉及的不变式：哪些保持、哪些修改}

## 验收标准
- [x] [从实现反推的已满足验收条件]

## Non-Goals（刻意不做）
- {明确排除的能力或范围}

## 受影响的组件
- modules/{module}/{ComponentName}.md（{模板级别}）：
  - 交互表 / 状态机：[哪些行变化 / 哪些新增]
  - 状态：[新增或变更的状态]
  - 边界情况：[处理的新边界情况]

## 模式
frontend | backend | fullstack

## API 交互（如有）
- {method} {endpoint} → { 请求结构 } → { 响应结构 }

## 产品地图更新要求
/update-map 须：
- [ ] 更新 modules/{module}/{ComponentName}.md（级别：{轻量/标准/完整}）
- [ ] 按上述规格新增交互行 / 状态机行 / 边界情况
- [ ] 如涉及完整级：更新不变式、故障旅程

## 治理合规（非 PATCH 必填）
### PD 边界定义
- 安全护栏：{从代码推断 / PD 未定义}
- 性能约束：{从代码推断 / PD 未定义}

### 研发补充（基于代码上下文）
- 已有约束：{从组件文件/代码中发现的已有治理约束}
- 风险点：{本次变更可能影响的已有边界}

## Open Issues
- [实现中遗留的未决问题或技术债]

## Baseline
> 以下文件哈希记录了 post-trace 起草时（实现后）的产品文档状态。

| 文件 | SHA256 前 8 位 |
|------|---------------|
| docs/product/PRODUCT-MAP.md | {计算哈希} |
| docs/product/modules/{module}/index.md | {计算哈希} |
| docs/product/modules/{module}/{ComponentName}.md | {计算哈希} |

## 实现追溯

### 代码变更
- `{文件路径}` — {实际做了什么改动}

### 架构决策记录（ADR）
**决策**：{选择了什么方案}
**考虑过的替代方案**：{其他方案}
**理由**：{为什么选这个}
**权衡**：{得到了什么 vs 放弃了什么}

### 迭代统计
- 审计得分：（由 Phase 3+4 填入）
- 新增技术债：（由 Phase 3+4 填入）
```

#### 1e. 写入文件并更新 CSV 索引

1. 若 `docs/traces/index.csv` 不存在，先初始化：
   ```bash
   python3 {ray_plugin_path}/scripts/search.py --init --project-dir {project_root}
   ```

2. 将 trace 文档写入 `docs/traces/{FEAT-ID}.md`（纯 Markdown，无 YAML frontmatter）。

3. 向 `docs/traces/index.csv` 追加一行：
   ```
   {FEAT-ID},{type},trace,{module},{component},{title},{keywords},confirmed,dev,{今天日期},{FEAT-ID}.md,,
   ```

---

### Phase 2: 测试补充

先检查变更文件是否已有对应测试。如果已有且覆盖充分，自动跳过本 Phase。

1. **扫描现有测试** — 在变更涉及的包中搜索 `__tests__/` 目录，确认是否有对应测试。

2. **分析测试缺口** — 对比验收标准与现有测试，列出缺失的测试场景。

3. **补写测试** — 遵循项目 QA 规范：
   - 测试文件：`packages/{pkg}/src/__tests__/{ID}.test.ts`
   - 每个验收标准至少一个测试
   - 测试错误路径和边界条件
   - 使用 MSW mock（如涉及 API）
   - 描述性测试名：`"should {expected behavior} when {condition}"`

4. **运行测试** — 确保所有测试 GREEN：
   ```bash
   pnpm --filter {package} test
   ```

5. **更新 trace 文件** `## 迭代统计` 中的测试数量。

---

### Phase 3 + 4: 质量审查 & 自动修复

审查与修复合并为一个自治循环，根据问题严重程度自动决策。

**评分维度（100 分制）**：

| 维度 | 权重 | 检查项 |
|------|------|--------|
| 需求一致性 | 30 | 验收标准是否全部有对应代码？ |
| 类型安全 | 20 | 是否使用了正确的类型？有无 any/as 断言？ |
| 安全性 | 20 | XSS/注入防护？输入校验？无硬编码秘钥？ |
| 代码质量 | 15 | 无死代码？无 console.log？遵循项目规范？ |
| 最佳实践 | 15 | React 模式？性能（无不必要渲染）？可访问性？RTL？ |

**自动修复决策逻辑**：

```
AUDIT_ROUND = 0

LOOP:
  AUDIT_ROUND += 1
  执行审查，计算得分

  IF score >= 80:
    → PASS，进入 Phase 5
    → 将 MINOR 问题记入 Open Issues

  IF score >= 60 AND AUDIT_ROUND <= 2:
    → 自动修复所有 CRITICAL 和 MAJOR 问题
    → 每次修复后运行测试确保不破坏现有功能
    → GOTO LOOP（重新审查）

  IF score < 60 OR AUDIT_ROUND > 2:
    → STOP，向用户输出审查报告，等待人工介入
    → 列出所有未修复的问题及建议
```

**自动修复范围**（无需人工确认）：
- CRITICAL：安全漏洞、类型错误、逻辑缺陷 → 立即修复
- MAJOR：缺失校验、不当模式、性能问题 → 自动修复
- MINOR：命名规范、冗余代码、可选优化 → 记入 trace 的 Open Issues，不自动修复

审查完成后，回填 trace 文件 `## 实现追溯` 中的审计得分和新增技术债数量。

---

### Phase 5: 知识沉淀

执行 `/update-map` 流程，将本次变更沉淀进产品文档网络和 CSV 索引。

#### 5a. 更新 CSV 族

1. **index.csv**：将本条 trace 的 `phase` 更新为 `done`，`status` 更新为 `done`
2. **files.csv**：为本次迭代每个变更文件追加一行 `({FEAT-ID}, {path}, {desc}, {lines})`
3. **tests.csv**：为每个测试文件追加一行
4. **apis.csv**：如有新 API 端点，追加行
5. **tech_debt.csv**：如审查报告含技术债，追加行

#### 5b. 更新产品文档三层网络

按 `/update-map` 规范更新：

1. **更新组件文件** `modules/{module}/{ComponentName}.md`：
   - 更新交互表 / 状态机
   - 新增边界情况
   - 更新不变式（完整级）
   - 更新故障旅程（完整级）
   - 更新"最后更新"日期

2. **更新用户旅程**（如跨组件流程变化）：更新 `modules/{module}/index.md` 的 `## 用户旅程`

3. **更新关系表**（双向原子）：如依赖关系变化，同时更新两端文件

4. **更新 PRODUCT-MAP.md**：如新增模块或组件，同步更新索引

#### 5c. 重新生成 MAP.md

```bash
python3 {ray_plugin_path}/scripts/search.py --generate-map --project-dir {项目根路径} > docs/MAP.md
```

验证生成结果无 warning。

---

### Phase 6: 完成报告

向用户展示最终摘要：

```
## Post-Trace 完成报告

### 本次改动
- ID: {FEAT/BUG/REFACTOR/PATCH}-{4hex}-{slug}
- 标题: {title}
- 模块: {module} / 组件: {ComponentName}

### 产出物
- ✅ Trace 文档: docs/traces/{FEAT-ID}.md
- ✅ CSV 索引: docs/traces/index.csv 已更新
- ✅ 测试: {N} 个测试用例（{pass}/{total} 通过）[或：已跳过（已有充分覆盖）]
- ✅ 审查得分: {score}/100（审查轮次: {N}）
- ✅ 产品文档: modules/{module}/{ComponentName}.md 已更新
- ✅ MAP.md 已重新生成
- ⚠️ 技术债: {N} 项（见 Open Issues）
- 🔧 自动修复: {N} 项 CRITICAL/MAJOR 问题已修复

### 文件变更清单
- [created] docs/traces/{FEAT-ID}.md
- [modified] docs/traces/index.csv
- [modified/created] docs/product/modules/{module}/{ComponentName}.md
- [modified] docs/MAP.md
```

---

## 快捷模式

用户可通过参数跳过部分阶段（Phase 0 确认仍保留）：

| 参数 | 效果 |
|------|------|
| `--doc-only` | 仅执行 Phase 0→1→5（trace 文档 + 知识沉淀，跳过测试和审查） |
| `--test-only` | 仅执行 Phase 0→2（仅补测试） |
| `--audit-only` | 仅执行 Phase 0→3+4（仅审查 + 自动修复） |
| `--no-fix` | 审查但不自动修复，仅报告问题 |

默认执行全部 Phase。

---

## Rules

1. **从代码推导，不凭空想象** — trace 文档必须忠实反映已有实现
2. **格式与 `/trace` 一致** — 产出 trace 文件必须是纯 markdown，使用新 ID 格式，写入 `index.csv`
3. **Phase 0 确认一次即可** — 确认后全流程自动执行，不再暂停（除非 score < 60 需要人工介入）
4. **复用现有测试模式** — 参考同包 `__tests__/` 中的现有测试风格
5. **不破坏现有功能** — 每次修改后都跑测试
6. **最小侵入** — 只补缺失的文档/测试/类型，不重构现有代码（除非审查发现 CRITICAL/MAJOR）
7. **尊重已有 trace** — 如果改动涉及的功能已有 trace 文件（同模块/组件），优先在原文件追加而非新建
8. **MINOR 不动代码** — MINOR 级别问题只记 Open Issues，不自动修改代码
9. **双向原子更新关系表** — 修改组件关系时，必须同时更新两端文件
10. **Baseline 是事后快照** — 明确标注 Baseline 哈希反映的是实现后状态，非实现前
