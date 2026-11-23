import json
import shutil

import pytest

from conftest import commit, git, rev
from harness_cli import verify
from harness_cli.installers import install_antigravity, install_claude

FAKE_GITHUB = "ghp_" + "a1B2" * 9
ZERO = "0" * 40


def errors(findings):
    return [f for f in findings if f.level == verify.ERROR]


# ------------------------------------------------------------------ pre-commit

def test_first_commit_on_unborn_main_allowed(repo, no_gitleaks):
    (repo / "app.py").write_text("print(1)", encoding="utf-8")
    git(repo, "add", "-A")
    assert errors(verify.run("pre-commit", repo)) == []


def test_commit_on_main_blocked_after_first_commit(repo, no_gitleaks):
    commit(repo, "init")
    found = errors(verify.run("pre-commit", repo))
    assert found and "main" in found[0].message


def test_commit_on_feature_branch_allowed(repo, no_gitleaks):
    commit(repo, "init")
    git(repo, "switch", "-q", "-c", "feat/x")
    (repo / "app.py").write_text("print(2)", encoding="utf-8")
    git(repo, "add", "-A")
    assert errors(verify.run("pre-commit", repo)) == []


def test_staged_secret_blocked(repo, no_gitleaks):
    commit(repo, "init")
    git(repo, "switch", "-q", "-c", "feat/x")
    (repo / "config.js").write_text(f"const token = '{FAKE_GITHUB}';\n", encoding="utf-8")
    git(repo, "add", "-A")
    found = errors(verify.run("pre-commit", repo))
    assert any("config.js" in f.message for f in found)


def test_staged_env_file_blocked(repo, no_gitleaks):
    commit(repo, "init")
    git(repo, "switch", "-q", "-c", "feat/x")
    (repo / ".env").write_text("API_KEY=abc\n", encoding="utf-8")
    git(repo, "add", "-f", ".env")
    found = errors(verify.run("pre-commit", repo))
    assert any(".env" in f.message and "git rm --cached" in f.message for f in found)


def test_missing_gitleaks_is_a_warning_not_an_error(repo, no_gitleaks):
    git(repo, "switch", "-q", "-c", "feat/x")
    findings = verify.run("pre-commit", repo)
    assert any(f.level == verify.WARNING and "Gitleaks" in f.message for f in findings)


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks not installed")
def test_gitleaks_blocks_staged_secret(repo):
    commit(repo, "init")
    git(repo, "switch", "-q", "-c", "feat/x")
    aws = "AKIA" + "QYLPMN5HHHFPZAM2"
    (repo / "deploy.py").write_text(f"aws_access_key_id = '{aws}'\n", encoding="utf-8")
    git(repo, "add", "-A")
    assert errors(verify.run("pre-commit", repo))


# ------------------------------------------------------------------ pre-push

def test_push_updating_main_blocked(repo):
    commit(repo, "one")
    old = rev(repo)
    commit(repo, "two")
    refs = f"refs/heads/main {rev(repo)} refs/heads/main {old}\n"
    assert errors(verify.run("pre-push", repo, refs))


def test_first_push_creating_main_allowed(repo):
    commit(repo, "one")
    refs = f"refs/heads/main {rev(repo)} refs/heads/main {ZERO}\n"
    assert errors(verify.run("pre-push", repo, refs)) == []


def test_deleting_main_blocked(repo):
    commit(repo, "one")
    refs = f"(delete) {ZERO} refs/heads/main {rev(repo)}\n"
    assert errors(verify.run("pre-push", repo, refs))


def test_force_push_to_feature_branch_blocked(repo):
    commit(repo, "base")
    git(repo, "switch", "-q", "-c", "feat/x")
    commit(repo, "remote-version")
    remote = rev(repo)
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "rewritten")
    refs = f"refs/heads/feat/x {rev(repo)} refs/heads/feat/x {remote}\n"
    found = errors(verify.run("pre-push", repo, refs))
    assert any("--force" in f.message for f in found)


def test_normal_push_to_feature_branch_allowed(repo):
    commit(repo, "base")
    git(repo, "switch", "-q", "-c", "feat/x")
    old = rev(repo)
    commit(repo, "more")
    refs = f"refs/heads/feat/x {rev(repo)} refs/heads/feat/x {old}\n"
    assert errors(verify.run("pre-push", repo, refs)) == []


# ------------------------------------------------------------------ ci

def test_ci_passes_with_guards(repo, no_gitleaks):
    install_claude(repo)
    install_antigravity(repo)
    commit(repo, "init")
    assert errors(verify.run("ci", repo)) == []


def test_ci_fails_when_guard_disabled(repo, no_gitleaks):
    install_claude(repo)
    install_antigravity(repo)
    settings = repo / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["disableAllHooks"] = True
    settings.write_text(json.dumps(data), encoding="utf-8")
    commit(repo, "init")
    found = errors(verify.run("ci", repo))
    assert any("Claude Code guard" in f.message for f in found)


def test_ci_only_checks_agents_listed_in_governance(repo, no_gitleaks):
    (repo / "governance.yaml").write_text("agents: [antigravity]\n", encoding="utf-8")
    install_antigravity(repo)
    commit(repo, "init")
    assert errors(verify.run("ci", repo)) == []


def test_ci_detects_committed_secret(repo, no_gitleaks):
    install_claude(repo)
    install_antigravity(repo)
    commit(repo, "init", {"src/settings.py": f"TOKEN = '{FAKE_GITHUB}'\n"})
    assert any("src/settings.py" in f.message for f in errors(verify.run("ci", repo)))


def test_invalid_governance_is_an_error(repo, no_gitleaks):
    (repo / "governance.yaml").write_text("rules: [broken", encoding="utf-8")
    assert any("governance.yaml" in f.message for f in errors(verify.run("ci", repo)))
