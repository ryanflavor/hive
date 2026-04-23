from pathlib import Path


def test_hive_skill_guides_multiline_send_via_artifact():
    """守 canonical heredoc + stdin artifact 片段(root 协议 happy path)。
    只断言低变更、高价值的 shell idioms,不守具体中文措辞。"""
    skill_text = (Path(__file__).resolve().parents[2] / "skills" / "hive" / "SKILL.md").read_text()

    # install / refresh canonical commands
    assert 'npx skills add https://github.com/notdp/hive -g --all' in skill_text
    assert 'npx skills add "$PWD" -g --all' in skill_text
    assert "pipx upgrade hive" in skill_text
    assert "npx skills update hive -g" in skill_text

    # heredoc + stdin artifact: command-first idiom (not `cat <<EOF | hive send`)
    assert "--artifact -" in skill_text
    assert "<<'EOF'" in skill_text
    assert "--artifact - <<'EOF'" in skill_text


def test_hive_install_docs_use_npx_skills_add_as_canonical_path():
    """守 install/refresh 命令在 README / AGENTS 跨文件一致 — contract test"""
    repo_root = Path(__file__).resolve().parents[2]
    readme_text = (repo_root / "README.md").read_text()
    agents_text = (repo_root / "AGENTS.md").read_text()

    assert "pipx upgrade hive" in readme_text
    assert "npx skills update hive -g" in readme_text
    assert 'npx skills add https://github.com/notdp/hive -g --all' in readme_text
    assert 'npx skills add "$PWD" -g --all' in readme_text
    assert 'npx skills add "$PWD" -g --all' in agents_text
    assert 'repo changes to `skills/hive/SKILL.md` do not reach agents unless you refresh it via `npx skills add`' in agents_text
