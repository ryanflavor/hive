# TUI Testing with tuistory

tuistory is a Playwright-like framework for terminal UIs. Use it for deterministic launch, key input, resize checks, and evidence capture.

## Setup

Ensure tuistory is available:
\`\`\`bash
which tuistory || (bun add -g tuistory || npm install -g tuistory)
tuistory --version
\`\`\`

Before using advanced flags, inspect the installed version's command surface:
\`\`\`bash
tuistory --help
tuistory snapshot --help
tuistory screenshot --help
\`\`\`

## Core Workflow (Reliable Path)

1. Launch a named session.
2. Wait for idle, then snapshot.
3. Handle first-run dialogs immediately.
4. Use short targeted waits for specific text.
5. Snapshot after every action.
6. Capture screenshots for visual proof.
7. Close the session when done.

\`\`\`bash
tuistory launch "my-tui-command" -s app --cols 110 --rows 32
tuistory -s app wait-idle --timeout 8000
tuistory -s app snapshot --trim

# interact
tuistory -s app type "help"
tuistory -s app press enter
tuistory -s app wait "Usage" --timeout 8000
tuistory -s app snapshot --trim

# capture visual artifact
tuistory -s app screenshot --format png -o /tmp/app-usage.png

# cleanup
tuistory -s app close
\`\`\`

## Key Input Rules (Critical)

- Use key tokens separated by spaces, not quoted chords.
- Correct: \`tuistory -s app press ctrl g\`
- Incorrect: \`tuistory -s app press "ctrl g"\`
- Use \`type\` for literal text and \`press\` for control/navigation keys.

Common keys:
\`\`\`bash
tuistory -s app press enter
tuistory -s app press esc
tuistory -s app press ctrl c
tuistory -s app press ctrl g
\`\`\`

## Wait Strategy (Avoid Flaky Long Sleeps)

- Prefer \`wait-idle\` after interactions that trigger repaint.
- Prefer \`wait <pattern>\` for async milestones.
- Keep timeouts bounded and contextual (3s-20s for most interactive steps).
- Avoid blind long waits unless absolutely necessary.

Recommended loop:
\`\`\`bash
tuistory -s app press enter
tuistory -s app wait-idle --timeout 3000
tuistory -s app snapshot --trim
\`\`\`

## Factory-Specific Gotchas (Important)

- Prefer \`droid-dev\` for local CLI validation. In some environments, \`bun run dev\` can fail if wrapper tools are unavailable.
- Ensure daemon + CLI deployment envs match (for example \`NODE_ENV/NEXT_ENV/FACTORY_ENV/FACTORY_DEPLOYMENT_ENV=development\`).
- Startup prompts can block flows (for example VSCode extension install). Detect and handle them early.
- Keep each action atomic: input -> wait-idle/wait -> snapshot.

## Factory CLI PR Verification Playbook (Known-Good)

When validating a CLI/TUI PR in factory-mono:

1. Ensure development daemon is running with dev env vars.
2. Launch CLI with a named session and explicit env in the launch command.
3. Immediately snapshot and resolve startup prompts (for example VSCode extension prompt).
4. Navigate to target UI state with deterministic key presses.
5. Run a resize matrix and capture both text snapshots and screenshots.
6. If needed, modify local test fixture files to induce error/edge states.

Before relaunching a reused session name, clean stale sessions:
\`\`\`bash
tuistory -s prcheck close >/dev/null 2>&1 || true
tuistory sessions
\`\`\`

Example pattern:
\`\`\`bash
# Start daemon separately (example)
NODE_ENV=development NEXT_ENV=development FACTORY_ENV=development FACTORY_DEPLOYMENT_ENV=development factoryd-dev

# Launch CLI test session (portable, explicit cwd/env)
tuistory launch "droid-dev --resume <session-id>"   -s prcheck   --cwd /path/to/apps/cli   --env NODE_ENV=development   --env NEXT_ENV=development   --env FACTORY_ENV=development   --env FACTORY_DEPLOYMENT_ENV=development   --cols 110 --rows 32

# Handle prompt and verify baseline
tuistory -s prcheck wait-idle --timeout 8000
tuistory -s prcheck snapshot --trim

# Open target view and verify
tuistory -s prcheck press ctrl g
tuistory -s prcheck wait "Mission Control" --timeout 10000
tuistory -s prcheck snapshot --trim

# Resize matrix
tuistory -s prcheck resize 90 28
tuistory -s prcheck wait-idle --timeout 3000
tuistory -s prcheck screenshot --format png -o /tmp/prcheck-90x28.png
tuistory -s prcheck resize 120 40
tuistory -s prcheck wait-idle --timeout 3000
tuistory -s prcheck screenshot --format png -o /tmp/prcheck-120x40.png
tuistory -s prcheck resize 70 22
tuistory -s prcheck wait-idle --timeout 3000
tuistory -s prcheck screenshot --format png -o /tmp/prcheck-70x22.png
\`\`\`

Note: shell-style launch strings (for example \`cd ... && ...\`) may work, but \`--cwd\` + \`--env\` is clearer and more portable.

## Artifact Capture

Use both text and image artifacts:

\`\`\`bash
tuistory -s app snapshot --trim > /tmp/state.txt
tuistory -s app screenshot --format png -o /tmp/state.png
\`\`\`

For a lightweight demo video, stitch screenshots with ffmpeg:
\`\`\`bash
# frames.txt format:
# file '/tmp/frame-01.png'
# duration 1.0
# ...
ffmpeg -y -f concat -safe 0 -i /tmp/frames.txt -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p" /tmp/demo.mp4
\`\`\`

Keep artifacts in one directory so you can hand users a single path.

## Troubleshooting

### Session won't reach expected state

- Capture a snapshot immediately and inspect current UI.
- Check for modal/prompt text that blocks navigation.
- Use incremental actions: key press -> wait-idle -> snapshot.

### Command appears to do nothing

- Confirm key syntax (space-separated tokens for chords).
- Verify session name is correct with \`tuistory sessions\`.
- Re-check the active command with \`snapshot\` before retrying.

### Rendering checks are inconclusive

- Use \`screenshot\` (not only text snapshots).
- Test multiple sizes (small/medium/large) and compare borders/alignment.

## Command Reference (Current)

\`\`\`bash
tuistory launch <command>
tuistory snapshot
tuistory screenshot
tuistory type <text>
tuistory press <key> [...keys]
tuistory click <pattern>
tuistory click-at <x> <y>
tuistory wait <pattern>
tuistory wait-idle
tuistory scroll <up|down> [lines]
tuistory resize <cols> <rows>
tuistory capture-frames <key> [...keys]
tuistory close
tuistory sessions
tuistory logfile
\`\`\`
