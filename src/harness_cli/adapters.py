"""Translate agent hook payloads into policy Actions, and decisions back into each agent's format.

Claude Code:  https://code.claude.com/docs/en/hooks         (PreToolUse, snake_case payload)
Antigravity:  https://antigravity.google/docs/hooks         (PreToolUse, camelCase payload, PascalCase args)
"""
import json
import os

from .policy import ALLOW, DENY, Action

# ---------------------------------------------------------------- Claude Code

CLAUDE_MATCHER = "Bash|PowerShell|Edit|MultiEdit|Write|NotebookEdit|Read"


def claude_actions(payload):
    tool = payload.get("tool_name", "")
    data = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", "")

    if tool in ("Bash", "PowerShell"):
        return [Action("command", command=data.get("command", ""), cwd=cwd)]
    path = data.get("file_path") or data.get("notebook_path") or ""
    if tool == "Read":
        return [Action("read", path=path, cwd=cwd)]
    if tool == "Write":
        return [Action("write", path=path, content=data.get("content", ""), cwd=cwd)]
    if tool == "Edit":
        return [Action("write", path=path, content=data.get("new_string", ""), cwd=cwd)]
    if tool == "MultiEdit":
        content = "\n".join(e.get("new_string", "") for e in data.get("edits") or [])
        return [Action("write", path=path, content=content, cwd=cwd)]
    if tool == "NotebookEdit":
        return [Action("write", path=path, content=data.get("new_source", ""), cwd=cwd)]
    return []


def claude_project_dir(payload):
    return os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()


def claude_output(decision):
    """Return (stdout, exit_code). Silence means 'no opinion': Claude's normal permission flow applies."""
    if decision.verdict == ALLOW:
        return "", 0
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if decision.verdict == DENY else "ask",
            "permissionDecisionReason": f"[MPHarness] {decision.reason}",
        }
    }, ensure_ascii=False), 0


# ---------------------------------------------------------------- Antigravity

ANTIGRAVITY_MATCHER = "run_command|write_to_file|replace_file_content|multi_replace_file_content|view_file"


def _collect_strings(value, keys):
    """Gather string values for the given keys anywhere inside nested args (edit chunks, etc.)."""
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in keys and isinstance(v, str):
                found.append(v)
            else:
                found.extend(_collect_strings(v, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_strings(item, keys))
    return found


def _first_path(args):
    for key in ("TargetFile", "AbsolutePath", "FilePath", "Path", "File"):
        if isinstance(args.get(key), str):
            return args[key]
    for key, value in args.items():
        if isinstance(value, str) and ("File" in key or "Path" in key):
            return value
    return ""


def antigravity_actions(payload):
    call = payload.get("toolCall") or {}
    name = call.get("name", "")
    args = call.get("args") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    workspaces = payload.get("workspacePaths") or []
    cwd = args.get("Cwd") or (workspaces[0] if workspaces else "")

    if name == "run_command":
        return [Action("command", command=args.get("CommandLine", ""), cwd=cwd)]
    if name == "view_file":
        return [Action("read", path=_first_path(args), cwd=cwd)]
    if name in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
        content = "\n".join(_collect_strings(args, {"CodeContent", "ReplacementContent", "Content"}))
        return [Action("write", path=_first_path(args), content=content, cwd=cwd)]
    return []


def antigravity_project_dir(payload):
    workspaces = payload.get("workspacePaths") or []
    return workspaces[0] if workspaces else os.getcwd()


def antigravity_output(decision):
    body = {"decision": decision.verdict}
    if decision.verdict != ALLOW:
        body["reason"] = f"[MPHarness] {decision.reason}"
    return json.dumps(body, ensure_ascii=False), 0


ADAPTERS = {
    "claude": (claude_actions, claude_project_dir, claude_output),
    "antigravity": (antigravity_actions, antigravity_project_dir, antigravity_output),
}
