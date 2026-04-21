# Repository Guidelines

`CLAUDE.md` is a symlink to this file. Update `AGENTS.md` only.

## Project Structure & Module Organization

Hive is a small Python CLI project. Main code lives in `src/hive/`:
- `cli.py` defines the Click command surface.
- `agent.py`, `team.py`, and `tmux.py` implement runtime behavior.
- `bus.py` and `context.py` handle workspace state and per-pane context.

Tests live under `tests/` and are split by level:
- `tests/unit/` for isolated logic
- `tests/cli/` for command behavior with mocks
- `tests/e2e/` for real tmux-backed flows

## Design Docs

- Runtime design lives in `docs/runtime-model.md`.
- Raw Claude/Codex/Droid transcript and JCL parsing rules live in `docs/transcript-signals.md`.
- Keep runtime-field semantics there in sync with code:
  - `busy`
  - `inputState`
  - `turnPhase`
- `CLAUDE.md` is only a symlink entrypoint to this file. Do not edit it separately.

## Build, Test, and Development Commands

- `python3 -m pip install -e .` — install Hive in editable mode.
- **MUST**: after ANY code change, run install + hive skill sync + plugin re-enable BEFORE testing, committing, or manual verification:
  ```
  python3 -m pip install -e . --break-system-packages && npx skills add "$PWD" -g --all && hive plugin enable code-review && hive plugin enable cvim && hive plugin enable fork && hive plugin enable notify
  ```
  This is a single mandatory step. Do not skip it. Do not split it. Do not "do it later".
- Why this matters: plugin commands under `~/.factory/commands/` are materialized copies, not symlinks, so changing plugin code without re-enabling can leave you testing stale command files. The base `hive` skill also lives outside the plugin install path, so repo changes to `skills/hive/SKILL.md` do not reach agents unless you refresh it via `npx skills add`.
- Sidecar upgrade rule: if your manual verification depends on new sidecar behavior or fields (for example `hive doctor`, delivery tracking, or other sidecar-backed runtime data), stop the existing sidecar for the current workspace after the mandatory refresh step, then rerun the target command so the sidecar restarts under the new code. Otherwise you may be verifying a stale daemon process instead of the code you just changed.
- `PYTHONPATH=src python -m pytest tests/ -q` — run the full test suite.
- `PYTHONPATH=src python -m pytest tests/ -m unit -q` — fast unit tests only.
- `PYTHONPATH=src python -m pytest tests/ -m cli -q` — CLI-layer tests.
- `PYTHONPATH=src python -m pytest tests/ -m e2e -q` — end-to-end tmux tests.
- `PYTHONPATH=src python -m pytest tests/unit/test_cvim_command.py tests/unit/test_cvim_payload.py -q` — focused `/cvim` and `/vim` sendback coverage.

## Coding Style & Naming Conventions

Use Python 3.11+ with 4-space indentation and type hints where practical. Match the existing style: small focused functions, minimal comments, and straightforward dataclass-based models. File names are lowercase with underscores. Test names should be explicit, e.g. `test_wait_status_times_out_without_match`. Do not leave dead code: if a function becomes a no-op or unused, delete it along with all call sites instead of leaving an empty body.

## Testing Guidelines

Every CLI command should have at least one CLI test and complex flows should also have e2e coverage. Add unit tests for pure logic before relying on higher-level tests. Keep new tests in the correct layer and use shared fixtures from `tests/conftest.py` or helpers in `tests/e2e/_helpers.py`.

When touching `/cvim` popup sendback behavior, keep `tests/unit/test_cvim_command.py::test_popup_schedules_post_after_popup_exits` passing. It guards the regression where `run-shell` was started before popup teardown completed, causing the returned edit payload to be swallowed.

## Commit & Pull Request Guidelines

Follow the existing history style: short conventional messages such as `fix: ...`, `refactor: ...`, or `docs: ...`. Keep commits scoped to one logical change. Before opening a PR, run the relevant pytest targets, summarize the behavioral change, and call out tmux/droid assumptions or manual verification steps.

## Version Bump

Only bump when the user explicitly says `bump`（或 `commit push bump`）. Normal `commit push` does **not** bump.

When bumping, scan all commits since the last version bump commit and determine the level automatically:

1. Find the last commit that touched `pyproject.toml` version (or the last `chore: bump version` commit).
2. Collect all commit headers between that point and HEAD.
3. Determine bump level from the **highest impact** in that range:
   - Bump **minor** only when there is a large user-facing feat: a genuinely new capability, workflow, or command surface, or a significant change in default behavior or external integration (e.g. 0.4.0 → 0.5.0)
   - Everything else is **patch**, including internal `feat:` improvements, reliability/performance, diagnostics, help/docs/skill text, refactors, and polish or surfacing of existing behavior (e.g. 0.4.0 → 0.4.1)
   - **Judgement test**: 问"user / agent 能做的真·新事情是什么?"。如果答案是"以前就能做,只是换了名字 / 修好了会崩的场景",就是 patch
   - **Patch traps**(这些看起来像 minor,实则是 patch):修 bug 顺带加的 override / escape-hatch flag、重命名 scheme、tag key 翻新、新 debug 子命令。即使单 commit 带 `feat:` 前缀也不自动提级
   - When in doubt, default to **patch**
4. **Never auto-bump major.** If any commit has breaking changes (`!` suffix or `BREAKING CHANGE`), ask the user.
5. Edit `pyproject.toml` version, commit as `chore: bump version to X.Y.Z`, then push.

## Security & Runtime Notes

Do not hardcode secrets, session IDs, or local machine paths. Hive depends on `tmux` and Factory `droid`; e2e tests assume tmux is available and use a fake droid binary for isolation.
The sidecar is a long-lived workspace process. When validating sidecar-related runtime changes manually, restart it from the current workspace before trusting `doctor`, delivery, or activity output.
