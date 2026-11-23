import json
import subprocess

import pytest

from harness_cli import github
from harness_cli.governance import load_policy


def test_dependabot_detects_ecosystems(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "App.csproj").write_text("", encoding="utf-8")
    assert github.detect_ecosystems(tmp_path) == ["npm", "uv", "nuget", "github-actions"]


def test_dependabot_always_watches_actions(tmp_path):
    text = github.render_dependabot(tmp_path)
    assert 'package-ecosystem: "github-actions"' in text and "Managed by MPHarness" in text


def test_workflow_pins_harness_and_protected_branches(tmp_path):
    (tmp_path / "governance.yaml").write_text("branches:\n  protected: [main, release]\n", encoding="utf-8")
    text = github.render_workflow(load_policy(tmp_path))
    assert "branches: [main, release]" in text
    assert "MPHarness@v" in text and "@main" not in text
    assert "name: mpharness" in text and "harness verify --stage ci" in text


def test_ruleset_payload():
    payload = github.ruleset_payload(["main", "master"])
    assert payload["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH", "refs/heads/main", "refs/heads/master"]
    types = [rule["type"] for rule in payload["rules"]]
    assert types == ["deletion", "non_fast_forward", "pull_request", "required_status_checks"]
    checks = payload["rules"][3]["parameters"]["required_status_checks"]
    assert checks == [{"context": "mpharness"}]
    assert payload["bypass_actors"] == []


class FakeGh:
    """Records gh calls and answers like the real API."""

    def __init__(self, fail=()):
        self.calls, self.fail = [], fail

    def __call__(self, args, cwd, capture=True, input_text=None, timeout=None):
        self.calls.append((args, json.loads(input_text) if input_text else None))
        joined = " ".join(args)
        if any(f in joined for f in self.fail):
            return subprocess.CompletedProcess(args, 1, "", "HTTP 403: Upgrade to GitHub Pro or make this repository public")
        if args[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if joined.endswith("/rulesets") and "-X" not in args:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        return subprocess.CompletedProcess(args, 0, json.dumps({"default_branch": "main"}), "")


@pytest.fixture
def policy(tmp_path):
    (tmp_path / "governance.yaml").write_text('project:\n  repository: "me/app"\n', encoding="utf-8")
    return load_policy(tmp_path)


def test_apply_creates_ruleset_and_enables_security(policy, monkeypatch):
    fake = FakeGh()
    monkeypatch.setattr(github, "run_tool", fake)
    monkeypatch.setattr(github.shutil, "which", lambda name: "gh")
    steps = github.apply(policy.root, policy)
    assert all(step.status == "ok" for step in steps), steps
    posted = [payload for args, payload in fake.calls if "POST" in args]
    assert posted and posted[0]["name"] == github.RULESET_NAME
    patched = [payload for args, payload in fake.calls if "PATCH" in args]
    assert patched[0]["security_and_analysis"]["secret_scanning_push_protection"]["status"] == "enabled"


def test_apply_reports_plan_limits_in_plain_words(policy, monkeypatch):
    monkeypatch.setattr(github, "run_tool", FakeGh(fail=("PATCH",)))
    monkeypatch.setattr(github.shutil, "which", lambda name: "gh")
    steps = {s.name: s for s in github.apply(policy.root, policy)}
    secret = steps["Secret scanning + push protection"]
    assert secret.status == "failed" and "plan" in secret.detail and "Gitleaks" in secret.detail
    assert steps["Branch protection ruleset"].status == "ok"


def test_preflight_requires_repository(tmp_path):
    with pytest.raises(github.GitHubError, match="No repository set"):
        github.preflight(tmp_path, "")
