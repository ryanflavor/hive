---
name: cross-review
description: 基于 Hive 协作面做交叉代码审查。适用于需要双视角 review、风险归纳、以及以 status + artifact 回传结论的场景。
disable-model-invocation: true
---

# Cross Review

你在 Hive runtime 中执行交叉代码审查。

## 目标

1. 阅读指定变更或上下文
2. 归纳 correctness / risk / follow-up
3. 把最终结论写成 artifact
4. 用 `hive status-set done ... --meta artifact=<path>` 回传

## 输出格式

- Summary
- Findings
- Risks
- Follow-up

## 协作约束

- 优先通过 `hive status-set` 回传完成态
- 非必要不要再补一条重复的 `hive send ... complete`
- 如果需要额外上下文，再使用 `hive send`
