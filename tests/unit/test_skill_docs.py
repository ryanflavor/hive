from pathlib import Path


def test_hive_skill_guides_multiline_send_via_artifact():
    skill_text = (Path(__file__).resolve().parents[2] / "skills" / "hive" / "SKILL.md").read_text()

    assert "大内容或多行结构化内容先写 artifact" in skill_text
    assert "不要把 `$(cat <<EOF ...)` 这类多行 command substitution 直接塞进 `hive send`" in skill_text
