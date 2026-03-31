"""Agent CLI profiles: droid, claude, codex."""

from __future__ import annotations

from dataclasses import dataclass

AGENT_CLI_NAMES = frozenset({"droid", "claude", "codex"})
SHELL_NAMES = frozenset({"zsh", "bash", "fish", "sh", "dash", "ksh", "tcsh", "csh"})


def is_agent_command(command: str) -> bool:
    return command in AGENT_CLI_NAMES


def is_shell_command(command: str) -> bool:
    return command in SHELL_NAMES


def member_role(command: str) -> str:
    if is_agent_command(command):
        return "agent"
    return "terminal"


@dataclass(frozen=True)
class CLIProfile:
    name: str
    ready_text: str
    resume_cmd: str
    fork_cmd: str | None
    fork_needs_tui: bool
    skill_cmd: str


PROFILES: dict[str, CLIProfile] = {
    "droid": CLIProfile(
        name="droid",
        ready_text="for help",
        resume_cmd="droid -r {session_id}",
        fork_cmd="/fork",
        fork_needs_tui=True,
        skill_cmd="/skill {name}",
    ),
    "claude": CLIProfile(
        name="claude",
        ready_text="for help",
        resume_cmd="claude -r {session_id} --fork-session",
        fork_cmd=None,
        fork_needs_tui=False,
        skill_cmd="/skill {name}",
    ),
    "codex": CLIProfile(
        name="codex",
        ready_text="for help",
        resume_cmd="codex fork {session_id}",
        fork_cmd=None,
        fork_needs_tui=False,
        skill_cmd="/skill {name}",
    ),
}

DEFAULT_PROFILE = PROFILES["droid"]


def get_profile(command: str) -> CLIProfile:
    return PROFILES.get(command, DEFAULT_PROFILE)


def detect_profile_from_pane_command(command: str) -> CLIProfile:
    return get_profile(command)
