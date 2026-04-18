# Hive Runtime Model

This document records the current runtime design that Hive actually implements.
It is intentionally narrower than a full architecture spec. The goal is to pin
down the meanings, sources, and intended uses of the runtime fields and deferred
root-delivery behavior that already exist in code.

## Scope

This document covers:

- `busy`
- `inputState`
- `interruptSafety`
- `safetyReason`
- root-message summary/artifact protocol
- `deferred` root delivery
- deferred lifecycle: `unopened` / `opened` / `handled`

This document does not define:

- a semantic global `busy/idle` truth model
- automatic scheduling
- automatic fork/spawn decisions
- automatic garbage collection

For the raw Claude/Codex/Droid transcript and JCL structures that feed these
runtime decisions, see `docs/transcript-signals.md`.

## Runtime Layers

Hive now exposes two different runtime layers on purpose:

1. Output activity layer
2. Interrupt-safety layer

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

### Interrupt-Safety Layer

Fields:

- `interruptSafety: safe | unsafe | unknown`
- `safetyReason: <token>`

Question answered:

- If Hive inserts a new root thread now, does current transcript/JCL evidence
  make that look safe, unsafe, or unknown?

What it is good for:

- deciding whether a root send should become `deferred`
- explaining why Hive treated that target as safe/unsafe/unknown

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

### `interruptSafety`

Source:

- transcript/JCL probe

Current values:

- `safe`
- `unsafe`
- `unknown`

Meaning:

- root-send safety, not output activity

### `safetyReason`

Source:

- specific branch hit inside the transcript/JCL interrupt-safety probe

Current reasons in active use:

- `tool_open`
- `task_closed`
- `turn_closed`
- `input_backlog`
- `tool_result_pending_reply`
- `user_prompt_pending`
- `assistant_text_idle`
- `unknown_evidence`

## Hard Busy vs Interrupt Safety

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

This is the strongest negative evidence Hive currently has.

Hard busy is not currently surfaced as its own public runtime field.

### Interrupt Safety

`interruptSafety` is the normalized interface Hive actually exports and consumes.

It is wider than hard busy:

- `unsafe` includes hard-busy cases such as `tool_open`
- `unsafe` also includes strategy-level non-open cases such as
  `input_backlog`
- `safe` exists for closed-turn/task evidence
- `unknown` covers ambiguous mid-turn states

So:

- hard busy is a subset of `interruptSafety=unsafe`
- `interruptSafety=unsafe` is not limited to hard busy

This distinction matters because `input_backlog` is currently treated as
`unsafe`, but it is not an "open without close" state.

## Current CLI-Specific Interrupt-Safety Evidence

### Claude

`unsafe`:

- `tool_use` open
- queue backlog (`input_backlog`)

`safe`:

- `turn_duration`
- `stop_hook_summary` with `preventedContinuation=false`

`unknown`:

- tool result arrived but assistant has not clearly continued
- real user prompt pending
- assistant text without stronger closing/opening evidence

### Codex

`unsafe`:

- `task_started` without `task_complete` / `turn_aborted`
- `function_call` / `custom_tool_call` without matching output

`safe`:

- `task_complete`
- `turn_aborted`

`unknown`:

- tool output just returned
- user prompt pending
- assistant text without stronger closing/opening evidence

### Droid

`unsafe`:

- `tool_use` block without matching `tool_result`

`safe`:

- none from the simple message-shape probe alone

`unknown`:

- tool result just arrived
- real user text pending
- assistant text without `tool_use`

## Root Send Protocol

Root sends are messages without `--reply-to`.

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

## Deferred Root Delivery

When a root send targets a member whose current `interruptSafety` is `unsafe`,
Hive currently:

1. accepts the send
2. stores the message durably in the bus/artifact layer
3. returns `state=deferred` to the sender
4. still injects the normal short Hive message to the receiver pane

So `deferred` currently means:

- accepted by Hive
- marked for delayed review/tracking
- not rejected

It does not mean:

- automatic rerouting
- automatic fork/spawn
- a separate message protocol

## Deferred Lifecycle

Deferred roots are tracked with three states:

- `unopened`
- `opened`
- `handled`

### `unopened`

The deferred root exists, but Hive has not yet observed the receiver open the
artifact.

### `opened`

Hive observed the receiver read the deferred artifact through transcript/JCL
evidence.

Current matching rules:

- Claude: `Read(file_path == artifact_path)`
- Codex: parsed command classified as `read` with `path == artifact_path`
- Droid: `Read(file_path == artifact_path)`

This is transcript/JCL-based observation, not a filesystem read detector.

### `handled`

Hive observed an explicit thread action on that deferred root:

- reply with `--reply-to`
- handoff along that root thread

`handled` is explicit. `opened` is observed.

## Why There Is Only One Runtime Doc

This design was split many times during discussion, but the stable part that
actually shipped is small enough to keep in one place:

- output activity
- interrupt safety
- root protocol
- deferred lifecycle

Keeping these together reduces drift between overlapping docs.
