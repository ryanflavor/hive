---
source: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
fetched: 2026-04-19
author: Anthropic (Barry Zhang, Keith Lazuka, Mahesh Murag)
published: 2025-10-16
---

# Equipping Agents for the Real World with Agent Skills

## Why this is relevant to harness

The word "harness" does not appear in this article, but Skills are one of the harness's plug-in slots. Under the `managed-agents.md` definition, the harness is the loop that routes Claude's tool calls; Skills are the route table it can discover at runtime. Skills also answer the "stale harness" warning in `managed-agents.md` — they let per-task procedural knowledge ship outside the harness core.

## Verbatim quotes

> "Progressive disclosure is the core design principle that makes Agent Skills flexible and scalable."

> "Like a well-organized manual that starts with a table of contents, then specific chapters, and finally a detailed appendix, skills let Claude load information only as needed"

> "Skills extend Claude's capabilities by packaging your expertise into composable resources for Claude"

> "anyone can now specialize their agents with composable capabilities by capturing and sharing their procedural knowledge"

> "Instead of building fragmented, custom-designed agents for each use case, anyone can now specialize their agents with composable capabilities"

## The progressive-disclosure contract

Three tiers, loaded lazily:

1. **Metadata**: only `name` + `description` are pre-loaded into the system prompt. Enough for the model to know *when* a skill is relevant.
2. **SKILL.md**: loaded on demand when the model decides the skill applies.
3. **Linked files**: loaded only when SKILL.md references them.

This is the same pattern `code-execution-with-mcp.md` uses for tool definitions (150k → 2k tokens by lazy loading). Anthropic is converging on lazy, disclosure-triggered loading as the default harness behaviour.

## Signal for Hive

- **Hive already has Skills in this shape.** The repo itself packages `skills/hive/SKILL.md` and relies on `npx skills add` to surface it. That maps cleanly onto Anthropic's model.
- **Hive's plugin commands are closer to Anthropic's "Skills + hooks" than to tools.** Things like `/review`, `/cvim`, `/fork` are procedural knowledge expressed as skills; they live in the harness layer, not in the LLM's prompt.
- **Skills absorb the "stale assumption" risk from `managed-agents.md`.** If a capability Hive used to bake into its core becomes Opus-4.7-native, it is cleaner to demote it to a skill than to leave dead weight in `src/hive/`.
- **Composability is the upgrade path.** Anthropic's framing is that specialists ship skills instead of forking agents. For Hive that means plugins should be the extension point, not new Python modules in the runtime.

## NOTE

The article did not surface any "harness" mentions. The tier structure and cross-references to Hive are synthesized from the fetched content plus the other files in this folder.
