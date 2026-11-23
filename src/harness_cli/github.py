"""GitHub layer: CI workflow, Dependabot config, and server-side protection applied with the `gh` CLI."""
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .util import TEMPLATES, harness_ref, run_tool

WORKFLOW_PATH = ".github/workflows/mpharness.yml"
DEPENDABOT_PATH = ".github/dependabot.yml"
RULESET_NAME = "MPHarness protection"
STATUS_CHECK = "mpharness"
GITLEAKS_VERSION = "8.21.2"

# (ecosystem, marker files), checked in the repository root.
ECOSYSTEMS = [
    ("npm", ["package.json"]),
    ("uv", ["uv.lock"]),
    ("pip", ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]),
    ("nuget", ["*.csproj", "*.sln", "packages.config"]),
    ("docker", ["Dockerfile"]),
    ("gomod", ["go.mod"]),
    ("cargo", ["Cargo.toml"]),
    ("composer", ["composer.json"]),
    ("maven", ["pom.xml"]),
    ("gradle", ["build.gradle", "build.gradle.kts"]),
    ("bundler", ["Gemfile"]),
]


# ------------------------------------------------------------------ files in the repository

def render_workflow(policy):
    template = (TEMPLATES / "github" / "mpharness.yml").read_text(encoding="utf-8")
    return (template.replace("__HARNESS_REF__", harness_ref())
                    .replace("__GITLEAKS__", GITLEAKS_VERSION)
                    .replace("__PROTECTED__", ", ".join(policy.protected_branches)))


def detect_ecosystems(root):
    root = Path(root)
    found = []
    for ecosystem, markers in ECOSYSTEMS:
        if any(list(root.glob(marker)) for marker in markers):
            if ecosystem == "pip" and "uv" in found:
                continue  # uv projects are handled by the uv ecosystem
            found.append(ecosystem)
    found.append("github-actions")
    return found


def render_dependabot(root):
    lines = [
        "# Managed by MPHarness. Regenerate with: harness update",
        "# Dependabot opens Pull Requests to update dependencies and fix known vulnerabilities.",
        "# Each PR runs the MPHarness checks and your tests before you merge it.",
        "version: 2",
        "updates:",
    ]
    for ecosystem in detect_ecosystems(root):
        lines += [
            f'  - package-ecosystem: "{ecosystem}"',
            '    directory: "/"',
            "    schedule:",
            '      interval: "weekly"',
            "    open-pull-requests-limit: 5",
        ]
    return "\n".join(lines) + "\n"


def github_files(root, policy):
    return {WORKFLOW_PATH: render_workflow(policy), DEPENDABOT_PATH: render_dependabot(root)}


# ------------------------------------------------------------------ server-side protection (gh CLI)

@dataclass
class Step:
    name: str
    status: str   # ok | skipped | failed | planned
    detail: str = ""


class GitHubError(Exception):
    pass


def _gh(args, root, payload=None):
    res = run_tool(["gh", *args], cwd=root, input_text=json.dumps(payload) if payload is not None else None)
    if res.returncode != 0:
        text = (res.stderr or res.stdout or "").strip() or "gh failed"
        raise GitHubError(text.splitlines()[-1])
    return json.loads(res.stdout) if res.stdout.strip() else {}


def _plain_error(text):
    lowered = text.lower()
    if "upgrade" in lowered or "advanced security" in lowered or "not available" in lowered or "403" in lowered:
        return "your GitHub plan does not include this for this repository (private repositories may need GitHub Pro / Team)"
    if "404" in lowered or "not found" in lowered:
        return "repository not found, or your account has no admin access to it"
    return text


def ruleset_payload(protected_branches):
    include = ["~DEFAULT_BRANCH"] + [f"refs/heads/{b}" for b in protected_branches]
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": include, "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": False,
            }},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": STATUS_CHECK}],
            }},
        ],
    }


def preflight(root, repository):
    if not repository:
        raise GitHubError("No repository set. Add it to governance.yaml (project.repository: owner/name).")
    if shutil.which("gh") is None:
        raise GitHubError("The GitHub CLI 'gh' is not installed. Get it from https://cli.github.com and run 'gh auth login'.")
    if run_tool(["gh", "auth", "status"], cwd=root).returncode != 0:
        raise GitHubError("You are not logged in to GitHub. Run 'gh auth login' first.")
    try:
        return _gh(["api", f"repos/{repository}"], root)
    except GitHubError as exc:
        raise GitHubError(f"Cannot access {repository}: {_plain_error(str(exc))}") from exc


def plan(policy):
    return [
        Step("Protect main: require Pull Requests, block force pushes and deletion", "planned"),
        Step(f"Require the '{STATUS_CHECK}' check (MPHarness CI) to pass before merging", "planned"),
        Step("Turn on Dependabot alerts and automatic security fixes", "planned"),
        Step("Turn on secret scanning and push protection (blocks pushes that contain secrets)", "planned"),
    ]


def apply(root, policy):
    """Apply server-side protection. Every step is independent so one unsupported feature does not stop the rest."""
    repository = policy.repository
    preflight(root, repository)
    steps = []

    payload = ruleset_payload(policy.protected_branches)
    try:
        existing = next((r for r in _gh(["api", f"repos/{repository}/rulesets"], root) or [] if r.get("name") == RULESET_NAME), None)
        if existing:
            _gh(["api", "-X", "PUT", f"repos/{repository}/rulesets/{existing['id']}", "--input", "-"], root, payload)
            steps.append(Step("Branch protection ruleset", "ok", "updated"))
        else:
            _gh(["api", "-X", "POST", f"repos/{repository}/rulesets", "--input", "-"], root, payload)
            steps.append(Step("Branch protection ruleset", "ok", "created"))
    except GitHubError as exc:
        steps.append(Step("Branch protection ruleset", "failed", _plain_error(str(exc))))

    for name, endpoint in (("Dependabot alerts", "vulnerability-alerts"),
                           ("Dependabot security fixes", "automated-security-fixes")):
        try:
            _gh(["api", "-X", "PUT", f"repos/{repository}/{endpoint}"], root)
            steps.append(Step(name, "ok"))
        except GitHubError as exc:
            steps.append(Step(name, "failed", _plain_error(str(exc))))

    try:
        _gh(["api", "-X", "PATCH", f"repos/{repository}", "--input", "-"], root, {"security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
        }})
        steps.append(Step("Secret scanning + push protection", "ok"))
    except GitHubError as exc:
        steps.append(Step("Secret scanning + push protection", "failed",
                          _plain_error(str(exc)) + ". Gitleaks in the MPHarness CI check still covers this."))
    return steps


def ruleset_active(root, repository):
    """True/False when it can be checked with gh, None when gh is unavailable."""
    if not repository or shutil.which("gh") is None:
        return None
    try:
        rulesets = _gh(["api", f"repos/{repository}/rulesets"], root) or []
    except GitHubError:
        return None
    return any(r.get("name") == RULESET_NAME and r.get("enforcement") == "active" for r in rulesets)
