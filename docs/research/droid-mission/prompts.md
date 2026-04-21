---
source: ~/.local/bin/droid (v0.104.0)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Agent Prompt Library

Each file under [`prompts/`](prompts/) is a **verbatim** extraction of a
backtick-delimited template-string from the droid binary. Extraction
was done by locating the `=\`# <Title>` opener, matching the closing
backtick with escape-awareness, and writing the resulting body out
as-is. Scrutiny prompt uses single-quoted form (`aaq='…'`) and was
unescaped for `\n`. No hand-editing. **[已验证]**

## Index

| File in `prompts/`                       | In-binary variable | Starts with …                     | Chars | Confidence |
|------------------------------------------|--------------------|-----------------------------------|-------|------------|
| `orchestrator_role.md`                   | `Og9`              | `# Role & Mindset`                | 58832 | [已验证]   |
| `skill_mission-planning.md`              | `raq`              | `# Mission Planning`              | 15019 | [已验证]   |
| `skill_designing-workers.md`             | `taq`              | `# Designing Your Worker System`  | 8254  | [已验证]   |
| `skill_worker-base-procedures.md`        | `saq`              | `# Worker Base Procedures`        | 14288 | [已验证]   |
| `skill_scrutiny-validator.md`            | `aaq`              | `# Scrutiny Validator`            | 8575  | [已验证]   |
| `skill_user-testing-validator.md`        | `eaq`              | `# User Testing Validator`        | 12560 | [已验证]   |
| `skill_user-testing-flow-validator.md`   | `Jg9`              | `# User Testing Flow Validator`   | 6741  | [已验证]   |
| `skill_browser-automation.md`            | `<unnamed>`        | `# Browser Automation with agent-browser` | 30806 | [已验证] |
| `skill_tui-testing.md`                   | `oaq`              | `# TUI Testing with tuistory`     | 6141  | [已验证]   |
| `playbook_refactoring.md`                | `Heq`              | `# Refactoring & Migration Playbook` | 7785 | [已验证] |
| `playbook_tui.md`                        | `Teq`              | `# TUI Application Playbook`      | 4166  | [已验证]   |
| `skill_figma-mcp-promotion.md`           | `<unnamed>`        | `# Figma MCP Promotion`           | 3191  | [已验证]   |
| `template_marker.md`                     | (template root)    | `# ${H}`                          | 12    | [已验证]   |

`template_marker.md` is a template-substitution placeholder. It is a
harmless leftover from a meta-template (`# ${H}` where `${H}` gets
replaced by a skill name at lookup time).

## Prompt role map

| Role in mission runtime              | Authoritative prompt(s)                                              |
|--------------------------------------|----------------------------------------------------------------------|
| **Orchestrator** system              | `orchestrator_role.md`                                               |
| Orchestrator helper skills           | `skill_mission-planning.md`, `skill_designing-workers.md`             |
| **Worker** system (shared)           | `skill_worker-base-procedures.md`                                    |
| **Scrutiny validator** worker        | `skill_scrutiny-validator.md`                                        |
| **User-testing validator** worker    | `skill_user-testing-validator.md`                                    |
| User-testing sub-agent               | `skill_user-testing-flow-validator.md`                               |
| Domain playbooks (optional, skill-invoked) | `playbook_refactoring.md`, `playbook_tui.md`                   |
| Cross-cutting skill prompts          | `skill_browser-automation.md`, `skill_tui-testing.md`, `skill_figma-mcp-promotion.md` |

**How roles become system prompts**: the binary does not hardcode a
single "worker system prompt"; instead the TUI assembles a bootstrap
message at worker spawn (see `TsB(missionDir, feature, workerSessionId)`
call from `MissionRunner.spawnWorker`). The first thing the worker does
is invoke both `worker-base-procedures` and the feature's
`feature.skillName` skill. That skill's file (`.factory/skills/…` or
one of the built-in ones above) becomes the worker's effective domain
prompt. **[已验证]** — pattern described literally in
`skill_worker-base-procedures.md` §1.1–1.3.

## Notable quotes

### Orchestrator self-description **[已验证]**

> You are the architect and manager of a multi-agent mission. You plan
> the work, design the system of workers that will build it, and ensure
> quality through that system.
>
> You don't build — you design systems that build, and steer them to
> success.

And later, regarding the runtime:

> **start_mission_run is a blocking call.** When you invoke it, the
> tool call remains open and you cede control to the mission runner.
> The runner spawns workers sequentially, each executing one feature.
> You cannot perform any other actions while the call is in flight —
> the runner owns execution until it returns control to you.

### Tools exposed to the orchestrator **[已验证]** (literal list)

```
- propose_mission   — Present a plan for user review
- start_mission_run — Begin worker execution after setup
- dismiss_handoff_items — Explicitly dismiss handoff items you've decided
                          not to act on (requires justification)
- Skill             — Invoke skills (use for mission-planning,
                      define-mission-skills)
- Create            — Create mission files and worker skills
```

### Worker tool-call boundary **[已验证]** (from worker base procedures)

> Your feature has been pre-assigned by the system and is shown in your
> bootstrap message. The feature includes: `id`, `description`,
> `skillName`, `expectedBehavior`, `verificationSteps`, `fulfills`.
>
> Your feature's `fulfills` field lists validation contract assertions
> that must be true after your work. Read these assertions carefully
> before starting — they define what "done" means for your feature.

### Worker's exit tool **[已验证]**

The worker ends its turn via `end_feature_run` with a Zod-validated
`handoff` object (see `schemas.md`). The orchestrator never sees the
worker's transcript directly; it sees the handoff summary and the
`handoffFile` path. A transcript *skeleton* is saved separately by the
runner (`appendTranscriptSkeleton`).

### Validator auto-injection **[已验证]**

Both scrutiny and user-testing validators are injected by the runtime,
not authored by the orchestrator. Orchestrator prompt calls this out:

> Both `scrutiny-validator` and `user-testing-validator` are
> auto-injected by the system when a milestone completes. Don't create
> these yourself — never add features with these skillNames to
> features.json. Always rely on the system's auto-injection.

## Prompt-level "skillName" conventions

Observed in prompts and code **[已验证]**:

- `mission-planning` — orchestrator helper skill; invoked first thing
  after mission proposal.
- `define-mission-skills` — orchestrator helper skill; co-invoked with
  `mission-planning`. **(Prompt body for this skill was not bundled in
  the binary we saw — it is referenced but the text lives elsewhere.)**
  [未验证] that it's a built-in vs ad-hoc skill.
- `scrutiny-validator` / `user-testing-validator` — reserved validator
  skillNames, auto-injected.
- `worker-base-procedures` — shared worker startup skill, invoked by
  every worker after reading its bootstrap message.

## What we could NOT find

- **A distinct "judge" / "reviewer" persona.** Review is embedded in
  scrutiny; there is no separate referee agent.
- **An "AskUser" / interrupt prompt tailored to the orchestrator.** The
  orchestrator relies on the generic AskUser tool and its own system
  prompt's "When to Return to User" section.
- **A worker-specific system prompt distinct from skill prompts.** The
  worker's identity is composed at runtime from
  `worker-base-procedures.md` + the feature's skill file.
