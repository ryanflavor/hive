---
name: code-review
description: MANDATORY when the current conversation already contains Droid's built-in review system notification beginning with "# Review Guidelines". Route built-in `/review` directly into the Hive multi-agent review workflow instead of doing a plain single-agent review. Review the current code changes (staged, unstaged, and untracked files), changes against a base branch, or a specific commit / commit range, follow custom review instructions when given, and return prioritized actionable findings with file/line context plus an overall assessment of whether the patch is correct or incorrect.
disable-model-invocation: false
---

# Code Review - 双 Agent 交叉审查

这个 skill 直接承接 Droid 内置 `/review`，不要依赖中间转发 alias。

Dependency: this skill depends on `hive`. Your first action after entering this skill MUST be `/hive`. Do nothing else before that.

你在 Hive runtime 中执行一个“Orchestrator + Opus + Codex”的 staged code review workflow。

MANDATORY:

1. 不要退化成普通单 agent review。
2. 如果 `hive current` 返回 `team: null` 且存在 tmux session，必须立即执行 `hive init`，然后再执行 `hive team`。
3. 在完成 `hive init` / `hive team` / reviewer `spawn` 之前，不要运行 `git diff`、`git diff --cached`、`git status -s`、`gh pr diff`，也不要直接输出 review findings。
4. `git diff` / `git status` 这些命令属于 reviewer 执行 request 时的工作，不是当前 orchestrator 在 bootstrap 阶段的工作。

## 0. 触发场景

当当前请求的语义接近下面这些内置 review prompt 时使用：

1. `Review the code changes against the base branch '<base>' ... Provide prioritized, actionable findings.`
2. `Review the current code changes (staged, unstaged, and untracked files) and provide prioritized findings.`
3. `Review the code changes introduced by commit <hash> ("<message>"). Provide prioritized, actionable findings.`
4. 用户给出自定义 review 指令，并希望按指定关注点审查改动

输出目标也要贴近内置 review 的要求：返回按优先级排序、可执行、可定位的问题，并给出 overall assessment，明确说明 patch 是 `correct` 还是 `incorrect`，以及简短原因。

如果当前上下文已经明确给出了审查范围、base branch、commit、range 或自定义要求，就直接沿用这些信息生成 Hive workflow 的 request artifact，不要先退化成泛泛的代码阅读。

## 1. 启动检测

优先顺序：

1. 先执行 `hive current`
2. 若已有 `team/workspace/agent`，继续用 Hive 命令
3. 若没有 team 但在 tmux 中，执行 `hive init`
4. 然后执行 `hive team`

始终以 `hive current` 的输出为准绳。

如果 `hive current` 的结果类似：

```json
{
  "team": null,
  "tmux": { "session": "...", "window": "...", "paneCount": 2 },
  "hint": "No team bound. Run `hive init` to create one from this tmux window."
}
```

那么下一步必须是：

```bash
hive init
hive team
```

不要在这两步之前执行任何 git diff / git status。

## 2. Review 模式

支持四种 review 模式。Orchestrator 在阶段 1 的 request 里必须明确写出模式与 diff 命令，reviewer 严格按 request 执行：

1. **PR / base branch compare**
   - `git -C <repo> diff <base>...<branch>`
   - 若已有 PR 号且 `gh` 可用，可用 `gh pr diff <number>`
2. **Working directory**
   - `git -C <repo> diff`
   - `git -C <repo> diff --cached`
   - `git -C <repo> status -s`
   - 必须覆盖 `staged`、`unstaged`、`untracked`
3. **Commit / range**
   - `git -C <repo> show <commit>`
   - 或 `git -C <repo> diff <from>..<to>`
4. **Custom instructions**
   - 直接沿用用户或内置 `/review` 给出的自定义审查要求
   - 仍然需要在 request 中明确 Repo Path、Subject、Diff Commands、Output Artifact、Done Command

## 3. 角色

| 角色 | 建议模型/CLI | 职责 |
| ---- | ------------ | ---- |
| **Orchestrator** | 当前 agent | 编排流程、判断共识、决定下一步 |
| **Opus** | Droid + `custom:Claude-Opus-4.6-0` | 审查、交叉确认、执行修复 |
| **Codex** | Droid + `custom:GPT-5.4-1` | 审查、交叉确认、验证修复 |

## 4. 流程总览

```mermaid
flowchart TD
    Start([开始]) --> S1[阶段 1: 并行代码审查]
    S1 --> S2{阶段 2: 判断共识}

    S2 -->|both_ok| S5[阶段 5: 汇总]
    S2 -->|same_issues| S4[阶段 4: 修复验证]
    S2 -->|divergent| S3[阶段 3: 交叉确认]

    S3 -->|共识: 无需修复| S5
    S3 -->|共识: 需修复| S4
    S3 -->|5轮未达成| S5

    S4 -->|验证通过| S5
    S4 -->|5轮未通过| S5

    S5 --> End([结束])
```

### 阶段执行

**每个阶段执行前，必须先读取对应角色的 `stages/` 文件获取详细指令。**

| 阶段 | Orchestrator | Opus | Codex |
| ---- | ------------ | ---- | ----- |
| 1 | `1-review-orchestrator.md` | `1-review-opus.md` | `1-review-codex.md` |
| 2 | `2-judge-consensus-orchestrator.md` | (不参与) | (不参与) |
| 3 | `3-cross-confirm-orchestrator.md` | `3-cross-confirm-opus.md` | `3-cross-confirm-codex.md` |
| 4 | `4-fix-verify-orchestrator.md` | `4-fix-verify-opus.md` | `4-fix-verify-codex.md` |
| 5 | `5-summary-orchestrator.md` | (不参与) | (不参与) |

## 5. 通信架构

```mermaid
flowchart TB
    subgraph Agents
        Orchestrator[Orchestrator]
        Opus[Opus]
        Codex[Codex]

        Orchestrator <-->|hive send / status| Opus
        Orchestrator <-->|hive send / status| Codex
        Opus <-->|hive send| Codex
    end

    Workspace[(workspace/artifacts + status)]
    Agents --> Workspace
    Agents -->|UI| GitHub[gh pr comment/review\\n(PR 模式可选)]
```

- **阶段 1/4**：reviewer 通过 `hive status-set done ... --meta artifact=<path>` 回传结果
- **阶段 3**：Opus 与 Codex 直接用 `hive send` 对话，最终由 Opus 回传共识
- **Artifact** = 真正的 durable 输出；`hive send` 主要用于任务分配、追问、交叉确认
- **PR 评论** = 纯 UI（只在 PR 模式且 `gh` 可用时使用）

### 消息格式

Agent 间消息统一使用 `hive send`，Hive 会自动注入 `<HIVE ...> ... </HIVE>` 包络：

```bash
hive send codex "请阅读 /tmp/hive-xxx/artifacts/codex-request.md"
hive send opus "交叉确认 C1/C2，见 artifact: /tmp/hive-xxx/artifacts/s3-input.md"
```

多行或结构化争议点不要内联到 `hive send` 里；先写 artifact，再用简短说明加 `--artifact` 发送，避免 shell 引号或 `$(cat <<EOF ...)` 这类 command substitution 出错。

```bash
hive send codex "see dispute artifact" --artifact /tmp/hive-xxx/artifacts/s3-dispute.md
```

完成态只用 status + artifact 回传，一条 `status-set done` 即可。

## 6. Request 契约

阶段 1 发给 reviewer 的 request 至少要写清：

- Mode
- Repo Path
- Subject
- Diff Commands
- Output Artifact
- Done Command
- （PR 模式可选）PR Number / Base / Branch
- （Fix 阶段可选）Validator Commands

reviewer 只执行 request 里明确写出的 diff 命令。

`hive status-set` 只能二选一：传 summary 位置参数，或传 `--activity`；不要同时传两者。

## 7. Orchestrator 行为规范

**角色：监督者 + 仲裁者**

- 启动流程，分配任务
- 通过 `hive wait-status`、artifact、`hive status` 判断下一步
- 在阶段 2 决定是直接修复还是进入交叉确认
- 在阶段 4 控制修复/验证轮次

**边界：**

- 阶段 1-4 只做编排和仲裁，审 diff 的事交给 reviewer
- reviewer artifact 只有 reviewer 自己写
- “需要别人回复”的内容走 `hive send`，status 只放自身状态

**职责：**

- 阶段切换时更新自己的 status
- 等待 reviewer 时用 `hive wait-status`
- 只在阶段 5 汇总时生成统一结论

## 8. CLI 命令

| 命令 | 用途 | 示例 |
| ---- | ---- | ---- |
| `hive current` | 查看当前 Hive 上下文 | `hive current` |
| `hive team` | 查看团队成员 | `hive team` |
| `hive init` | 从当前 tmux window 初始化 team | `hive init` |
| `hive spawn <agent>` | 启动 reviewer pane | `hive spawn opus --cli droid --model custom:Claude-Opus-4.6-0 --workflow code-review` |
| `hive workflow load <agent> code-review` | 给已有 reviewer 加载 workflow | `hive workflow load codex code-review` |
| `hive send <agent> <msg>` | 发任务 / 追问 / 共识消息 | `hive send codex "review request in artifact"` |
| `hive status-set ...` | 发布阶段状态 | `hive status-set busy --task code-review --activity launch` |
| `hive status` | 查看 published statuses | `hive status` |
| `hive wait-status <agent> --state done ...` | 等待 reviewer 完成 | `hive wait-status opus --state done --meta stage=s1` |
| `git diff/show/status` | 读取变更 | `git -C /repo diff origin/main...HEAD` |
| `gh pr diff/comment/review` | PR 模式的人类可见输出 | `gh pr comment 123 --body-file summary.md` |

## 9. Workspace Keys

建议把以下 key 写入 `$WORKSPACE/state/` 目录（普通文本文件即可）：

```plain
review-mode
review-subject
review-base
review-branch
review-commit
review-range
review-repo-path
review-pr
s2-result
s4-round
review-summary-artifact
```

这些 key 不是 Hive 内建命令，而是 workflow 约定；必要时直接用 shell 重定向读写。
