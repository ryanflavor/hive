---
source: https://www.anthropic.com/engineering/writing-tools-for-agents
fetched: 2026-04-19
author: Anthropic (Ken Aizawa)
published: 2025-09-11
---

# Writing Effective Tools for Agents — with Agents

## Overview

This post explores how to build high-quality tools for LLM agents. The authors argue that agents require fundamentally different software design approaches than traditional deterministic systems.

## Key Principles for Tool Design

### 1. Strategic Tool Selection

"More tools don't always lead to better outcomes." Rather than wrapping every API endpoint, developers should build focused tools targeting high-impact workflows. Tools can consolidate multiple operations — for example, a single `schedule_event` tool that handles availability checking and booking, rather than separate `list_users`, `list_events`, and `create_event` tools.

### 2. Namespacing and Organization

Grouping related tools with consistent prefixes (like `asana_search` vs. `jira_search`) helps agents understand which tool to use. "Selecting between prefix- and suffix-based naming" produces measurable performance differences in evaluations.

### 3. Meaningful Context Returns

Tools should return "only high signal information" to agents, prioritizing semantic clarity over technical identifiers. Converting cryptic UUIDs to readable names "significantly improves Claude's precision in retrieval tasks by reducing hallucinations." Tools can expose a `response_format` parameter allowing agents to request concise or detailed outputs.

### 4. Token Efficiency

Implementing pagination, filtering, and truncation with sensible defaults prevents context waste. The post recommends **restricting responses to around 25,000 tokens** and using helpful error messages that guide agents toward more efficient strategies rather than opaque error codes.

### 5. Tool Description Optimization

Clear, unambiguous descriptions steer agent behavior significantly. Treat descriptions like onboarding documentation — making implicit context explicit and avoiding naming ambiguity (use `user_id` instead of `user`).

## Evaluation-Driven Development

The workflow involves:
- Building prototypes with Claude Code or local MCP servers.
- Creating comprehensive evaluation tasks grounded in real-world use cases.
- Running programmatic evaluations with simple agentic loops.
- Having Claude analyze results to identify and fix issues iteratively.

The post demonstrates this approach yielded measurable improvements in internal Slack and Asana tool implementations through repeated optimization cycles.

---

NOTE: WebFetch returned a condensed rendering. The five tool design principles, the 25k-token ceiling, and evaluation-driven workflow are preserved. Consult the source URL for original full-length prose.
