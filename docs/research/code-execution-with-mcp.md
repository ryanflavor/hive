---
source: https://www.anthropic.com/engineering/code-execution-with-mcp
fetched: 2026-04-19
author: Anthropic (Adam Jones, Conor Kelly)
published: 2025-11-04
---

# Code Execution with MCP: Building More Efficient Agents

## Overview

The Model Context Protocol (MCP) enables AI agents to connect with external systems through a universal standard. However, as agents scale to handle hundreds or thousands of tools, two efficiency problems emerge: tool definitions consume excessive context, and intermediate results must repeatedly pass through the model's attention.

## The Core Problems

### Tool Definition Overload

When MCP clients load all tool definitions upfront, they occupy substantial context space. For agents connected to thousands of tools, this can mean processing "hundreds of thousands of tokens before reading a request."

### Intermediate Result Duplication

When an agent retrieves a document and then uses it in a subsequent operation, the full content must pass through the model multiple times. A two-hour meeting transcript could require an additional 50,000 tokens to be processed, and extremely large documents may exceed context limits entirely.

## The Solution: Code Execution with MCP

Rather than exposing tools as direct function calls, agents can interact with MCP servers by writing code. This approach addresses both challenges through on-demand tool discovery and in-environment data processing.

### Implementation Pattern

Tools can be organized as a filesystem structure:

```
servers/
├── google-drive/
│   ├── getDocument.ts
│   └── index.ts
├── salesforce/
│   ├── updateRecord.ts
│   └── index.ts
```

Agents then discover tools by exploring directories and load only necessary definitions. The authors' example demonstrates reducing token usage "from 150,000 tokens to 2,000 tokens — a time and cost saving of 98.7%."

## Key Benefits

**Progressive Disclosure**
Models can navigate filesystems to load tool definitions on-demand rather than upfront, or use a search function to find relevant tools by category.

**Context-Efficient Results**
Agents filter and transform data within the execution environment before returning summaries to the model. Processing 10,000 spreadsheet rows and returning only filtered results keeps context lean.

**Control Flow Efficiency**
Loops, conditionals, and error handling execute as code rather than chaining multiple tool calls, reducing latency and improving reliability.

**Privacy Preservation**
Intermediate results remain in the execution environment by default. Sensitive data can flow between systems without entering the model's context. The article describes tokenizing personally identifiable information automatically, preventing agents from accidentally processing or logging sensitive details.

**State Persistence**
Agents maintain progress across operations through filesystem access, enabling resumable workflows and persistence of reusable skills developed during execution.

## Important Tradeoffs

Code execution introduces operational complexity requiring "secure execution environment with appropriate sandboxing, resource limits, and monitoring." The authors note these "infrastructure requirements add operational overhead and security considerations that direct tool calls avoid," requiring careful evaluation against the efficiency benefits.

## Acknowledgment

Written by Adam Jones and Conor Kelly, with feedback from Jeremy Fox, Jerome Swannack, Stuart Ritchie, Molly Vorwerck, Matt Samuels, and Maggie Vo.

---

NOTE: WebFetch returned a condensed rendering of the article. The filesystem-as-tool-registry pattern, the 150k→2k token reduction figure, and the five benefit categories are preserved; consult the source URL for the original full-length prose.
