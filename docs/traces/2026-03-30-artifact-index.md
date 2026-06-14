# FEAT-0330-artifact-index: 开发产物统一索引体系

## 当前产品状态（Before）
> 来源：yoke 插件内部架构

元数据存储在每个 trace markdown 文件的 YAML frontmatter 中，由 `/update-map` 写入，`generate-map.ts` 读取并生成 `MAP.md`。FEAT-ID 采用 `FEAT-{NNN}` 递增序号（并行易冲突、无语义）。trace 文件名为 `YYYY-MM-DD-{feature}.md`（AI 生成 slug 质量不稳定、无 FEAT-ID、按日期排序无功能归类）。Architect 输出 `docs/specs/FEAT-{NNN}.spec.md`，audit 输出 `docs/audit/FEAT-{NNN}-audit.md`。

## 场景

> 张三和用户是同一团队的开发者，同时在用 yoke 开发同一个项目。张三用 `/trace` 注册了一个需求，拿到 `FEAT-003`。与此同时，用户在另一个分支也用 `/trace` 注册了需求，也拿到 `FEAT-003`——因为两人各自读 MAP.md 时看到的最大编号都是 002。合并时 ID 冲突了。
>
> 另外，张三想找"那个跟通知闪烁相关的 trace"，但文件名是 `2026-03-28-fix-display.md`，完全看不出内容。他只能逐个打开文件找。
>
> 变更后：张三的需求注册为 `BUG-e1c2-toast-flicker`（内容哈希，不可能冲突），用户的注册为 `FEAT-a3f7-rate-limit`。张三想找价格相关的 trace，运行搜索脚本 `python3 search.py "price flicker"`，直接定位到目标文档。

## 关键规则
- CSV 是唯一元数据源，trace/spec/audit markdown 文件不再包含 YAML frontmatter
- FEAT-ID 格式改为 `{TYPE}-{4位内容哈希}-{短语义}`，TYPE 为 FEAT/BUG/REFACTOR/PATCH，并行安全、幂等
- `generate-map.ts` 废弃，由 `search.py --generate-map` 替代
- 搜索脚本放在 yoke 插件 `scripts/` 中，复用 ui-ux-pro-max 的 BM25 算法
- 用户项目只有 `docs/traces/*.csv` + 各 markdown 文件
- 多张 CSV 关系型设计，按 domain 分表

## 验收标准
- [ ] 新 FEAT-ID 格式：`{TYPE}-{4hex}-{slug}`，对相同输入幂等
- [ ] 多表 CSV 索引覆盖 trace、spec、audit 三类文档及其关联数据（files、tests、apis、tech_debt）
- [ ] BM25 搜索脚本支持按 type/module/status/关键词/domain 检索
- [ ] 搜索脚本支持 `--generate-map` 输出 MAP.md，替代 `generate-map.ts`
- [ ] `/trace`、`/architect`、`/audit`、`/coder` 四个 skill 更新为写 CSV + 新命名
- [ ] `/update-map` 更新为写 CSV 而非 frontmatter
- [ ] `/digest`、`/explore`、`/pipeline` 中引用 trace 路径/格式的地方同步更新
- [ ] 搜索脚本支持 `--json` 输出格式

## Non-Goals（刻意不做）
- 不引入 SQLite 或向量数据库——CSV + BM25 够用
- 不改动产品文档体系（`docs/product/`）——三层结构不变
- 不为搜索脚本加 Web UI 或 API 服务
- 不做现有项目自动迁移脚本（首版手动或按需补充）

## 受影响的 Skill

| Skill | 改动 |
|-------|------|
| `/trace` | 新 ID 生成逻辑（内容哈希）+ 写 index.csv + 新文件命名 |
| `/architect` | 读 index.csv 获取 trace 元数据 + spec 文件新命名 + 写 index.csv（phase=spec） |
| `/audit` | 读 index.csv + audit 文件新命名 + 写 index.csv（phase=audit, status） |
| `/coder` | STUCK 报告新命名 |
| `/update-map` | 写 CSV 各表替代写 frontmatter；调用 search.py --generate-map 替代 generate-map.ts |
| `/pipeline` | 引用路径格式更新 |
| `/digest` | 读 CSV 替代读 frontmatter |
| `/explore` | 读 CSV 替代读 frontmatter |

## 新增文件

| 文件 | 位置 | 说明 |
|------|------|------|
| `search.py` | yoke 插件 `scripts/` | BM25 搜索引擎（复用 ui-ux-pro-max 的 core 算法） |

## 用户项目 CSV 结构

```
docs/traces/
├── index.csv        <- 主表
├── files.csv        <- 文件关联表
├── tests.csv        <- 测试关联表
├── apis.csv         <- API 关联表
├── tech_debt.csv    <- 技术债表
└── *.md             <- trace/spec/audit 纯内容文档
```

### index.csv（主表）

```csv
id,type,phase,module,component,title,keywords,status,author,date,file,depends_on,depended_by
FEAT-a3f7-trace-naming,FEAT,trace,yoke,trace,Trace命名优化,"trace naming convention search",confirmed,anonymous,2026-03-30,docs/traces/FEAT-a3f7-trace-naming.md,,
FEAT-a3f7-trace-naming,FEAT,spec,yoke,trace,Trace命名优化合约,"trace naming spec",drafted,anonymous,2026-03-30,docs/specs/FEAT-a3f7-trace-naming.spec.md,,
FEAT-a3f7-trace-naming,FEAT,audit,yoke,trace,Trace命名优化审计,"trace naming audit",pass,anonymous,2026-03-31,docs/audit/FEAT-a3f7-trace-naming-audit.md,,
```

### files.csv（文件关联表）

```csv
feat_id,path,desc,lines
FEAT-a3f7-trace-naming,scripts/search.py,BM25 搜索引擎,200
FEAT-a3f7-trace-naming,skills/trace/SKILL.md,需求接收 skill,210
```

### tests.csv（测试关联表）

```csv
feat_id,path,count
FEAT-a3f7-trace-naming,tests/search.test.ts,12
```

### apis.csv（API 关联表）

```csv
feat_id,method,path,desc
FEAT-e1c2-notif-api,GET,/api/notifications,获取实时通知列表
FEAT-e1c2-notif-api,POST,/api/tasks,创建任务
```

### tech_debt.csv（技术债表）

```csv
feat_id,td_id,priority,desc,added,resolved_by
FEAT-e1c2-notif-api,TD-001,高,缺少 WebSocket 错误重试,2026-03-28,
```

## 搜索脚本能力

```bash
# 按关键词搜 trace
python3 search.py "price flicker"

# 按模块筛选
python3 search.py --module trading --status confirmed

# 查某个 API 被哪些 FEAT 用到
python3 search.py --domain apis "tasks"

# 查技术债
python3 search.py --domain tech_debt --priority 高

# 生成 MAP.md（替代 generate-map.ts）
python3 search.py --generate-map

# JSON 输出供脚本消费
python3 search.py "price" --json
```

## 废弃项
- `scripts/generate-map.ts` — 由 `search.py --generate-map` 替代
- trace markdown 中的 YAML frontmatter — 由 CSV 主表替代
- `FEAT-{NNN}` 递增序号 — 由 `{TYPE}-{4hex}-{slug}` 替代
- `YYYY-MM-DD-{feature}.md` 文件命名 — 由 `{TYPE}-{4hex}-{slug}.md` 替代

## Open Issues（待决问题）
- `depends_on` / `depended_by` 是否需要单独一张关系表？当前放在 index.csv 中用逗号分隔值，复杂场景可能不够
- 搜索脚本是否需要支持跨表 join 查询（如"找所有有高优技术债且状态为 done 的 FEAT"）？
- `yoke.map.config.json` 中的 domain 配置是否需要适配新的 CSV 结构？
