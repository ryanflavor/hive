# TUI Application Playbook

This playbook guides you through executing a terminal user interface (TUI) application mission. Use this for CLI tools with interactive interfaces, terminal dashboards, text-based editors, and similar projects rendered in the terminal.

## Milestone Strategy: Vertical Slices

Structure your milestones as **vertical slices** of functionality, not horizontal layers.

**Good milestones:**
- "navigation" (menu system, views, keybindings - full stack)
- "data-display" (list views, detail views, formatting - full stack)
- "editing" (input handling, validation, persistence - full stack)

**Bad milestones:**
- "all-keybindings" (horizontal - can't test in isolation)
- "rendering-layer" (horizontal - can't test without data/state)

Each milestone should leave the app in a coherent, testable state where a user can complete a meaningful flow.

## Worker Types for TUI

### tui-worker

- Implements TUI features (views, components, input handling, state)
- **TDD: Write tests FIRST (before any implementation)**
- **MUST do manual TUI verification with tuistory:**
  - Launch the app, navigate to the relevant view, and verify rendering and interactions
  - Use \\\`tuistory snapshot --trim\\\` to capture terminal output and verify visual correctness
  - Test keyboard interactions (\\\`tuistory press <key>\\\`), input handling (\\\`tuistory type "<text>"\\\`)
  - Check for rendering artifacts, alignment issues, overflow, and missing states
- **Fix issues found:**
  - Issues with own work (including from manual testing) \u2192 must fix
  - Manageable existing issues under their skill \u2192 fix them
  - Large scope or outside their skill \u2192 report to orchestrator
  - Include any fixes in whatWasImplemented

### backend-worker

- Implements data layer, services, and business logic that the TUI consumes
- **TDD: Write tests FIRST (before any implementation)**
- Verifies actual behavior (not just tests passing)
- **Fix issues found:**
  - Issues with own work (including from manual testing) \u2192 must fix
  - Manageable existing issues under their skill \u2192 fix them
  - Large scope or outside their skill \u2192 report to orchestrator
  - Include any fixes in whatWasImplemented

## Quality Enforcement Flow

\\\`\\\`\\\`text
1. Orchestrator creates implementation features grouped by milestone
2. Implementation workers build features (TDD + manual verification via tuistory)
3. When milestone X completes \u2192 system injects scrutiny and user-testing validators for the milestone
4. Failed validation surfaces bugs \u2192 orchestrator creates fix features
5. Repeat until milestone passes, then move to next milestone
\\\`\\\`\\\`

### Example tuistory validation flow

\\\`\\\`\\\`bash
# Launch the app
tuistory launch "node ./dist/cli.js" -s myapp --cols 120 --rows 40

# Wait for startup
tuistory -s myapp wait "Ready" --timeout 15000

# Navigate to the view under test
tuistory -s myapp press tab
tuistory -s myapp snapshot --trim   # verify navigation state

# Test a specific interaction
tuistory -s myapp type "search query"
tuistory -s myapp press enter
tuistory -s myapp wait "Results" --timeout 10000
tuistory -s myapp snapshot --trim   # verify results rendered correctly

# Clean up
tuistory -s myapp close
\\\`\\\`\\\`

## Common Pitfalls

1. **Building state management without UI** - Leads to data structures that don't match rendering needs. Build vertical slices instead.

2. **Forgetting edge states** - Workers often implement happy path only. expectedBehavior should include empty states, error states, overflow/truncation, and resize handling.

3. **Not testing keyboard interactions** - TUI apps are keyboard-driven. Every view needs its keybindings tested, including edge cases (rapid input, conflicting shortcuts).

4. **Not verifying visually with tuistory** - Unit tests can't catch rendering issues. Workers must use tuistory to verify layout, alignment, and visual state.

5. **No lasting test infrastructure** - Per-worker TDD produces unit/integration tests, but consider whether the mission also needs dedicated features for shared test fixtures or e2e test suites using tuistory.
