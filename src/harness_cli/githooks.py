"""Install git hooks that run `harness verify`, so git enforces the same governance.yaml as the AI guards."""
import os
from pathlib import Path

from .util import REPO_URL, git, is_git_repo

MANAGED_MARKER = "# MPHarness managed hook"
LEGACY_MARKERS = ("# MPHarness Mechanical Pre-Commit Hook",)

_NOT_INSTALLED = (
    'echo "[MPHarness] \'harness\' is not installed, so this change cannot be checked." >&2\n'
    f'  echo "Install it with: uv tool install git+{REPO_URL}" >&2\n'
)

HOOKS = {
    "pre-commit": f"""#!/bin/sh
{MANAGED_MARKER} (regenerate with: harness init)
if ! command -v harness >/dev/null 2>&1; then
  {_NOT_INSTALLED}  exit 1
fi
harness verify --stage pre-commit || exit 1

# Run the project's previous hook, preserved by 'harness init'
LOCAL_HOOK="$(dirname "$0")/pre-commit.local"
if [ -f "$LOCAL_HOOK" ]; then
  "$LOCAL_HOOK" "$@" || exit $?
fi
exit 0
""",
    "pre-push": f"""#!/bin/sh
{MANAGED_MARKER} (regenerate with: harness init)
if ! command -v harness >/dev/null 2>&1; then
  {_NOT_INSTALLED}  exit 1
fi
# git passes the refs being pushed on stdin; both checks need them.
REFS="$(cat)"
printf '%s\\n' "$REFS" | harness verify --stage pre-push || exit 1

LOCAL_HOOK="$(dirname "$0")/pre-push.local"
if [ -f "$LOCAL_HOOK" ]; then
  printf '%s\\n' "$REFS" | "$LOCAL_HOOK" "$@" || exit $?
fi
exit 0
""",
}


class HookResult:
    def __init__(self, name, status, detail=""):
        self.name, self.status, self.detail = name, status, detail  # status: installed | preserved | skipped | error


def _is_ours(text):
    return MANAGED_MARKER in text or any(m in text for m in LEGACY_MARKERS)


def hooks_dir(root):
    rel = git(["rev-parse", "--git-path", "hooks"], root)
    if rel is None:
        return None
    path = Path(rel)
    return path if path.is_absolute() else Path(root) / path


def install_git_hooks(root):
    """Install pre-commit and pre-push hooks. Existing foreign hooks are kept and chained as <name>.local."""
    root = Path(root)
    if not is_git_repo(root):
        return [HookResult("git hooks", "skipped", "not a git repository")]

    custom = git(["config", "--get", "core.hooksPath"], root)
    if custom:
        return [HookResult("git hooks", "skipped",
                           f"core.hooksPath is set to '{custom}' (husky, lefthook...). Add 'harness verify --stage pre-commit' "
                           "and 'harness verify --stage pre-push' to that hook manager instead.")]

    directory = hooks_dir(root)
    if directory is None:
        return [HookResult("git hooks", "error", "could not locate the git hooks folder (is git installed?)")]
    directory.mkdir(parents=True, exist_ok=True)

    results = []
    for name, script in HOOKS.items():
        path = directory / name
        chained = directory / f"{name}.local"
        status = "installed"
        if path.exists() and not _is_ours(path.read_text(encoding="utf-8", errors="ignore")):
            if chained.exists():
                results.append(HookResult(name, "error", f"an existing hook and {chained.name} both exist; merge them manually"))
                continue
            path.rename(chained)
            status = "preserved"
        path.write_text(script, encoding="utf-8", newline="\n")
        if os.name == "posix":
            path.chmod(0o755)
        results.append(HookResult(name, status, f"your previous hook still runs as {chained.name}" if status == "preserved" else ""))
    return results


def git_hooks_installed(root):
    directory = hooks_dir(root)
    if directory is None:
        return False
    return all((directory / name).exists() and MANAGED_MARKER in (directory / name).read_text(encoding="utf-8", errors="ignore")
               for name in HOOKS)
