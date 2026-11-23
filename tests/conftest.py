import subprocess

import pytest

from harness_cli import verify


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def rev(root, ref="HEAD"):
    return subprocess.run(["git", "rev-parse", ref], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def commit(root, message="change", files=None):
    for name, content in (files or {f"file-{message}.txt": message}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--no-verify", "-m", message)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


@pytest.fixture
def no_gitleaks(monkeypatch):
    """Force the built-in scanner so results do not depend on what is installed on the machine."""
    monkeypatch.setattr(verify, "_gitleaks", lambda: None)
