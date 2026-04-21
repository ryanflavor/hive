---
name: gang
description: GANG entry skill. 用户打 /gang 表示要把当前 pane 升级成 GANG orchestrator 并启动 gang 闭环。skill 内容 = 跑 `hive gang init`,把当前 pane 搬到新 window,布好 board + skeptic,并自动 dispatch /gang-orch 接管 duty。
---

# GANG — entry

你被 `/gang` 触发,用户要启动 GANG 闭环。**你做一件事**:在当前 pane 执行:

```bash
hive gang init
```

完事。剩下全部由 `hive gang init` 内部负责:

- `tmux break-pane` 把当前 pane 搬到新 window `gang`(orch 身份随当前 CLI 带过去)
- 按屏幕宽高 auto-pick 横 / 竖屏 layout
- spawn **skeptic**(anti-orch 家族 CLI,claude↔codex;droid 默认 claude)
- spawn **board**(vim 打开 BLACKBOARD.md)
- dispatch `/gang-orch` 给 orch pane → 你之后的 duty 由 `gang-orch` skill 接管,本 skill 退场

## 前置

- **当前 pane 正在跑 agent CLI**(claude / codex / droid),不是光秃秃 shell
- **workspace 已经 `hive init`**(未 init 时 `hive gang init` 会报错提示)

## 不做什么

- 不要自己 `tmux new-window` / `split-window` —— `hive gang init` 负责
- 不要手工 spawn skeptic / board —— 同上
- 不要在这个 skill 里做 planning / 拆 feature —— planning 由 `gang-orch` 接管后再做
- 不要问用户要 workspace 路径 / agent name —— 都从当前 pane 上下文推断

## 报错兜底

- `hive: command not found` → 告诉用户 `pipx install git+https://github.com/notdp/hive.git`
- 报 "not an agent pane" → 当前 pane 不是 agent CLI,换到跑着 claude/codex/droid 的 pane 再 `/gang`
- 报 "workspace not initialized" → 提示用户先 `hive init`

## 模型异质

`hive gang init` 默认会用 anti-orch 家族 CLI 起 skeptic(claude↔codex;droid 默认 claude)。若当前 CLI 是 droid 但跑的是 Anthropic 模型(opus / sonnet),显式 override:

```bash
hive gang init --peer-cli codex
```
