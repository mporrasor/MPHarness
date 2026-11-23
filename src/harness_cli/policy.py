"""The policy engine: decides whether an AI agent action is allowed, needs confirmation, or is denied.

Agent adapters (Claude Code, Antigravity) translate their tool calls into an `Action`,
and git hooks / CI reuse the same rules, so every layer enforces one policy.
"""
import fnmatch
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .governance import (
    APPROVAL_FILE,
    GOVERNANCE_PATHS,
    NON_CODE_PATTERNS,
    SECRET_FILE_EXCEPTIONS,
    SECRET_FILE_PATTERNS,
    Policy,
)
from .messages import msg
from .secrets_scan import find_secret

ALLOW, ASK, DENY = "allow", "ask", "deny"
_SEVERITY = {ALLOW: 0, ASK: 1, DENY: 2}

# A command "segment" stops at shell separators so a rule never spans two commands.
_SEG = r"[^|;&\n]"


@dataclass
class Action:
    kind: str                     # "command" | "write" | "read"
    command: str = ""
    path: str = ""
    content: str = ""
    cwd: str = ""


@dataclass
class Decision:
    verdict: str = ALLOW
    reasons: list = field(default_factory=list)

    def add(self, verdict, reason):
        if _SEVERITY[verdict] > _SEVERITY[self.verdict]:
            self.verdict = verdict
        if verdict != ALLOW:
            self.reasons.append(reason)

    @property
    def reason(self):
        return " ".join(self.reasons)


def current_branch(root):
    if shutil.which("git") is None or not Path(root).is_dir():
        return None
    try:
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    branch = res.stdout.strip()
    # "HEAD" means detached or an unborn branch (no commits yet): not a protected-branch commit.
    return branch if res.returncode == 0 and branch != "HEAD" else None


def _relative(path, root):
    p = Path(path)
    if not p.is_absolute():
        p = Path(root) / p
    try:
        rel = p.resolve().relative_to(Path(root).resolve())
        return PurePosixPath(rel.as_posix())
    except ValueError:
        return PurePosixPath(p.as_posix())


def _matches(rel, patterns):
    text, name = str(rel), rel.name
    for pattern in patterns:
        target = text if "/" in pattern else name
        if fnmatch.fnmatch(target, pattern) or (pattern.endswith("/*") and text.startswith(pattern[:-1])):
            return True
    return False


def is_secret_file(rel):
    return _matches(rel, SECRET_FILE_PATTERNS) and not _matches(rel, SECRET_FILE_EXCEPTIONS)


def _plan_approved(root, branch):
    path = Path(root) / APPROVAL_FILE
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data.get("branch") in (None, branch)


def evaluate(action, policy: Policy, branch=None):
    """Evaluate an action. `branch` overrides the detected git branch (used by tests)."""
    decision = Decision()
    if branch is None:
        cwd = action.cwd if action.cwd and Path(action.cwd).is_dir() else policy.root
        branch = current_branch(cwd)

    if action.kind == "command":
        _check_command(action.command, policy, branch, decision)
    elif action.kind in ("write", "read"):
        _check_file(action, policy, branch, decision)
    return decision


def _check_file(action, policy, branch, decision):
    rel = _relative(action.path, policy.root)
    secret_file = is_secret_file(rel)

    if policy.rule("protect_secret_files") and secret_file:
        decision.add(ASK, msg("secret_file", path=rel))

    if action.kind == "read":
        return

    if str(rel) == APPROVAL_FILE:
        decision.add(DENY, msg("approval_tamper"))
        return

    if policy.rule("protect_governance_files") and _matches(rel, GOVERNANCE_PATHS):
        decision.add(ASK, msg("governance_file", path=rel))

    if policy.custom_protected_paths and _matches(rel, policy.custom_protected_paths):
        decision.add(ASK, msg("custom_protected", path=rel))

    # Secrets are expected inside .env-style files (git-ignored); everywhere else they are a leak.
    if policy.rule("block_secrets_in_code") and not secret_file:
        kind = find_secret(action.content)
        if kind:
            decision.add(DENY, msg("secret_in_content", kind=kind))

    if policy.rule("require_plan_approval") and not _matches(rel, NON_CODE_PATTERNS):
        if not _plan_approved(policy.root, branch):
            decision.add(DENY, msg("plan_not_approved"))


_GIT = r"\bgit\b(?:\s+-[cC]\s+\S+)*"
_DESTRUCTIVE = [
    (r"\brm\s+(?:-\S*[rR]\S*|--recursive)\b", "rm -r"),
    (r"\bRemove-Item\b" + _SEG + r"*-Recurse", "Remove-Item -Recurse"),
    (r"\b(?:rd|rmdir)\s+/s\b", "rmdir /s"),
    (_GIT + r"\s+reset\s+" + _SEG + r"*--hard\b", "git reset --hard"),
    (_GIT + r"\s+clean\s+-\S*f", "git clean -f"),
    (_GIT + r"\s+(?:checkout|restore)\s+(?:--\s+)?\.(?:\s|$)", "discard all local changes"),
    (_GIT + r"\s+branch\s+" + _SEG + r"*-D\b", "git branch -D"),
    (r"(?i)\bdrop\s+(?:database|table|schema)\b", "DROP"),
    (r"(?i)\btruncate\s+table\b", "TRUNCATE"),
    (r"\b(?:npm|pnpm|yarn)\s+publish\b", "publish package"),
    (r"\bgh\s+repo\s+delete\b", "gh repo delete"),
    (r"\bterraform\s+destroy\b", "terraform destroy"),
    (r"\bdocker\s+(?:system|volume)\s+prune\b", "docker prune"),
]
_REMOTE_SCRIPT = re.compile(
    r"(?i)\b(?:curl|wget|iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^|;&\n]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh|python3?|iex|Invoke-Expression)\b")
_WRITE_OPS = re.compile(r"(?:>|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item)")


def _check_command(command, policy, branch, decision):
    if not command:
        return

    if re.search(r"\bharness\s+approve\b", command) or ("approval.json" in command and _WRITE_OPS.search(command)):
        decision.add(DENY, msg("approval_tamper"))

    if policy.rule("block_skipping_checks"):
        if re.search(_GIT + _SEG + r"*\b(?:commit|push|merge|rebase|am)\b" + _SEG + r"*\s--no-verify\b", command):
            decision.add(DENY, msg("skip_checks", detail="--no-verify"))
        elif re.search(_GIT + _SEG + r"*\bcommit\b" + _SEG + r"*\s-[a-zA-Z]*n[a-zA-Z]*\b", command):
            decision.add(DENY, msg("skip_checks", detail="git commit -n"))
        if re.search(r"core\.hooksPath", command):
            decision.add(DENY, msg("skip_checks", detail="core.hooksPath"))

    if policy.rule("block_force_push"):
        push = re.search(_GIT + r"\s+push\b(" + _SEG + r"*)", command)
        if push:
            args = push.group(1)
            if re.search(r"\s--force(?!-with-lease|-if-includes)\b|\s-[a-zA-Z]*f[a-zA-Z]*\b|\s\+\S+", args):
                decision.add(DENY, msg("force_push"))
            elif "--force-with-lease" in args:
                decision.add(ASK, msg("force_with_lease"))

    protected = policy.protected_branches
    if policy.rule("block_commits_to_protected") and protected:
        names = "|".join(re.escape(b) for b in protected)
        target = re.search(_GIT + r"\s+push\b" + _SEG + r"*?[\s:](?:refs/heads/)?(" + names + r")(?=\s|$)", command)
        if target:
            decision.add(DENY, msg("push_protected", branch=target.group(1)))
        if branch in protected and re.search(_GIT + r"\s+commit\b", command):
            # Allow "git switch -c feat/x && git commit": the commit lands on the new branch.
            switches = re.search(_GIT + r"\s+(?:switch\s+-[cC]|checkout\s+-[bB])\s+\S+", command)
            commit_pos = re.search(_GIT + r"\s+commit\b", command).start()
            if not (switches and switches.start() < commit_pos):
                decision.add(DENY, msg("commit_protected", branch=branch))

    if policy.rule("ask_before_destructive"):
        for pattern, label in _DESTRUCTIVE:
            if re.search(pattern, command):
                decision.add(ASK, msg("destructive", detail=label))
                break

    if policy.rule("ask_before_remote_scripts") and _REMOTE_SCRIPT.search(command):
        decision.add(ASK, msg("remote_script"))

    if policy.rule("protect_governance_files") and _WRITE_OPS.search(command):
        for path in ["governance.yaml", ".claude/settings", ".agents/hooks.json", ".github/workflows", ".git/hooks", ".gitleaks.toml"]:
            if path in command.replace("\\", "/"):
                decision.add(ASK, msg("governance_file", path=path))
                break

    if policy.rule("block_secrets_in_code"):
        kind = find_secret(command)
        if kind and re.search(r"(?:>|\btee\b|Set-Content|Add-Content|Out-File|\bgit\s+commit\b)", command):
            decision.add(DENY, msg("secret_in_content", kind=kind))

    for pattern in policy.custom_blocked_commands:
        try:
            if re.search(pattern, command):
                decision.add(DENY, msg("custom_blocked", pattern=pattern))
        except re.error:
            # Treat an invalid regex as a literal string so a typo never disables the rule.
            if pattern in command:
                decision.add(DENY, msg("custom_blocked", pattern=pattern))
