---
source: https://www.anthropic.com/engineering/building-effective-agents
fetched: 2026-04-19
author: Anthropic (Erik Schluntz, Barry Zhang)
published: 2024-12-19
---

# Building Effective Agents

## Overview

Anthropic's research on dozens of customer implementations reveals that "the most successful implementations weren't using complex frameworks or specialized libraries. Instead, they were building with simple, composable patterns."

## Key Distinctions

The document establishes crucial architectural differences:

- **Workflows**: LLMs and tools orchestrated through predefined code paths
- **Agents**: Systems where LLMs dynamically direct their own processes and maintain control

## When to Use Each Approach

Developers should start with the simplest solution possible. Not all applications need agentic systems — many benefit from optimizing single LLM calls with retrieval and examples. Workflows suit well-defined tasks requiring predictability, while agents excel when flexibility and model-driven decision-making matter at scale.

## Core Patterns

### Building Block: Augmented LLM
The foundation combines LLMs with retrieval, tools, and memory capabilities. Anthropic recommends the Model Context Protocol for integrating third-party tools.

### Workflow Patterns

1. **Prompt Chaining**: Decomposes tasks into sequential steps with programmatic gates for quality checks.
2. **Routing**: Classifies inputs and directs them to specialized handlers.
3. **Parallelization**: Runs tasks simultaneously through sectioning or voting approaches.
4. **Orchestrator-Workers**: Central LLM dynamically breaks down tasks and synthesizes results.
5. **Evaluator-Optimizer**: Iterative refinement loop with feedback mechanisms.

#### Evaluator-Optimizer — when to use, when to avoid

In the evaluator-optimizer workflow, one LLM call generates a response while another provides evaluation and feedback in a loop.

This workflow is particularly effective when:
- There are clear evaluation criteria.
- Iterative refinement provides measurable value.
- LLM responses can be demonstrably improved when a human articulates their feedback.
- The LLM can provide such feedback.

Examples:
- Literary translation where nuances the translator LLM might miss can be surfaced by an evaluator LLM.
- Complex search tasks requiring multiple rounds of searching and analysis, where the evaluator decides whether further searches are warranted.

Avoid evaluator-optimizer when:
- First-attempt quality already meets requirements.
- Evaluation criteria are subjective or unclear.
- Time and cost constraints outweigh quality improvements.
- You need real-time responses.
- The task is a simple routine like basic classification.
- You are in a resource-constrained environment with strict token budgets.

### Autonomous Agents
Best for open-ended problems requiring many steps and unpredictable paths. Agents require "clear evaluation criteria" and are suitable for trusted environments with proper sandboxing and guardrails.

## Practical Applications

**Customer Support**: Combines conversation with tool integration for information retrieval and actions like refund processing.

**Coding Agents**: Leverage automated tests as feedback; demonstrated solving real GitHub issues in SWE-bench benchmarks.

## Implementation Principles

Three core recommendations:

1. Maintain simplicity in agent design.
2. Prioritize transparency through explicit planning steps.
3. Craft agent-computer interfaces (ACI) through thorough tool documentation and testing.

## Tool Design Guidance

Effective tools require investing effort comparable to human-computer interface design. Recommendations include:

- Providing sufficient tokens for model reasoning.
- Keeping formats close to natural text patterns.
- Eliminating formatting overhead.
- Including clear usage examples and edge cases.
- Testing extensively in the Claude workbench.
- Applying "poka-yoke" principles to reduce mistakes.

The SWE-bench agent development spent more time optimizing tools than overall prompts, discovering that absolute filepaths eliminated common relative path errors.

---

NOTE: WebFetch returned a condensed rendering rather than the full verbatim article. The pattern list, evaluator-optimizer guidance, and principles are preserved; consult the source URL for original prose and diagrams.
