---
source: https://www.anthropic.com/engineering/harness-design-long-running-apps
fetched: 2026-04-19
author: Anthropic (Prithvi Rajasekaran, Anthropic Labs)
published: 2026-03-24
---

# Harness Design for Long-Running Application Development

## Core framing

Where `effective-harnesses-for-long-running-agents.md` defines the problem, this article documents the **design discipline** of building a harness: what to put in, what to strip out, and when to stop. The punchline is that every harness component is a temporary crutch for a current-model weakness.

## Verbatim quotes

> "Harness design is key to performance at the frontier of agentic coding."

> "This work originated with earlier efforts on our frontend design skill and long-running coding agent harness, where my colleagues and I were able to improve Claude's performance well above baseline through prompt engineering and harness design—but both eventually hit ceilings."

> "We've previously shown that harness design has a substantial impact on the effectiveness of long running agentic coding."

> "The harness used Sonnet 4.5, which exhibited the 'context anxiety' tendency mentioned earlier."

> "The harness was over 20x more expensive, but the difference in output quality was immediately apparent."

> "The full harness run started from the same one-sentence prompt, but the planner step expanded that prompt into a 16-feature spec spread across ten sprints."

> "I kept both the planner and evaluator, as each continued to add obvious value."

> "Based on that experience, I moved to a more methodical approach, removing one component at a time and reviewing what impact it had on the final result."

## The three-agent reference architecture

| Agent | Role |
| --- | --- |
| Planner | Expands a brief prompt into a detailed spec with technical direction |
| Generator | Implements features iteratively; does self-evaluation |
| Evaluator | Tests via live interaction; grades against criteria |

> Communication between them happens through **structured file handoffs**, not direct conversation.

## Design principles the article lays out

1. **Context management via resets, not compaction.** Address "context anxiety" by clearing the window entirely and handing off via structured artifacts, instead of trying to compress everything in place.
2. **Separate doer from judge.** "Separating the agent doing the work from the agent judging it proves to be a strong lever." Self-evaluation has blind spots an external evaluator catches.
3. **Decomposition with slack.** Break work into tractable chunks, but avoid over-specification — tight specs cascade errors downstream.
4. **Simplification discipline.** "Every component in a harness encodes an assumption about what the model can't do on its own." When the model improves, walk through components and remove ones that have become dead weight. The article's own experiment kept planner+evaluator because they kept adding value even with a stronger model.
5. **Harnesses hit ceilings.** Prompt engineering and harness design helped, but both plateaued — at the frontier, raw model capability eventually dominates.

## Signal for Hive

- Hive's four-pane team (orchestrator, worker, validator, terminal) maps cleanly onto Planner/Generator/Evaluator plus a user-facing seat. The separation-of-concerns justification is the exact one this article uses.
- The "20x more expensive, quality immediately apparent" number reinforces the 15x multi-agent token premium from `multi-agent-research-system.md`. Treat this as the upper bound of what's defensible.
- The "simplification discipline" is a pointer to periodically audit Hive's helpers: any pane, tool, or hook that was added to compensate for Claude Sonnet 4.5 quirks should be rechecked against Claude Opus 4.7. See the `managed-agents.md` note on context-reset dead weight.
- "Structured file handoffs, not direct conversation" aligns with Anthropic's subagent model (prompt in, final message out). Hive's `send` / `reply` already lean on tmux buffers plus worktree files — keep the file side of it load-bearing.

## NOTE

WebFetch returned a compressed summary with verbatim harness-containing quotes. The numbered design principles are paraphrased from that summary and should not be quoted as Anthropic's own words without rechecking the source HTML.
