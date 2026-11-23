"""Project setup used by `harness init` and `harness update`.

Files fall into three groups:
- managed blocks (AGENTS.md, CLAUDE.md): MPHarness owns the text between its markers; user notes outside stay.
- managed files (CI workflow, Dependabot): regenerated while they keep the "Managed by MPHarness" header.
- user files (governance.yaml, .gitleaks.toml, SPECIFICATION.md, TASKS.md): created once, never overwritten.
"""
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .github import github_files
from .governance import GOVERNANCE_FILE, load_policy
from .planners import planner_section
from .util import TEMPLATES, git, harness_ref

BLOCK_BEGIN = "<!-- mpharness:begin"
BLOCK_END = "<!-- mpharness:end -->"
MANAGED_HEADER = "Managed by MPHarness"

GITIGNORE_ENTRIES = [
    ".env", ".env.*", "!.env.example", "*.env", "*.pem", "*.key", "*.p12", "*.pfx",
    "secrets.json", "credentials.json", "/docs/",
    ".harness/updates/", ".harness/approval.json", ".harness/legacy/", ".claude/settings.local.json",
]

# Files created by MPHarness 0.1.x that the new layout replaces.
LEGACY_FILES = ["CONSTITUTION.md", "ARCHITECTURE.md", "MANUAL.md", "TRACKING.md",
                ".cursorrules", ".windsurfrules", ".clinerules"]
LEGACY_AGENTS_MARKERS = ("Open Spec Project Harness", "harness update --auto")
LEGACY_DIR = ".harness/legacy"


@dataclass
class Change:
    path: str
    action: str   # created | updated | unchanged | kept | moved | skipped
    detail: str = ""


# ------------------------------------------------------------------ detection

def detect_repository(root):
    url = git(["remote", "get-url", "origin"], root) or ""
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else ""


_SCAFFOLD = {".git", ".harness", "docs", ".gitignore", "README.md", "LICENSE", GOVERNANCE_FILE, "AGENTS.md",
             "CLAUDE.md", ".claude", ".agents", ".github", ".gitleaks.toml", "SPECIFICATION.md", "TASKS.md",
             *LEGACY_FILES}


def detect_stage(root):
    """'existing' when the folder has git history or files beyond MPHarness scaffolding, else 'new'."""
    root = Path(root)
    if git(["rev-parse", "--verify", "HEAD"], root):
        return "existing"
    return "existing" if any(p.name not in _SCAFFOLD for p in root.iterdir()) else "new"


def legacy_files(root):
    root = Path(root)
    found = [name for name in LEGACY_FILES if (root / name).exists()]
    agents = root / "AGENTS.md"
    if agents.exists():
        text = agents.read_text(encoding="utf-8", errors="ignore")
        if BLOCK_BEGIN not in text and any(m in text for m in LEGACY_AGENTS_MARKERS):
            found.append("AGENTS.md")
    return found


# ------------------------------------------------------------------ writers

def move_legacy(root):
    root = Path(root)
    target = root / LEGACY_DIR
    changes = []
    for name in legacy_files(root):
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root / name), str(target / name))
        changes.append(Change(name, "moved", f"to {LEGACY_DIR}/"))
    return changes


def write_governance(root, repository, stage, planner, agents):
    path = Path(root) / GOVERNANCE_FILE
    if path.exists():
        return Change(GOVERNANCE_FILE, "kept", "already exists")
    template = (TEMPLATES / "governance" / "governance.yaml").read_text(encoding="utf-8")
    path.write_text(template.replace("__REPOSITORY__", repository)
                            .replace("__STAGE__", stage)
                            .replace("__PLANNER__", planner)
                            .replace("__AGENTS__", ", ".join(agents)), encoding="utf-8", newline="\n")
    return Change(GOVERNANCE_FILE, "created")


def _render(template_name, planner):
    text = (TEMPLATES / "project" / template_name).read_text(encoding="utf-8")
    return text.replace("__HARNESS_REF__", harness_ref()).replace("__PLANNER_SECTION__", planner_section(planner))


def merge_block(existing, rendered):
    """Replace the MPHarness block in `existing`, or add it on top, keeping everything else."""
    block = rendered[rendered.index(BLOCK_BEGIN):rendered.index(BLOCK_END) + len(BLOCK_END)]
    if not existing.strip():
        return rendered
    if BLOCK_BEGIN in existing and BLOCK_END in existing:
        start = existing.index(BLOCK_BEGIN)
        end = existing.index(BLOCK_END) + len(BLOCK_END)
        return existing[:start] + block + existing[end:]
    return block + "\n\n" + existing


def write_managed_block(root, name, planner):
    path = Path(root) / name
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = merge_block(existing, _render(name, planner))
    if updated == existing:
        return Change(name, "unchanged")
    path.write_text(updated, encoding="utf-8", newline="\n")
    return Change(name, "updated" if existing else "created")


def write_once(root, rel, source):
    path = Path(root) / rel
    if path.exists():
        return Change(rel, "kept", "already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, path)
    return Change(rel, "created")


def write_managed_file(root, rel, content):
    path = Path(root) / rel
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return Change(rel, "unchanged")
        if MANAGED_HEADER not in current:
            return Change(rel, "kept", "customized by you (no 'Managed by MPHarness' header), not changed")
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(content, encoding="utf-8", newline="\n")
    return Change(rel, "updated" if existed else "created")


def update_gitignore(root):
    path = Path(root) / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    present = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in GITIGNORE_ENTRIES if entry not in present]
    if not missing:
        return Change(".gitignore", "unchanged")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n# Secrets and local files (added by MPHarness)\n" + "\n".join(missing) + "\n")
    return Change(".gitignore", "updated" if existing else "created", f"{len(missing)} entries added")


def write_project_files(root, policy):
    """Everything except governance.yaml, agent guards and git hooks. Shared by init and update."""
    root = Path(root)
    changes = [
        write_managed_block(root, "AGENTS.md", policy.planner),
        write_managed_block(root, "CLAUDE.md", policy.planner),
        write_once(root, ".gitleaks.toml", TEMPLATES / "project" / ".gitleaks.toml"),
        update_gitignore(root),
    ]
    if policy.planner == "none":
        for name in ("SPECIFICATION.md", "TASKS.md"):
            changes.append(write_once(root, name, TEMPLATES / "native" / name))
    for rel, content in github_files(root, policy).items():
        changes.append(write_managed_file(root, rel, content))
    return changes


def reload_policy(root):
    return load_policy(root)
