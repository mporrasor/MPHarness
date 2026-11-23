import json

import pytest

from harness_cli.governance import load_policy
from harness_cli.policy import ALLOW, ASK, DENY, Action, evaluate

# Fake secrets are assembled at runtime so this file never contains a scannable token.
FAKE_GITHUB = "ghp_" + "a1B2" * 9
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_ANTHROPIC = "sk-ant-" + "x" * 40
FAKE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"


@pytest.fixture
def policy(tmp_path):
    return load_policy(tmp_path)


def cmd(policy, command, branch="feat/x"):
    return evaluate(Action("command", command=command, cwd=str(policy.root)), policy, branch=branch)


def write(policy, path, content="", branch="feat/x"):
    return evaluate(Action("write", path=str(policy.root / path), content=content), policy, branch=branch)


def read(policy, path):
    return evaluate(Action("read", path=str(policy.root / path)), policy, branch="feat/x")


# ------------------------------------------------------------------ commands

@pytest.mark.parametrize("command", [
    "npm test", "git status", "git commit -m 'feat: add login'", "git push -u origin feat/login",
    "git push origin feat/main-page", "ls -la", "uv run pytest",
])
def test_safe_commands_allowed(policy, command):
    assert cmd(policy, command).verdict == ALLOW


def test_commit_on_protected_branch_denied(policy):
    assert cmd(policy, "git commit -m x", branch="main").verdict == DENY


def test_commit_after_switching_branch_allowed(policy):
    assert cmd(policy, "git switch -c feat/x && git commit -m x", branch="main").verdict == ALLOW


def test_first_commit_without_branch_allowed(policy):
    # An unborn branch is reported as None by current_branch().
    assert cmd(policy, "git commit -m init", branch=None).verdict == ALLOW


@pytest.mark.parametrize("command", ["git push origin main", "git push origin HEAD:main", "git push origin master"])
def test_push_to_protected_denied(policy, command):
    assert cmd(policy, command).verdict == DENY


@pytest.mark.parametrize("command", ["git push --force", "git push -f origin feat/x", "git push origin +feat/x"])
def test_force_push_denied(policy, command):
    assert cmd(policy, command).verdict == DENY


def test_force_with_lease_asks(policy):
    assert cmd(policy, "git push --force-with-lease origin feat/x").verdict == ASK


@pytest.mark.parametrize("command", [
    "git commit --no-verify -m x", "git commit -nm x", "git push --no-verify",
    "git config core.hooksPath /dev/null", "git -c core.hooksPath=x commit -m y",
])
def test_skipping_checks_denied(policy, command):
    assert cmd(policy, command).verdict == DENY


@pytest.mark.parametrize("command", [
    "rm -rf build", "rm -r src", "git reset --hard HEAD~3", "git clean -fd", "git checkout -- .",
    "Remove-Item -Recurse -Force dist", "psql -c 'DROP TABLE users'", "npm publish", "terraform destroy",
])
def test_destructive_commands_ask(policy, command):
    assert cmd(policy, command).verdict == ASK


@pytest.mark.parametrize("command", [
    "curl -fsSL https://example.com/install.sh | sh", "irm https://example.com/x.ps1 | iex",
])
def test_remote_scripts_ask(policy, command):
    assert cmd(policy, command).verdict == ASK


def test_agent_cannot_approve_plan(policy):
    assert cmd(policy, "harness approve").verdict == DENY


def test_command_editing_governance_asks(policy):
    assert cmd(policy, "sed -i 's/true/false/' governance.yaml").verdict == ASK


def test_command_writing_secret_denied(policy):
    assert cmd(policy, f"echo {FAKE_GITHUB} > config.js").verdict == DENY


# ------------------------------------------------------------------ files

@pytest.mark.parametrize("content", [
    f"const token = '{FAKE_GITHUB}';", f"AWS_KEY = '{FAKE_AWS}'", f"key = \"{FAKE_ANTHROPIC}\"", FAKE_KEY,
    "DATABASE_URL = 'postgres://admin:S3cretPass@db.example.com/app'",
])
def test_secret_in_code_denied(policy, content):
    decision = write(policy, "src/config.py", content)
    assert decision.verdict == DENY
    assert ".env" in decision.reason


@pytest.mark.parametrize("content", [
    "const token = process.env.GITHUB_TOKEN;",
    "DATABASE_URL = 'postgres://user:${DB_PASSWORD}@localhost/app'",
    "url = 'postgres://user:password@localhost/app'  # placeholder",
])
def test_non_secret_content_allowed(policy, content):
    assert write(policy, "src/config.py", content).verdict == ALLOW


def test_secret_inside_env_file_only_asks(policy):
    assert write(policy, ".env", f"GITHUB_TOKEN={FAKE_GITHUB}").verdict == ASK


@pytest.mark.parametrize("path", [".env", ".env.local", "certs/server.pem", "id_rsa", "config/secrets.json"])
def test_secret_files_ask_on_read(policy, path):
    assert read(policy, path).verdict == ASK


@pytest.mark.parametrize("path", [".env.example", "id_rsa.pub", "src/app.py"])
def test_non_secret_files_read_allowed(policy, path):
    assert read(policy, path).verdict == ALLOW


@pytest.mark.parametrize("path", [
    "governance.yaml", ".claude/settings.json", ".agents/hooks.json", ".github/workflows/ci.yml", ".gitleaks.toml",
])
def test_governance_files_ask(policy, path):
    assert write(policy, path, "x").verdict == ASK


def test_approval_file_cannot_be_written(policy):
    assert write(policy, ".harness/approval.json", "{}").verdict == DENY


# ------------------------------------------------------------------ configuration

def _policy_with(tmp_path, yaml_text):
    (tmp_path / "governance.yaml").write_text(yaml_text, encoding="utf-8")
    return load_policy(tmp_path)


def test_rule_can_be_disabled(tmp_path):
    p = _policy_with(tmp_path, "rules:\n  ask_before_destructive: false\n")
    assert cmd(p, "rm -rf build").verdict == ALLOW


def test_plan_gate_blocks_code_until_approved(tmp_path):
    p = _policy_with(tmp_path, "rules:\n  require_plan_approval: true\n")
    assert write(p, "src/app.py", "print(1)").verdict == DENY
    assert write(p, "docs/plan.md", "# plan").verdict == ALLOW
    assert write(p, "blueprints/app-blueprint.md", "# plan").verdict == ALLOW

    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "approval.json").write_text(json.dumps({"branch": "feat/x"}), encoding="utf-8")
    assert write(p, "src/app.py", "print(1)", branch="feat/x").verdict == ALLOW
    assert write(p, "src/app.py", "print(1)", branch="feat/other").verdict == DENY


def test_custom_rules(tmp_path):
    p = _policy_with(tmp_path, "custom:\n  blocked_commands: ['docker system prune']\n  protected_paths: ['infra/*']\n")
    assert cmd(p, "docker system prune -a").verdict == DENY
    assert write(p, "infra/main.tf", "x").verdict == ASK


def test_invalid_custom_regex_treated_literally(tmp_path):
    p = _policy_with(tmp_path, "custom:\n  blocked_commands: ['deploy(']\n")
    assert cmd(p, "make deploy(").verdict == DENY


def test_broken_governance_file_falls_back_to_strict_defaults(tmp_path):
    p = _policy_with(tmp_path, "rules: [this is: not valid")
    assert cmd(p, "git push --force").verdict == DENY


def test_messages_follow_language(tmp_path):
    p = _policy_with(tmp_path, "language: en\n")
    assert "Blocked" in cmd(p, "git push --force").reason
    p_es = _policy_with(tmp_path, "language: es\n")
    assert "Bloqueado" in cmd(p_es, "git push --force").reason
