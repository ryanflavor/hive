---
source: https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously
fetched: 2026-04-19
author: Anthropic
published: 2025-09-29
---

# Enabling Claude Code to Work More Autonomously

## Why this matters for harness questions

This announcement is where Anthropic first packages "checkpoints + subagents + hooks + background tasks" together as the autonomy surface of Claude Code. It does not use the word "harness", but every capability it adds is a **harness-layer** concern under the `managed-agents.md` definition ("the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure"). Together these features are what make Claude Code the specific harness that Anthropic then points to everywhere else.

## Verbatim quotes

> "Claude Code is now more capable of handling sophisticated tasks."

> "Checkpoints let you pursue more ambitious and wide-scale tasks knowing you can always return to a prior code state."

> "Subagents delegate specialized tasks—like spinning up a backend API while the main agent builds the frontend—allowing parallel development workflows"

> "Hooks automatically trigger actions at specific points, such as running your test suite after code changes or linting before commits"

> "Background tasks keep long-running processes like dev servers active without blocking Claude Code's progress on other work"

> "Together, these capabilities let you confidently delegate broad tasks like extensive refactors or feature exploration to Claude Code."

> "Checkpoints apply to Claude's edits and not user edits or bash commands, and we recommend using them in combination with version control."

## How each feature maps to the harness definition

| Feature announced | Harness role |
| --- | --- |
| Checkpoints | State rollback — recovering from harness failure (see `managed-agents.md`) |
| Subagents | Delegation primitive; scoped context and tool restrictions (see `sub-agents.md`) |
| Hooks | Event-triggered routing — "routes Claude's tool calls to the relevant infrastructure" |
| Background tasks | Long-running process lifetime, separate from Claude's turn loop |

## Signal for Hive

- Hive's four panes are the spiritual parallel to this feature set: pane-as-subagent + pane-as-background-task + Hive hooks + git worktree checkpointing. Hive already delivers all four, just at the workspace level rather than inside one Claude Code process.
- **Checkpoints apply only to Claude's edits.** Hive users who edit in a terminal pane outside the orchestrator's control are outside the checkpoint envelope. This is the same asymmetry Anthropic calls out — worth surfacing in Hive docs.
- **Hooks as harness routing.** Anthropic's framing is that hooks are part of the harness, not the agent. If Hive wants per-pane hooks (pre-send, post-reply, validator-pass), they belong in Hive's code paths, not in each agent's prompt.

## NOTE

WebFetch returned a compact set of verbatim quotes plus a short summary paragraph. No quotes were invented; the table above is synthesized.
