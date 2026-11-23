"""Loading and defaults for the project's governance.yaml policy file."""
import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

GOVERNANCE_FILE = "governance.yaml"
APPROVAL_FILE = ".harness/approval.json"

PLANNERS = ("architect", "speckit", "openspec", "none")

DEFAULTS = {
    "version": 1,
    "language": "es",
    "project": {
        "repository": "",
        "stage": "new",
        "planner": "speckit",
    },
    "branches": {"protected": ["main", "master"]},
    "rules": {
        "block_secrets_in_code": True,
        "protect_secret_files": True,
        "block_commits_to_protected": True,
        "block_force_push": True,
        "block_skipping_checks": True,
        "ask_before_destructive": True,
        "ask_before_remote_scripts": True,
        "protect_governance_files": True,
        "require_plan_approval": False,
    },
    "custom": {
        "blocked_commands": [],
        "protected_paths": [],
    },
}

# Files that control the guardrails themselves. Editing them could switch the guardrails off.
GOVERNANCE_PATHS = [
    GOVERNANCE_FILE,
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".agents/hooks.json",
    ".github/workflows/*",
    ".git/hooks/*",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
]

SECRET_FILE_PATTERNS = [
    ".env", ".env.*", "*.env",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore",
    "id_rsa*", "id_ed25519*", "id_ecdsa*",
    "secrets.json", "credentials.json", "*.tfvars",
]
SECRET_FILE_EXCEPTIONS = [".env.example", ".env.sample", ".env.template", "*.pub"]

# Planning and documentation locations: never treated as "code" by the plan-approval gate.
NON_CODE_PATTERNS = [
    "*.md", "docs/*", "specs/*", ".specify/*", "openspec/*", "blueprints/*",
    ".harness/*", "archive/*",
]


@dataclass
class Policy:
    root: Path
    data: dict = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    found: bool = False

    @property
    def language(self):
        return self.data.get("language", "es")

    @property
    def protected_branches(self):
        return list(self.data["branches"].get("protected") or [])

    def rule(self, name):
        return bool(self.data["rules"].get(name, DEFAULTS["rules"].get(name, False)))

    @property
    def custom_blocked_commands(self):
        return list(self.data["custom"].get("blocked_commands") or [])

    @property
    def custom_protected_paths(self):
        return list(self.data["custom"].get("protected_paths") or [])


def _merge(base, override):
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def find_root(start):
    """Return the nearest directory containing governance.yaml, else the git root, else start."""
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / GOVERNANCE_FILE).exists():
            return candidate
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def load_policy(start):
    root = find_root(start)
    policy = Policy(root=root)
    path = root / GOVERNANCE_FILE
    if path.exists():
        # A broken policy file must not silently disable the guardrails: fall back to strict defaults.
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            loaded = {}
        if isinstance(loaded, dict):
            _merge(policy.data, loaded)
        policy.found = True
    return policy
