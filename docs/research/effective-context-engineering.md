---
source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
fetched: 2026-04-19
author: Anthropic Applied AI team (Prithvi Rajasekaran, Ethan Dixon, Carly Ryan, Jeremy Hadfield, with Rafi Ayub, Hannah Moran, Cal Rueb, Connor Jennings)
published: 2025-09-29
---

# Effective Context Engineering for AI Agents

## Overview

Context engineering represents the evolution beyond prompt engineering. Rather than optimizing individual prompts, it focuses on managing the entire set of tokens available to an LLM during inference — including system instructions, tools, external data, and message history.

## Key Distinction: Context Engineering vs. Prompt Engineering

While prompt engineering emphasizes writing effective prompts, context engineering addresses "what configuration of context is most likely to generate our model's desired behavior?" As agents operate across multiple turns and longer time horizons, engineers must manage the complete context state rather than isolated prompts.

## The Attention Budget Problem

LLMs face inherent constraints:

- **Context rot**: Model accuracy decreases as token count increases.
- **Architectural limits**: Transformer-based "n² pairwise relationships" strain as context grows.
- **Training distribution bias**: Models have less experience with extended sequences.

The implication is clear: "LLMs, like humans, lose focus or experience confusion at a certain point." Treating context as a finite resource with "diminishing marginal returns" is essential.

## Anatomy of Effective Context

### System Prompts

The optimal approach strikes a balance between extremes:
- Avoid brittle, hardcoded if-else logic.
- Avoid vague guidance that assumes shared context.
- Target the "Goldilocks zone" with specific yet flexible instructions.

Use organizational sections (XML tags, Markdown headers) to structure prompts clearly. Begin with minimal instructions on your strongest model, then add examples based on identified failure modes.

### Tools

Tools define the agent-environment contract. Effective tool design requires:
- Minimal overlap in functionality.
- Clear, unambiguous input parameters.
- Self-contained, robust implementations.

Bloated tool sets create decision paralysis. "If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better."

### Examples (Few-Shot Prompting)

Curate diverse, canonical examples rather than exhaustive edge-case lists. For LLMs, "examples are the 'pictures' worth a thousand words."

## Context Retrieval and Agentic Search

### Just-In-Time Loading

Rather than pre-processing all data, agents can maintain lightweight identifiers (file paths, URLs, queries) and dynamically load information via tools. This approach:
- Mirrors human cognition.
- Enables progressive disclosure.
- Maintains working memory focus.
- Allows metadata signals to guide behavior.

Claude Code exemplifies this: the model writes targeted queries, uses bash commands like `head` and `tail` to analyze data, and leverages file system organization without loading entire objects into context.

### Hybrid Strategies

The most effective systems may combine:
- Pre-loaded data for speed (e.g., CLAUDE.md files).
- Just-in-time exploration (e.g., glob, grep operations).

## Long-Horizon Task Management

For tasks spanning minutes to hours that exceed context windows, three specialized techniques address context pollution:

### Compaction

Compaction summarizes conversation contents when approaching context limits, reinitializing a fresh window with the summary. Implementation requires:
- Selecting what to preserve (architectural decisions, unresolved bugs, implementation details).
- Discarding redundant content (duplicate tool outputs).
- Careful prompt tuning on complex traces.

One effective lightweight approach: **"tool result clearing"** — once tool results are established in history, removing redundant raw results minimizes waste.

### Structured Note-Taking

Agents maintain notes in persistent external memory (outside the context window), retrieved when needed. Benefits include:

- Persistent tracking across complex sequences.
- Minimal overhead.
- Coherence across summarization steps.

Claude playing Pokémon demonstrates this: the agent maintains "precise tallies across thousands of game steps," remembering objectives, explored regions, unlocked achievements, and combat strategies without explicit memory prompting.

### Sub-Agent Architectures

Specialized sub-agents handle focused tasks with clean context windows, while a coordinator maintains high-level planning:

- Each sub-agent explores extensively but returns condensed summaries (**1,000-2,000 tokens**).
- Detailed search contexts remain isolated.
- Clear separation of concerns.

This pattern proved effective for complex research tasks, showing "substantial improvement over single-agent systems."

## Practical Guidance

The guiding principle across all techniques: **"find the smallest set of high-signal tokens that maximize the likelihood of some desired outcome."**

As models improve, they require less prescriptive engineering, enabling greater autonomy. However, "treating context as a precious, finite resource will remain central to building reliable, effective agents."

---

NOTE: WebFetch returned a condensed rendering. The "1,000-2,000 tokens" figure for sub-agent summaries, the three long-horizon techniques (compaction / note-taking / sub-agents), and the guiding principle are preserved. Consult the source URL for original prose and diagrams.
