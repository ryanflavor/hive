---
source: https://docs.claude.com/en/docs/agent-sdk/subagents (redirected to code.claude.com/docs/en/agent-sdk/subagents)
fetched: 2026-04-19
author: Anthropic
---

# Subagents in the SDK

> Define and invoke subagents to isolate context, run tasks in parallel, and apply specialized instructions in your Claude Agent SDK applications.

Subagents are separate agent instances that your main agent can spawn to handle focused subtasks.

Use subagents to isolate context for focused subtasks, run multiple analyses in parallel, and apply specialized instructions without bloating the main agent's prompt.

## Overview

You can create subagents in three ways:

* **Programmatically**: use the `agents` parameter in your `query()` options
* **Filesystem-based**: define agents as markdown files in `.claude/agents/` directories
* **Built-in general-purpose**: Claude can invoke the built-in `general-purpose` subagent at any time via the Agent tool without you defining anything

When you define subagents, Claude determines whether to invoke them based on each subagent's `description` field. Write clear descriptions that explain when the subagent should be used, and Claude will automatically delegate appropriate tasks. You can also explicitly request a subagent by name in your prompt.

## Benefits of using subagents

### Context isolation

Each subagent runs in its own fresh conversation. Intermediate tool calls and results stay inside the subagent; only its final message returns to the parent.

**Example:** a `research-assistant` subagent can explore dozens of files without any of that content accumulating in the main conversation. The parent receives a concise summary, not every file the subagent read.

### Parallelization

Multiple subagents can run concurrently, dramatically speeding up complex workflows.

**Example:** during a code review, you can run `style-checker`, `security-scanner`, and `test-coverage` subagents simultaneously, reducing review time from minutes to seconds.

### Specialized instructions and knowledge

Each subagent can have tailored system prompts with specific expertise, best practices, and constraints.

### Tool restrictions

Subagents can be limited to specific tools, reducing the risk of unintended actions.

**Example:** a `doc-reviewer` subagent might only have access to Read and Grep tools, ensuring it can analyze but never accidentally modify your documentation files.

## Creating subagents

### Programmatic definition (recommended)

Define subagents directly in your code using the `agents` parameter. The `Agent` tool must be included in `allowedTools` since Claude invokes subagents through the Agent tool.

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for message in query(
    prompt="Review the authentication module for security issues",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob", "Agent"],
        agents={
            "code-reviewer": AgentDefinition(
                description="Expert code review specialist. Use for quality, security, and maintainability reviews.",
                prompt="""You are a code review specialist...""",
                tools=["Read", "Grep", "Glob"],
                model="sonnet",
            ),
            "test-runner": AgentDefinition(
                description="Runs and analyzes test suites. Use for test execution and coverage analysis.",
                prompt="""You are a test execution specialist...""",
                tools=["Bash", "Read", "Grep"],
            ),
        },
    ),
):
    ...
```

### AgentDefinition configuration

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `description` | `string` | Yes | Natural language description of when to use this agent |
| `prompt` | `string` | Yes | The agent's system prompt defining its role and behavior |
| `tools` | `string[]` | No | Array of allowed tool names. If omitted, inherits all tools |
| `model` | `'sonnet' \| 'opus' \| 'haiku' \| 'inherit'` | No | Model override for this agent |
| `skills` | `string[]` | No | List of skill names available to this agent |
| `memory` | `'user' \| 'project' \| 'local'` | No | Memory source for this agent (Python only) |
| `mcpServers` | `(string \| object)[]` | No | MCP servers available to this agent |

> Subagents cannot spawn their own subagents. Don't include `Agent` in a subagent's `tools` array.

## What subagents inherit

A subagent's context window starts fresh (no parent conversation) but isn't empty. **The only channel from parent to subagent is the Agent tool's prompt string**, so include any file paths, error messages, or decisions the subagent needs directly in that prompt.

| The subagent receives | The subagent does not receive |
| :--- | :--- |
| Its own system prompt (`AgentDefinition.prompt`) and the Agent tool's prompt | The parent's conversation history or tool results |
| Project CLAUDE.md (loaded via `settingSources`) | Skills (unless listed in `AgentDefinition.skills`) |
| Tool definitions (inherited from parent, or the subset in `tools`) | The parent's system prompt |

> The parent receives the subagent's final message verbatim as the Agent tool result, but may summarize it in its own response. To preserve subagent output verbatim in the user-facing response, include an instruction to do so in the prompt or `systemPrompt` option you pass to the main `query()` call.

## Invoking subagents

### Automatic invocation

Claude automatically decides when to invoke subagents based on the task and each subagent's `description`. For example, if you define a `performance-optimizer` subagent with the description "Performance optimization specialist for query tuning", Claude will invoke it when your prompt mentions optimizing queries.

### Explicit invocation

To guarantee Claude uses a specific subagent, mention it by name in your prompt:

```
"Use the code-reviewer agent to check the authentication module"
```

### Dynamic agent configuration

You can create agent definitions dynamically based on runtime conditions. Example: a security reviewer with different strictness levels, using a more powerful model for strict reviews.

## Resuming subagents

Subagents can be resumed to continue where they left off. Resumed subagents retain their full conversation history, including all previous tool calls, results, and reasoning. The subagent picks up exactly where it stopped rather than starting fresh.

Subagent transcripts persist independently of the main conversation:

* **Main conversation compaction**: When the main conversation compacts, subagent transcripts are unaffected.
* **Session persistence**: Subagent transcripts persist within their session.
* **Automatic cleanup**: Transcripts are cleaned up based on the `cleanupPeriodDays` setting (default: 30 days).

## Tool restrictions

Subagents can have restricted tool access via the `tools` field:

* **Omit the field**: agent inherits all available tools (default)
* **Specify tools**: agent can only use listed tools

### Common tool combinations

| Use case | Tools | Description |
| :--- | :--- | :--- |
| Read-only analysis | `Read`, `Grep`, `Glob` | Can examine code but not modify or execute |
| Test execution | `Bash`, `Read`, `Grep` | Can run commands and analyze output |
| Code modification | `Read`, `Edit`, `Write`, `Grep`, `Glob` | Full read/write access without command execution |
| Full access | All tools | Inherits all tools from parent (omit `tools` field) |

## Troubleshooting

### Claude not delegating to subagents

1. **Include the Agent tool**: subagents are invoked via the Agent tool, so it must be in `allowedTools`.
2. **Use explicit prompting**: mention the subagent by name in your prompt.
3. **Write a clear description**: explain exactly when the subagent should be used so Claude can match tasks appropriately.

---

NOTE: Captured via WebFetch. Full SDK documentation page preserved including the critical "What subagents inherit" table (load-bearing for context-sharing design decisions), the AgentDefinition schema, and the warning that subagents cannot spawn subagents. Mintlify CodeGroup tags flattened to single Python examples.
