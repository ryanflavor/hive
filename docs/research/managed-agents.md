---
source: https://www.anthropic.com/engineering/managed-agents
fetched: 2026-04-19
author: Anthropic (Lance Martin, Gabe Cemaj, Michael Cohen)
---

# Scaling Managed Agents: Decoupling the Brain from the Hands

## Why this matters

This is the article with the single clearest operational definition of "harness" Anthropic has published. It also introduces "meta-harness" — the level above a harness — which matters because Hive itself is not a harness in the Claude Code sense; it's closer to the meta-harness Anthropic describes here.

## Verbatim quotes (all the mentions of "harness")

> "A running topic on the Engineering Blog is how to build effective agents and design harnesses for long-running work."

> "A common thread across this work is that harnesses encode assumptions about what Claude can't do on its own."

> "those assumptions need to be frequently questioned because they can go stale as models improve."

> "We addressed this by adding context resets to the harness."

> "when we used the same harness on Claude Opus 4.5, we found that the behavior was gone."

> "The resets had become dead weight."

> "We expect harnesses to continue evolving."

> "a harness (the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure)"

> "The harness leaves the container."

> "the harness no longer lived inside the container."

> "Recovering from harness failure."

> "The harness also became cattle."

> "During the agent loop, the harness writes to the session with emitEvent(id, event)."

> "the harness removes compacted messages from Claude's context window"

> "These transformations can be whatever the harness encodes, including context organization."

> "The interfaces push that context management into the harness."

> "Many brains. Decoupling the brain from the hands solved one of our earliest customer complaints."

> "the container holding the harness assumed every resource sat next to it."

> "Once the harness was no longer in the container, that assumption went away."

> "Managed Agents is a meta-harness in the same spirit, unopinionated about the specific harness that Claude will need."

> "For example, Claude Code is an excellent harness that we use widely across tasks."

## The load-bearing definition

The clearest single sentence in Anthropic's public writing, from this article:

> "a harness (the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure)"

Everything else — context management, subagents, permissions, skills — is layered **on top of** that loop.

## The "harness as cattle" pattern

The article describes a move where Anthropic pulled the harness **out** of the per-task container:

- Before: harness + Claude + tool infrastructure lived inside one container; every resource "sat next to it."
- After: the harness lives outside; the container holds the hands (tools, workspace). When something goes wrong, the harness can be restarted without losing the session.
- Events flow through `emitEvent(id, event)`.
- Compaction is now a harness responsibility: "the harness removes compacted messages from Claude's context window."

## "Meta-harness"

> "Managed Agents is a meta-harness in the same spirit, unopinionated about the specific harness that Claude will need."

Managed Agents is the layer that hosts whichever harness a workload needs. Claude Code is **one** harness that runs on top of it.

## Signal for Hive

- **Hive's place in the stack is now explicit.** Hive is closer to "meta-harness" than "harness": it hosts tmux panes, orchestrates sessions, and is agnostic to whether each pane runs Claude Code, Droid, or Codex. The per-pane process is the harness; Hive is the thing around the harness.
- **Harness ≠ the agent.** The harness is the *loop and the routing*, not the model and not the tools. This means when Hive imports Claude Code practices ("use subagents", "fresh context for review"), it is importing *harness* patterns, not model patterns — the analogy is strong for Hive-internal workflows too.
- **Stale assumptions rot.** The article explicitly describes context resets that became dead weight on Claude Opus 4.5. Hive's existing helpers (busy/inputState heuristics, forced handoff cadence) should be audited against Opus 4.7 and 4.8 on a regular cadence.
- **Harness-level compaction is the model, not per-agent compaction.** Anthropic pushes compaction **up** into the harness. For Hive that implies a workspace-level context strategy (bus + sidecar + worktree artifacts) rather than trusting each pane to compact itself.

## NOTE

WebFetch returned verbatim quotes plus structural summary. The "before/after container" and `emitEvent` description above are verbatim and near-verbatim from the fetched output. The publication date was not surfaced by the fetch and is not included in the frontmatter.
