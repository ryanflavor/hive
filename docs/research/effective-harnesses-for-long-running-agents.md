---
source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
fetched: 2026-04-19
author: Anthropic (Justin Young)
published: 2025-11-26
---

# Effective Harnesses for Long-Running Agents

## Core framing

This article is the most direct statement Anthropic has put out on what a "harness" is and what it has to do when an agent runs across many context windows. The central problem:

- Agents work in discrete sessions
- Each new session starts with no memory of what came before
- Single-session context compaction is not enough once work spans multiple windows

The solution Anthropic demonstrates is a **two-agent harness**: an initializer agent and a recurring coding agent.

## Verbatim definitions and claims

> "The Claude Agent SDK is a powerful, general-purpose agent harness adept at coding, as well as other tasks that require the model to use tools to gather context, plan, and execute."

> "It has context management capabilities such as compaction, which enables an agent to work on a task without exhausting the context window."

> "We developed a two-fold solution to enable the Claude Agent SDK to work effectively across many context windows: an initializer agent that sets up the environment on the first run, and a coding agent that is tasked with making incremental progress in every session, while leaving clear artifacts for the next session."

> "This research demonstrates one possible set of solutions in a long-running agent harness to enable the model to make incremental progress across many context windows."

> "In the updated Claude 4 prompting guide, we shared some best practices for multi-context window workflows, including a harness structure that uses 'a different prompt for the very first context window.'"

## What the harness contains (in this article's reference design)

| Harness component | Role |
| --- | --- |
| Initializer agent | One-shot setup on first run — creates `init.sh`, `claude-progress.txt`, initial git commit |
| Coding agent | Runs every subsequent session; makes incremental progress and leaves artifacts |
| Feature list (JSON) | 200+ features, each flagged `failing` initially — acts as a durable task backlog |
| Progress log | `claude-progress.txt` + git history — the cross-session memory |
| Verification loop | Puppeteer MCP driving the browser to confirm features actually work end to end |

## Failure modes the harness is designed against

1. Agents attempting too much simultaneously, exhausting context mid-implementation
2. Premature "project complete" declarations
3. Insufficient feature verification before marking tasks done

## Signal for Hive

- The two-agent split (initializer vs. recurring coder) is one of the few Anthropic patterns that explicitly runs **across** context windows, not just within one. Hive's orchestrator ↔ worker ↔ validator loop, which is session-persistent via tmux panes, is adjacent but distinct — Hive does not reset context per session in the way this article advocates.
- The "artifact on disk" handoff (progress file + feature list + git commits) is the concrete return channel. Hive already has this shape implicitly in the worktree.
- "Context management capabilities such as compaction" is listed as **part of** the harness, not a separate concern. If Hive is a harness, compaction/reset has to be a first-class Hive responsibility, not left to each pane's tool.

## NOTE

WebFetch returned primarily a structured summary with a handful of verbatim quotes. The quotes above are confirmed verbatim from the fetch; the architectural breakdown (initializer/coding agent, feature list, Puppeteer MCP) is summarized from the same fetch and has not been re-checked against the raw HTML.
