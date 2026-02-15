# Mission: 基于 tmux 的 Droid Agent 协作框架

## Phase 0 测试结论 (2026-02-15)

### 测试矩阵

| 测试项 | 结果 | 说明 |
|---|---|---|
| `exec --stream-jsonrpc` | ✅ | JSON-RPC 双向可用（但只有 headless） |
| `load_session` 恢复 | ✅ | 顺序恢复完美，ALPHA_123 验证通过 |
| 交互式 droid + send_keys | ✅ | TUI 接受输入，droid 正常处理和回复 |
| 交互式 droid + JSON-RPC flags | ❌ | flags 被忽略，TUI 照常启动 |
| 双进程并发同一 session | ❌ | load_session 是磁盘快照，不共享内存 |
| `droid daemon` | ❌ | WebSocket + 需 Factory 付费认证 |

### 架构决策

**放弃 JSON-RPC，采用 Claude Code 方案：交互式 droid in tmux + send_keys + 文件 inbox。**

理由：
1. JSON-RPC 只能在 headless 模式用，无法与交互式 TUI 共存
2. Claude Code 的 Agent Teams 也不用 JSON-RPC，用的是 send_keys + 文件 inbox
3. send_keys 可以模拟所有 TUI 操作（Escape=中断, Ctrl+N=切模型, Ctrl+L=改 autonomy）
4. 文件 inbox 提供结构化的 agent 间通信
5. 人可以直接 attach 到 tmux pane 操作原生 droid TUI

### Claude Code TmuxBackend 逆向分析

从二进制提取的关键实现：
- spawn: `tmux split-window` → `send-keys "claude --resume <sessionId>"`
- 布局: `select-layout tiled` / `main-vertical`，leader pane 30% 宽
- pane 管理: border color + title 标识 agent
- 通信: `~/.claude/teams/{name}/inboxes/{agent}.json`（文件 inbox）
- 任务: `~/.claude/tasks/{name}/{id}.json` + `.lock`（文件锁）
- 环境变量: `CLAUDE_CODE_TEAM_NAME`, `CLAUDE_CODE_AGENT_NAME`
- 生命周期: idle_notification, shutdown_request/approved

### 环境版本

- droid: 0.57.14（支持 `--resume [sessionId]`）
- tmux: 3.4
- Python: 3.12.0

---

## 核心架构

```
human ──attach──→ tmux pane（原生 droid TUI）
                    │
                  droid -r <sessionId>（交互式）
                    │
mission CLI ──send_keys──→ droid TUI stdin（控制）
mission CLI ──capture_pane──→ droid TUI stdout（读取）
                    │
agents ──file inbox──→ ~/.mission/teams/{name}/inboxes/（通信）
agents ──file tasks──→ ~/.mission/tasks/{name}/（协调）
```

### 控制映射

| 操作 | 实现 |
|---|---|
| 发消息 | `send_keys "prompt text" Enter` |
| 中断 | `send_keys Escape` |
| 切模型 | `send_keys Ctrl+N` |
| 切 autonomy | `send_keys Ctrl+L` |
| 切模式 | `send_keys Shift+Tab` |
| 读输出 | `capture_pane` |
| 人工接入 | `tmux attach / select-pane` |

---

## 借鉴 Claude Code（1:1 映射）

| Claude Code | mission |
|---|---|
| `claude --resume <id>` in tmux pane | `droid -r <id>` in tmux pane |
| `~/.claude/teams/{name}/config.json` | `~/.mission/teams/{name}/config.json` |
| `~/.claude/teams/{name}/inboxes/` | `~/.mission/teams/{name}/inboxes/` |
| `~/.claude/tasks/{name}/` | `~/.mission/tasks/{name}/` |
| `CLAUDE_CODE_TEAM_NAME` | `MISSION_TEAM_NAME` |
| `CLAUDE_CODE_AGENT_NAME` | `MISSION_AGENT_NAME` |
| TeammateTool（内置） | mission CLI + SKILL.md（外部） |
| `select-layout tiled` | 同 |
| pane border color + title | 同 |

---

## 模块设计

```
mission/
├── src/mission/
│   ├── __init__.py
│   ├── tmux.py      # tmux 操作（split/send_keys/capture_pane/layout/border）
│   ├── agent.py     # Agent = tmux pane + 交互式 droid
│   ├── team.py      # Team = tmux session + config.json + 一组 Agent
│   ├── inbox.py     # 文件 inbox（JSON 消息投递/读取）
│   ├── tasks.py     # 共享任务列表（文件 + flock）
│   └── cli.py       # mission create/spawn/send/capture/attach/status/shutdown
├── skill/
│   └── SKILL.md     # 教 droid 使用 mission CLI
├── pyproject.toml   # 依赖: click
└── tests/
```

---

## 分阶段

- **Phase 0** ✅: 可行性测试 + 架构决策
- **Phase 1**: tmux.py + agent.py + team.py + cli.py + skill（MVP）
- **Phase 2**: inbox.py + tasks.py + 委派模式
- **Phase 3**: 工作流模板 + 计划审批 + 质量门禁

---

## 与现有项目的关系

- **droid-agent-sdk**: 不再直接使用（FIFO + JSON-RPC 方案已弃用），但设计经验保留
- **duo-cli**: CLI 命令设计参考
- **duoduo skill**: Phase 3 移植为工作流模板
