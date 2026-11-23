"""`harness doctor`: a plain-language health check of every protection layer, with a live self-test."""
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .github import DEPENDABOT_PATH, WORKFLOW_PATH, ruleset_active
from .githooks import git_hooks_installed
from .governance import GOVERNANCE_FILE, load_policy
from .installers import AGENT_CONFIG, AGENT_LABELS, GUARD_STATES
from .planners import PLANNER_SETUP, is_installed
from .policy import DENY, Action, evaluate
from .scaffold import GITIGNORE_ENTRIES, legacy_files
from .util import git, install_command, is_git_repo
from .verify import check_tracked_secret_files

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class Check:
    status: str
    title: str
    fix: str = ""


def _guard_self_test(root):
    """Run the real guard command the way Claude Code does, and expect it to block a force push."""
    exe = shutil.which("harness")
    if exe is None:
        return False
    payload = {"tool_name": "Bash", "tool_input": {"command": "git push --force"}, "cwd": str(root)}
    try:
        res = subprocess.run([exe, "guard", "--agent", "claude"], input=json.dumps(payload), capture_output=True,
                             text=True, timeout=30, env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
        return json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return False


def run(start):
    policy = load_policy(start)
    root = policy.root
    checks = []

    checks.append(Check(OK, "MPHarness is installed") if shutil.which("harness") else
                  Check(FAIL, "'harness' is not on PATH, so the AI guards block everything",
                        f"Install it: {install_command()}"))

    if not policy.found:
        checks.append(Check(FAIL, "governance.yaml is missing", "Run: harness init"))
    elif policy.error:
        checks.append(Check(FAIL, f"governance.yaml has an error: {policy.error}", "Fix the file, then run harness doctor"))
    else:
        checks.append(Check(OK, f"governance.yaml found (planner: {policy.planner})"))

    for agent in policy.agents:
        state_fn = GUARD_STATES.get(agent)
        if state_fn is None:
            checks.append(Check(WARN, f"Unknown agent '{agent}' in governance.yaml"))
        elif state_fn(root) == "ok":
            checks.append(Check(OK, f"{AGENT_LABELS[agent]} guard is active ({AGENT_CONFIG[agent]})"))
        else:
            checks.append(Check(FAIL, f"{AGENT_LABELS[agent]} guard is missing or disabled", "Run: harness init"))

    if policy.found and not policy.error:
        blocked = evaluate(Action("command", command="git push --force"), policy, branch="feat/doctor").verdict == DENY
        live = _guard_self_test(root)
        checks.append(Check(OK, "Self-test: a forced push by the AI is blocked") if blocked and live else
                      Check(FAIL, "Self-test failed: the guard did not block a forced push",
                            "Check that block_force_push is true and that 'harness' runs from a terminal"))

    if not is_git_repo(root):
        checks.append(Check(FAIL, "This folder is not a git repository", "Run: git init -b main, then harness init"))
    else:
        custom = git(["config", "--get", "core.hooksPath"], root)
        if git_hooks_installed(root):
            checks.append(Check(OK, "Git hooks run MPHarness before each commit and push"))
        elif custom:
            checks.append(Check(WARN, f"Git hooks are managed elsewhere (core.hooksPath={custom})",
                                "Add 'harness verify --stage pre-commit' and '--stage pre-push' to that hook manager"))
        else:
            checks.append(Check(FAIL, "Git hooks are not installed", "Run: harness init"))

        tracked = check_tracked_secret_files(root)
        checks.append(Check(OK, "No secret files are tracked by git") if not tracked else
                      Check(FAIL, f"{len(tracked)} secret file(s) tracked by git", tracked[0].message))

    checks.append(Check(OK, "Gitleaks is installed (full secret scanning)") if shutil.which("gitleaks") else
                  Check(WARN, "Gitleaks is not installed (only basic secret checks run locally)",
                        "Install it: winget install Gitleaks.Gitleaks  (macOS: brew install gitleaks)"))

    gitignore = Path(root) / ".gitignore"
    present = set(gitignore.read_text(encoding="utf-8").splitlines()) if gitignore.exists() else set()
    missing = [e for e in GITIGNORE_ENTRIES if e not in present]
    checks.append(Check(OK, ".gitignore keeps secrets out of git") if not missing else
                  Check(WARN, f".gitignore is missing {len(missing)} secret entries", "Run: harness update"))

    for rel, label in ((WORKFLOW_PATH, "GitHub check workflow"), (DEPENDABOT_PATH, "Dependabot config")):
        checks.append(Check(OK, f"{label} present ({rel})") if (Path(root) / rel).exists() else
                      Check(WARN, f"{label} missing", "Run: harness update"))

    if not policy.repository:
        checks.append(Check(WARN, "No GitHub repository set in governance.yaml",
                            "Create the repo on GitHub, set project.repository (owner/name), then run: harness github apply"))
    else:
        active = ruleset_active(root, policy.repository)
        if active is True:
            checks.append(Check(OK, f"GitHub protection is active on {policy.repository}"))
        elif active is False:
            checks.append(Check(WARN, f"GitHub protection is not applied on {policy.repository}", "Run: harness github apply"))
        else:
            fix = ("Check that the repository exists and run 'gh auth login', then: harness github apply"
                   if shutil.which("gh") else
                   "Install the GitHub CLI (https://cli.github.com), run 'gh auth login', then: harness github apply")
            checks.append(Check(WARN, f"Could not check GitHub protection on {policy.repository}", fix))

    if policy.planner in PLANNER_SETUP and not is_installed(policy.planner):
        checks.append(Check(WARN, f"Planner '{policy.planner}' is not installed", "Run: harness planner setup"))

    legacy = legacy_files(root)
    if legacy:
        checks.append(Check(WARN, f"Old MPHarness files found: {', '.join(legacy)}", "Run: harness init  (moves them to .harness/legacy/)"))

    return checks
