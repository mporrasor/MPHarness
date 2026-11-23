"""Small shared helpers: console output, running external tools, git queries."""
import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from rich.console import Console

console = Console()

PACKAGE_NAME = "ai-harness-cli"
REPO_URL = "https://github.com/mporrasor/MPHarness"
TEMPLATES = Path(__file__).parent / "templates"


def harness_version():
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def harness_ref():
    """Git tag of the installed MPHarness version; generated files pin to it."""
    return f"v{harness_version()}"


def install_command(ref=None):
    return f'uv tool install --force "git+{REPO_URL}@{ref or harness_ref()}"'


def run_tool(args, cwd, capture=True, input_text=None, timeout=None):
    """Run an external CLI without a shell, resolving Windows .cmd/.bat shims."""
    exe = shutil.which(args[0])
    if exe is None:
        raise FileNotFoundError(f"{args[0]} not found on PATH")
    cmd = [exe, *args[1:]]
    kwargs = dict(cwd=cwd, text=True, input=input_text, timeout=timeout)
    if capture:
        kwargs["capture_output"] = True
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        # Batch shims (npm.cmd, pnpm.cmd...) can only be executed through cmd.exe.
        return subprocess.run(subprocess.list2cmdline(cmd), shell=True, **kwargs)
    return subprocess.run(cmd, **kwargs)


def git(args, cwd):
    """Return stripped stdout of a git command, or None if git is missing or the command fails."""
    if shutil.which("git") is None or not Path(cwd).is_dir():
        return None
    try:
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def git_ok(args, cwd):
    if shutil.which("git") is None:
        return False
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0


def is_git_repo(root):
    return (Path(root) / ".git").exists()
