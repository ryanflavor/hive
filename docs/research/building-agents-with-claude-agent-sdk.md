---
source: https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk (redirected to claude.com/blog/...)
fetched: 2026-04-19
author: Anthropic (Thariq Shihipar, with Molly Vorwerck, Suzanne Wang, Alex Isken, Cat Wu, Keir Bradwell, Alexander Bricken, Ashwin Bhat)
published: 2025-09-29
---

# Building Agents with the Claude Agent SDK

## Overview

The Claude Agent SDK represents an evolution of the Claude Code SDK, renamed to reflect its broader applicability beyond coding tasks. The SDK provides developers with tools to build autonomous agents capable of complex workflows by giving Claude access to computer-like capabilities.

## Core Design Philosophy

The fundamental principle is straightforward: **"give your agents a computer, allowing them to work like humans do."** By equipping Claude with tools such as bash commands, file editing, and code generation, developers can create general-purpose agents for diverse applications.

## Agent Loop Architecture

Agents operate through a structured feedback cycle:

1. **Gather Context** → 2. **Take Action** → 3. **Verify Work** → 4. **Repeat**

### Gather Context Phase

**Agentic Search & File System**
- The file system functions as structured information retrieval.
- Agents use bash commands like `grep` and `tail` to intelligently load relevant file content.
- Folder structure becomes "a form of context engineering."

**Semantic Search**
- Faster than agentic search but less transparent and harder to maintain.
- Involves chunking content, creating vector embeddings, and querying concepts.
- Recommendation: Start with agentic search; add semantic search only if performance requires it.

**Subagents**
- Enable parallelization: multiple subagents handle different tasks simultaneously.
- Manage context isolation: each subagent maintains its own context window.
- Ideal for information-heavy tasks where filtering large datasets is necessary.

**Compaction**
- Automatically summarizes previous messages as context limits approach.
- Prevents context window exhaustion during extended agent runs.
- Built on Claude Code's `/compact` slash command.

### Take Action Phase

**Tools** — Primary building blocks for agent execution. Should represent the main, frequent actions agents will undertake. Must be designed with context efficiency in mind.

**Bash & Scripts** — Enables flexible, general-purpose work via computer access.

**Code Generation** — Excels at precise, composable, reusable operations. Ideal for complex tasks like spreadsheet creation or document generation.

**MCPs (Model Context Protocol)** — Provides standardized integrations to external services. Handles authentication and API calls automatically.

### Verify Work Phase

**Defining Rules**
- Most effective feedback provides clearly defined output rules.
- Code linting exemplifies rules-based feedback.
- Example: Validate email addresses and warn on repeated recipients.

**Visual Feedback**
- Screenshots or renders useful for UI-related tasks.
- Validates: layout, styling, content hierarchy, responsiveness.
- Tools like Playwright automate visual feedback loops.

**LLM as Judge**
- Separate language models evaluate agent output against fuzzy criteria.
- Generally less robust than other verification methods.
- Useful when any performance improvement justifies latency tradeoffs.
- Example: Separate subagent judges email tone against user's communication style.

## Use Cases Enabled by the SDK

- **Finance agents:** Portfolio analysis, investment evaluation through APIs.
- **Personal assistant agents:** Travel booking, calendar management, appointment scheduling.
- **Customer support agents:** Handle ambiguous requests by collecting data and connecting to external systems.
- **Deep research agents:** Comprehensive document analysis and report generation.

## Testing & Improvement Guidance

Developers should evaluate agents by asking:
- Does the agent have necessary information? Can search APIs be restructured?
- Does it repeatedly fail? Can formal rules be added to identify and fix errors?
- Can additional tools provide alternative problem-solving approaches?
- Does performance vary with new features? Build representative test sets for programmatic evaluation.

## Key Takeaway

The Claude Agent SDK democratizes agent development by providing the infrastructure — context management, tool execution, and verification mechanisms — necessary for building reliable, autonomous systems across diverse domains.

---

NOTE: WebFetch returned a condensed rendering. The Gather/Act/Verify/Repeat loop, the three verification categories (rules, visual, LLM-judge), and the subagent/compaction guidance are preserved. Consult the source URL for original prose.
