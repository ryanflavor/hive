---
source: ~/.local/bin/droid (v0.104.0)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Mission Runtime Architecture

This document describes **how** droid runs a mission once the orchestrator
accepts a `propose_mission` call.

## TL;DR

- **[已验证]** Single in-process runner class `dAA` = `MissionRunner`,
  located at byte offset `66733181` in the v0.104.0 binary.
- **[已验证]** Workers are sibling **sessions spawned via a local daemon
  (`factoryd`)**; they are not OS subprocesses from the orchestrator's
  point of view.
- **[已验证]** Execution is **sequential, one worker at a time**, with
  preemption via reordering `features.json`.
- **[已验证]** State is persisted on disk in
  `<FactoryHome>/<workspaceSlug>/missions/<baseSessionId>/state.json` and
  friends; there is **no in-memory cache authoritative over disk**.

## Entry points

### How a mission is started

1. The **orchestrator session** is chosen by the user via Mission Control
   TUI (`/missions` slash command), which flips the session into
   orchestrator interaction-mode. **[已验证]**:
   ```
   missionRequiresOrchestrator: "Mission Control is only available in
     orchestrator sessions. Run /missions and select + New Mission first."
   ```
2. The orchestrator LLM emits the `propose_mission` tool call (see
   [`cli-surface.md`](cli-surface.md)) with `title`, `proposal`, and
   `workingDirectory`. **[已验证]** (class `bAA`, around offset ~62.5MB in
   the bundle).
3. User approves the proposal; the tool handler creates the mission dir
   via `missionFileService.initializeMissionDir()`, writes `mission.md`,
   writes `working-directory` metadata, and appends a
   `mission_accepted` progress-log entry.
4. The orchestrator produces `validation-contract.md`, `features.json`,
   `AGENTS.md`, skills, manifests. **Still an LLM turn — the runner is
   dormant.**
5. The orchestrator calls `start_mission_run`. This is the entry point
   into `MissionRunner.start(abortSignal, resumeWorkerSessionId?)`.

### Runner invariants

- `isRunning=true` is a hard single-instance lock; a second `start()` is
  ignored with a log (`"[MissionRunner] Already running, ignoring start
  request"`). **[已验证]**
- The runner installs a `process.on("SIGINT", …)` handler that routes to
  `this.pause()`. Ctrl-C inside droid pauses the mission. **[已验证]**
- `start_mission_run` is **a blocking tool call**. The orchestrator's turn
  is suspended until the runner returns control by writing
  `state=orchestrator_turn` / `paused` / `completed`. This is called out
  explicitly in the orchestrator prompt (see
  `prompts/orchestrator_role.md`). **[已验证]**

## Runner state machine

`state.json.state` is an enum **[已验证]**
(from offset 59605865, declared as TS enum `uK`):

```
awaiting_input | initializing | running | paused | orchestrator_turn | completed
```

Verbatim source:
```
((C)=>{C.AwaitingInput="awaiting_input";C.Initializing="initializing";
       C.Running="running";C.Paused="paused";
       C.OrchestratorTurn="orchestrator_turn";C.Completed="completed"})(uK||={})
```

Transitions executed by the runner (`dAA.runLoop`) **[已验证]**:

```
                ┌── new mission accepted (propose_mission)
                ▼
          initializing
                │ orchestrator writes features.json, commits artifacts
                ▼
          running  ◀──────────── start_mission_run
             │  │
   runner picks next pending feature
             │  │
             ▼  ▼
        spawn/resume worker
             │
             ├─ worker s쳮ds, no returnToOrchestrator ─► running (loop)
             ├─ worker returnToOrchestrator=true ─────────► orchestrator_turn
             ├─ worker success=false (failure|partial)   ─► orchestrator_turn
             ├─ milestone complete ─► inject scrutiny + user-testing validators
             │                       (ordered at TOP of features.json)
             ├─ no pending features and NOT all completed ► orchestrator_turn
             └─ all features completed|cancelled        ─► completed
                │                     (also: mission_duration_ms metric)
                ▼
           completed  (orchestrator must call start_mission_run again
                      if new pending features appear)

 pause():
     any non-terminal state + SIGINT ─► interrupt worker session, append
     worker_paused + mission_paused progress entries, set state=paused.
 resume:
     calling start_mission_run with resumeWorkerSessionId re-attaches to
     the still-alive worker; plain start_mission_run resumes the
     in-progress feature from where the worker left off.
 preemption:
     if a pending feature is above the in-progress one in features.json
     order, runner kills the paused worker, resets the in-progress
     feature to pending (currentWorkerSessionId=null), and spawns a new
     worker on the higher-priority feature.
```

**[已验证] preemption snippet** (abridged, from runner loop):
```js
if (M!==-1 && w!==-1 && M<w) {
  kH("[MissionRunner] Preempting paused worker: pending feature exists
      above in-progress feature", ...);
  await twH({ missionFileService, featureId:L, workerSessionId:h });
  T=void 0; continue;
}
```
(`twH` = reset-feature helper; see **Feature mutations** below.)

### What state transitions fire out to the TUI

`updateState(H)` emits a project-notification **[已验证]**:
```js
vL.emit("project-notification",
  { notification: { type:"mission_state_changed", state: R.state } });
```
Mission Control listens via `getMissionStoreForSession(T).setState(...)`
(offset 62042612). That is how the `/missions` TUI panels update the
status bar (`RUNNING / PAUSED / PLANNING / COMPLETED`, mapped at offset
73510841+). **[已验证]**

## Worker spawn model

**[已验证]** `MissionRunner.spawnWorker()` generates a spawnId
`worker_<8hex>` and calls:

```js
W = await FbT({
  label: "spawnWorkerSession",
  promise: CB().spawnWorkerSession({
    cwd: $,                       // from state.workingDirectory
    baseSessionId: this.baseSessionId,
    modelId: L,                   // validation vs implementation model
    interactionMode: "auto",      // always auto for workers
    autonomyLevel: "high",        // always high for workers
    reasoningEffort: h,
    inactivityTimeoutMs: VB8,     // MISSION_WORKER_INACTIVITY_TIMEOUT_MS env, default hardcoded
    runtimeSettingsPath: E,
    tags: [{ name: "exec" }, { name: $aH }]
  })
});
```

Then:
- `missionFileService.updateFeature(T.id, { status:"in_progress",
  workerSessionIds:[...T.workerSessionIds, W] })`
- appends `worker_selected_feature` + `worker_started` progress entries
- builds a worker bootstrap message (`TsB(missionDir, feature,
  workerSessionId)` — see prompt `skill_worker-base-procedures.md` for
  what that message looks like) and calls
  `CB().addUserMessage({ sessionId:W, text:w })`.

**Worker is a separate Droid session inside the same factoryd.** Not a
child process from the orchestrator's perspective. Evidence:

- **[已验证]** There is no `ZtB`/`spawn` call in the runner; all worker
  control goes through `CB()` (the factoryd RPC proxy: `spawnWorkerSession`,
  `closeSession`, `interruptSession`, `addUserMessage`).
- **[已验证]** A TCP probe function `FB8(host,port)` exists to check that
  factoryd is reachable. Timing out on it returns
  `"Timed out waiting for factoryd <label>"`.
- **[已验证]** Orphaned-worker cleanup path calls
  `CB().closeSession(workerSessionId)` — purely RPC, not `process.kill`.

Concurrency: **one worker per mission at a time**. `spawnWorker` is only
called when `getInProgressFeature()` is falsy. **[已验证]** The runtime
provides no parallel worker support.

### Worker termination / resume

- **Successful end** comes from the worker calling `end_feature_run`
  (class `lAA`, offset ~62.6MB). That tool:
  - Validates handoff shape, sentence count (1–4), length (20–500 chars).
  - Updates feature status (`completed` if success, else `pending`).
  - Moves completed features to the bottom of `features.json`.
  - Writes `handoffs/<feature>-<worker>.json`.
  - Generates a transcript skeleton with `ntB(messageEvents)` and appends
    it to `transcript-skeleton.md`.
  - Sets state=`orchestrator_turn` if returnToOrchestrator / failure /
    partial.
  - Appends `worker_completed` progress entry.
  - Returns to the worker: "Your session is now complete. Do not make
    any further tool calls or continue working. End your turn immediately."
- **Pause** sends `interruptSession(workerId)` and persists
  `worker_paused`. The worker's current in-progress feature keeps
  `status=in_progress` so resume can pick up later.
- **Manual kill** (`killWorkerSession` helper, offset ~66755999) appends
  `worker_failed` with reason `"Killed by user"` and flips state to
  `orchestrator_turn`. **[已验证]**
- **Crash / orphan on runner startup**: `cleanupOrphanedWorker` closes
  the stray session, appends `worker_failed` with `reason:"orphan_cleanup"`,
  and resets the feature to pending. **[已验证]**

### Inactivity timeout

**[已验证]** `fB8()` helper reads env `MISSION_WORKER_INACTIVITY_TIMEOUT_MS`
and falls back to `YB8` (a hardcoded default — numeric constant in the
bundle, not extracted here). Runner passes it to factoryd's
`spawnWorkerSession`.

## Validator auto-injection

**Validators are first-class mission citizens.** The factoryd
process/session model only distinguishes `orchestrator` from `worker`,
but the mission runtime reserves **three validator skillNames** — each
with a full independent system prompt — that `MissionRunner` itself
inserts into `features.json` at milestone boundaries. The orchestrator
is explicitly forbidden from authoring these features.

### The three reserved validators [已验证]

| skillName | Role | Spawn path | Prompt file |
|---|---|---|---|
| `scrutiny-validator` | Runs test / typecheck / lint as hard gate, spawns review subagents per completed feature, synthesises findings to `.factory/validation/<milestone>/scrutiny/synthesis.json`. | Injected as a top-of-`features.json` worker feature by the runner. | `prompts/skill_scrutiny-validator.md` |
| `user-testing-validator` | Determines testable assertions from features' `fulfills` field, sets up isolation, spawns flow validator subagents, synthesises to `.factory/validation/<milestone>/user-testing/synthesis.json` and updates `validation-state.json`. | Injected as a top-of-`features.json` worker feature by the runner (sits below `scrutiny-validator` in the injection order, i.e. runs second). | `prompts/skill_user-testing-validator.md` |
| `user-testing-flow-validator` | **Subagent** of `user-testing-validator`. Tests one assertion group inside its assigned isolation boundary, writes per-group JSON report under `.factory/validation/<milestone>/user-testing/flows/<group-id>.json` plus evidence files. | **Not** injected into `features.json`. Spawned by the user-testing validator via `Task({ subagent_type: "user-testing-flow-validator", … })` — i.e. as a normal Claude-style subagent inside the validator's own session. | `prompts/skill_user-testing-flow-validator.md` |

> Source quote (orchestrator_role.md, line ~329 and ~546):
>
> > **NEVER create features with skillName `scrutiny-validator` or
> > `user-testing-validator`.** These validation features are
> > auto-injected by the system when a milestone completes. […]
> > Always rely on the system's auto-injection.
>
> Source quote (skill_user-testing-validator.md §4 "Spawn flow
> validator subagents via Task tool"):
>
> > `Task({ subagent_type: "user-testing-flow-validator", description:
> > "Test assertions <group-name>", prompt: … })`

### Validator handoff is the same path as any worker [已验证]

- A validator worker ends its turn via the same `end_feature_run` tool,
  with the same Zod-validated `handoff` schema. There is **no separate
  "verdict" schema** — pass/fail is encoded as `successState` +
  `handoff.discoveredIssues` + the synthesis file path, not as a
  runtime-enforced enum.
- When a validator's handoff is `partial` / `failure`, the runner flips
  state to `orchestrator_turn` exactly like for any other worker, and
  the validator feature is reset to `pending` so the same feature
  re-runs after the orchestrator lands fix features.
- The `user-testing-flow-validator` subagent does **not** call
  `end_feature_run`. It is a Claude-style subagent inside its parent's
  session; its output is the JSON report file that the parent validator
  reads during its synthesis step.

### Injection mechanism [已验证]

`MissionRunner.checkMilestoneCompletionAndInjectValidation(featureId)`
runs **after every worker completion** (both the resume path and the
fresh-spawn path). Logic:

1. Look at the finished feature's `milestone`; bail if none or if
   already injected (`hasValidationPlannerRun(milestone)`).
2. Compute implementation-complete predicate via
   `isMilestoneImplementationComplete(milestone)`: every feature in
   that milestone whose `skillName` is **not** in the protected set
   `JIH` (= `[scrutiny-validator, user-testing-validator]`) must be
   `completed` or `cancelled`. This is why the orchestrator is barred
   from authoring these skillNames — they would otherwise be counted as
   implementation features and break the predicate.
3. Read `missionSettings.skipScrutiny` and `missionSettings.skipUserTesting`.
4. Build synthetic features:
   - `user-testing-<milestone>` with `skillName = sfH`
     (sfH = `"user-testing-validator"` [推断] — name leaked in TUI
     label strings and orchestrator prompt).
   - `scrutiny-<milestone>` with `skillName = tfH`
     (`"scrutiny-validator"`).
5. `insertFeatureAtTop` for each injected feature that wasn't skipped.
   **Insertion order is user-testing first, then scrutiny** — so
   scrutiny ends up above user-testing in `features.json`, i.e.
   scrutiny runs first, user-testing runs second.
6. Append `milestone_validation_triggered` progress entry.

The injected features' `description`, `expectedBehavior`, and
`preconditions` are hardcoded English strings (see the byte-offset
dumps referenced in `tooling-notes.md`).

### Orchestrator-side obligations when a validator fails [已验证]

Pulled from `orchestrator_role.md` §"Milestone validation flow":

- A failed validator re-enters `pending`; the orchestrator creates fix
  features (with correct `fulfills` references) and calls
  `start_mission_run` — the **same** validator feature re-runs.
- On re-run, the validator reads its previous synthesis report and
  re-validates **only what failed**.
- Extra context can be appended to the validator feature's
  `description` (the validator reads it on startup).
- A validator feature may be force-completed as an override, but this
  must be auditable: status → `completed`, move to bottom of
  `features.json`, justification recorded in the synthesis file.
- Once both validators pass for a milestone, that milestone is
  **sealed** — no new features may be added to it.

## Control flow on `start_mission_run` return

The tool's result object contains (inferred from orchestrator prompt +
partial extracts **[推断]**):

- `workerHandoffs` — array of summarised handoffs since the last run
  (featureId, resultState=pass/fail, counts of discoveredIssues /
  unfinishedWork, `whatWasImplemented` summary, `handoffFile` path).
- `latestWorkerHandoff` — the most recent handoff summary *plus* the
  full `handoffJson` inline (via `XbT({ includeLatestWorkerHandoff:true })`
  = `nAA.ts`). **[已验证]**

After `start_mission_run` returns, orchestrator state is `paused`,
`orchestrator_turn`, or `completed`; runner is no longer running.
Orchestrator resumes by calling `start_mission_run` again.

## Feature mutations

`MissionFileService` (`class rKH`, offset 62582419) is the authoritative
file-level API. Methods observed **[已验证]**:

- `createInitialState(cwd)` → writes `state.json` with
  `missionId = "mis_<8hex>"`, `state="initializing"`, timestamps.
- `readFeatures()` / `writeFeatures()` / `readFeaturesOrThrow()`
  (accepts both `{features:[…]}` and bare-array legacy layouts).
- `updateFeature(id, patch)`.
- `getInProgressFeature()` / `getNextPendingFeature()`.
- `areAllFeaturesCompleted()` — all are `completed` or `cancelled`.
- `insertFeatureAtTop(f)` / `moveFeatureToBottom(id)` /
  `moveStrandedDoneFeaturesToBottom()`.
- `getMilestoneFeatures(m)` / `getAllMilestones()` /
  `isMilestoneImplementationComplete(m)` /
  `hasValidationPlannerRun(m)`.
- `ensureWorkerHandoffJson(...)` — writes per-feature handoff into
  `handoffs/` (filename pattern inferred from call sites:
  `<featureId>-<workerSessionId>.json`, **[推断]**).
- `appendTranscriptSkeleton(...)` — per-feature transcript skeleton.
- `writeMissionMd(title, proposal)` — serialises `mission.md`.
- `writeRuntimeCustomModels(models[])` — dumps the per-session custom
  model list so workers can resolve model IDs.
- `writeModelSettings(patch)` — only writes fields that differ from the
  user's global mission defaults (offset 66759508 comparison).
- `appendProgressLog(entry)` — JSONL stream of events (see `schemas.md`).
  Emits TUI notifications on `worker_started` / `worker_completed`.

`twH({missionFileService, featureId, workerSessionId})` is the shared
"unreserve a feature from its worker" helper **[已验证]**:

- Rewrites the in-progress feature back to `pending` and clears
  `currentWorkerSessionId`, **only if** the recorded worker matches the
  one passed in.
- Used for: pause-preempt, kill, orphan cleanup, and explicit restart.

## TUI ↔ runner integration

- All runner-produced events go through `vL.emit("project-notification",
  { notification:{…} })`. Observed notification types **[已验证]**:
  `mission_state_changed`, `mission_features_changed`,
  `mission_progress_entry`, `mission_worker_started`,
  `mission_worker_completed`.
- Mission Control is a TUI view. Keybindings (offset 73563554+)
  **[已验证]**:

  ```
  F : Features                M : Mission Models
  W : Workers                 D : Mission dir (open missionDir in editor)
  P : Pause    (enabled in running|orchestrator_turn)
  R : Resume   (enabled in paused|orchestrator_turn)
  ```

- Mission labels mapped from state **[已验证]** (offset 71570912):

  ```
  running            → RUNNING
  paused             → PAUSED
  completed          → COMPLETED
  orchestrator_turn  → PLANNING
  initializing       → INITIALIZING
  awaiting_input     → AWAITING
  ```

- Mission progress incremental reader: `readProgressLogIncrementalOrThrow`
  keeps a `{size, mtimeMs, offset, remainder, entries,
  derivedWorkerStates}` cache and re-reads only the new tail of
  `progress_log.jsonl`. **[已验证]**

## Daemon / sidecar model — is it a daemon?

Droid itself is **not** a background daemon. The MissionRunner lives in
the same foreground CLI process as the orchestrator session. What is a
separate process is `factoryd`:

- Runner talks to it via `CB()` proxy and `FbT({label, promise})` which
  wraps each RPC in a timeout (`MB8`, default 15s based on other
  timing helpers). **[推断]**
- Env marker: `R1.MISSION_WORKER_INACTIVITY_TIMEOUT_MS` is the only
  mission-specific env var we observed. **[已验证]**
- Crash recovery on fresh runner startup: `cleanupOrphanedWorker` closes
  stray sessions and unreserves their features (see above).
- If factoryd is down, `start_mission_run` fails and the orchestrator
  prompt instructs the orchestrator to "Retry start_mission_run once. If
  it fails again, stop and ask the user to restart Droid/factoryd, then
  retry." **[已验证]** (orchestrator_role.md tail).

Concrete **[未验证]**: the factoryd transport. We saw a TCP probe but the
runner itself doesn't open sockets directly — it uses the `CB()` proxy.
Could be UNIX socket, loopback TCP, or JSON-RPC-over-stdio. Next analyst
should trace `CB()`'s factory function.

## Crash recovery summary

| Scenario                                     | Recovery                                                           |
|----------------------------------------------|--------------------------------------------------------------------|
| `state.json` missing                         | Runner logs, exits. User must retrigger via TUI.                   |
| Orphaned worker session on runner startup    | `cleanupOrphanedWorker`: closeSession + worker_failed + unreserve  |
| Runner paused mid-feature                    | Resume via `start_mission_run` (optionally `resumeWorkerSessionId`)|
| Worker session mismatch on resume            | Warn + skip; runner falls through to fresh spawn.                  |
| Worker spawn fails                           | progress `worker_failed`, unreserve, state → `orchestrator_turn`.  |
| Fresh spawn s쳮ds but session vanishes    | **[未验证]** — no explicit code path; likely caught by factoryd.   |

## Open questions for the next analyst

1. Factoryd transport + RPC wire format (see `CB()` getter at ~66.5MB).
2. The exact `validation/<milestone>/*/synthesis.json` schema — is there
   a Zod validator, or is it prompt-level only?
3. The `tags: [{name:"exec"}, {name:$aH}]` on spawnWorkerSession:
   `$aH` is likely `"mission"` but we didn't pin it down.
4. Whether the runner persists a `mission.log` separate from
   `progress_log.jsonl` (orchestrator prompt never mentions one — we
   found no such file reference in the binary either, so this is
   **[已验证-negative]**: there is no separate mission log).
