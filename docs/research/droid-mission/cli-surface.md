---
source: ~/.local/bin/droid (v0.104.0)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Mission CLI & Human Interface

The short version: there is **no `droid mission <subcommand>` surface**.
Missions are driven entirely through (a) the `/missions` slash command
inside a running droid TUI session, (b) a small number of mission-aware
Mission Control keybindings in that same TUI, and (c) LLM tool calls on
the orchestrator side. **[已验证]**

## Top-level `droid` subcommands related to missions

We grepped the binary for every `new Command(…)`-style token and every
help text containing `mission`. The only matches are:

- The `/missions` **slash command** inside a session (TUI only).
- The message `Mission Control is only available in orchestrator
  sessions. Run /missions and select + New Mission first.` **[已验证]**
- The settings panel key `headerMissionDefaults` (where the user sets
  default worker model, validator model, skipScrutiny, skipUserTesting,
  etc). **[已验证]**

No `droid mission list|start|pause|resume|kill|show|open` subcommand
exists. **[已验证]**

## Interaction modes and the orchestrator

Droid has three **[已验证]** interaction modes:

```
auto  — "droid completes task autonomously"
spec  — "research task before implementing"
agi   — internal name used by the enum, surfaced as "mission" in user-
        facing labels (`modeDescriptions.mission = "orchestrate missions
        (/missions)"`)
```

`R4` enum: `auto | spec | agi`. `gK` agent-role enum: `orchestrator |
worker`. Mission-mode is **always orchestrator**-side; workers spawn in
`interactionMode:"auto"` + `autonomyLevel:"high"` (both hardcoded in
`MissionRunner.spawnWorker`). **[已验证]**

## `/missions` slash command

Opens the **Mission picker** view. Functions observable in the TUI:

- "+ New Mission" — switches the current session into orchestrator mode
  and surfaces the orchestrator prompt. Mission itself is created only
  when the LLM subsequently emits `propose_mission`. **[已验证]**
- Select an existing mission → opens **Mission Control**, which is a
  multi-view panel whose state is driven by `MissionState`.

Mission Control inner navigation keybindings **[已验证]** (offset
73563554 region, literal strings):

```
F : Features               — feature list panel
W : Workers                — per-worker session drill-down
M : Models                 — mission model selector
D : Mission dir            — opens missionDir in user's $EDITOR
P : Pause                  — enabled when state ∈ {running, orchestrator_turn}
R : Resume                 — enabled when state ∈ {paused, orchestrator_turn}
```

Mission status strings **[已验证]** (labels fed to TUI):

```
running           → "RUNNING"
paused            → "PAUSED"
completed         → "COMPLETED"
orchestrator_turn → "PLANNING"
initializing      → "INITIALIZING"
awaiting_input    → "AWAITING"
```

Active-worker detail panel **[已验证]**:

```
[K] Kill    — SIGTERM worker, set state=orchestrator_turn
[F] Force Kill — SIGKILL the worker session
[Esc] Back
```

## Tool-call surface for the orchestrator LLM

The orchestrator prompt explicitly lists **[已验证]**:

- `propose_mission(title, proposal, workingDirectory?)`
- `start_mission_run(resumeWorkerSessionId?, restartFeature?)`
- `dismiss_handoff_items(dismissals[])`
- plus generic tools: `Skill`, `Create`, `Read`, `Grep`, `Glob`, etc.

### `propose_mission` flow

1. Orchestrator calls with title+proposal.
2. User is shown a proposal confirmation UI (`proposeMission` i18n
   strings: `awaitingApproval`, `approved`, `missionDir`, `changesRequested`,
   `summaryProposal`). **[已验证]**
3. On approve (confirmationOutcome `proceed_once` / `proceed_always`):
   - MissionFileService initializes the mission dir.
   - Writes `mission.md`, `working-directory`, optional
     `model-settings.json`.
   - Appends `mission_accepted` progress entry.
   - Returns `{ accepted:true, missionDir, llmGuidance? }` to the LLM.
4. On reject:
   - Returns `{ accepted:false }`.

Edit-on-approve path: the user can **edit** the proposal before
accepting. The tool tracks `isEdited`; if edited, an
`llmGuidance` string is synthesised ("Mission was approved but the user
has left a required comment to address…"), which droid surfaces as a
system-notification to the orchestrator. **[已验证]**

### `start_mission_run` flow

1. Orchestrator invokes.
2. Tool checks `state` — if `paused` with an in-progress worker, it
   offers to resume (`resumeWorkerSessionId`).
3. Tool launches `MissionRunner.start(abortSignal, resumeWorkerSessionId)`.
4. The tool call is **blocking**; the orchestrator turn is held open.
5. Runner returns on `paused | orchestrator_turn | completed`.
6. Tool returns `{ state, message, workerHandoffs[], latestWorkerHandoff? }`
   (see `schemas.md`).

### `dismiss_handoff_items` flow

Each dismissal has `{ type, sourceFeatureId, summary, justification }`.
Tool appends a single `handoff_items_dismissed` progress entry and
replies `"Dismissed N item(s). You may now call start_mission_run to
continue."`. **[已验证]**

### `end_feature_run` (worker side)

Worker-only tool. Not listed to the orchestrator. It:

- Validates `handoff` per Zod + extra rules (sentence count, length).
- Moves feature to `completed` (if success) or leaves as `pending`.
- Writes `handoffs/<feature>-<worker>.json`.
- Sets state to `orchestrator_turn` if `returnToOrchestrator /
  partial / failure`.
- Returns `{ recorded, nextAction:"orchestrator"|"continue", message }`
  + the hard stop text:
  `"IMPORTANT: Your session is now complete. Do not make any further
  tool calls or continue working. End your turn immediately."` **[已验证]**

## Mission settings (persisted per-user)

From the `headerMissionDefaults` block in the settings TUI strings
**[已验证]**:

- `workerModel`
- `workerReasoningEffort`
- `validationWorkerModel`
- `validationWorkerReasoningEffort`
- `skipScrutiny` (bool)
- `skipUserTesting` (bool)

Settings live in `~/.factory/settings.json` (inferred from generic
settings path elsewhere in the binary; not separately confirmed for
mission defaults, hence **[推断]**).

## Non-interactive (`droid headless`) mode?

Droid has `droid headless login` and `droid exec` for one-shot
operations. We **did not** find a headless entry point that starts a
mission. Missions require the TUI runtime because the
`propose_mission` → approve → `start_mission_run` handshake goes
through the TUI's confirmation UI. **[已验证-negative]**

## Exit / lifecycle boundaries

- SIGINT inside droid → MissionRunner.pause() (`mission_paused` entry).
- Quitting the droid process while a mission is running → on next launch,
  `MissionRunner.cleanupOrphanedWorker` fires (orphan cleanup). **[已验证]**
- Killing the **factoryd** daemon while droid is attached → runner RPC
  calls fail; orchestrator prompt instructs user to retry
  `start_mission_run` once and then escalate. **[已验证]**

## How the runner talks back to the human

Runner emits `project-notification` events which the TUI renders. Types
observed **[已验证]**:

```
mission_state_changed        — updates status bar
mission_features_changed     — refreshes the Features panel
mission_progress_entry       — drives the "mission feed" ticker
mission_worker_started       — prompts the Workers panel and sounds
mission_worker_completed
```

Sounds: droid plays the usual tool/session sounds on worker start/end;
no dedicated mission sound was found. **[已验证-negative]**
