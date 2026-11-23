"""`harness verify`: the checks shared by git hooks (pre-commit, pre-push) and CI.

Each check returns Findings with a plain-language problem and how to fix it.
"""
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .governance import load_policy
from .installers import AGENT_CONFIG, AGENT_LABELS, GUARD_STATES
from .messages import msg
from .policy import current_branch, is_secret_file
from .secrets_scan import find_secret
from .util import git, git_ok, run_tool

ERROR, WARNING = "error", "warning"
ZERO_SHA = "0" * 40

# Generated files where long random strings are normal and secrets are not expected.
SCAN_SKIP = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock", "Cargo.lock",
             "composer.lock", "Gemfile.lock", "go.sum", "packages.lock.json")
MAX_SCAN_BYTES = 1_000_000


@dataclass
class Finding:
    level: str
    message: str


# ------------------------------------------------------------------ shared checks

def check_governance_file(policy):
    if not policy.found:
        return [Finding(WARNING, "governance.yaml is missing, so strict default rules are used. Run 'harness init' to create it.")]
    if policy.error:
        return [Finding(ERROR, msg("invalid_governance", detail=policy.error))]
    return []


def check_tracked_secret_files(root):
    listed = git(["ls-files", "-z"], root)
    if not listed:
        return []
    findings = []
    for name in listed.split("\0"):
        if name and is_secret_file(PurePosixPath(name)):
            findings.append(Finding(ERROR, msg("tracked_secret_file", path=name)))
    return findings


def check_agent_guards(root, policy):
    """Detect guard hooks that were removed or disabled (e.g. by an AI editing its own settings)."""
    findings = []
    for agent in policy.agents:
        state_fn = GUARD_STATES.get(agent)
        if state_fn is None:
            findings.append(Finding(WARNING, f"Unknown agent '{agent}' in governance.yaml (supported: {', '.join(GUARD_STATES)})."))
            continue
        if state_fn(root) != "ok":
            findings.append(Finding(ERROR, f"The {AGENT_LABELS[agent]} guard ({AGENT_CONFIG[agent]}) is missing or disabled. "
                                           "Restore it with 'harness init'."))
    return findings


# ------------------------------------------------------------------ secret scanning

def _gitleaks():
    return shutil.which("gitleaks")


def _gitleaks_supports_git_subcommand(exe):
    res = run_tool([exe, "version"], cwd=".")
    match = re.search(r"(\d+)\.(\d+)", res.stdout or "")
    return bool(match) and (int(match.group(1)), int(match.group(2))) >= (8, 19)


def _run_gitleaks(root, staged):
    exe = _gitleaks()
    if exe is None:
        return None
    if _gitleaks_supports_git_subcommand(exe):
        args = [exe, "git", "--redact", "--no-banner", "--exit-code", "1"] + (["--staged"] if staged else [])
    else:
        args = [exe, "protect", "--staged", "--redact"] if staged else [exe, "detect", "--redact"]
    res = run_tool(args, cwd=root)
    if res.returncode == 0:
        return []
    report = "\n".join(line for line in (res.stdout + res.stderr).splitlines() if line.strip())[-3000:]
    return [Finding(ERROR, "Gitleaks found secrets:\n" + report +
                    "\nRemove them, move them to .env, and rotate (replace) any real key that was exposed.")]


def _scan_added_lines(diff_text):
    findings, current = [], None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            continue
        if not current or not line.startswith("+") or current.endswith(SCAN_SKIP):
            continue
        if is_secret_file(PurePosixPath(current)):
            continue
        kind = find_secret(line[1:])
        if kind:
            findings.append(Finding(ERROR, msg("secret_in_content", kind=f"{kind} in {current}")))
    return findings


def scan_staged(root):
    findings = _run_gitleaks(root, staged=True)
    builtin = _scan_added_lines(git(["diff", "--cached", "-U0", "--diff-filter=ACMR"], root) or "")
    if findings is None:
        return builtin + [Finding(WARNING, "Gitleaks is not installed, so only the basic secret check ran. "
                                           "Install it for full coverage: winget install Gitleaks.Gitleaks  (or: brew install gitleaks)")]
    return findings or builtin


def scan_repository(root):
    findings = _run_gitleaks(root, staged=False)
    if findings is not None:
        return findings
    builtin = []
    for name in (git(["ls-files", "-z"], root) or "").split("\0"):
        path = Path(root) / name
        if not name or name.endswith(SCAN_SKIP) or is_secret_file(PurePosixPath(name)) or not path.is_file():
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            continue
        kind = find_secret(path.read_text(encoding="utf-8", errors="ignore"))
        if kind:
            builtin.append(Finding(ERROR, msg("secret_in_content", kind=f"{kind} in {name}")))
    return builtin + [Finding(WARNING, "Gitleaks is not installed, so only the basic secret check ran.")]


# ------------------------------------------------------------------ stages

def verify_pre_commit(root, policy):
    findings = check_governance_file(policy)
    branch = current_branch(root)
    if policy.rule("block_commits_to_protected") and branch in policy.protected_branches:
        findings.append(Finding(ERROR, msg("commit_protected", branch=branch)))
    findings += check_tracked_secret_files(root)
    if policy.rule("block_secrets_in_code"):
        findings += scan_staged(root)
    return findings


def verify_pre_push(root, policy, refs_text):
    findings = []
    protected = set(policy.protected_branches)
    for line in refs_text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts
        branch = remote_ref.removeprefix("refs/heads/")
        creating, deleting = remote_sha == ZERO_SHA, local_sha == ZERO_SHA

        if branch in protected and policy.rule("block_commits_to_protected"):
            if deleting:
                findings.append(Finding(ERROR, f"Blocked: deleting the protected branch '{branch}' is not allowed."))
            elif not creating:
                # Creating the branch is allowed so a brand-new repository can publish main once.
                findings.append(Finding(ERROR, msg("push_protected", branch=branch)))

        if policy.rule("block_force_push") and not creating and not deleting:
            if git_ok(["cat-file", "-e", remote_sha], root) and not git_ok(["merge-base", "--is-ancestor", remote_sha, local_sha], root):
                findings.append(Finding(ERROR, msg("force_push")))
    return findings


def verify_ci(root, policy):
    findings = check_governance_file(policy)
    findings += check_tracked_secret_files(root)
    findings += check_agent_guards(root, policy)
    if policy.rule("block_secrets_in_code"):
        findings += scan_repository(root)
    return findings


def run(stage, start, refs_text=""):
    policy = load_policy(start)
    root = policy.root
    if stage == "pre-commit":
        return verify_pre_commit(root, policy)
    if stage == "pre-push":
        return verify_pre_push(root, policy, refs_text)
    return verify_ci(root, policy)
