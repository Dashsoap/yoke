# FEAT-1ff0-skill-execution-observability: Harness Hardening

## 当前产品状态（Before）
> 来源：yoke 插件 skills/ 目录

Yoke 的 7 个核心 skill 组成开发流水线。当前存在三类问题：
1. /audit 的不变式违反只"标记"不硬拒，最后防线有漏洞
2. /pipeline 未定义子 agent 调度协议，phase 间上下文丢失
3. 测试执行规则在 3 个 skill 中重复定义，措辞不一致

## 场景

> 张三用 yoke 开发一个完整级组件。/coder 实现了代码，测试全部通过。
> /audit 打了 85 分，但报告中标记了一个不变式违反（在某个罕见状态路径上）。
> 由于 85 >= 80，/audit 判定"通过"。代码合并上线。
>
> 一周后，生产环境触发了那个罕见状态路径，业务规则被违反。
>
> 变更后：/audit 检测到不变式违反，无条件硬拒。coder 必须修复后才能通过。

## 关键规则
- /audit 严重问题（不变式违反、安全漏洞、AI 护栏缺失）= 无条件硬拒
- /pipeline 定义标准化的子 agent 调度协议（传什么、返回什么）
- 测试执行规则以 /pipeline 为唯一来源
- execution-log 为 best-effort，不阻塞流水线

## 验收标准
- [x] /audit 决策逻辑中，严重问题检查在分数检查之前
- [x] /audit 严重问题列表用 HARD-GATE 标记
- [x] /pipeline 包含子 agent 调度协议段（传入格式 + 返回格式）
- [x] /pipeline 各 Phase 引用调度协议而非自由描述
- [x] /coder 末尾定义结构化完成摘要格式
- [x] /trace 需求模板包含 Baseline 哈希段
- [x] /pipeline Phase 0 创建 execution-log.json
- [x] /pipeline Phase 7 从 execution-log 生成报告
- [x] /qa 和 /coder 的测试执行规则引用 /pipeline 而非重复定义

## Non-Goals（刻意不做）
- 不接 OTel / Langfuse 等外部观测平台
- 不加 AC-{N} 编号或 spec-coverage 注释（agent 不可靠维护）
- 不修改 /architect、/origin、/explore、/digest、/migrate
- 不为 /update-map 添加新的验证步骤

## 受影响的 Skill

| Skill | 改动类型 |
|-------|---------|
| /audit | BUG 修复：严重问题硬拒 + HARD-GATE 标记 |
| /pipeline | 增强：调度协议 + execution-log + Phase 7 改用 log 生成报告 |
| /coder | 增强：结构化完成摘要 |
| /trace | 增强：Baseline 哈希段 |
| /qa | 重构：测试规则引用 pipeline |

## 模式
plugin-internal
