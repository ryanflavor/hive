---
source: https://www.anthropic.com/research/swe-bench-sonnet
fetched: 2026-04-19
author: Anthropic (Erik Schluntz)
published: 2025-01-06
---

# Raising the Bar on SWE-bench Verified with Claude 3.5 Sonnet

## Why this sits in the harness bucket

This is the article that introduced the **scaffold / agent-system distinction** in Anthropic's own voice. "Scaffold" here is a near-synonym for "harness" (Anthropic's later writing uses "harness" as the more precise term — see `managed-agents.md`). The key claim: SWE-bench measures the *combined* system — model + surrounding code — not the model alone.

See also: `writing-tools-for-agents.md` (tool-surface design), `managed-agents.md` (the formal harness definition).

## Verbatim quotes

> "SWE-bench doesn't just evaluate the AI model in isolation, but rather an entire 'agent' system."

> "an 'agent' refers to the combination of an AI model and the software scaffolding around it."

> "This scaffolding is responsible for generating the prompts that go into the model, parsing the model's output to take action, and managing the interaction loop where the result of the model's previous action is incorporated into its next prompt."

> "The performance of an agent on SWE-bench can vary significantly based on this scaffolding, even when using the same underlying AI model."

> "The agent has a prompt, a Bash Tool for executing bash commands, and an Edit Tool, for viewing and editing files and directories."

> "We put a lot of effort into the descriptions and specs for these tools across a wide variety of agentic tasks."

> "We believe that much more attention should go into designing tool interfaces for models, in the same way that a large amount of attention goes into designing tool interfaces for humans."

## Minimal scaffold Anthropic shipped for SWE-bench

- **One system prompt**
- **One Bash tool** (execute bash commands)
- **One Edit tool** (view and edit files/directories)
- **A loop** that feeds tool results back as the next prompt

That is Anthropic's reference minimum for an agent harness. Everything beyond it is optional complexity that has to earn its place.

## Signal for Hive

- **Scaffold decides outcomes as much as model does.** This is the source citation for the "harness design is key" claim Anthropic repeats in later work. For Hive, it means pane layout, send/reply discipline, and worktree hygiene are not decoration — they are the thing being evaluated.
- **Tool interface design is named as the under-invested lever.** Hive's built-in "tools" are `send`, `reply`, `handoff`, `spawn`, `fork`, plus whichever tools each pane's agent happens to carry. The outward-facing contract (what the orchestrator can invoke on other panes) deserves the same care as an Edit/Bash tool.
- **"Minimum viable scaffold".** Hive should be able to justify every pane and every helper above Anthropic's 2-tool minimum. If a helper is there because Sonnet 4.5 once struggled with something Opus 4.7 handles natively, it is the "dead weight" from `managed-agents.md`.

## NOTE

Publication date is from the article footer as surfaced by WebFetch. The "minimum viable scaffold" section above is synthesized from the fetched quotes, not lifted verbatim.
