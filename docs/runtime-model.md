# Hive Runtime Model

This document records the current runtime design that Hive actually implements.
It is intentionally narrower than a full architecture spec. The goal is to pin
down the meanings, sources, and intended uses of the runtime fields and
active-turn fork routing that already exist in code.

## Scope

This document covers:

- `busy`
- `inputState`
- `turnPhase`
- root-message summary/artifact protocol
- active-turn fork routing

This document does not define:

- a semantic global `busy/idle` truth model
- automatic scheduling
- automatic fork/spawn decisions
- automatic garbage collection

For the raw Claude/Codex/Droid transcript and JCL structures that feed these
runtime decisions, see `docs/transcript-signals.md`.

## Runtime Layers

Hive now exposes two different runtime layers on purpose:

1. Output activity layer (`busy`)
2. Turn phase layer (`turnPhase`)

They answer different questions and should not be conflated.

### Output Activity Layer

Field:

- `busy: true | false`

Question answered:

- Has this pane produced tmux-visible output in the last 3 seconds?

What it is good for:

- lightweight live activity display
- knowing whether a pane is currently emitting output

What it is not:

- not a semantic "agent is definitely busy"
- not a safe-to-interrupt truth value

### Turn Phase Layer

Field:

- `turnPhase: <token>`

Question answered:

- What phase of a turn does the receiver's transcript tail currently show?

What it is good for:

- deciding whether to fork the target or direct-send
- explaining why Hive treated that target as it did

What it is not:

- not the same thing as pane output activity
- not the same thing as a universal busy/idle truth model

## Runtime Field Reference

### `busy`

Source:

- tmux control mode output stream
- implementation: `tmux.ControlModeOutputMonitor`

Current rule:

- `busy=true` when Hive observed pane output within the last `3s`
- `busy=false` otherwise

Notes:

- `busy` is output-based
- it is intentionally fast and shallow
- it does not come from transcript/JCL parsing

### `inputState`

Source:

- transcript gate inspection via `check_input_gate()`

Current values:

- `ready`
- `waiting_user`
- `unknown`
- `offline`

Meaning:

- whether the agent is currently waiting for a user answer

Important consumer:

- `hive answer`

### `turnPhase`

Source:

- transcript/JCL probe (last observed transcript state)

Current values:

- `tool_open`
- `task_closed`
- `turn_closed`
- `input_backlog`
- `tool_result_pending_reply`
- `user_prompt_pending`
- `assistant_text_idle`
- `unknown_evidence`

Meaning:

- the phase the receiver's turn is in, as seen in the transcript tail
- consumers pick the subsets they care about (see "Consumer Subsets" below)

## Hard Busy vs Turn Phase

These are related, but they are not the same concept.

### Hard Busy

`hard busy` is a reasoning concept, not a public field. It means:

- a tool/task open event has happened
- the corresponding close event has not happened yet

Examples:

- Claude: `tool_use` without matching `tool_result`
- Codex: `task_started` without `task_complete` / `turn_aborted`
- Codex: `function_call` / `custom_tool_call` without matching output
- Droid: `tool_use` without matching `tool_result`

In `turnPhase` terms, hard busy surfaces as `tool_open`. `input_backlog` is a
strategy-level non-open state that also matters to consumers but is not hard
busy.

Hard busy is not currently surfaced as its own public runtime field.

## Consumer Subsets of `turnPhase`

One decision site inside Hive reads `turnPhase` directly:

- Fork selector in root send (`cli._maybe_route_busy_root_send`):
  - `turnPhase ∈ {task_closed, turn_closed}` → never fork (turn already closed)
  - `busy=False ∧ turnPhase ∈ {tool_open, user_prompt_pending, tool_result_pending_reply}` → fork (hard unclosed even though pane is idle)
  - otherwise, fork only when `busy=True`

## Current CLI-Specific Evidence

Each row maps a transcript/JCL observation to the emitted `turnPhase` value.

### Claude

- `tool_open` — `tool_use` open
- `input_backlog` — queue backlog observed
- `turn_closed` — `turn_duration` or `stop_hook_summary` with `preventedContinuation=false`
- `tool_result_pending_reply` — tool result arrived but assistant has not clearly continued
- `user_prompt_pending` — real user prompt pending
- `assistant_text_idle` — assistant text without stronger closing/opening evidence

### Codex

- `tool_open` — `task_started` without `task_complete` / `turn_aborted`, or `function_call` / `custom_tool_call` without matching output
- `task_closed` — `task_complete` or `turn_aborted`
- `tool_result_pending_reply` — tool output just returned
- `user_prompt_pending` — user prompt pending
- `assistant_text_idle` — assistant text without stronger closing/opening evidence

### Droid

- `tool_open` — `tool_use` block without matching `tool_result`
- `tool_result_pending_reply` — tool result just arrived
- `user_prompt_pending` — real user text pending
- `assistant_text_idle` — assistant text without `tool_use`

Droid's simple message-shape probe does not currently emit `task_closed` / `turn_closed`.

## Root Send Protocol

Root sends are every `hive send`; the command no longer accepts
`--reply-to`. Continuing an existing thread is done via `hive reply`
(which always carries a `replyTo` and is therefore not subject to the
root protocol).

Hive enforces a two-layer protocol for root sends:

- `body`: short summary only
- `artifact`: detailed content

Current root-body hard failures:

- body longer than `500` chars
- body with `3+` lines
- body containing fenced code
- body lines starting with markdown heading/list markers:
  - `# `
  - `- `
  - `* `

This rule applies to root sends. Replies are not subject to these summary-body
limits.

## Active-Turn Fork Routing

When a root send's target is in an active turn — `busy=true`, or
`turnPhase ∈ {tool_open, user_prompt_pending, tool_result_pending_reply}`
even when `busy=false` — Hive automatically forks a clone pane (named
`<target>-c1`, `-c2`, ...) and routes the message there. The clone is
spawned with a boundary system block; the original target is never
interrupted.

Three bypass exemptions skip the fork and deliver to the original target
directly:

1. peer relationship (`sender.peer == target`, symmetric)
2. owner parent → child (`sender == target.@hive-owner`)
3. child → parent owner (`target == sender.@hive-owner`)

When a fork happens, the routing return payload carries:

- `routingMode=fork_handoff`
- `routingReason=active_turn_fork`
- `forkedFromPane`
- `forkedToPane`

`turnPhase ∈ {task_closed, turn_closed}` never forks: the turn is already
closed, so the message goes straight to the original target.

## Why There Is Only One Runtime Doc

This design was split many times during discussion, but the stable part that
actually shipped is small enough to keep in one place:

- output activity
- interrupt safety
- root protocol
- active-turn fork routing

Keeping these together reduces drift between overlapping docs.
