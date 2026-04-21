---
source: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
fetched: 2026-04-19
author: Anthropic
published: 2026-01-09
---

# Demystifying Evals for AI Agents

## Introduction

Effective evaluations help development teams deploy AI agents with confidence. Evaluations reveal issues before production deployment and their benefits compound throughout an agent's lifecycle.

Agent capabilities — autonomy, flexibility, and intelligence — create evaluation challenges. Unlike single-turn language model responses, agents operate across multiple turns with tool calls and state modifications, making assessment more complex.

## Core Evaluation Structure

Key terminology:

- **Tasks**: Individual tests with defined inputs and success criteria.
- **Trials**: Multiple attempts at a task (since outputs vary between runs).
- **Graders**: Logic that scores performance aspects.
- **Transcripts**: Complete records of agent interactions, tool calls, and reasoning.
- **Outcomes**: Final environmental state after task completion.
- **Evaluation harness**: Infrastructure running end-to-end evaluations.

Three grader types appear throughout:

- **Code-based graders** offer speed and objectivity but struggle with valid variations.
- **Model-based graders** handle nuance and open-ended tasks but require calibration.
- **Human graders** provide gold-standard quality but prove expensive and slow.

## Evaluation Approaches by Agent Type

**Coding agents** benefit from deterministic test-based grading. SWE-bench Verified, which verifies solutions by running test suites, is a good example — agents must fix failing tests without breaking existing ones.

**Conversational agents** require multidimensional evaluation: state verification, transcript constraints, and interaction quality rubrics. These often need LLM-simulated users.

**Research agents** face unique challenges since "comprehensive" and "well-sourced" depend heavily on context. The piece recommends combining grader types: groundedness checks, coverage verification, and source quality assessment.

**Computer use agents** interact through GUIs like humans do, requiring evaluation in sandboxed environments with state verification (confirming orders were actually placed, not just that pages appeared).

## Handling Non-Determinism

Two metrics capture agent reliability:

- **pass@k**: Probability of ≥1 correct solution in k attempts.
- **pass^k**: Probability that all k trials succeed.

The distinction matters: pass@k approaches 100% with more attempts while pass^k falls, reflecting different product requirements.

## Practical Development Roadmap

Eight-step roadmap:

1. **Start early** with 20-50 realistic tasks from actual failures.
2. **Convert manual tests** to automated cases.
3. **Write unambiguous tasks** where domain experts reach identical verdicts.
4. **Balance problem sets** testing both positive and negative cases.
5. **Build robust harnesses** with isolated, clean environments.
6. **Design thoughtful graders** favoring deterministic checks.
7. **Review transcripts** to verify grading fairness.
8. **Monitor for saturation** when agents pass all solvable tasks.

Key insight: **"Grading what the agent produced, not the path it took"** prevents overly brittle tests that penalize valid creative solutions.

## Complementary Evaluation Methods

Automated evals work alongside:

- **Production monitoring**: Reveals real-world behavior but requires reactive response.
- **A/B testing**: Measures actual user outcomes but runs slowly.
- **User feedback**: Surfaces unforeseen problems but remains sparse.
- **Manual transcript review**: Builds intuition but doesn't scale.
- **Systematic human studies**: Provides calibration for model graders.

The article uses a Swiss Cheese Model analogy: **"no single evaluation layer catches every issue."**

## Notable Examples

- Claude Code evolved from employee feedback to narrow evals (concision, file edits) to broader assessments (over-engineering).
- Descript's video editing agent built evals around three dimensions: not breaking things, following instructions, quality execution.
- Bolt's team created evals combining static analysis, browser testing, and LLM judges within three months.

The article notes that Opus 4.5 "failed" τ2-Bench by discovering a loophole in flight booking policies — demonstrating that creative solutions may surpass static eval specifications.

## Key Warnings

Pitfalls:

- Eval saturation occurs at 100% pass rates, eliminating improvement signals.
- Opus 4.5's CORE-Bench score jumped from 42% to 95% after fixing grading bugs like rigid string matching and ambiguous specs.
- Unbalanced evals (testing only positive cases) lead to one-sided optimization.
- Shared state between trials introduces correlated failures unrelated to agent performance.

## Maintenance

"An eval suite is a living artifact needing ongoing attention." Effective approaches involved dedicated infrastructure teams with domain experts contributing tasks — treating evaluations "as routine as maintaining unit tests."

## Conclusion

Development teams without evaluations face "reactive loops — fixing one failure, creating another." Early eval investment accelerates progress by transforming failures into test cases and preventing regressions.

---

NOTE: WebFetch returned a condensed rendering. Key terminology, the three grader types, the pass@k / pass^k distinction, and the eight-step roadmap are preserved. Consult the source URL for original full-length prose.
