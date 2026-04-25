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
- `turnPhase` come from transcript/JCL

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

### Turn Phase

`turnPhase` is the exported interface built on top of transcript/JCL signals.
It reports a single token describing the transcript tail. Consumers choose their
own subsets (see `docs/runtime-model.md`):

- `tool_open` — hard-busy (tool_use open)
- `input_backlog` — strategy-level busy (queue has unprocessed enqueues)
- `task_closed` / `turn_closed` — turn collapsed
- `tool_result_pending_reply` — tool result observed, assistant hasn't continued
- `user_prompt_pending` — user prompt observed, assistant hasn't acked
- `assistant_text_idle` — assistant text without stop_reason
- `unknown_evidence` — no reliable probe evidence

Hard busy is a subset of "not closed" but not the only member.

## Claude Code Transcript

Hive expects Claude transcript records in JSONL form and looks at:

- `type`
- `subtype`
- `operation`
- `message.stop_reason`
- `message.content[*].type`

### Signals Used


- queue backlog from `queue-operation`
  - `enqueue` increments backlog
  - `dequeue` / `remove` decrement backlog
  - backlog > 0 => `turnPhase=input_backlog`
- `assistant` with:
  - `stop_reason=tool_use`
  - or any `content[*].type == tool_use`
  - => `turnPhase=tool_open`


- `system.subtype=turn_duration`
- `system.subtype=stop_hook_summary` with `preventedContinuation=false`

Both map to:

- `turnPhase=turn_closed`


- `user` carrying `tool_result`
  - => `tool_result_pending_reply`
- real user text
  - => `user_prompt_pending`
- assistant text without stronger open/close evidence
  - => `assistant_text_idle`

## Codex JCL / Event JSONL

Hive treats Codex session logs as JCL-like event JSONL and looks at:

- top-level `type`
- `payload.type`
- `payload.parsed_cmd`

### Signals Used


- `event_msg.payload.type = task_started`
  - => `turnPhase=tool_open`
- `response_item.payload.type in {function_call, custom_tool_call}`
  - => `turnPhase=tool_open`


- `event_msg.payload.type in {task_complete, turn_aborted}`
  - => `turnPhase=task_closed`


- `event_msg.payload.type in {exec_command_end, mcp_tool_call_end, patch_apply_end}`
  - => `tool_result_pending_reply`
- `response_item.payload.type in {function_call_output, custom_tool_call_output}`
  - => `tool_result_pending_reply`
- `event_msg.payload.type = user_message`
  - => `user_prompt_pending`
- assistant message with text but without stronger evidence
  - => `assistant_text_idle`

## Droid Transcript

Hive treats Droid transcript as message-oriented JSONL and looks at:

- message role
- `content[*].type`
- `tool_use` / `tool_result`

### Signals Used


- assistant message containing `tool_use`
  - => `turnPhase=tool_open`


- none from the simple transcript probe alone


- `tool_result`
  - => `tool_result_pending_reply`
- real user text (ignoring `<system-reminder>`)
  - => `user_prompt_pending`
- assistant text without `tool_use`
  - => `assistant_text_idle`

## What Does Not Count

The following do not count as transcript-derived `busy`:

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
