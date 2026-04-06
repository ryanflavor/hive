# 阶段 3: 交叉确认 - Codex

收到 Opus 的交叉确认请求后，只围绕争议点回复。

## 规则

1. 先阅读 Opus 给出的争议点和上下文 artifact
2. 对每个 issue 明确给出 `Fix` / `Skip` / `Deadlock`
3. 理由保持简短、可验证、面向代码行为
4. 普通进度通过 `hive send opus ...` 回复，status 只放阶段性结论
5. 若回复包含多行结构化内容，先写 artifact 再 `hive send opus ... --artifact <path>`；不要把 `$(cat <<EOF ...)` 直接内联进 `hive send`

## 回复格式

```markdown
C1: Fix - 因为 ...
C2: Skip - 因为 ...
```

长回复可改用 artifact：

```bash
ROUND_ARTIFACT="$WORKSPACE/artifacts/s3-codex-round-1.md"
cat > "$ROUND_ARTIFACT" <<'EOF'
C1: Fix - 因为 ...
C2: Skip - 因为 ...
EOF
hive send opus "阶段 3：我的逐项结论见 artifact。" --artifact "$ROUND_ARTIFACT"
```

若 Opus 已宣布达成共识或结束讨论，等待后续阶段任务即可。
