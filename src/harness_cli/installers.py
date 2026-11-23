"""Install MPHarness guard hooks into each AI agent's project configuration (merging, never clobbering)."""
import json
from pathlib import Path

from .adapters import ANTIGRAVITY_MATCHER, CLAUDE_MATCHER

GUARD_MARKER = "harness guard"

# `|| exit 2` makes the hook fail closed: if harness is missing or crashes, Claude Code blocks the action.
CLAUDE_HOOK = {
    "matcher": CLAUDE_MATCHER,
    "hooks": [{
        "type": "command",
        "command": "harness guard --agent claude || exit 2",
        "shell": "bash",
        "timeout": 30,
    }],
}

ANTIGRAVITY_HOOK_NAME = "mpharness-guard"
ANTIGRAVITY_HOOK = {
    "PreToolUse": [{
        "matcher": ANTIGRAVITY_MATCHER,
        "hooks": [{"type": "command", "command": "harness guard --agent antigravity", "timeout": 30}],
    }],
}


class ConfigError(Exception):
    pass


def _load_json(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError as exc:
        raise ConfigError(f"{path} is not valid JSON ({exc}); fix it and run again.") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object.")
    return data


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def install_claude(root):
    path = Path(root) / ".claude" / "settings.json"
    settings = _load_json(path)
    groups = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    groups[:] = [g for g in groups
                 if not any(GUARD_MARKER in h.get("command", "") for h in g.get("hooks", []))]
    groups.insert(0, CLAUDE_HOOK)
    _write_json(path, settings)
    return path


def install_antigravity(root):
    path = Path(root) / ".agents" / "hooks.json"
    hooks = _load_json(path)
    hooks[ANTIGRAVITY_HOOK_NAME] = ANTIGRAVITY_HOOK
    _write_json(path, hooks)
    return path


def claude_installed(root):
    path = Path(root) / ".claude" / "settings.json"
    try:
        settings = _load_json(path)
    except ConfigError:
        return False
    return any(GUARD_MARKER in h.get("command", "")
               for g in settings.get("hooks", {}).get("PreToolUse", []) for h in g.get("hooks", []))


def antigravity_installed(root):
    try:
        hooks = _load_json(Path(root) / ".agents" / "hooks.json")
    except ConfigError:
        return False
    entry = hooks.get(ANTIGRAVITY_HOOK_NAME) or {}
    return entry.get("enabled", True) is not False and "PreToolUse" in entry


AGENTS = {
    "claude": install_claude,
    "antigravity": install_antigravity,
}
