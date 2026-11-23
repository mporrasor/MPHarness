"""End-to-end tests of `harness guard` using the real hook payload shapes of each agent."""
import json

from click.testing import CliRunner

from harness_cli.cli import main
from harness_cli.installers import (
    antigravity_installed,
    claude_installed,
    install_antigravity,
    install_claude,
)

FAKE_GITHUB = "ghp_" + "a1B2" * 9


def run_guard(agent, payload):
    result = CliRunner().invoke(main, ["guard", "--agent", agent], input=json.dumps(payload))
    return result.exit_code, result.output


# ------------------------------------------------------------------ Claude Code

def claude_payload(tmp_path, tool, tool_input):
    return {"hook_event_name": "PreToolUse", "cwd": str(tmp_path), "tool_name": tool, "tool_input": tool_input}


def test_claude_allow_is_silent(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    code, out = run_guard("claude", claude_payload(tmp_path, "Bash", {"command": "npm test"}))
    assert code == 0 and out == ""


def test_claude_deny_force_push(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    code, out = run_guard("claude", claude_payload(tmp_path, "Bash", {"command": "git push --force"}))
    body = json.loads(out)["hookSpecificOutput"]
    assert code == 0
    assert body["hookEventName"] == "PreToolUse"
    assert body["permissionDecision"] == "deny"
    assert "MPHarness" in body["permissionDecisionReason"]


def test_claude_deny_secret_in_write(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = claude_payload(tmp_path, "Write", {"file_path": str(tmp_path / "app.js"), "content": f"t='{FAKE_GITHUB}'"})
    assert json.loads(run_guard("claude", payload)[1])["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_multiedit_scans_every_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    edits = [{"old_string": "a", "new_string": "b"}, {"old_string": "c", "new_string": f"'{FAKE_GITHUB}'"}]
    payload = claude_payload(tmp_path, "MultiEdit", {"file_path": str(tmp_path / "app.js"), "edits": edits})
    assert json.loads(run_guard("claude", payload)[1])["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_ask_reading_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = claude_payload(tmp_path, "Read", {"file_path": str(tmp_path / ".env")})
    assert json.loads(run_guard("claude", payload)[1])["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_claude_nonexistent_cwd_still_evaluates(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = {"tool_name": "Bash", "tool_input": {"command": "npm test"}, "cwd": str(tmp_path / "missing")}
    assert run_guard("claude", payload) == (0, "")


def test_guard_fails_closed_on_garbage(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    result = CliRunner().invoke(main, ["guard", "--agent", "claude"], input="not json")
    assert json.loads(result.output)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ------------------------------------------------------------------ Antigravity

def ag_payload(tmp_path, name, args):
    return {"conversationId": "c1", "workspacePaths": [str(tmp_path)], "toolCall": {"name": name, "args": args}, "stepIdx": 0}


def test_antigravity_allow(tmp_path):
    code, out = run_guard("antigravity", ag_payload(tmp_path, "run_command", {"CommandLine": "npm test", "Cwd": str(tmp_path)}))
    assert code == 0 and json.loads(out) == {"decision": "allow"}


def test_antigravity_deny_no_verify(tmp_path):
    out = run_guard("antigravity", ag_payload(tmp_path, "run_command", {"CommandLine": "git commit --no-verify -m x"}))[1]
    body = json.loads(out)
    assert body["decision"] == "deny" and "MPHarness" in body["reason"]


def test_antigravity_deny_secret_in_replace_chunks(tmp_path):
    args = {"TargetFile": str(tmp_path / "app.py"),
            "ReplacementChunks": [{"TargetContent": "x", "ReplacementContent": f"T='{FAKE_GITHUB}'"}]}
    assert json.loads(run_guard("antigravity", ag_payload(tmp_path, "multi_replace_file_content", args))[1])["decision"] == "deny"


def test_antigravity_ask_editing_governance(tmp_path):
    args = {"TargetFile": str(tmp_path / "governance.yaml"), "CodeContent": "rules: {}"}
    assert json.loads(run_guard("antigravity", ag_payload(tmp_path, "write_to_file", args))[1])["decision"] == "ask"


# ------------------------------------------------------------------ installers

def test_install_claude_merges_existing_settings(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    other_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "./my-hook.sh"}]}
    settings.write_text(json.dumps({"model": "opus", "hooks": {"PreToolUse": [other_hook]}}), encoding="utf-8")

    install_claude(tmp_path)
    install_claude(tmp_path)  # idempotent

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "opus"
    groups = data["hooks"]["PreToolUse"]
    assert other_hook in groups
    assert sum("harness guard" in h["command"] for g in groups for h in g["hooks"]) == 1
    assert claude_installed(tmp_path)


def test_install_antigravity_merges_existing_hooks(tmp_path):
    hooks = tmp_path / ".agents" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(json.dumps({"my-linter": {"PostToolUse": []}}), encoding="utf-8")

    install_antigravity(tmp_path)

    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert "my-linter" in data and "mpharness-guard" in data
    assert antigravity_installed(tmp_path)
