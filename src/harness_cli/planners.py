"""Planning tools: what the AI should do with each one, and how to install it.

Recommended by project stage: Spec Kit for new projects, OpenSpec for existing code.
The Architect is an optional Claude Code plugin that interviews the user and writes a full blueprint.
"""
import shutil
import subprocess

from .util import run_tool

PLANNER_SECTIONS = {
    "speckit": (
        "   - This project plans with **GitHub Spec Kit**. Run `/speckit-specify` (what and why), `/speckit-plan`\n"
        "     (how), `/speckit-tasks` (checklist), then `/speckit-implement`. Spec Kit keeps the specs and tasks;\n"
        "     do not copy them into other files. Use `/speckit-constitution` once to record project principles.\n"
        "   - Show the user the spec and plan in plain words and wait for their OK before implementing."
    ),
    "openspec": (
        "   - This project plans with **OpenSpec**. For each change run `/openspec-propose <change>`, show the user\n"
        "     the proposal in plain words, and after their OK run `/openspec-apply-change`. When it is merged,\n"
        "     run `/openspec-archive-change`. The specs in `openspec/` describe how the system works today."
    ),
    "architect": (
        "   - This project plans with **The Architect** (Claude Code plugin). For a new app run `/architect`\n"
        "     (or `/architect-quick`); to change an existing app run `/architect-brownfield`. Build by following\n"
        "     the blueprint in `blueprints/` step by step, using `/architect-next` to pick the next task.\n"
        "   - Before running any bootstrap or install command from a blueprint, tell the user what it will do."
    ),
    "none": (
        "   - Write the goal and decisions in `SPECIFICATION.md` and the steps in `TASKS.md` (keep both short),\n"
        "     show the user the plan in plain words, and wait for their OK before writing code."
    ),
}

# Each entry: (description, [commands]). `{integration}` / `{tools}` are filled per agent.
PLANNER_SETUP = {
    "speckit": {
        "label": "GitHub Spec Kit",
        "needs": "uv",
        "install": [["uv", "tool", "install", "specify-cli"]],
        "init": [["specify", "init", "--here", "--force", "--integration", "{integration}"]],
        "docs": "https://github.com/github/spec-kit",
    },
    "openspec": {
        "label": "OpenSpec",
        "needs": "npm",
        "install": [["npm", "install", "-g", "@fission-ai/openspec@latest"]],
        "init": [["openspec", "init", "--scope", "project", "--tools", "{tools}"]],
        "docs": "https://github.com/Fission-AI/OpenSpec",
    },
    "architect": {
        "label": "The Architect (Claude Code plugin)",
        "needs": "claude",
        "install": [["claude", "plugin", "marketplace", "add", "Hainrixz/the-architect"],
                    ["claude", "plugin", "install", "the-architect@soyenriquerocha"]],
        "init": [],
        "docs": "https://github.com/Hainrixz/the-architect",
    },
}

SPECKIT_INTEGRATIONS = {"claude": "claude", "antigravity": "agy"}


def planner_section(planner):
    return PLANNER_SECTIONS.get(planner, PLANNER_SECTIONS["none"])


def setup_commands(planner, agents):
    """Return the list of commands (as argument lists) to install and initialize a planner."""
    spec = PLANNER_SETUP.get(planner)
    if spec is None:
        return []
    primary = agents[0] if agents else "claude"
    values = {
        "integration": SPECKIT_INTEGRATIONS.get(primary, "claude"),
        "tools": ",".join(a for a in agents if a in ("claude", "antigravity")) or "claude",
    }
    commands = list(spec["install"])
    commands += [[part.format(**values) for part in cmd] for cmd in spec["init"]]
    return commands


def is_installed(planner):
    if planner == "architect":
        if shutil.which("claude") is None:
            return False
        try:
            res = run_tool(["claude", "plugin", "list"], cwd=".", timeout=30)
        except (OSError, subprocess.SubprocessError):
            return False
        return "the-architect" in (res.stdout or "")
    binary = {"speckit": "specify", "openspec": "openspec"}.get(planner)
    return binary is None or shutil.which(binary) is not None
