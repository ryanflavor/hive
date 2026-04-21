---
source: https://www.anthropic.com/engineering/built-multi-agent-research-system
fetched: 2026-04-19
author: Anthropic (Jeremy Hadfield, Barry Zhang, Kenneth Lien, Florian Scholz, Jeremy Fox, Daniel Ford)
published: 2025-06-13
---

# How We Built Our Multi-Agent Research System

## Overview

Anthropic's Research feature employs multiple Claude agents working in parallel to explore complex topics more effectively than single-agent systems. The system uses an orchestrator-worker architecture where a lead agent coordinates the research process while delegating tasks to specialized subagents.

## Key Performance Finding

According to internal evaluations, "a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2%." The system excels particularly for breadth-first queries requiring simultaneous exploration of multiple independent directions.

## Architecture

The system follows this workflow:

1. **Lead Researcher** analyzes user queries and develops research strategies
2. **Subagents** work in parallel, each exploring specific aspects
3. **Dynamic Search** adapts based on findings (contrasting with static RAG approaches)
4. **Citation Agent** attributes claims to sources
5. **Results** return to users with proper citations

## Token Efficiency Trade-offs

While powerful, multi-agent systems demand significant resources: "agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats." This makes them economically viable only for high-value tasks.

## Prompt Engineering Principles

The team identified eight core strategies:

1. **Understand agent behavior** through simulation and step-by-step observation
2. **Teach delegation** with detailed task descriptions including objectives and output formats
3. **Scale effort appropriately** based on query complexity
4. **Design tools carefully** with clear descriptions and distinct purposes
5. **Enable self-improvement** by having Claude suggest prompt refinements
6. **Start broad, then narrow** search strategies progressively
7. **Guide thinking** using extended thinking mode
8. **Parallelize** both subagent spawning and tool calling

## Evaluation Approach

- **Start small:** Early testing with ~20 queries revealed major issues before scaling
- **Use LLM judges:** Evaluate outputs against rubrics for accuracy, citations, completeness, source quality, and efficiency
- **Supplement with humans:** Manual testing catches edge cases and hallucinations that automation misses

## Production Challenges

**Statefulness and Error Compounding:** Agents maintain context across many turns; minor failures cascade unpredictably. Solutions include durable execution, graceful error handling, and resumption from checkpoints.

**Debugging Complexity:** Non-deterministic behavior between runs requires "full production tracing" to diagnose failures without violating privacy.

**Deployment Coordination:** The team uses "rainbow deployments" to prevent code changes from disrupting running agents.

**Synchronous Bottlenecks:** Current lead agents wait for subagents sequentially, limiting parallelism. Asynchronous execution could improve performance but adds coordination complexity.

## What Doesn't Work Well

Multi-agent architectures underperform for:
- Tasks requiring shared context across all agents
- Heavily interdependent work requiring real-time coordination
- Most coding tasks with limited parallelization opportunities

## Real-World Impact

Users report the system helping them "find business opportunities they hadn't considered, navigate complex healthcare options, resolve thorny technical bugs, and save up to days of work."

Top use cases include developing specialized software systems (10%), creating professional content (8%), business strategy development (8%), academic research (7%), and information verification (5%).

## Key Takeaway

The gap between prototype and production proved wider than anticipated. Success required careful orchestration of prompts, tools, execution logic, observability, and cross-functional collaboration — transforming research workflows from hours to minutes while maintaining reliability at scale.

---

NOTE: WebFetch returned a condensed rendering of the article rather than the full verbatim text. Original article should be consulted directly at the source URL for complete prose; headline figures, section structure, and the "what doesn't work" list are preserved faithfully.
