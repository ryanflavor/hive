# Anthropic Sources — Synthesis for a 4-Role Hive Team

**Target architecture:** 1 orchestrator + 1 worker + 1 validator + 1 terminal, running as tmux panes coordinated by Hive (`send` / `reply` / `handoff` / `spawn` / `fork`).

**Scope:** Cross-cut Anthropic's own published guidance and pull the rules that bind on this design. This is not a per-article summary — see the individual saved files for that.

## Sources saved

| File | Source | Primary relevance |
| --- | --- | --- |
| `multi-agent-research-system.md` | anthropic.com/engineering/built-multi-agent-research-system | Orchestrator-worker at production scale; token cost; "what doesn't work" |
| `building-effective-agents.md` | anthropic.com/engineering/building-effective-agents | Canonical pattern catalog (orchestrator-workers, evaluator-optimizer, routing, prompt chaining) |
| `claude-code-best-practices.md` | anthropic.com/engineering/claude-code-best-practices (→ code.claude.com) | Writer/Reviewer, subagents for verification, verification as the "single highest-leverage" thing |
| `sub-agents.md` | docs.claude.com/en/docs/claude-code/sub-agents | Subagent scope, context isolation, tool restrictions, "subagents cannot spawn subagents" |
| `sdk-subagents.md` | docs.claude.com/en/docs/agent-sdk/subagents | **Load-bearing**: "What subagents inherit" table — the exact rule for parent↔subagent context |
| `effective-context-engineering.md` | anthropic.com/engineering/effective-context-engineering-for-ai-agents | Sub-agent summaries at 1,000–2,000 tokens; compaction + note-taking |
| `building-agents-with-claude-agent-sdk.md` | anthropic.com/engineering/building-agents-with-the-claude-agent-sdk (→ claude.com) | Gather→Act→Verify loop; three verification modes |
| `code-execution-with-mcp.md` | anthropic.com/engineering/code-execution-with-mcp | Progressive disclosure; intermediate-result privacy; 150k→2k tokens |
| `demystifying-evals.md` | anthropic.com/engineering/demystifying-evals-for-ai-agents | Validator-relevant: grader taxonomy, pass@k vs pass^k, "grade what was produced, not the path" |
| `writing-tools-for-agents.md` | anthropic.com/engineering/writing-tools-for-agents | Tool surface design for each role; 25k-token ceiling |
| `effective-harnesses-for-long-running-agents.md` | anthropic.com/engineering/effective-harnesses-for-long-running-agents | **Harness** definition via Claude Agent SDK; initializer + coding-agent pattern |
| `harness-design-long-running-apps.md` | anthropic.com/engineering/harness-design-long-running-apps | Planner/Generator/Evaluator; "every component encodes an assumption" |
| `managed-agents.md` | anthropic.com/engineering/managed-agents | **Load-bearing definition of harness**; "meta-harness"; harness-as-cattle |
| `building-c-compiler.md` | anthropic.com/engineering/building-c-compiler | Real parallel-Claude harness; file-lock coordination; 16 agents |
| `enabling-claude-code-to-work-more-autonomously.md` | anthropic.com/news/enabling-claude-code-to-work-more-autonomously | Checkpoints + subagents + hooks + background tasks as harness surface |
| `swe-bench-sonnet.md` | anthropic.com/research/swe-bench-sonnet | "Scaffold" = proto-harness; agent = model + scaffolding |
| `equipping-agents-for-the-real-world-with-agent-skills.md` | anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | Skills as lazy-loaded harness plug-ins; progressive disclosure |

**Not findable as a standalone Anthropic page:** No standalone Anthropic article specifically titled "evaluator pattern" or "critic pattern" was surfaced; the canonical treatment lives inside `building-effective-agents.md` ("Evaluator-Optimizer" section) and the validator-style practice is elaborated in `demystifying-evals.md` and the "Verify Work" phase of `building-agents-with-claude-agent-sdk.md`. The "agent teams" docs page was mentioned in `sub-agents.md` but not fetched; noted for possible follow-up.

---

## 1. When orchestrator-worker vs single-agent loop?

Anthropic is explicit that you should **not** default to multi-agent.

> "The most successful implementations weren't using complex frameworks or specialized libraries. Instead, they were building with simple, composable patterns." (`building-effective-agents.md`)

> "Developers should start with the simplest solution possible. Not all applications need agentic systems — many benefit from optimizing single LLM calls with retrieval and examples." (`building-effective-agents.md`)

The multi-agent research post quantifies the cost:

> "Agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats. … This makes them economically viable only for high-value tasks." (`multi-agent-research-system.md` §Token Efficiency Trade-offs)

Orchestrator-worker helps when the work is **parallelizable and breadth-first**:

> "The system excels particularly for breadth-first queries requiring simultaneous exploration of multiple independent directions." (`multi-agent-research-system.md` §Key Performance Finding)

> "A multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2%." (`multi-agent-research-system.md`)

It **hurts** when work is interdependent:

> "Multi-agent architectures underperform for: tasks requiring shared context across all agents; heavily interdependent work requiring real-time coordination; most coding tasks with limited parallelization opportunities." (`multi-agent-research-system.md` §What Doesn't Work Well)

**Implication for a 4-role Hive team:** The orchestrator is justified only if (a) the task benefits from a fresh context for the worker and validator, and (b) the user-facing terminal role needs insulation from worker noise. For a linear code-editing workflow with tight back-and-forth, Anthropic would push you back to one agent. Hive `handoff` is closer to their "chain subagents" than to true parallel fan-out.

---

## 2. What does Anthropic say about validator / evaluator agents?

The validator role maps to Anthropic's **evaluator-optimizer** pattern and **LLM-as-judge** verification.

### When the pattern helps

> "This workflow is particularly effective when we have clear evaluation criteria, and when iterative refinement provides measurable value. The two signs of good fit are, first, that LLM responses can be demonstrably improved when a human articulates their feedback; and second, that the LLM can provide such feedback." (`building-effective-agents.md` §Evaluator-Optimizer)

Claude Code reinforces this through the "fresh context" argument:

> "A fresh context improves code review since Claude won't be biased toward code it just wrote." (`claude-code-best-practices.md` §Run multiple Claude sessions)

> "You can also use subagents for verification after Claude implements something: `use a subagent to review this code for edge cases`." (`claude-code-best-practices.md` §Use subagents for investigation)

### When it hurts

> "Avoid evaluator-optimizer workflows when first-attempt quality already meets requirements, evaluation criteria are subjective or unclear, or when time and cost constraints outweigh quality improvements." (`building-effective-agents.md`)

> "LLM as Judge … Generally less robust than other verification methods. Useful when any performance improvement justifies latency tradeoffs." (`building-agents-with-claude-agent-sdk.md` §Verify Work Phase)

### Preferred verification order

Anthropic ranks verification methods with **LLM-as-judge last**:

> "Verify Work Phase: **Defining Rules** (most effective — code linting, email validation rules) → **Visual Feedback** (screenshots, Playwright) → **LLM as Judge** (generally less robust)." (`building-agents-with-claude-agent-sdk.md`)

And the eval doc is adamant:

> "Grading what the agent produced, not the path it took, prevents overly brittle tests that penalize valid creative solutions." (`demystifying-evals.md` §Practical Development Roadmap)

**Implication for Hive's validator role:** Do not make the validator a pure "LLM judges worker's prose" pane. Its highest-value shape is:
1. Run deterministic checks (tests, lint, build) — the "Defining Rules" tier.
2. Only when those pass, layer in semantic review.
3. Grade the output artifact (the diff / the file), not the worker's transcript.

If the task's success criterion cannot be made rule-based, a second LLM validator has low marginal value and burns ~15× tokens.

---

## 3. How does Anthropic share context between orchestrator and worker?

**This is the most load-bearing rule in the collection and the wording is exact.** From the Claude Agent SDK docs:

> "A subagent's context window starts fresh (no parent conversation) but isn't empty. **The only channel from parent to subagent is the Agent tool's prompt string**, so include any file paths, error messages, or decisions the subagent needs directly in that prompt." (`sdk-subagents.md` §What subagents inherit)

The inheritance table (verbatim from `sdk-subagents.md`):

| The subagent receives | The subagent does not receive |
| --- | --- |
| Its own system prompt and the Agent tool's prompt | The parent's conversation history or tool results |
| Project CLAUDE.md (loaded via `settingSources`) | Skills (unless listed in `AgentDefinition.skills`) |
| Tool definitions (inherited from parent, or the subset in `tools`) | The parent's system prompt |

The return channel is equally constrained:

> "The parent receives the subagent's final message verbatim as the Agent tool result, but may summarize it in its own response." (`sdk-subagents.md`)

And the size target for that return message:

> "Each sub-agent explores extensively but returns condensed summaries (1,000–2,000 tokens). Detailed search contexts remain isolated. Clear separation of concerns." (`effective-context-engineering.md` §Sub-Agent Architectures)

The research-system post reinforces the same rule in practice:

> "Subagents use their own isolated context windows, and only send relevant information back to the orchestrator, rather than their full context." (surfaced via `sdk-subagents.md` §Benefits; same principle stated in `multi-agent-research-system.md`)

**Implication for Hive:** The orchestrator pane should **not** pipe its full transcript to the worker or validator. The `send` / `handoff` payload should be a compressed brief: goal, constraints, file paths (not file contents), expected output shape. On the return leg, the worker's reply should itself be a ~1–2k-token summary, not the worker's raw scroll. If the terminal role is user-facing, Anthropic explicitly warns the orchestrator may further compress the subagent's message in its response — if verbatim preservation matters, an explicit instruction is required.

---

## 4. Spawn / parallelism tradeoff: token vs latency vs quality

Three numeric anchors in the collection:

- **+90.2% quality** for multi-agent on breadth-first research (`multi-agent-research-system.md`)
- **~15× token cost** vs chat baseline (`multi-agent-research-system.md`)
- **~98.7% token reduction** (150k → 2k) from progressive disclosure of tools via code execution (`code-execution-with-mcp.md`)

The quality win only lands when the work is parallel:

> "Parallelize both subagent spawning and tool calling." (`multi-agent-research-system.md` §Prompt Engineering Principles)

Latency is not free even when spawning is:

> "Current lead agents wait for subagents sequentially, limiting parallelism. Asynchronous execution could improve performance but adds coordination complexity." (`multi-agent-research-system.md` §Synchronous Bottlenecks)

Anthropic also flags a subtle context risk of parallel fan-out:

> "**Warning:** When subagents complete, their results return to your main conversation. Running many subagents that each return detailed results can consume significant context." (`sub-agents.md` §Run parallel research)

Latency vs. subagent cost from the other direction:

> "Use the main conversation when: latency matters. Subagents start fresh and may need time to gather context." (`sub-agents.md` §Choose between subagents and main conversation)

**Implication for Hive:** A 4-pane static team (orchestrator/worker/validator/terminal) mostly skips the dynamic-spawn tradeoff — you've pre-paid the seat cost. The live tradeoff becomes:

- **Parallelism:** run worker and validator concurrently only if their tasks are genuinely independent (e.g. worker writes code, validator pre-researches the spec). If the validator must see the worker's output, it's sequential and there is no latency win.
- **Orchestrator compaction:** the orchestrator receiving condensed replies from three panes still risks context bloat. Budget ~2k tokens per return message; plan for `/clear`-equivalent on the orchestrator between tasks.

---

## 5. Explicit "do not do X" warnings

Collected verbatim or near-verbatim:

### Architectural

> "Subagents cannot spawn other subagents. If your workflow requires nested delegation, use Skills or chain subagents from the main conversation." (`sub-agents.md` §Choose between subagents and main conversation)

Hive's `spawn` across panes is unusual compared to Claude Code's model, which caps delegation depth at one. If you allow a worker pane to spawn helpers, you are past Anthropic's guardrail.

### Scoping and context

> "Tasks requiring shared context across all agents [are where multi-agent underperforms]." (`multi-agent-research-system.md`)

> "Heavily interdependent work requiring real-time coordination [is where multi-agent underperforms]." (`multi-agent-research-system.md`)

### Context pollution

> "The kitchen sink session. You start with one task, then ask Claude something unrelated, then go back to the first task. Context is full of irrelevant information." (`claude-code-best-practices.md` §Avoid common failure patterns)

> "The infinite exploration. You ask Claude to 'investigate' something without scoping it. Claude reads hundreds of files, filling the context." (`claude-code-best-practices.md`)

> "Bloated tool sets create decision paralysis. If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better." (`effective-context-engineering.md` §Tools)

### Verification discipline

> "The trust-then-verify gap. Claude produces a plausible-looking implementation that doesn't handle edge cases. Fix: Always provide verification (tests, scripts, screenshots). If you can't verify it, don't ship it." (`claude-code-best-practices.md`)

> "Address the root cause, don't suppress the error." (`claude-code-best-practices.md` §Give Claude a way to verify its work)

### Tool design

> "More tools don't always lead to better outcomes." (`writing-tools-for-agents.md`)

> "We recommend restricting responses to around 25,000 tokens." (`writing-tools-for-agents.md` §Token Efficiency)

### Evals

> "Eval saturation occurs at 100% pass rates, eliminating improvement signals." (`demystifying-evals.md` §Key Warnings)

> "Shared state between trials introduces correlated failures unrelated to agent performance." (`demystifying-evals.md`)

---

## 6. Role-by-role map for Hive's 4 panes

Each role lists the 2–4 most load-bearing rules from the sources above.

### Orchestrator (lead / planner)

- **Hold the plan, not the raw work.** "Specialized sub-agents handle focused tasks with clean context windows, while a coordinator maintains high-level planning." (`effective-context-engineering.md` §Sub-Agent Architectures)
- **Compress the brief going out.** "The only channel from parent to subagent is the Agent tool's prompt string" — the orchestrator must inline paths/errors/decisions, not assume shared history. (`sdk-subagents.md`)
- **Expect 1–2k-token replies back** and size the orchestrator's context accordingly. (`effective-context-engineering.md`)
- **Chain sequentially when tasks depend.** "For multi-step workflows, ask Claude to use subagents in sequence. Each subagent completes its task and returns results to Claude, which then passes relevant context to the next subagent." (`sub-agents.md` §Chain subagents)

### Worker (executor)

- **Worker is the one with the heaviest tool belt and the noisiest context.** The orchestrator should not mirror that noise. "Isolating operations that produce large amounts of output … the verbose output stays in the subagent's context while only the relevant summary returns to your main conversation." (`sub-agents.md` §Isolate high-volume operations)
- **Give the worker verifiable success criteria.** "Include tests, screenshots, or expected outputs so Claude can check itself. This is the single highest-leverage thing you can do." (`claude-code-best-practices.md` §Give Claude a way to verify its work)
- **Scoped tools beat broad tools.** "Each subagent should excel at one specific task" and "Grant only necessary permissions for security and focus." (`sub-agents.md` §Best practices)
- **The worker is where token-cost discipline lives.** "Find the smallest set of high-signal tokens that maximize the likelihood of some desired outcome." (`effective-context-engineering.md` §Practical Guidance)

### Validator (reviewer / critic)

- **Prefer deterministic over LLM-as-judge.** "Defining Rules → Visual Feedback → LLM as Judge (generally less robust)." (`building-agents-with-claude-agent-sdk.md` §Verify Work Phase)
- **Fresh context is the validator's edge.** "A fresh context improves code review since Claude won't be biased toward code it just wrote." (`claude-code-best-practices.md`)
- **Grade the artifact, not the path.** "Grading what the agent produced, not the path it took, prevents overly brittle tests that penalize valid creative solutions." (`demystifying-evals.md` §Practical Development Roadmap)
- **Know when validator is overkill.** "Avoid evaluator-optimizer workflows when first-attempt quality already meets requirements, evaluation criteria are subjective or unclear, or when time and cost constraints outweigh quality improvements." (`building-effective-agents.md` §Evaluator-Optimizer)

### Terminal (user-facing pane)

Anthropic doesn't name this role directly, but several rules bind:

- **Preservation across handoffs requires an explicit ask.** "The parent receives the subagent's final message verbatim as the Agent tool result, but may summarize it in its own response. To preserve subagent output verbatim in the user-facing response, include an instruction to do so in the prompt." (`sdk-subagents.md`)
- **Course-correct early; don't let the terminal accumulate failed tries.** "If you've corrected Claude more than twice on the same issue in one session, the context is cluttered with failed approaches. Run `/clear` and start fresh with a more specific prompt that incorporates what you learned." (`claude-code-best-practices.md`)
- **Permission prompts funnel through the human-facing pane.** "Foreground subagents block the main conversation until complete. Permission prompts and clarifying questions are passed through to you. Background subagents … auto-deny anything not pre-approved." (`sub-agents.md` §Run subagents in foreground or background) — implication: the terminal pane must be the one holding the permission prompts; background worker/validator must pre-negotiate permissions.
- **Let the user steer, not the orchestrator.** The `AskUserQuestion` / interview pattern belongs at the terminal: "For larger features, have Claude interview you first … Ask about technical implementation, UI/UX, edge cases, concerns, and tradeoffs." (`claude-code-best-practices.md` §Let Claude interview you)

---

## 7. Open tensions / things to resolve in Hive's design

These are inferences, not direct quotes — flagged [推断]:

- [推断] Hive's `handoff` looks like Anthropic's "chain subagents" — sequential, compressed. Hive's `spawn` looks like "parallel subagents." Hive's `send` / `reply` has no direct Anthropic analog because in their model the parent↔subagent channel is **one prompt + one final message**, not bidirectional chat. If Hive's design allows mid-task `send` into a running worker, you are building something past the Claude SDK model.
- [推断] Anthropic's strongest published rule — "subagents cannot spawn subagents" — is motivated by "prevent infinite nesting." A 4-pane static team sidesteps this by construction, but any dynamic-spawn escape hatch should preserve the same invariant.
- [推断] The 15× token premium is the hardest commercial rule to argue around. For Hive, it suggests the 4-pane setup should be reserved for workflows where a single-agent loop demonstrably fails (verification gap, breadth-first search, or a hard need for fresh-context review) — not a default team assembled for every task.
- [未验证] No Anthropic page surfaced in this pass gives first-class treatment to **bidirectional agent-to-agent messaging**. Hive's `send` / `reply` model between agents in one "session" may be closer in spirit to Anthropic's unfetched "agent teams" page (referenced but not retrieved) than to the subagent model documented here.

---

## 8. Harness — Anthropic 的定义与对 Hive 的启示

新增的 7 篇文章里有四篇把 "harness" 作为中心概念：`effective-harnesses-for-long-running-agents.md`、`harness-design-long-running-apps.md`、`managed-agents.md`、`building-c-compiler.md`。另外三篇（`enabling-claude-code-to-work-more-autonomously.md`、`swe-bench-sonnet.md`、`equipping-agents-for-the-real-world-with-agent-skills.md`）是 harness 的周边组件。下面只回答本节四个问题。

### 8.1 原文定义

Anthropic 最明确的一句（`managed-agents.md`）：

> "a harness (the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure)"

接下来两句同样直接：

> "harnesses encode assumptions about what Claude can't do on its own." (`managed-agents.md`)

> "The Claude Agent SDK is a powerful, general-purpose agent harness adept at coding, as well as other tasks that require the model to use tools to gather context, plan, and execute." (`effective-harnesses-for-long-running-agents.md`)

再补一条，把 Claude Code 钉成一个具体的 harness：

> "Claude Code is an excellent harness that we use widely across tasks." (`managed-agents.md`)

### 8.2 Anthropic 说 harness 里必须有的组件

把散在四篇里的 harness 职责合起来，能组成一张清单（每条都至少有一篇文章背书）：

| Harness 组件 | 文章出处 | 原文要点 |
| --- | --- | --- |
| **Tool loop**（最底层，无可协商） | `managed-agents.md`, `swe-bench-sonnet.md` | "the loop that calls Claude and routes Claude's tool calls" / "managing the interaction loop" |
| **Context management**（compaction + reset） | `effective-harnesses-for-long-running-agents.md`, `managed-agents.md` | "context management capabilities such as compaction" / "the harness removes compacted messages from Claude's context window" / "added context resets to the harness" |
| **Cross-session memory (file-based)** | `effective-harnesses-for-long-running-agents.md`, `building-c-compiler.md` | `claude-progress.txt` + git commit / "maintain extensive READMEs and progress files" |
| **Subagent / 分工** | `enabling-claude-code-to-work-more-autonomously.md`, `harness-design-long-running-apps.md` | "Subagents delegate specialized tasks" / Planner + Generator + Evaluator |
| **External evaluator（判人与做人分离）** | `harness-design-long-running-apps.md` | "Separating the agent doing the work from the agent judging it proves to be a strong lever" |
| **Permissions / hooks / checkpoints** | `enabling-claude-code-to-work-more-autonomously.md` | Hooks、Checkpoints、Background tasks 被并列为自主工作的必备面 |
| **Skills（懒加载程序性知识）** | `equipping-agents-for-the-real-world-with-agent-skills.md` | "Progressive disclosure is the core design principle" |
| **Recovery：harness 可以失败后独立重启** | `managed-agents.md` | "Recovering from harness failure" / "The harness also became cattle" |
| **Tool surface design** | `swe-bench-sonnet.md`, `writing-tools-for-agents.md` | "much more attention should go into designing tool interfaces for models" |

**特别值得注意的反向动作**：Anthropic 也说 harness 会**过时**——"The resets had become dead weight"（`managed-agents.md`）。Harness 设计里必须有"定期下线组件"的规则，否则就会长期在修一个模型已经不需要的伤口。

### 8.3 Hive 已经具备 vs. 还缺

对照上表：

| 组件 | Hive 现状 | 缺口 |
| --- | --- | --- |
| Tool loop | 每个 pane 里由 Claude/Codex/Droid **自带**，Hive 不管 | [推断] Hive 是 meta-harness，不该自己实现 tool loop — 这一条不算缺口 |
| Context management | 每个 pane 自己 compact；Hive 不统一管 | **缺**：workspace 级别没有 reset 策略；长会话只能指望 pane agent 自己 `/clear` |
| Cross-session memory | 有 worktree + git；没有 Anthropic 式的 `progress.txt` 约定 | **缺**：无"每次会话必须留下 artifacts"的硬约束 |
| Subagent / 分工 | orch + worker + validator + terminal 四 pane 静态分工 | 已具备 |
| External evaluator | validator pane | 已具备，正是 `harness-design-long-running-apps.md` 推的模式 |
| Permissions / hooks / checkpoints | 有 plugin hook 体系；permission 在 pane agent 里 | **缺**：workspace 级 checkpoint（git worktree 接近但非自动）；permission 聚合策略 |
| Skills | `skills/hive/SKILL.md` + `npx skills add` | 已具备 |
| Recovery（harness-as-cattle） | 依赖 sidecar；CLAUDE.md 里写到重启 sidecar 才能验证 | **缺**：sidecar 崩溃不会自动恢复；没有 `emitEvent` 式事件流 |
| Tool surface design | `send`/`reply`/`handoff`/`spawn`/`fork` | 已具备，但工具描述/权限未按 25k-token 预算体系化 |

最刺眼的两个缺口：**workspace 级 context reset** 和 **sidecar 的 cattle 化**。前者是 `managed-agents.md` 和 `harness-design-long-running-apps.md` 都点名的事，Hive 现在还是 pet 不是 cattle。

### 8.4 orch/worker/validator/terminal 四 pane 闭环，算不算 harness 的进化？

**结论：算，但前提是 Hive 自觉把自己定位成 meta-harness，不是又一个 harness。**

理由：

1. Anthropic 在 `managed-agents.md` 里明确把 **harness** 和 **meta-harness** 拆开——"Managed Agents is a meta-harness … unopinionated about the specific harness that Claude will need." Hive 天然在这一层：每个 pane 里跑的是具体 harness（Claude Code / Droid / Codex），Hive 自己并不拥有 tool loop。把 Hive 定位成 meta-harness，这四 pane 闭环就是"多个 harness 被 meta-harness 串起来做 long-running work"的具象化，比 `building-c-compiler.md` 的 16-agent 文件锁方案信息密度更高，比 `harness-design-long-running-apps.md` 的 3-agent 文件 handoff 多一个面向人的终端。
2. 但 Hive 如果继续在 `src/hive/` 里**自己复刻** harness 能力（比如往里加 context compaction、加自己的 tool loop），就会偏离 meta-harness 定位，变成又一个普通 harness，同时还要背 pane agent 自带的 harness 层的所有成本。
3. 四 pane 闭环的独特价值在 `building-c-compiler.md` 作者亲口承认的空白上：他那套 16-agent 架构"haven't yet implemented any other method for communication between agents, nor do I enforce any process for managing high-level goals"。Hive 的 `send`/`reply`/`handoff` 就是填这两个空。这是进化，不是并列。
4. 但要兑现"进化"这个判断，Hive 必须把缺口补上：workspace-level compaction、sidecar 的 cattle 化恢复、workspace checkpoint。只要这三条不补，Hive 就还是"多 pane 的 pet"，而不是"多 harness 的 cattle"。

一句话：**四 pane 闭环是进化，但目前 Hive 的 meta-harness 身份只兑现了一半。**

### NOTE

第 8 节中的 8.3、8.4 两节为 [推断]：对 Hive 现状的对照与定位判断不是 Anthropic 原文提法。8.1、8.2 两节的引号均为 WebFetch 返回的原文，如需进一步核验请对照各个单篇文件顶部的原文引号块。
