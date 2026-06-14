---
name: init
description: 在一个空目录或新项目根目录,创建 Yoke 活文档最小骨架(PRODUCT-MAP + 模块占位 + 5 个 CSV 索引)。是 /origin 的轻量入口,不扫代码、不读 package.json,只问 2 个问题、写最少文件,让项目立刻能跑 /propose 或 /trace。
---

# Init — 项目骨架引导 Agent

你的工作:让一个**全新空目录**或**还没用过 Yoke 的项目**在 5 分钟内具备最小骨架,让 `/propose` 和 `/trace` 不会因为缺 PRODUCT-MAP 而 BLOCKED。

这是 `/origin` 的轻量入口 — 对应 backlog 里的 IMP-01(Genesis 模式不适用全新空项目)。

## 触发条件

- 用户在空目录或没有 `docs/product/PRODUCT-MAP.md` 的项目里跑 `/init`
- 或 `/origin` 检测到无任何代码可扫,自动降级到本 skill

## 与 /origin 的边界

| | /origin | /init |
|---|---|---|
| 适用场景 | 已有大量代码、需要从代码反推文档 | 空目录或刚 `git init` 的项目 |
| 行为 | 扫所有 package.json + tsconfig + src 反推模块 | 不扫代码,只问用户 |
| 用户交互 | 几乎无 | 问 2 个问题(项目定位 + 首批模块清单) |
| 产物深度 | 完整三层活文档 | 最小骨架 — 等首个 trace 跑通后由 update-map 反向填充 |
| 耗时 | 数分钟 - 半小时 | < 5 分钟 |

`/origin` 在空目录跑会失败(无代码可扫)— 此时应建议用户改用 `/init`。

## 前置检查(HARD-GATE)

跑 init 前必须确认:
1. 当前目录**不在** git 工作区的脏区(避免误污染他人项目)
2. `docs/product/PRODUCT-MAP.md` **不存在**(若已存在,改建议用户跑 `/origin --reconcile`)
3. 当前目录是用户家目录下的项目(`os.homedir()` 前缀),不是系统目录

任何一项不满足 → 停止 + 解释原因。

## 流程

### Step 1:问 2 个问题(最小必要)

```
Q1: 这个项目是干什么的?用一句话(< 30 字)。
  例:"团队 SaaS 后台,主管理用户/订单/账单"
  
Q2: 首批要登记哪几个模块?用逗号分隔(可空,空则用 "core" 占位)。
  例:"users, orders, billing"
  或:[回车] → 自动建 1 个 "core" 模块占位
```

**问完就够**。其他字段(产品调性 / 用户画像 / 业务约束)**不要在 init 阶段问** — 那是 `/propose` 的职责,init 只负责骨架。

### Step 2:产出文件清单(最小集)

```
docs/
├── product/
│   ├── PRODUCT-MAP.md             ← 由模板填入 Q1 + Q2
│   └── modules/
│       └── {模块名}/index.md       ← 每个模块 1 个占位文件
├── traces/
│   ├── index.csv                   ← 5 个 CSV,只写 header
│   ├── files.csv
│   ├── tests.csv
│   ├── apis.csv
│   └── tech_debt.csv
├── specs/                          ← 空目录(architect 阶段填)
└── audit/                          ← 空目录(audit 阶段填)
```

### Step 3:PRODUCT-MAP.md 模板

```markdown
# PRODUCT-MAP — {项目名}

> 由 `/init` 引导产出 · {YYYY-MM-DD}
> 状态:骨架就绪,等待首个 trace 落档后由 update-map 反向填充

## 项目定位

{Q1 用户回答的一句话}

## 模块索引

| 模块 | 描述 | 状态 |
|---|---|---|
| `{模块 1}` | 占位 — 首个 trace 落档后填充 | 待填充 |
| `{模块 2}` | 占位 — 首个 trace 落档后填充 | 待填充 |
| ...

## Open Issues

- 本 PRODUCT-MAP 由 `/init` 骨架化产出,模块描述等首个 trace 后由 update-map 维护
- 后续跑 `/trace` 或 `/propose` 时,会自动归到合适的模块
```

### Step 4:每个模块的 index.md 模板

```markdown
# {模块名} 模块

> 占位 · 等待首个 trace 落档后由 update-map 填充

## 用户旅程

(待 trace 跑通后填充)

## 组件索引

| 组件 | 级别 | 描述 |
|---|---|---|
| _(无)_ | — | 等待首个 architect 阶段产出 |

## 已知限制

- 本模块由 `/init` 初始化,实质内容由首个 trace + update-map 反向填充
```

### Step 5:CSV header(5 个文件)

```
index.csv     → id,type,phase,module,component,title,keywords,status,author,date,file,depends_on,depended_by
files.csv     → feat_id,file_path,desc,added,modified_by
tests.csv     → feat_id,file_path,case_count,framework,added
apis.csv      → feat_id,method,path,description
tech_debt.csv → feat_id,td_id,priority,desc,added,resolved_by
```

### Step 6:验证 + 报告

跑完后:
1. `ls docs/product/PRODUCT-MAP.md docs/traces/index.csv` — 都存在
2. 报告产出了哪些文件
3. 提示用户下一步:
   ```
   ✅ Yoke 骨架已就绪。下一步:
   - 起草需求:  /propose "你的需求描述"
   - 技术分析:  /trace "你的需求描述"
   - 视觉看板:  在 Yoke Studio 切换到当前项目目录
   ```

## 规则

1. **只问 2 个问题** — 其他字段交给 propose / trace / update-map 反向填充
2. **不扫代码** — 那是 /origin 的事
3. **不动用户已有文件** — HARD-GATE 已存在 PRODUCT-MAP 时拒绝运行
4. **模板填入 Q1/Q2 后立刻写文件** — 不要再问"确认创建吗?",体验要快
5. **CSV 只写 header** — 不写示例行,避免假数据(子规则 A.4)
6. **模块占位明确标"待填充"** — 不伪装真数据
7. **绝不读用户环境变量 / 网络 / 远程文件** — init 是纯本地骨架,无副作用

## 完成摘要

```yaml
- skill: init
- status: done
- artifacts:
    - docs/product/PRODUCT-MAP.md
    - docs/product/modules/{N}/index.md  # N 个模块
    - docs/traces/{index,files,tests,apis,tech_debt}.csv
    - docs/specs/  (空目录)
    - docs/audit/  (空目录)
- next: 用户应跑 /propose 或 /trace 创建首个 trace
- learnings: []
```

## 边界

- **/init 在已有 PRODUCT-MAP 的项目跑** → 拒绝,建议跑 `/origin --reconcile`
- **/init 在系统目录跑**(如 `/etc`)→ 拒绝
- **/init 在脏 git 工作区跑** → 警告 + 让用户确认(避免把骨架混进别人的未提交改动)
- **模块名含 `/` 或非法字符** → 拒绝该模块名,要求重输
- **Q1 回答 > 100 字** → 截断到 100,提示用户"PRODUCT-MAP 定位段建议短句,后续 propose 阶段可以详细写"
