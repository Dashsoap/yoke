# Yoke 改进 Backlog

> 来源:2026-05-24 用 Yoke 开发 Yoke Studio v1 的 dogfood 跑通,真实暴露的 4 个 gap。
> 状态:Backlog,待优先级排期。

## 总览

| ID | gap | 触发场景 | 影响面 | 优先级 | 工作量 |
|---|---|---|---|---|---|
| YOKE-IMP-01 | Genesis 模式不适用全新空项目 | 新项目第一次跑 `/origin` | 阻塞 — 新项目根本进不去流水线 | **P0** ✅ 已修复 2026-05-25 | 实际 15min |
| YOKE-IMP-02 | 项目骨架初始化无归属 | trace → architect → qa 之间缺 scaffold check | 阻塞 — coder 跑测试前必崩 | **P0** | 0.5 天 |
| YOKE-IMP-03 | subagent 看不到 orchestrator 历史决策 | trace 用了"小李"(已被全局清理的示例名) | 中 — 污染产出,需事后修 | **P1** ✅ 已修复 2026-05-24 | 实际 5min |
| YOKE-IMP-04 | audit 提的 TD 没自动同步 tech_debt.csv | audit 报告与 csv 索引不一致 | 中 — update-map 不跑时 csv 永远空 | **P1** ✅ 已修复 2026-05-24 | 实际 3min |
| YOKE-IMP-07 | INV-5 副行折叠条件 spec 字面 vs 实现差异(v4.1 修 spec amendment) | v4 audit 91/100 通过但发现 spec §5.1 INV-5 与 `LiveAgentBoard.tsx:116` 字面偏离 | 低 — 实现更对(UX 折叠合理),但 spec 未授权偏离属流程脱节 | **P2** | <0.5 天(纯改 spec) |
| YOKE-IMP-05 | client/server 边界守门缺失,同类 `node:` scheme 进 client bundle bug 已发生 2 次(v3.2 + v6) | v6 首版 `projectPath.client.ts` import `node:path` → 整站 SSR HTTP 500;v3.2 `actions.ts` re-export 同类问题 | **高** — 直接 HTTP 500 / SSR 全挂;三阶段防线(architect/coder/qa)全断且短期内 2 次同类问题说明流程缺陷 | **P1 已立项** | 1-1.5 天(3 件套:ESLint + smoke + spec template) |

---

## YOKE-IMP-01: Genesis 模式不适用全新空项目

> ✅ **已修复 2026-05-25**(估 1 天,实际 15 分钟):新增 `skills/init/SKILL.md` 作为 `/origin` 的轻量入口。空目录跑 `/init`,问 2 个问题(项目定位 + 模块清单),写最小 PRODUCT-MAP + 模块占位 + 5 CSV header,5 分钟内让项目具备首跑 trace 的骨架。`/origin` 仍负责"代码反推文档"的复杂场景,两者职责互补。README Skills 表已加 init 条目。

### 症状

`/origin` skill 的 Phase 1 "地形扫描" 假设有 `package.json` / `tsconfig.json` / `src/` 可读。**全新空项目这些都不存在**,Phase 1 输出空骨架,Phase 2-3 也无意义。

### 触发场景(本次 dogfood 实录)

1. 新建空目录 `yoke-studio/`
2. 尝试跑 trace `/trace Yoke Studio v1`
3. trace HARD-GATE 要求先读 `docs/product/PRODUCT-MAP.md`
4. PRODUCT-MAP 不存在 → SKILL 建议跑 `/origin`
5. 跑 `/origin` → 没代码可扫,无法产出有意义的 PRODUCT-MAP

**实际绕过方式**:orchestrator 手写一个 v0 占位 PRODUCT-MAP,让 trace 跑下去。

### 影响

- 阻塞:每个新项目首次使用都卡这。
- 隐性损失:用户感知 Yoke "无法从零开始",转去用其他框架。

### 建议改动

新增 `/origin --blank` 模式,跳过代码扫描,只做以下事:
1. 询问产品定位一句话
2. 询问预期模块清单(可空,只填一个占位模块)
3. 写最简 PRODUCT-MAP.md(头部 + 模块占位表 + Open Issues)
4. 初始化 CSV 索引(沿用现有 `search.py --init` 逻辑)
5. 标记"首个 trace 后,update-map 会反向填充"

或者修改现有 `/origin` 的 Phase 1:检测到空目录时自动降级到 `--blank` 模式,不需要用户传 flag。

### 验收

- 在完全空目录跑 `/origin`,不报错,产出最简 PRODUCT-MAP + 5 个 CSV 文件
- 紧接着跑 `/trace` 不报"PRODUCT-MAP 不存在"

---

## YOKE-IMP-02: 项目骨架初始化谁都不管

### 症状

trace / architect 都不动 `package.json`、测试框架、构建配置。coder 默认这些就绪。**全新项目这些一个都没有**,coder 跑 `npm test` 直接崩。

### 触发场景(本次 dogfood 实录)

1. architect 完成 → 在 `src/types/trace.ts` 写了类型
2. QA 准备写测试 → 需要 vitest + RTL + jsdom 配置 + tsconfig
3. 全部不存在 → orchestrator 手动补位写了 package.json + vitest.config + tsconfig + next.config + vitest.setup
4. coder 才能 `npm install` + 跑测试

**实际绕过方式**:orchestrator 在 architect 和 QA 之间手动写了 5 个配置文件。

### 影响

- 阻塞:同 IMP-01,新项目首次必踩。
- 责任不清:scaffold 应该归谁?architect?coder?还是新角色?

### 建议改动

`/pipeline` 新增 **Phase 0.5: scaffold check**(在 architect 之后、qa 之前):
1. 检测项目是否有可跑测试的最小基础设施:`package.json` + 测试运行器配置 + tsconfig(或对应语言的等价物)
2. 缺失 → 调用一个新 sub-skill `/scaffold`(或扩展 architect 的职责)生成最简骨架
3. 已存在 → 跳过

新的 `/scaffold` 应该:
- 从 trace 的"模式"(frontend/backend/fullstack)和"技术栈约束"段推断需要装什么
- 不 `npm install`(留给 coder),只写配置文件
- 输出报告:你生成了哪些文件、coder 后续需要装哪些依赖

### 验收

- 空项目跑完 pipeline,scaffold 阶段产出 package.json 等基础配置
- coder 阶段不需要 orchestrator 补位

---

## YOKE-IMP-03: subagent 看不到 orchestrator 历史决策

> ✅ **已修复 2026-05-24**(估 0.5 天,实际 5 分钟):`skills/propose/SKILL.md:150-154` + `skills/trace/SKILL.md:139-143` 的"小明是一个加密新手..."模板替换为 `{用户角色,例:用户 A,核心使用者,日常 N 次使用本产品}` 变量化模板。grep `小明|加密新手` 残留 = 0。

### 症状

Yoke 的 SKILL.md 模板里有具名示例("小明是一个加密新手...")。subagent 读 SKILL.md 后,在新 trace 里也用了"小李"等具名人物。**但 orchestrator 之前已经做过统一脱名决策**(把"小李/小王"全清成"用户/张三"),subagent 完全不知道,产出污染。

### 触发场景(本次 dogfood 实录)

1. orchestrator 之前在 Yoke 项目内全局把"小李/小王"清成"用户/张三"
2. 但 `skills/trace/SKILL.md:141` 第 3 步模板里残留"小明"作为示例
3. trace subagent 读 SKILL.md → 模仿"小明"句式 → 产出 trace 里写了"小李"
4. orchestrator 事后才发现,需要手动修

### 影响

- 中:产出污染,需要事后审查 + 修。
- 一致性:Yoke 自身的 SKILL.md 应该跟开源版本的命名约定一致(脱业务、脱姓名)。

### 建议改动

**根治**:把所有 SKILL.md 里的具名示例改成变量化:
- ❌ "小明是一个加密新手,他刚打开应用..."
- ✅ "{用户角色}(如:核心用户 A)在 {场景} 下打开应用..."

涉及文件清单(需要逐个 grep):
```bash
grep -rn "小[明李王张刘陈赵孙周吴郑]" /Users/mac/Downloads/归档/skills/
```

### 验收

- `grep` 命中 0 处
- 新 dogfood 跑 trace 不再出现具名人物

---

## YOKE-IMP-04: audit 提的 TD 没自动同步进 tech_debt.csv

> ✅ **已修复 2026-05-24**(估 0.5 天,实际 3 分钟):采用方案 A(audit 必须双写)。在 `skills/audit/SKILL.md` 第 188 行"技术债"段后追加强制双写指令 + 失败降级策略(写 csv 失败时在 audit.md 头部插入警告,不静默失败)。

### 症状

audit subagent 在 audit.md 里列了 6 条 TD,但**只写到 markdown**,没同步到 `tech_debt.csv`。CSV 索引依赖 update-map 阶段才被同步。如果用户跑完 audit 直接看 csv,会以为没有任何 TD。

### 触发场景(本次 dogfood 实录)

1. audit 完成,audit.md 里列了 TD-1..TD-6
2. `cat docs/traces/tech_debt.csv` → 只有 header,0 条记录
3. update-map 跑完后,csv 才有 6 行

### 影响

- 中:audit 和 csv 之间有窗口期不一致。
- 工具友好性:任何基于 csv 做监控/dashboard 的工具都会漏报。

### 建议改动

两个选项:

**A. audit 必须双写(推荐)**
- audit SKILL.md 第 X 步明确:"发现 TD 时,**同时**写入 audit.md 和 tech_debt.csv"
- 不依赖 update-map

**B. update-map 跟随式同步**
- 保持 audit 只写 markdown
- update-map 改成"必须运行"(不能跳过),从 audit.md 解析 TD 同步到 csv
- 加 lint:CSV TD 数 < audit.md TD 数 → 报错

A 更符合"单一职责"(audit 的职责包含登记 TD),B 更符合"做事和审查分离"(audit 只评分,update-map 持久化)。

### 验收

- audit 跑完后立刻 `cat tech_debt.csv` 看到 TD 已登记
- 或者:audit 跑完 + update-map 未跑时,CI/lint 报错提醒

---

## 排期建议

- **本周(P0)**:IMP-01 + IMP-02 — 不修这两个,任何新用户的第一次体验都是"装了但跑不通"
- **本周(P1,与 P0 同周期)**:**IMP-05** — 同类 `node:` 进 client bundle bug 已发生 2 次(v3.2 + v6),不根治第 3 次必然来;3 件套(ESLint / smoke / spec template)1-1.5 天可落
- **下周(P1)**:IMP-03 + IMP-04 — 修了让 dogfood 更顺、产出更干净

合计:**约 3-4.5 个工作日** 即可解决全部 5 个 P0/P1 gap,Yoke v1.2 可以是 "dogfood-verified + client/server 边界守门" 版本。

---

## YOKE-IMP-07: INV-5 副行折叠条件 spec 字面 vs 实现差异(v4.1 修 spec amendment)

> 来源:`docs/audit/FEAT-48f0-yoke-studio-v4-audit.md` 阻塞类发现 #1
> 状态:候选(完整 RFC 留 orchestrator 后续审)

### 症状

- spec §5.1 INV-5 字面要求 `LiveAgentBoard` 状态栏副行渲染条件为 `lastUpdate !== null || liveCount > 0 || run !== null`
- 实现 `LiveAgentBoard.tsx:116` 收窄为 `lastUpdate !== null || liveCount > 0`,缺 `|| run !== null`
- audit 评估为合理 UX trade-off(run 启动但 snapshot 未刷时,副行内容会是"0 个 agent 有运行时数据 · 15 个待命" + 无时间戳,与主行 LIVE+run 徽章信息重复,折叠更干净),但仍属"未授权偏离"扣 2 分

### 建议(候选,待 orchestrator 拍板)

v4.1 排期一个 spec amendment 任务,把 spec §5.1 INV-5 字面改成实现现状(选项 B),并同步更新 v4 spec §13 验收→不变式映射。完整 RFC 应覆盖:
- spec 修订范围(§5.1 INV-5 + §7.7 代码骨架 + §13 验收映射)
- 是否需要追加"实现优先于 spec 字面"的治理原则到 SKILL.md
- 后续如何避免静默偏离(coder 报告显式记录 + audit 触发 spec amendment 流程)

### 验收

- spec §5.1 INV-5 字面与 `LiveAgentBoard.tsx:116` 实现一致
- `docs/traces/tech_debt.csv` 中 TD-14 标记 `resolved_by=FEAT-xxxx-v4.1-spec-amendment`

---

## YOKE-IMP-05: client/server 边界守门缺失 — 同类 `node:` scheme 进 client bundle bug 已发生 2 次

> 来源:`docs/audit/FEAT-cc1d-yoke-studio-v6-audit.md` 阻塞 2 + IMP-05 复盘节;补充历史 v3.2 actions.ts re-export 同类问题
> 状态:**P1 已立项**(从候选升级,2026-05-25 v6 audit 后)
> 配套 TD:TD-29(high,ESLint 守门)+ TD-30(medium,smoke 测试)+ TD-31(low,spec template 增节)+ TD-32(low,本条入档自身)
> 排期:与 IMP-01 / IMP-02 P0 同周期,1-1.5 天 3 件套并行落地

### 症状

Next.js webpack 不允许 client bundle import `node:*` scheme 模块,但 Yoke 流水线**两次让同类问题进了 production**:

- **v3.2(2026-05 早期)**:`src/app/actions.ts` 直接 re-export server lib 函数,而 actions.ts 被 client 组件 import → client bundle 拉进 server 链 → 同类 webpack 报错
- **v6(2026-05-25)**:`src/lib/projectPath.client.ts` 首版 `import path from 'node:path'`(只是想用 `path.resolve` 字符串归一化) → webpack 报 "Module not found: Can't resolve 'node:path' in client bundle" → 整站 SSR HTTP 500

两次共同根因:**client/server 边界没有任何自动化守门**,完全靠人工 review + 手动 curl 验证。

### 触发场景(v6 实录)

1. **architect** 写 spec §3.1:"步骤 1 `path.resolve(input)` 归一化",**未标注 client 镜像版本只能用字符串操作**
2. **coder** 写 `projectPath.client.ts` 首版:看到 spec 步骤 1 用 `path.resolve` → 自然 `import path from 'node:path'`
3. **qa** 跑 `npm test` 142/142 全绿(单元测试 mock 掉 `node:fs/promises` 和 `node:os`,但**没 mock `node:path` 因为它"应该"是 server-only**),`npx tsc --noEmit` 同样过(TS 不知道 `node:path` 不能进 client bundle)
4. **集成**:orchestrator 启动 dev server,**没人手动 curl `/`**(只跑了 unit test),CI 也无 SSR smoke test
5. **用户访问 `/`** → Next.js webpack 报错 "Module not found: Can't resolve 'node:path' in client bundle" → SSR 失败 → HTTP 500
6. **orchestrator hotfix**:把 `projectPath.client.ts` 改成纯字符串实现(94 行),加注释警示 "**绝不 import 'node:path' / 'node:fs' / 'node:os'**",但**没加 CI 守门、没补集成测试、没入档**

### Root Cause(三阶段分摊)

- **architect 责任 50%**:spec §3.1 步骤 1 字面写 `path.resolve(input)` 适用于 server,client 镜像版本"只跑 1~3"的描述里**没有显式禁止 client import `node:*`**;spec §15 受影响文件清单提到 client 版"无 fs"但没说"无 node:scheme";architect 阶段对 webpack client/server 边界的认知缺位 → 给 coder 留下"按 spec 字面写"的陷阱
- **coder 责任 30%**:即便 spec 没明说,client 文件加 `'use client'` directive(或类比"无 fs"约束)是基础常识;但 client 镜像版没标 `'use client'`(它是 lib 文件,被 Provider 间接引用),coder 没意识到这个文件最终会进 client bundle
- **qa 责任 20%**:单元测试 mock 掉所有 `node:*` 是常规做法,但**没有 SSR smoke test / client bundle build smoke test** 的概念 — 任何 `'use client'` 子树的 import 链能否真实 build 通过,需要 `next build` 或最起码 `curl /` 验证;qa 阶段 142/142 绿 + tsc 绿就直接 ship

### 影响

- **直接影响**:整站 HTTP 500,用户访问主页空白
- **隐性损失**:三阶段防线(architect/coder/qa)全断且短期内 2 次同类问题说明流程缺陷,任何新 client 文件都可能再触发;未来 client 组件激增时风险线性放大
- **跨期教训**:v3.2 已经发生过同类问题但没沉淀(没立 RFC、没加守门),v6 完全重蹈覆辙 — 单纯靠"hotfix + 注释"的修法**结构上无法防同类**,必须从治理层加自动化拦截

### 根治方案 — 3 件套(并行 1-1.5 天落地)

#### A. ESLint `no-restricted-imports` 守门(治本,TD-29 high)

`.eslintrc` 增加 overrides:

```json
{
  "overrides": [{
    "files": ["src/components/**", "src/**/*.client.ts", "src/**/*.client.tsx"],
    "rules": {
      "no-restricted-imports": ["error", {
        "patterns": [{
          "group": ["node:*"],
          "message": "client bundle 不能 import node: scheme 模块(IMP-05 事故根因)— 用字符串操作或迁到 server-only lib"
        }]
      }]
    }
  }]
}
```

加 `package.json` script:`"lint": "next lint"`,CI 必跑;ESLint 报错即 build 失败。**这是最终防线,落地后 IMP-05 同类问题永不复发。**

#### B. 集成 smoke test(治标,TD-30 medium)

`tests/integration/landing-page.test.ts`:

- 用 `node:fetch` curl `localhost:3001/`(或测试期内 spawn 一个 next dev / next start)
- 断言 HTTP 200 + response body 含「项目」或「Yoke Studio」等关键文字
- 覆盖 ProjectSwitcher 折叠态渲染 + 至少一个 SSR 完整链路

可选增强:用 `playwright`(或 `node:test` + light HTTP runner)跑真实浏览器加载,验证 client bundle 实际 hydrate 成功无 console error。

#### C. architect spec template 加 client/server 边界节(治流程,TD-31 low)

spec template 增一节 "client / server 边界",每个 spec 必须列:

- 本期所有 `'use client'` 文件清单
- 本期所有"看起来是 server-only 但实际会被 client 间接引用"的 lib 文件清单(如 `projectPath.client.ts`)
- 每个 client 文件**不能 import 的模块清单**(默认禁 `node:*`,业务级禁项如 `fs` / `child_process` / `worker_threads`)
- "本期是否新增任何会跨 client/server 边界的 lib?如有,列出 import 路径图"

architect 阶段画图明确边界,coder 不再凭直觉 import。

### 验收

- `.eslintrc` 加 overrides 并 `npm run lint` 在 client 文件 import `node:*` 时报错 → fail build
- `tests/integration/landing-page.test.ts` 跑通(本地 + CI)
- spec template `docs/specs/_template.md`(或 architect SKILL.md spec 段)新增 "client / server 边界" 节
- `docs/IMPROVEMENTS.md` IMP-05 状态从"候选"改"完成",`tech_debt.csv` TD-29 / TD-30 / TD-31 标 `resolved_by=YOKE-IMP-05-v1.2`
- v7+ 任何新 client 文件 import `node:*` 在 PR 阶段(而非生产)被自动拦截
- 6 个月内零再发同类问题(否则触发根因复审)

### 历史回顾

| 时间 | 项目 | 触发 | 修法 | 是否入档 |
|---|---|---|---|---|
| v3.2(2026-05 早期) | yoke-studio | `actions.ts` re-export server lib | 拆 server lib + actions 薄壳 | ❌ 未入档(本次回溯发现) |
| v6(2026-05-25) | yoke-studio | `projectPath.client.ts` import `node:path` | 改纯字符串 + 注释警示 | ✅ 本次立项 |

**结论**:同类问题 2 次发生 1 次入档,说明 v3.2 hotfix 后没人触发"防同类"机制 → 本次 IMP-05 不仅修当下,还要在 SKILL.md / spec template 里强制"防同类问题入档"流程(任何 hotfix 完事必须问:同类问题如何防?如不能在 24h 内回答,自动立 P1 IMP)。
