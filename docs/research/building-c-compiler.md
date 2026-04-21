---
source: https://www.anthropic.com/engineering/building-c-compiler
fetched: 2026-04-19
author: Anthropic (Nicholas Carlini)
published: 2026-02-05
---

# Building a C Compiler with a Team of Parallel Claudes

## Why this is in the harness bucket

This is Anthropic's most concrete public demo of a **multi-agent harness running unattended** — 16 parallel Claudes cooperating on a single codebase over many sessions to build a C compiler. The article explicitly calls the surrounding code a "harness" and documents the file-system-based coordination scheme.

See also: `multi-agent-research-system.md`, `effective-harnesses-for-long-running-agents.md`.

## Verbatim quotes — harness mentions

> "To stress test it, I tasked 16 agents with writing a Rust-based C compiler, from scratch, capable of compiling the Linux kernel."

> "I built a harness that sticks Claude in a simple loop (if you've seen Ralph-loop, this should look familiar)."

> "The scaffolding runs Claude in a loop, but that loop is only useful if Claude can tell how to make progress."

> "Most of my effort went into designing the environment around Claude—the tests, the environment, the feedback—so that it could orient itself without me."

> "To help Claude help itself, I included instructions to maintain extensive READMEs and progress files that should be updated frequently with the current status."

## How the 16 agents coordinate

> "Each agent clones a local copy to `/workspace`, and when it's done, pushes from its own local container to upstream."

> "To prevent two agents from trying to solve the same problem at the same time, the harness uses a simple synchronization algorithm"

> "Claude takes a 'lock' on a task by writing a text file to current_tasks/"

> "Claude works on the task, then pulls from upstream, merges changes from other agents, pushes its changes, and removes the lock."

> "The infinite agent-generation-loop spawns a new Claude Code session in a fresh container"

> "I haven't yet implemented any other method for communication between agents, nor do I enforce any process for managing high-level goals."

## The design moves worth stealing

| Move | What it replaces |
| --- | --- |
| File-based lock in `current_tasks/` | A central coordinator / lead agent |
| Git push-pull as the sync primitive | Explicit inter-agent messaging |
| READMEs + progress files as memory | Live in-context state across sessions |
| Fresh container per new agent | Context inheritance |
| No inter-agent chat | The author flags this as a known limitation |

## Signal for Hive

- Hive's `send` / `reply` **is** the inter-agent channel this experiment deliberately omitted. That is a feature, not a bug, if the target workloads are not embarrassingly parallel.
- The "lock via text file" pattern maps onto `hive fork` worktrees: if two panes might touch overlapping state, a cheap file-based lock is more Anthropic-flavored than bespoke coordination.
- The author's candid admission — "no communication between agents, no process for managing high-level goals" — is a ceiling Hive has *already passed* structurally. The question is whether Hive's extra machinery is worth the context and token overhead for the tasks it runs. For embarrassingly-parallel workloads, the answer from this article is arguably "no."
- "Most of my effort went into designing the environment around Claude" is the quote to anchor Hive's investment priorities: pane layout and coordination is Hive's version of the "environment around Claude."

## NOTE

WebFetch returned all the verbatim quotes above; the "design moves worth stealing" table is synthesized from the fetched content and should not be cited as Anthropic's own formatting.
