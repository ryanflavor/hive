---
source: ~/.local/bin/droid (v0.104.0)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Mission Data Schemas

All structures below are on-disk representations used by droid's
MissionFileService (`class rKH`, offset 62582419) and its Zod schema
IIFE `sXT=c(()=>{…})` (offset ~59690530). Zod identifier aliasing:

- `CH` = `zod`
- `oXT` = **Feature** schema
- `dXT` = **SuccessState** enum (`zz` before aliasing, `q_H` is the enum
  source)
- `hV0 / IV0 / LV0 / $V0 / OV0 / uyH / rXT` = handoff sub-schemas
- `tXT` = **ProgressLogEntry** discriminated union
- `WV0, JV0, EV0, QV0, KV0, GV0, UV0, NV0, wV0, XV0, PV0` = individual
  log-entry variants
- `zz` = **FeatureStatus** enum

Where the binary uses obfuscated identifiers (`q_H`, `zz`, `rKR`, `tKR`),
the possible enum values are reverse-engineered from adjacent string
literals. Unless noted, every quoted schema below is **[已验证]** —
pasted verbatim from the binary text.

## Mission workspace layout

From `MissionFileService` constructors + path helpers **[已验证]**:

```
<FactoryHome>/<workspaceSlug>/missions/<baseSessionId>/
  ├── state.json                       ← authoritative mission state
  ├── mission.md                       ← user-accepted proposal (orchestrator writes)
  ├── features.json                    ← feature list + ordering
  ├── progress_log.jsonl               ← JSONL event stream (runner + tools append)
  ├── validation-contract.md           ← orchestrator-authored, no Zod schema
  ├── validation-state.json            ← per-assertion pass/pending/failed (inferred)
  ├── AGENTS.md                        ← worker constraints / boundaries
  ├── working-directory                ← tiny file storing mission.workingDirectory
  ├── model-settings.json              ← mission-scoped overrides (only written when ≠ global)
  ├── runtime-custom-models.json       ← dumped BYOK custom-model list (workers share)
  ├── handoffs/
  │     └── <featureId>-<workerSessionId>.json   ← EndFeatureRun payload (full handoff)
  └── transcript-skeleton.md           ← per-feature transcript skeleton
```

`<FactoryHome>` resolves via `NB()` + `f9()` (user's `~/.factory` +
workspace-hashed slug; `ep(cwd)` hashes the cwd). **[已验证]** path
helper: `eX.join(rz(), "missions", baseSessionId)`.

There is **no separate `mission.log`**; `progress_log.jsonl` is the
single structured event log. **[已验证]**

### Repo-root artifacts (written by agents, NOT by runner)

The orchestrator prompt enumerates additional files that live under the
**repo root**, inside `.factory/`:

- `.factory/services.yaml` — single source of truth for commands + services
- `.factory/init.sh` — idempotent env setup
- `.factory/library/*.md` — living knowledge base (architecture,
  environment, user-testing, etc.)
- `.factory/skills/<worker-type>/SKILL.md` — per-worker-type procedures
- `.factory/validation/<milestone>/scrutiny/synthesis.json`
- `.factory/validation/<milestone>/scrutiny/<feature>.json`
- `.factory/validation/<milestone>/user-testing/synthesis.json`
- `.factory/validation/<milestone>/user-testing/<assertion>.json`

Validator synthesis files are **prompt-contract only [未验证]** — no Zod
validator was found. Their shape is sketched at the end of this doc.

## `state.json`

```ts
type MissionState = {
  missionId: string;                   // `mis_<8hex>`
  state: "awaiting_input" | "initializing" | "running" | "paused" |
         "orchestrator_turn" | "completed";
  workingDirectory: string;            // absolute path; mirrors working-directory file
  createdAt: string;                   // ISO-8601
  updatedAt: string;                   // ISO-8601, refreshed on every write
  lastReviewedHandoffCount?: number;   // cursor into progress_log worker_completed events
}
```

Verbatim constructor **[已验证]**:
```js
let T = new Date().toISOString(),
    R = {
      missionId: `mis_${W1().slice(0,8)}`,
      state: "initializing",
      workingDirectory: H,
      createdAt: T,
      updatedAt: T
    };
return await this.writeState(R), R
```

## `features.json`

Zod **[已验证]** (`oXT`):

```js
oXT = CH.object({
  id:                      CH.string(),
  description:             CH.string(),
  status:                  CH.nativeEnum(zz),            // FeatureStatus
  skillName:               CH.string(),
  preconditions:           CH.array(CH.string()),
  expectedBehavior:        CH.array(CH.string()),
  verificationSteps:       CH.array(CH.string()),
  fulfills:                CH.array(CH.string()).optional(), // validation-contract IDs
  milestone:               CH.string().optional(),
  workerSessionIds:        CH.array(CH.string()).optional(),
  currentWorkerSessionId:  CH.string().nullable().optional(),
  completedWorkerSessionId:CH.string().nullable().optional()
})
```

Root file is `{ features: Feature[] }`; legacy bare-array format is
tolerated. `writeFeatures` always serialises the object form. **[已验证]**

### `FeatureStatus` (`zz`) enum

**[已验证]** — values enumerated from code paths (`updateFeature(..., {status:"in_progress"})`,
`status==="completed"`, `status==="cancelled"`, `status==="pending"`,
`moveStrandedDoneFeaturesToBottom`):

```
pending | in_progress | completed | cancelled
```

Runner semantics:
- `pending` → eligible for next worker.
- `in_progress` → owned by the worker whose id is at
  `workerSessionIds[-1]` (also mirrored to `currentWorkerSessionId`).
- `completed` → auto-moved to bottom; frozen.
- `cancelled` → treated as done for milestone completion; also bottomed.

### `skillName` values observed

Built-in validator skillNames **[已验证]** (declared in the runner as
`JIH = [scrutiny-validator, user-testing-validator]`):

- `scrutiny-validator`
- `user-testing-validator`

All other skillNames are author-declared and map to files under
`.factory/skills/<skillName>/SKILL.md`. **[推断]** (reader pattern in
worker-base procedures prompt.)

## Progress log — `progress_log.jsonl`

Discriminated union `tXT` **[已验证]**:

```js
tXT = CH.discriminatedUnion("type", [
  WV0,  // mission_accepted
  JV0,  // mission_paused
  EV0,  // mission_resumed
  QV0,  // mission_run_started
  KV0,  // worker_started
  GV0,  // worker_selected_feature
  UV0,  // worker_completed
  NV0,  // worker_failed
  wV0,  // worker_paused
  XV0,  // handoff_items_dismissed
  PV0,  // milestone_validation_triggered
]);
```

Base shape `rn` **[已验证]**:

```js
rn = CH.object({ timestamp: CH.string() });           // ISO-8601
```

Each variant extends `rn`. Verbatim **[已验证]**:

```js
WV0 = rn.extend({ type: CH.literal("mission_accepted"),
                  title: CH.string() });

JV0 = rn.extend({ type: CH.literal("mission_paused") });

EV0 = rn.extend({ type: CH.literal("mission_resumed"),
                  resumeWorkerSessionId: CH.string().optional() });

QV0 = rn.extend({ type: CH.literal("mission_run_started"),
                  message: CH.string().optional() });

KV0 = rn.extend({ type: CH.literal("worker_started"),
                  workerSessionId: CH.string(),
                  spawnId:         CH.string(),
                  featureId:       CH.string().optional() });

GV0 = rn.extend({ type: CH.literal("worker_selected_feature"),
                  workerSessionId: CH.string(),
                  featureId:       CH.string() });

UV0 = rn.extend({ type: CH.literal("worker_completed"),
                  workerSessionId:     CH.string(),
                  featureId:           CH.string(),
                  successState:        dXT,         // success|partial|failure
                  returnToOrchestrator:CH.boolean(),
                  commitId:            CH.string().optional(),
                  exitCode:            CH.number(),
                  validatorsPassed:    CH.boolean().optional(),
                  handoff:             uyH.optional() });

NV0 = rn.extend({ type: CH.literal("worker_failed"),
                  workerSessionId: CH.string().optional(),
                  spawnId:         CH.string(),
                  exitCode:        CH.number().optional(),
                  reason:          CH.string() });

wV0 = rn.extend({ type: CH.literal("worker_paused"),
                  workerSessionId: CH.string(),
                  featureId:       CH.string().optional() });

XV0 = rn.extend({ type: CH.literal("handoff_items_dismissed"),
                  dismissals: CH.array(rXT).optional() });

PV0 = rn.extend({ type: CH.literal("milestone_validation_triggered"),
                  milestone: CH.string(),
                  featureId: CH.string() });
```

## `SuccessState` (`dXT = CH.nativeEnum(q_H)`)

**[已验证]** — values `"success"`, `"partial"`, `"failure"` (`end_feature_run`
tool uses them directly; runner checks `n==="failure"||n==="partial"`).

## Handoff payload (`uyH`)

Full Zod **[已验证]**:

```js
uyH = CH.object({
  salientSummary:     CH.string().optional(),
  whatWasImplemented: CH.string(),
  whatWasLeftUndone:  CH.string(),
  verification:       hV0,    // commands + interactive checks
  tests:              IV0,    // tests added/updated
  discoveredIssues:   CH.array(LV0),
  skillFeedback:      OV0.optional()
});
```

Sub-schemas **[已验证]**:

```js
// Verification artefacts
qV0 = CH.object({ command: CH.string(),
                  exitCode: CH.number(),
                  observation: CH.string() });
DV0 = CH.object({ action:   CH.string(),
                  observed: CH.string() });
hV0 = CH.object({ commandsRun:       CH.array(qV0),
                  interactiveChecks: CH.array(DV0).optional() });

// Tests
CV0 = CH.object({ name: CH.string(), verifies: CH.string() });
_V0 = CH.object({ file: CH.string(), cases: CH.array(CV0) });
IV0 = CH.object({ added:    CH.array(_V0),
                  updated:  CH.array(CH.string()).optional(),
                  coverage: CH.string() });

// Discovered issues
AV0 = CH.nativeEnum(rKR);   // Severity enum   [推断] low|medium|high|critical
BV0 = CH.nativeEnum(tKR);   // HandoffItemType [推断] issue|unfinished|question|...
LV0 = CH.object({ severity:     AV0,
                  description:  CH.string(),
                  suggestedFix: CH.string().optional() });

// Skill-feedback / deviations
$V0 = CH.object({ step:             CH.string(),
                  whatIDidInstead:  CH.string(),
                  why:              CH.string() });
OV0 = CH.object({ followedProcedure: CH.boolean(),
                  deviations:        CH.array($V0),
                  suggestedChanges:  CH.array(CH.string()).optional() });
```

Runtime validation in `end_feature_run` adds **behaviour on top of the
Zod schema** **[已验证]**:

- `salientSummary` is **required** (despite `.optional()` in Zod),
  20–500 chars, 1–4 sentences, no `\n`.
- `successState==="success"` → `commitId` + `validatorsPassed===true`
  both required.
- `returnToOrchestrator` is derived from any of:
  - tool arg `returnToOrchestrator === true`, OR
  - `handoff.discoveredIssues.length > 0`, OR
  - `handoff.whatWasLeftUndone` non-empty & not `"none"`.

## Handoff dismissal (`rXT`)

**[已验证]**:

```js
rXT = CH.object({
  type:           BV0,             // HandoffItemType enum
  sourceFeatureId:CH.string(),
  summary:        CH.string(),
  justification:  CH.string()
});
```

The orchestrator calls `dismiss_handoff_items` with an array of these
before re-starting the run so that the dismissals are auditable. The
tool appends a single `handoff_items_dismissed` progress entry.
**[已验证]** (class `mAA` at end of `dismiss_handoff_items` tool code).

## Per-feature handoff file (`handoffs/<feature>-<worker>.json`)

Produced by `missionFileService.ensureWorkerHandoffJson(...)`. Contents
**[推断]** from call-sites — it serialises:

```ts
{
  timestamp: string;           // ISO
  workerSessionId: string;
  featureId: string;
  milestone?: string;
  commitId?: string;
  successState: "success"|"partial"|"failure";
  returnToOrchestrator: boolean;
  handoff: uyH;                // full Zod-validated payload above
}
```

`XbT({ missionFileService, includeLatestWorkerHandoff:true })`
(`src … nAA.ts` in original source) reads this file when constructing
`start_mission_run`'s return value, so the orchestrator receives the
freshest one in full. **[已验证]**

## `model-settings.json`

Only fields that deviate from the user's global mission defaults are
written. Keys observed in comparison helper `KB8({currentSettings,
globalSettings})` **[已验证]**:

```
workerModel
workerReasoningEffort
validationWorkerModel
validationWorkerReasoningEffort
skipScrutiny
skipUserTesting
```

Mission-model label strings (for the TUI) **[已验证]**:

```
missionModelLabels: {
  orchestrator:           "Orchestrator: {{model}}",
  orchestratorShort:      "Orch: {{model}}",
  orchestratorLabel:      "Orchestrator: ",
  orchestratorLabelShort: "Orch: ",
  worker:                 "Worker: {{model}}",
  workerShort:            "Wrkr: {{model}}",
  workerLabel:            "Worker: ",
  workerLabelShort:       "Wrkr: ",
  ...
}
```

## `propose_mission` payload

The tool arg schema is not explicitly Zod-fied in the bundle we read;
runtime validation is done against **[已验证]** fields extracted from
the tool implementation (`class bAA`):

```ts
type ProposeMissionArgs = {
  title:             string;
  proposal:          string;   // markdown body of mission.md
  workingDirectory?: string;   // defaults to process.cwd()
};
```

Tool output on accept (evidence from `etB(missionDir)` system
notification and `g08(result)`):

```ts
{
  accepted: true,
  missionDir: string,
  isEdited?: boolean,
  llmGuidance?: string      // "Mission was approved but the user has left…"
}
```

On reject (confirmationOutcome absent / non-proceed):

```ts
{ accepted: false }
```

## `start_mission_run` return

**[推断]** (pieced together from `XbT` (= `nAA.ts`) + tool wrapper
(`class aAA`) at offset ~66759508):

```ts
{
  state: "paused" | "orchestrator_turn" | "completed",
  message: string,                         // human explanation of why runner returned
  workerHandoffs: Array<{
    featureId: string,
    resultState: "pass"|"fail",
    discoveredIssuesCount: number,
    unfinishedWorkCount: number,
    whatWasImplemented: string,
    handoffFile: string,
  }>,
  latestWorkerHandoff?: {
    featureId: string,
    resultState: "pass"|"fail",
    handoffFile: string,
    handoffJson: string                    // raw JSON text of the handoff file
  }
}
```

## Validation files (prompt-level contract)

Based on orchestrator prompt text (`prompts/orchestrator_role.md`):

### `validation-contract.md`

Markdown with **assertion IDs** of the form `VAL-<AREA>-NNN` (example
`VAL-LLM-XXX` appears in the prompt). Each assertion is a behavioural
description + pass/fail criteria. Organised by surface → area, plus
cross-area flows.

### `validation-state.json` **[未验证]** — no Zod schema found

Inferred shape:
```ts
Record<AssertionId, "pending"|"passed"|"failed"|"blocked">
```
Every `VAL-*` ID must also appear as exactly one feature's `fulfills[]`
(the "coverage invariant" enforced by the orchestrator prompt).

### `.factory/validation/<milestone>/scrutiny/synthesis.json` **[未验证]**

Observed references:
- `appliedUpdates` — field surfaced to orchestrator as "already done, FYI"
- `suggestedGuidanceUpdates` — field to act on
- justification notes for overrides

No runtime Zod validator. This is a prompt-level contract between the
scrutiny-validator skill and the orchestrator.

### `.factory/validation/<milestone>/user-testing/synthesis.json` **[未验证]**

Same structural pattern. May include knowledge-persistence updates
applied to `.factory/library/user-testing.md` and `.factory/services.yaml`.

## Enum tables (consolidated)

| Enum                     | Values (verbatim where possible)                                                     | Confidence |
|--------------------------|--------------------------------------------------------------------------------------|------------|
| MissionState (`uK`)      | `awaiting_input`, `initializing`, `running`, `paused`, `orchestrator_turn`, `completed` | [已验证]   |
| FeatureStatus (`zz`)     | `pending`, `in_progress`, `completed`, `cancelled`                                   | [已验证]   |
| SuccessState (`q_H`)     | `success`, `partial`, `failure`                                                      | [已验证]   |
| Severity (`rKR`)         | likely `low|medium|high|critical`                                                    | [推断]    |
| HandoffItemType (`tKR`)  | likely enumerates dismissal/item types (issue, unfinished, question, override)       | [推断]    |
| InteractionMode (`R4`)   | `auto`, `spec`, `agi`                                                                | [已验证]   |
| AutonomyLevel (`MO`)     | `off`, `low`, `medium`, `high`                                                       | [已验证]   |
| AgentRole (`gK`)         | `orchestrator`, `worker`                                                             | [已验证]   |
| ReasoningEffort (`M1`)   | shared with generic chat: `off|low|medium|high` (plus custom-model extras)           | [已验证]   |
