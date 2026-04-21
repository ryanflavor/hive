---
source: ~/.local/bin/droid (Mach-O 64-bit arm64, Bun-compiled SEA)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
droid_version: 0.104.0
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Droid Mission — Reverse-engineered reference

This folder documents the **mission** subsystem of Factory's `droid` CLI as
reconstructed from the binary. It is the blueprint for Hive's own `gang`
plugin. Every statement below is either lifted verbatim from the binary or
is labeled with one of the confidence markers defined in §Confidence.

## Confidence markers

- **[已验证]** — text / identifier comes directly out of the binary (cited by
  byte-offset or `strings` / `rg` command).
- **[推断]** — reasoned from surrounding bundle code, but no single string
  proves it.
- **[未验证]** — reasonable guess / literature support, but no direct evidence
  in this binary.
- **[猜测]** — pure speculation; keep or drop at your own risk.

## File guide

- [`architecture.md`](architecture.md) — runner entry points, state machine,
  worker spawn model, milestone validation injection.
- [`schemas.md`](schemas.md) — every persisted structure: `state.json`,
  `features.json`, `progress_log.jsonl`, worker handoff JSON, mission
  proposal payload, Zod schemas (raw), enums.
- [`prompts.md`](prompts.md) — index / extraction log for all agent system
  prompts; the prompts themselves live one-per-file in
  [`prompts/`](prompts/).
- [`cli-surface.md`](cli-surface.md) — how the user invokes mission
  functionality (TUI-only: `/missions` slash-command + Mission Control
  keybindings) and the mission-aware tools (`propose_mission`,
  `start_mission_run`, `dismiss_handoff_items`, `end_feature_run`).
- [`tooling-notes.md`](tooling-notes.md) — exact commands and byte offsets
  used so that the next analyst can resume at will.

## Binary fingerprint

```
file:    Mach-O 64-bit executable arm64
size:    109,173,232 bytes
sha256:  2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
version: 0.104.0              # from `droid --version`
linked:  libicucore, libresolv, libc++, libSystem (no Node / no V8 dylib)
embed:   Bun-compiled single-executable application (SEA).
         Not classic Node `--experimental-sea-config`; the interpreter is
         WebKit JavaScriptCore shipped with Bun, and the JS bundle is
         concatenated into the Mach-O tail in plain UTF-8 text.
symbols: stripped; `nm` returns nothing useful.
codesign: runtime signature only, no entitlements file.
```

## High-level takeaways

1. **Bun SEA + plain-text JS bundle.** Prompts, Zod schemas, and class
   bodies are all UTF-8 strings in the Mach-O, so `strings | rg` is the
   primary analysis tool.
2. **Mission storage is a per-mission directory inside the droid
   workspace**, rooted at `<FactoryHome>/<workspaceSlug>/missions/<baseSessionId>/`.
   Files: `state.json`, `features.json`, `mission.md`,
   `validation-contract.md`, `validation-state.json`, `progress_log.jsonl`,
   `AGENTS.md`, per-feature `handoffs/<featureId>-<workerSessionId>.json`,
   worker transcript skeletons, plus a runtime-custom-models file.
3. **Runner is in-process, sequential, one worker at a time.** `MissionRunner`
   (class `dAA`) runs inside the same Bun process as the orchestrator TUI
   session and `spawnWorkerSession`s against an RPC client called
   `factoryd`. Workers are *separate sessions inside the same daemon*, not
   subprocesses.
4. **State machine** on `state.json`:
   `initializing → running ⇄ paused ⇄ orchestrator_turn → (completed)`.
   See `architecture.md`.
5. **Validators are first-class mission citizens, not ad-hoc workers.**
   [已验证] The runtime's process/session abstraction only distinguishes
   `orchestrator` and `worker`, but there are **3 reserved validator
   skillNames** that the runtime auto-injects as workers at milestone
   boundaries, each with its own full system prompt:
   - `scrutiny-validator` — injected at the top of `features.json` when
     a milestone's implementation features finish (runs first).
   - `user-testing-validator` — injected alongside scrutiny at milestone
     completion (runs after scrutiny).
   - `user-testing-flow-validator` — **subagent** of
     `user-testing-validator`; spawned via `Task({ subagent_type:
     "user-testing-flow-validator" })` from inside the user-testing
     validator session, one per assertion group. Prompt body lives at
     `prompts/skill_user-testing-flow-validator.md`.
     [已验证] — referenced literally in `skill_user-testing-validator.md`
     §"Spawn flow validator subagents".
   Injection is done by `MissionRunner.checkMilestoneCompletionAndInject\
Validation()`; orchestrator prompts **forbid** the orchestrator from
   ever writing these skillNames into `features.json`. See
   `architecture.md` §"Validator auto-injection" for the full mechanism.
6. **Orchestrator / worker / validator personas are all prompt-driven.**
   The runtime distinguishes orchestrator vs worker sessions at the
   factoryd layer, but does not know about "validator" as a separate
   role class — validators are workers whose reserved skillName + full
   independent prompt is injected by the runner itself. Skill routing +
   auto-injection + per-skill system prompts produce the effective role
   separation.
7. **Human controls = Mission Control TUI.** `/missions` slash command
   opens the mission picker; `P`/`R`/`D`/`M` cycle through Pause / Resume /
   Mission-dir / Model settings. There is **no** `droid mission` CLI
   subcommand at the top level; the agent drives missions through
   tool-calls.
8. **Handoff is structured JSON**, not prose. `successState ∈ {success,
   partial, failure}`, rich `handoff` body (what was implemented / left
   undone / discovered issues / verification commands / tests / skill
   feedback). Orchestrator reads **summaries** plus the *latest* full
   handoff when `start_mission_run` returns.

## Remaining unknowns

- **[未验证] Validator → orchestrator synthesis file layout**
  (`.factory/validation/<milestone>/scrutiny/synthesis.json`,
  `.../user-testing/synthesis.json`): the orchestrator prompt references
  these fields (`appliedUpdates`, `suggestedGuidanceUpdates`) but we did
  not confirm a Zod schema that enforces them. They appear to be
  prompt-level contracts, not runtime-validated.
- **[未验证] Exact factoryd RPC surface.** We see `CB().spawnWorkerSession`,
  `CB().closeSession`, `CB().interruptSession`, `CB().addUserMessage`, and
  an inactivity timeout env var `MISSION_WORKER_INACTIVITY_TIMEOUT_MS`,
  but the underlying transport (UNIX socket? named pipe? TCP?) was not
  fully traced. `FB8` in `architecture.md` implements a plain TCP probe
  against `host`/`port`.
- **[推断] `state.initializing`** is the default for a freshly-accepted
  proposal before the orchestrator has produced `features.json`; the
  runner itself transitions out of it as soon as it writes `running`.
- **[未验证]** What happens if `state.json` is deleted mid-run. Runner logs
  `No state file found, stopping` and exits; we did not reproduce.

## Analysis method (summary)

1. Read `~/.factory/skills/droid-bin-mod/SKILL.md` → told us the bundle is
   plain minified JS inside the binary and that many single-letter idents
   (`UR()`, `vT()`, `CB()`) are lazy getters.
2. Confirmed via `file` + `otool -L` that this is a Bun-compiled SEA, not
   Node.
3. `strings -a droid > droid-strings.txt` + `LC_ALL=C grep -oab` for exact
   byte offsets of every mission keyword
   (`Mission`, `features.json`, `MissionRunner`, `propose_mission`,
   `start_mission_run`, `orchestrator_turn`, etc.).
4. Sliced hot regions with `dd bs=1 skip=<off> count=<N>` and disassembled
   on the JS text level (the bundle uses backtick template strings for
   every long prompt, so Python-side tick-pairing recovers the verbatim
   text).
5. Extracted Zod schemas around the `sXT=c(()=>{...})` IIFE and the
   `class rKH` (MissionFileService) and `class dAA` (MissionRunner).

See [`tooling-notes.md`](tooling-notes.md) for command replay.
