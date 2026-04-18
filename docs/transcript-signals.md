# Transcript Signal Model

This document explains the CLI-specific transcript/JCL evidence Hive currently
uses for runtime decisions.

It exists to answer a narrow question:

- What do Claude Code, Codex, and Droid transcripts actually look like?
- Which events count as open/close/read signals in current code?

It does not define tmux output activity. `busy` is documented separately in
`docs/runtime-model.md` because `busy` does not come from transcript parsing.

## Important Clarification

Hive currently does **not** compute `busy` from transcript/JCL.

Current split:

- `busy` comes from tmux control-mode output activity
- `interruptSafety` / `safetyReason` come from transcript/JCL
- deferred `opened` detection also comes from transcript/JCL

So if someone remembers an earlier “JSONL busy” discussion, that was design
reasoning, not the shipped public field.

## Concepts

### Open / Close

The strongest transcript signal Hive uses is an open-without-close pattern:

- an open event starts some work
- a close event ends that work
- open without close is strong negative evidence

This is the basis for the internal reasoning concept often described as
"hard busy".

### Hard Busy

`hard busy` is not a public field. It is a reasoning concept:

- a tool/task open event exists
- the corresponding close event has not appeared yet

Examples:

- Claude: `tool_use` without matching `tool_result`
- Codex: `task_started` without `task_complete` / `turn_aborted`
- Codex: `function_call` / `custom_tool_call` without matching output
- Droid: `tool_use` without matching `tool_result`

### Interrupt Safety

`interruptSafety` is the exported interface built on top of transcript/JCL
signals.

It has three values:

- `safe`
- `unsafe`
- `unknown`

It is wider than hard busy:

- hard busy feeds into `unsafe`
- close evidence feeds into `safe`
- ambiguous mid-turn states feed into `unknown`
- some strategy-level cases such as `input_backlog` also feed into `unsafe`

So:

- hard busy is a subset of `interruptSafety=unsafe`
- `interruptSafety=unsafe` is not limited to hard busy

## Claude Code Transcript

Hive expects Claude transcript records in JSONL form and looks at:

- `type`
- `subtype`
- `operation`
- `message.stop_reason`
- `message.content[*].type`

### Signals Used

#### Unsafe

- queue backlog from `queue-operation`
  - `enqueue` increments backlog
  - `dequeue` / `remove` decrement backlog
  - backlog > 0 => `interruptSafety=unsafe`, `safetyReason=input_backlog`
- `assistant` with:
  - `stop_reason=tool_use`
  - or any `content[*].type == tool_use`
  - => `interruptSafety=unsafe`, `safetyReason=tool_open`

#### Safe

- `system.subtype=turn_duration`
- `system.subtype=stop_hook_summary` with `preventedContinuation=false`

Both map to:

- `interruptSafety=safe`
- `safetyReason=turn_closed`

#### Unknown

- `user` carrying `tool_result`
  - => `tool_result_pending_reply`
- real user text
  - => `user_prompt_pending`
- assistant text without stronger open/close evidence
  - => `assistant_text_idle`

### Artifact Opened Detection

Hive treats the artifact as opened when Claude transcript shows:

- `assistant`
- `tool_use`
- tool name `Read`
- `input.file_path == artifact_path`

Nothing else counts as opened.

## Codex JCL / Event JSONL

Hive treats Codex session logs as JCL-like event JSONL and looks at:

- top-level `type`
- `payload.type`
- `payload.parsed_cmd`

### Signals Used

#### Unsafe

- `event_msg.payload.type = task_started`
  - => `interruptSafety=unsafe`, `safetyReason=tool_open`
- `response_item.payload.type in {function_call, custom_tool_call}`
  - => `interruptSafety=unsafe`, `safetyReason=tool_open`

#### Safe

- `event_msg.payload.type in {task_complete, turn_aborted}`
  - => `interruptSafety=safe`, `safetyReason=task_closed`

#### Unknown

- `event_msg.payload.type in {exec_command_end, mcp_tool_call_end, patch_apply_end}`
  - => `tool_result_pending_reply`
- `response_item.payload.type in {function_call_output, custom_tool_call_output}`
  - => `tool_result_pending_reply`
- `event_msg.payload.type = user_message`
  - => `user_prompt_pending`
- assistant message with text but without stronger evidence
  - => `assistant_text_idle`

### Artifact Opened Detection

Hive treats the artifact as opened when Codex log shows:

- `event_msg`
- `payload.type = exec_command_end`
- `payload.parsed_cmd[*].type = read`
- `payload.parsed_cmd[*].path == artifact_path`

This is stricter than “a shell command happened to mention the file”.

## Droid Transcript

Hive treats Droid transcript as message-oriented JSONL and looks at:

- message role
- `content[*].type`
- `tool_use` / `tool_result`

### Signals Used

#### Unsafe

- assistant message containing `tool_use`
  - => `interruptSafety=unsafe`, `safetyReason=tool_open`

#### Safe

- none from the simple transcript probe alone

#### Unknown

- `tool_result`
  - => `tool_result_pending_reply`
- real user text (ignoring `<system-reminder>`)
  - => `user_prompt_pending`
- assistant text without `tool_use`
  - => `assistant_text_idle`

### Artifact Opened Detection

Hive treats the artifact as opened when Droid transcript shows:

- assistant message
- `tool_use`
- tool name `Read`
- `input.file_path == artifact_path`

## What Does Not Count

The following do not count as opened in current code:

- filesystem access time
- editor previews
- shell grep/search mentioning msgId or content
- directory listing
- management commands such as move/remove
- arbitrary shell commands unless they are normalized into the exact supported
  read structure

The following also do not count as transcript-derived `busy`:

- any transcript tail heuristic on its own
- any single “there was output” observation

That is why `busy` remains tmux-based rather than transcript-based.

## Why Two Docs

`docs/runtime-model.md` answers:

- what public runtime fields exist
- what they mean
- what uses them

This document answers:

- what raw transcript/JCL structures exist
- which exact events currently map into those runtime fields
