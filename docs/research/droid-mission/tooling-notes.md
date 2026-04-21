---
source: ~/.local/bin/droid (v0.104.0)
binary_sha256: 2a09cf8b2ff08dd78397a5a148abf80b6e3c935fe104d653030183d656d62ba2
binary_size: 109173232
analyzed_at: 2026-04-19
analyst: worker (Hive "gang" research)
---

# Tooling notes & replay log

This is the cookbook the next analyst should read first if they want to
extend or re-validate this research.

## What you have on disk

- The droid binary: `~/.local/bin/droid` — Mach-O arm64, 109,173,232 B.
- The pre-existing modder skill that decoded the bundle layout for us:
  `~/.factory/skills/droid-bin-mod/SKILL.md` (and the scripts under
  `scripts/mods/`). Mods 1–12 in that skill all assume the bundle is
  plain text strings inside the Mach-O — a strong corroboration of this
  research's "use `strings | rg`" approach.
- Working scratch dir produced during this research:
  - `/tmp/droid-analysis/droid-strings.txt` (450k lines) — full strings dump.
  - `/tmp/droid-analysis/chunk_*.bin` and `chunk_*.strings.txt` —
    extracted hot regions.
  - `/tmp/droid-analysis/prompts/` — verbatim prompt templates (also
    copied into `docs/research/droid-mission/prompts/`).

## Why this is easy

The droid binary is **a Bun-compiled single-executable application**.
Bun does not encrypt the embedded bundle — it concatenates a UTF-8 JS
text payload to the Mach-O. That means:

- Every backtick template literal (orchestrator prompt, mission-planning
  skill, etc.) is recoverable as plain text.
- Every Zod schema (`CH.object({...})`) is plain text.
- Identifier renaming is the only mangling: minified two/three-letter
  names like `oXT`, `dAA`, `rKH`, `CB()`, `vT()` etc. that need
  context-aware mapping.

`nm` and `otool -tV` are useless here (stripped, native-only); but
`strings` + `rg` + offset-targeted `dd` produce a complete view.

## Recon commands (replay)

```bash
file ~/.local/bin/droid
shasum -a 256 ~/.local/bin/droid
~/.local/bin/droid --version
otool -L ~/.local/bin/droid          # libicucore, libresolv, libc++, libSystem
codesign -d --entitlements - ~/.local/bin/droid    # only ad-hoc runtime sig
```

## Find offsets for any string

```bash
LC_ALL=C grep -oab '<KEYWORD>' ~/.local/bin/droid | head -20
```

Examples that drove this research:

```
LC_ALL=C grep -oab 'MissionRunner'    droid   # → 67517855 etc
LC_ALL=C grep -oab 'class dAA{'       droid   # → 66733181 (the runner)
LC_ALL=C grep -oab 'class rKH{'       droid   # → MissionFileService
LC_ALL=C grep -oab 'features.json'    droid
LC_ALL=C grep -oab 'orchestrator_turn' droid  # state machine values
LC_ALL=C grep -oab '=`# '             droid   # all big template strings
```

## Slice and inspect

```bash
mkdir -p /tmp/droid-analysis
dd if=~/.local/bin/droid bs=1 skip=66730000 count=600000 \
   of=/tmp/droid-analysis/runner.bin status=none
strings -a /tmp/droid-analysis/runner.bin > /tmp/droid-analysis/runner.txt
rg -n 'class dAA|spawnWorker|runLoop|cleanupOrphaned' /tmp/droid-analysis/runner.txt
```

For the prompt bank:

```bash
dd if=~/.local/bin/droid bs=1 skip=62540000 count=260000 \
   of=/tmp/droid-analysis/prompts.bin status=none
```

## Extracting prompts cleanly

The prompts are template-literal RHS values: `<id>=\`# Title\n…\``. The
following Python snippet pairs the backticks with escape-awareness and
dumps each one to a file. (The same script handles `aaq='…'` for
Scrutiny which uses single-quoted form with `\n` escapes.)

```python
import re, os
path = "/Users/notdp/.local/bin/droid"
START, SIZE = 62540000, 260000
data = open(path,'rb').read()[START:START+SIZE].decode('utf-8','replace')

os.makedirs('/tmp/droid-analysis/prompts', exist_ok=True)

for m in re.finditer(r"=`# ", data):
    h = m.start()
    i = h + 2  # skip '=`'
    out = []
    while i < len(data):
        c = data[i]
        if c == '\\' and i+1 < len(data):
            out.append(c); out.append(data[i+1]); i += 2; continue
        if c == '`': break
        out.append(c); i += 1
    body = ''.join(out)
    title = body.splitlines()[0][2:].strip()
    fname = title.lower().replace(' ', '-') + '.md'
    open(f"/tmp/droid-analysis/prompts/{fname}", 'w').write(body)
```

## Key offsets table (v0.104.0 binary)

| Offset      | Symbol / artifact                                | Notes                                                  |
|-------------|--------------------------------------------------|--------------------------------------------------------|
| 59605865    | `((C)=>{C.AwaitingInput="awaiting_input";…})`    | MissionState enum body                                 |
| 59674308    | first `i.object({…})`                            | model-id allow/block sets                              |
| 59690530    | `oXT = CH.object({id…})`                         | Feature schema (start of `sXT=c(()=>{…})` IIFE)        |
| 59691733    | `whatWasImplemented`                             | inside `uyH` handoff schema                            |
| 60388816    | first `propose_mission`                          | tool name string                                       |
| 60388852    | first `start_mission_run`                        | tool name string                                       |
| 60480744    | `mission_state` enum hint                        | UI side                                                |
| 60913305    | second `skillName` reference                     | feature normalization                                  |
| 62042612    | `mission_state_changed` switch                   | TUI bus mapping                                        |
| 62540963    | `Yaq=Tg9(Hg9())`                                 | nearby IIFE bootstrap                                  |
| 62580075    | `Og9=\`# Role & Mindset…\``                      | **Orchestrator system prompt start**                   |
| 62582419    | `class rKH{baseSessionId;missionDir;…}`          | **MissionFileService**                                 |
| 62638911    | `raq=\`# Mission Planning…\``                    | mission-planning skill                                 |
| 62653937    | `taq=\`# Designing Your Worker System…\``        | designing-workers skill                                |
| 62662201    | `saq=\`# Worker Base Procedures…\``              | worker-base-procedures skill                           |
| 62676493    | `aaq='# Scrutiny Validator…'`                    | scrutiny-validator skill (single-quoted form)          |
| 62691558    | `eaq=\`# User Testing Validator…\``              | user-testing-validator skill                           |
| 62704128    | `Jg9=\`# User Testing Flow Validator…\``         | flow validator subagent skill                          |
| 62710876    | `Heq=\`# Refactoring & Migration Playbook…\``    | playbook                                               |
| 62718668    | `Teq=\`# TUI Application Playbook…\``            | playbook                                               |
| 66733181    | `class dAA{baseSessionId;…}`                     | **MissionRunner**                                      |
| 66753902    | `async function tqH(H){…}`                       | wrapper that pauses runners + handles non-resume case  |
| 66755999    | `killWorkerSession` handler                      | TUI Kill action                                        |
| 66759508    | `class aAA{async*execute(H,T){…}`                | `start_mission_run` tool implementation                |
| 71570912    | `K7A` / `Q7A` / `Nv8`                            | TUI status icons / labels                              |
| 73510841    | `eT1` / `HR1`                                    | mission badge / label functions                        |
| 73563554    | `keyboardHints` / `[F][W][M][D][P][R]`           | Mission Control keybindings                            |

## Useful regex patterns

```text
# every prompt template
=`# .{1,80}\n

# every Zod object schema in the bundle
CH\.object\(\{[^}]{20,400}

# every progress-log type literal
type:CH\.literal\("[a-z_]+"\)
```

## Pitfalls

1. **Single-quoted prompts.** Most prompts use backticks but
   `Scrutiny Validator` (`aaq='…'`) uses single-quoted strings with
   `\n` escapes. Treat them differently.
2. **Concatenation.** Several prompt files were emitted in a single
   chained expression like `\`...\`,raq=\`...\``. The naive `=\`…\``
   regex picks them up but the variable-name capture fails because the
   preceding closing backtick is not preceded by `;` or whitespace.
   Don't trust the assigned variable name; trust the markdown title at
   line 1.
3. **`UR()`, `vT()`, `CB()`** are lazy-init module getter functions
   (the modder-skill notes confirm this for `vT` and `UR`); their names
   change between minor versions. The droid-bin-mod scripts use
   "dynamic discovery" by call-pattern (`getCustomModels`,
   `hasSpecModeModel`, …) — apply the same trick if you need to follow
   them across releases.
4. **String "missing" doesn't mean missing in code.** Some functions
   build strings via concatenation; e.g. the worker bootstrap message
   is assembled via `TsB(missionDir, feature, workerSessionId)` and
   does not exist as one searchable literal. Trace the assembler
   instead.

## Suggested follow-ups

- Trace `CB()` to identify the factoryd RPC transport. (`CB().spawnWorkerSession`,
  `CB().closeSession`, `CB().interruptSession`, `CB().addUserMessage`.)
- Locate the Zod schema for `validation-state.json` if any (so far we
  found none; this looks prompt-only).
- Diff against an older droid binary (e.g. 0.96.0) to see how the
  schema/state machine has evolved — useful before Hive's gang plugin
  freezes its own contracts.
- If you have radare2 or Ghidra: open the binary, search for
  cross-references to the `state.json` filename literal at offset
  62582464 (inside `class rKH`). All mission file IO funnels through
  that class.

## Audit log

- 2026-04-19, validator-audit worker: reframed validators as first-class
  mission citizens across two files to prevent future readers from
  treating them as "just workers".
  - `index.md` — expanded takeaway #5 to list all 3 reserved validator
    skillNames (`scrutiny-validator`, `user-testing-validator`,
    `user-testing-flow-validator`) with injection timing / parent-child
    relationship; clarified takeaway #6 so the runtime-vs-prompt split
    isn't over-claimed.
  - `architecture.md` — replaced "Milestone validation auto-injection"
    with a richer `## Validator auto-injection` section covering: the
    3 reserved skillNames table, insertion order (scrutiny first,
    user-testing second), `JIH` protected-set predicate, validator
    handoff going through the same `end_feature_run` + Zod path (no
    separate verdict schema), `flow-validator` spawned via `Task`
    inside the parent session, orchestrator override / re-run rules,
    and milestone sealing.
  - No new facts invented; all claims come from `prompts/orchestrator_role.md`
    and `prompts/skill_user-testing-validator.md`.
