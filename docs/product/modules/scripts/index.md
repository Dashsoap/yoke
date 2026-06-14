# scripts 模块

> 工具脚本,辅助 SKILL 执行。

## 组件索引

| 组件 | 描述 |
|---|---|
| `search.py` | 用 BM25 算法搜 trace 文档 + 生成内容哈希 FEAT-ID |

## 已知限制

- search.py 在 Python 3 环境下跑,要求目标项目可执行 python3
- FEAT-ID 用标题内容哈希前 4 位 + slug,可能跨语言碰撞(低概率)
