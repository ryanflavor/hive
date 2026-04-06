import json

from hive.cli import cli


def test_plugin_list_enable_and_disable_cvim(runner, configure_hive_home):
    hive_home = configure_hive_home(tmux_inside=False)
    factory_home = hive_home.parent / ".factory"
    (factory_home / "settings.json").parent.mkdir(parents=True, exist_ok=True)
    (factory_home / "settings.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "~/.dotfiles/bin/droid-session-map-hook"}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "~/.dotfiles/bin/droid-session-map-hook"}]}],
            "SessionEnd": [{"hooks": [{"type": "command", "command": "~/.dotfiles/bin/droid-session-map-hook"}]}],
        }
    }))

    listed = runner.invoke(cli, ["plugin", "list"])
    assert listed.exit_code == 0
    assert "Plugins (0/4 enabled)" in listed.output
    assert "cvim" in listed.output
    assert "disabled" in listed.output

    settings = json.loads((factory_home / "settings.json").read_text())
    expected_hook = str(hive_home / "core" / "bin" / "droid-session-map-hook")
    for event in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
        assert settings["hooks"][event][0]["hooks"][0]["command"] == "~/.dotfiles/bin/droid-session-map-hook"
        assert settings["hooks"][event][1]["hooks"][0]["command"] == expected_hook

    listed_json = runner.invoke(cli, ["plugin", "list", "--json"])
    assert listed_json.exit_code == 0
    names = {item["name"]: item for item in json.loads(listed_json.output)}
    assert {"cvim", "notify", "code-review", "fork"}.issubset(names)
    assert names["cvim"]["enabled"] is False

    enabled = runner.invoke(cli, ["plugin", "enable", "cvim"])
    assert enabled.exit_code == 0
    assert "Plugin 'cvim' enabled." in enabled.output
    assert "commands: cvim, vim" in enabled.output

    enabled_json = runner.invoke(cli, ["plugin", "enable", "cvim", "--json"])
    assert enabled_json.exit_code == 0
    enable_payload = json.loads(enabled_json.output)
    assert enable_payload["enabled"] is True
    assert (factory_home / "commands" / "vim").exists()
    assert not (factory_home / "commands" / "vim").is_symlink()
    assert (factory_home / "commands" / "cvim").exists()
    assert not (factory_home / "commands" / "cvim").is_symlink()
    install_root = hive_home / "plugins" / "installed" / "cvim"
    installed_runner = install_root / "bin" / "droid-vim-command"
    installed_payload_builder = install_root / "bin" / "droid-vim-payload"
    installed_seed_helper = install_root / "bin" / "droid-vim-seed"
    installed_session_helper = install_root / "bin" / "droid-vim-session"
    installed_protocol = install_root / "resources" / "droid_edit_protocol.json"
    assert installed_runner.exists()
    assert installed_payload_builder.exists()
    assert installed_seed_helper.exists()
    assert installed_session_helper.exists()
    assert installed_protocol.exists()
    installed_runner_text = installed_runner.read_text()
    installed_cvim_text = (factory_home / "commands" / "cvim").read_text()
    installed_vim_text = (factory_home / "commands" / "vim").read_text()
    assert "from hive." not in installed_runner_text
    assert 'src_pane_pid="$(tmux display-message -p -t "$src_pane" \'#{pane_pid}\')"' in installed_runner_text
    assert 'src_pane_tty="$(tmux display-message -p -t "$src_pane" \'#{pane_tty}\')"' in installed_runner_text
    assert 'src_pane_tty_key="${src_pane_tty#/dev/}"' in installed_runner_text
    assert 'seed_helper="$script_dir/droid-vim-seed"' in installed_runner_text
    assert 'session_helper="$script_dir/droid-vim-session"' in installed_runner_text
    assert '"$seed_helper" "$cwd" "$dst" "$session_map_file" "$droid_pid" "$droid_tty" "$droid_args"' in installed_runner_text
    assert 'transcript_path="$("$session_helper" "$session_map_file" "$src_cwd" "" "$src_pane_tty_key" "")"' in installed_runner_text
    assert '"$seed_helper" "$src_cwd" "$msg_file" "$transcript_path"' in installed_runner_text
    assert 'capture_session_seed_to_file "$src_cwd" "$msg_file" "$droid_pid" "$droid_tty" "$droid_args"' in installed_runner_text
    assert '"$helper_file" "$reply_pane" "$editor_bin" "$msg_file" "$orig_file" "$tmpdir" "$output_mode"' in installed_runner_text
    assert '"$submit_delay_default" "$cursor_mode" "$payload_builder"' in installed_runner_text
    assert 'payload_builder="${13}"' in installed_runner_text
    assert "\"$payload_builder\" \"$orig_file\" \"$msg_file\" \"$send_file\" \"$send_mode\"" in installed_runner_text
    payload_builder_text = installed_payload_builder.read_text()
    assert "droid_edit_protocol.json" in payload_builder_text
    assert "<edit_target>" in payload_builder_text
    protocol_text = installed_protocol.read_text()
    assert "紧邻上一条 assistant message" in protocol_text
    assert "previous_assistant_message" in protocol_text
    assert str(installed_runner) in installed_cvim_text
    assert str(installed_runner) in installed_vim_text
    assert "previous_assistant_message</edit_target>" in installed_cvim_text
    assert "immediately" in installed_cvim_text
    assert "previous_assistant_message</edit_target>" in installed_vim_text
    assert "immediately" in installed_vim_text

    settings = json.loads((factory_home / "settings.json").read_text())
    for event in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
        assert settings["hooks"][event][0]["hooks"][0]["command"] == "~/.dotfiles/bin/droid-session-map-hook"
        assert settings["hooks"][event][1]["hooks"][0]["command"] == expected_hook

    relisted = runner.invoke(cli, ["plugin", "list", "--json"])
    assert relisted.exit_code == 0
    relisted_payload = {item["name"]: item for item in json.loads(relisted.output)}
    assert relisted_payload["cvim"]["enabled"] is True

    disabled = runner.invoke(cli, ["plugin", "disable", "cvim"])
    assert disabled.exit_code == 0
    assert "Plugin 'cvim' disabled." in disabled.output
    assert not (factory_home / "commands" / "vim").exists()
    assert not (factory_home / "commands" / "cvim").exists()
    assert (hive_home / "core" / "bin" / "droid-session-map-hook").exists()


def test_plugin_enable_cross_review_materializes_skill(runner, configure_hive_home):
    hive_home = configure_hive_home(tmux_inside=False)
    factory_home = hive_home.parent / ".factory"

    enabled = runner.invoke(cli, ["plugin", "enable", "code-review"])

    assert enabled.exit_code == 0
    assert "Plugin 'code-review' enabled." in enabled.output
    assert "skills: code-review" in enabled.output
    assert (factory_home / "skills" / "code-review").is_symlink()

    skill = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "SKILL.md"
    assert skill.exists()
    skill_text = skill.read_text()
    assert "disable-model-invocation: false" in skill_text
    assert "MANDATORY when the current conversation already contains Droid's built-in review system notification" in skill_text
    assert "Route built-in `/review` directly into the Hive multi-agent review workflow" in skill_text
    assert "this skill depends on `hive`" in skill_text
    assert "Your first action after entering this skill MUST be `/hive`" in skill_text
    assert "如果 `hive current` 返回 `team: null` 且存在 tmux session，必须立即执行 `hive init`" in skill_text
    assert "在完成 `hive init` / `hive team` / reviewer `spawn` 之前，不要运行 `git diff`" in skill_text
    assert "Review the current code changes (staged, unstaged, and untracked files)" in skill_text
    assert "Review the code changes against the base branch '<base>'" in skill_text
    assert "patch 是 `correct` 还是 `incorrect`" in skill_text
    assert "`hive status-set` 只能二选一：传 summary 位置参数，或传 `--activity`；不要同时传两者。" in skill_text
    assert "多行或结构化争议点不要内联到 `hive send` 里" in skill_text
    assert 'hive send codex "see dispute artifact" --artifact /tmp/hive-xxx/artifacts/s3-dispute.md' in skill_text

    stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "1-review-orchestrator.md"
    assert stage.exists()
    stage_text = stage.read_text()
    assert 'Done Command: hive status-set done "review complete" --task code-review --meta stage=s1 --meta reviewer=${reviewer} --meta artifact=$out --meta verdict=<ok|issues>' in stage_text
    assert "hive status-set busy --task code-review --activity launch-reviews" in stage_text
    assert "hive spawn opus --cli droid --model custom:Claude-Opus-4.6-0 --workflow code-review" in stage_text
    assert "hive spawn codex --cli droid --model custom:GPT-5.4-1 --workflow code-review" in stage_text
    assert "hive team" in stage_text
    assert "至少 90s" in stage_text
    assert "hive workflow load opus code-review" in stage_text
    assert "hive workflow load codex code-review" in stage_text
    assert "不要重复 spawn 同一个 reviewer" in stage_text
    assert "不要回复 ready" in stage_text
    assert "若 reviewer 只回复了泛化的 ready / 自我介绍" in stage_text
    assert "仅凭 team 成员列表不能确认 reviewer 已就绪" in stage_text
    assert "hive capture" in stage_text
    assert 'hive status-set busy "stage-1" --task code-review --activity launch-reviews' not in stage_text
    assert '--activity ${reviewer}-r1-done' not in stage_text

    review_opus_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "1-review-opus.md"
    assert review_opus_stage.exists()
    review_opus_stage_text = review_opus_stage.read_text()
    assert 'hive status-set failed "invalid request" --task code-review --meta stage=s1 --meta reviewer=opus' in review_opus_stage_text
    assert "不要先回复泛化的 ready / 自我介绍" in review_opus_stage_text
    assert "不要先发送任何只表示“已准备好”的 Hive 消息" in review_opus_stage_text
    assert '--activity request-invalid' not in review_opus_stage_text

    review_codex_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "1-review-codex.md"
    assert review_codex_stage.exists()
    review_codex_stage_text = review_codex_stage.read_text()
    assert "不要先回复泛化的 ready / 自我介绍" in review_codex_stage_text
    assert "不要先发送任何只表示“已准备好”的 Hive 消息" in review_codex_stage_text

    judge_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "2-judge-consensus-orchestrator.md"
    assert judge_stage.exists()
    judge_stage_text = judge_stage.read_text()
    assert 'hive status-set busy --task code-review --activity judge-consensus' in judge_stage_text
    assert 'hive status-set busy "stage-2" --task code-review --activity judge-consensus' not in judge_stage_text

    cross_orch_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "3-cross-confirm-orchestrator.md"
    assert cross_orch_stage.exists()
    cross_orch_stage_text = cross_orch_stage.read_text()
    assert 'hive status-set busy --task code-review --activity launch-cross-confirm' in cross_orch_stage_text
    assert 'hive status-set busy "stage-3" --task code-review --activity launch-cross-confirm' not in cross_orch_stage_text

    cross_opus_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "3-cross-confirm-opus.md"
    assert cross_opus_stage.exists()
    cross_opus_stage_text = cross_opus_stage.read_text()
    assert 'hive status-set done "cross confirm complete" \\' in cross_opus_stage_text
    assert "不要把 `$(cat <<EOF ...)` 这类多行 command substitution 内联进 `hive send`" in cross_opus_stage_text
    assert 'hive send codex "阶段 3：请结合争议点 artifact 回复 Fix / Skip / Deadlock。" --artifact "$DISPUTE_ARTIFACT"' in cross_opus_stage_text
    assert '--activity cross-confirm-done' not in cross_opus_stage_text

    cross_codex_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "3-cross-confirm-codex.md"
    assert cross_codex_stage.exists()
    cross_codex_stage_text = cross_codex_stage.read_text()
    assert "若回复包含多行结构化内容，先写 artifact 再 `hive send opus ... --artifact <path>`" in cross_codex_stage_text
    assert 'hive send opus "阶段 3：我的逐项结论见 artifact。" --artifact "$ROUND_ARTIFACT"' in cross_codex_stage_text

    fix_orch_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "4-fix-verify-orchestrator.md"
    assert fix_orch_stage.exists()
    fix_orch_stage_text = fix_orch_stage.read_text()
    assert 'hive status-set busy --task code-review --activity fix-verify-round-1' in fix_orch_stage_text
    assert 'hive status-set busy "stage-4" --task code-review --activity fix-verify-round-1' not in fix_orch_stage_text

    fix_opus_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "4-fix-verify-opus.md"
    assert fix_opus_stage.exists()
    fix_opus_stage_text = fix_opus_stage.read_text()
    assert 'hive status-set done "fix round complete"           --task code-review           --meta stage=s4' in fix_opus_stage_text
    assert '--activity fix-round-done' not in fix_opus_stage_text

    fix_codex_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "4-fix-verify-codex.md"
    assert fix_codex_stage.exists()
    fix_codex_stage_text = fix_codex_stage.read_text()
    assert 'hive status-set done "verify round complete"           --task code-review           --meta stage=s4' in fix_codex_stage_text
    assert '--activity verify-round-done' not in fix_codex_stage_text

    summary_stage = hive_home / "plugins" / "installed" / "code-review" / "skills" / "code-review" / "stages" / "5-summary-orchestrator.md"
    assert summary_stage.exists()
    summary_stage_text = summary_stage.read_text()
    assert 'hive status-set done "review workflow complete" \\' in summary_stage_text
    assert '--activity summary-done' not in summary_stage_text

    enabled_json = runner.invoke(cli, ["plugin", "enable", "code-review", "--json"])
    assert enabled_json.exit_code == 0
    assert json.loads(enabled_json.output)["enabled"] is True


def test_plugin_enable_code_review_does_not_touch_existing_user_review_skill(runner, configure_hive_home):
    hive_home = configure_hive_home(tmux_inside=False)
    factory_home = hive_home.parent / ".factory"

    user_skill_dir = factory_home / "skills" / "review"
    user_skill_dir.mkdir(parents=True, exist_ok=True)
    user_skill_file = user_skill_dir / "SKILL.md"
    user_skill_file.write_text("---\nname: review\ndescription: my custom review skill\n---\n")

    enabled = runner.invoke(cli, ["plugin", "enable", "code-review"])

    assert enabled.exit_code == 0
    assert "skills: code-review" in enabled.output
    assert "Warning: skipped skill(s) review" not in enabled.output
    assert user_skill_file.read_text().startswith("---\nname: review\ndescription: my custom review skill")
    assert not user_skill_dir.is_symlink()
    assert (factory_home / "skills" / "code-review").is_symlink()


def test_plugin_reenable_preserves_user_skill_that_replaced_old_plugin_symlink(runner, configure_hive_home):
    hive_home = configure_hive_home(tmux_inside=False)
    factory_home = hive_home.parent / ".factory"

    enabled = runner.invoke(cli, ["plugin", "enable", "code-review"])
    assert enabled.exit_code == 0

    review_skill = factory_home / "skills" / "review"
    if review_skill.is_symlink():
        review_skill.unlink()
    elif review_skill.is_dir():
        import shutil
        shutil.rmtree(review_skill)
    review_skill.mkdir(parents=True, exist_ok=True)
    (review_skill / "SKILL.md").write_text("---\nname: review\ndescription: user custom\n---\n")

    reenabled = runner.invoke(cli, ["plugin", "enable", "code-review"])
    assert reenabled.exit_code == 0
    assert review_skill.exists()
    assert not review_skill.is_symlink()
    assert (review_skill / "SKILL.md").read_text().startswith("---\nname: review\ndescription: user custom")


def test_plugin_enable_notify_materializes_command_and_hooks(runner, configure_hive_home):
    hive_home = configure_hive_home(tmux_inside=False)
    factory_home = hive_home.parent / ".factory"

    enabled = runner.invoke(cli, ["plugin", "enable", "notify"])

    assert enabled.exit_code == 0
    assert "Plugin 'notify' enabled." in enabled.output
    assert "commands: notify" in enabled.output
    assert (factory_home / "commands" / "notify").exists()

    installed_root = hive_home / "plugins" / "installed" / "notify"
    hook_runner = installed_root / "bin" / "droid-notify-hook"
    hook_defs = installed_root / "hooks" / "hooks.json"
    assert hook_runner.exists()
    assert hook_defs.exists()

    settings = json.loads((factory_home / "settings.json").read_text())
    for event in ("Notification", "Stop"):
        group = settings["hooks"][event][0]
        assert group["hooks"][0]["command"] == str(hook_runner)
        assert group["hooks"][0]["timeout"] == 5
