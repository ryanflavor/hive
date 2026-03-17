# Hive

tmux-based multi-agent collaboration framework for [Factory](https://factory.ai)'s `droid` CLI.

Spawn multiple droid agents in tmux panes, orchestrate them via CLI, inject short control messages inline via tmux, and persist workflow state in a workspace.

## Architecture

```
┌──────────────┬──────────────┐
│              │   agent-1    │
│ orchestrator ├──────────────┤
│   (you)      │   agent-2    │
└──────────────┴──────────────┘

orchestrator ──hive spawn──→ tmux split-window → droid TUI
orchestrator ──hive send───→ tmux send_keys → inline <HIVE ...> message
orchestrator ──hive capture─→ capture_pane → agent stdout
agents ────────workspace────→ artifacts/ + status/
```

## Install

Requires: Python 3.11+, tmux, [droid](https://docs.factory.ai)

```bash
pipx install git+https://github.com/notdp/hive.git
```

## Usage

```bash
# Create a team + workspace
hive create my-team -d "code review" --workspace /tmp/hive-demo

# Spawn agents
hive spawn claude -t my-team -m "custom:claude-opus-4-6"
hive spawn gpt -t my-team -m "custom:gpt-5.3-codex"

# Send a task
hive send claude "Review the PR diff and write findings to the workspace artifact" -t my-team

# Monitor
hive who -t my-team
hive status-show -t my-team -w /tmp/hive-demo
hive wait-status claude -t my-team -w /tmp/hive-demo --state done
hive capture claude -t my-team

# Interrupt / cleanup
hive interrupt claude -t my-team
hive delete my-team
```

## Commands

| Command | Description |
|---------|-------------|
| `hive create <team>` | Create a team + optional workspace |
| `hive spawn <agent>` | Spawn a droid agent in a new tmux pane |
| `hive type <agent> "text"` | Send a raw prompt directly to an agent (debug / escape hatch) |
| `hive send <agent> "text"` | Deliver an inline `<HIVE ...>` message to an agent |
| `hive who` / `hive status` | Show team presence and published statuses |
| `hive status-set` / `hive status-show` | Publish and read workflow state snapshots |
| `hive wait-status` | Poll until an agent publishes the expected state |
| `hive capture <agent>` | Read agent's pane output |
| `hive interrupt <agent>` | Press Escape in agent's pane |
| `hive delete <team>` | Kill agents + remove team data |

## Workspace

When created with `--workspace`, hive initializes a workspace for durable workflow state and large artifacts:

```
workspace/
├── state/          # Shared key-value state files
├── presence/       # Team presence snapshots from `hive who` / `hive status`
├── status/         # Per-agent workflow status snapshots
└── artifacts/      # Large payloads exchanged by path
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HIVE_TEAM_NAME` | Default team name (auto-set for spawned agents) |
| `HIVE_AGENT_NAME` | Agent's own name (auto-set on spawn) |
| `HIVE_HOME` | Data directory (default: `~/.hive`) |

## How It Works

Hive runs interactive `droid` sessions in tmux panes. Short coordination messages arrive inline as `<HIVE ...>` blocks via tmux `send_keys`; long payloads and durable completion signals live in workspace `artifacts/` and `status/`. No JSON-RPC, no daemon — just tmux + workspace files.

Each spawned agent is a full `droid` TUI session. You can `tmux select-pane` to interact with any agent directly.

## License

MIT
