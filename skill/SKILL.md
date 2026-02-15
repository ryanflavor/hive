# Mission Skill

You are part of a multi-agent team managed by **mission**. Use the `mission` CLI to communicate with teammates and coordinate work.

## Environment Variables

- `MISSION_TEAM_NAME` — your team name
- `MISSION_AGENT_NAME` — your agent name

## Commands

### Read your inbox
```bash
mission mail read $MISSION_AGENT_NAME -t $MISSION_TEAM_NAME
```

### Send a message to a teammate
```bash
mission mail send <teammate> "your message" -t $MISSION_TEAM_NAME --from $MISSION_AGENT_NAME --summary "brief summary"
```

### Check team status
```bash
mission status -t $MISSION_TEAM_NAME
```

## Protocol

### When you start
1. Check your inbox for initial instructions
2. If you have a task, start working on it
3. When done, send results to the requesting agent via `mission mail send`

### Communication format
When sending messages, include:
- Clear description of what you did
- Results or findings
- Any issues encountered

### Idle notification
When you finish your task and have no more work, send an idle notification:
```bash
mission mail send team-lead '{"type":"idle_notification","from":"'$MISSION_AGENT_NAME'","reason":"available"}' -t $MISSION_TEAM_NAME --from $MISSION_AGENT_NAME --summary "idle"
```

### Shutdown
If team-lead sends a shutdown request, acknowledge and stop working. Do not start new tasks.
