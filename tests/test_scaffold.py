from pathlib import Path

from click.testing import CliRunner

from conftest import git
from harness_cli.cli import main
from harness_cli.githooks import git_hooks_installed, hooks_dir
from harness_cli.installers import antigravity_installed, claude_installed
from harness_cli.scaffold import BLOCK_BEGIN, BLOCK_END, merge_block


def init(root, *extra):
    result = CliRunner().invoke(main, ["init", "--dir", str(root), "--yes", *extra])
    assert result.exit_code == 0, result.output
    return result


def test_init_new_project_creates_everything(repo):
    init(repo, "--repo", "me/app")
    gov = (repo / "governance.yaml").read_text(encoding="utf-8")
    assert 'repository: "me/app"' in gov and "stage: new" in gov and "planner: speckit" in gov
    assert "agents: [claude, antigravity]" in gov
    agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert BLOCK_BEGIN in agents and "/speckit-specify" in agents and "__" not in agents
    assert "@AGENTS.md" in (repo / "CLAUDE.md").read_text(encoding="utf-8")
    for rel in (".gitleaks.toml", ".github/workflows/mpharness.yml", ".github/dependabot.yml", ".gitignore"):
        assert (repo / rel).exists(), rel
    assert not (repo / "SPECIFICATION.md").exists()
    assert claude_installed(repo) and antigravity_installed(repo) and git_hooks_installed(repo)


def test_init_existing_code_recommends_openspec(repo):
    (repo / "app.py").write_text("print(1)", encoding="utf-8")
    init(repo)
    gov = (repo / "governance.yaml").read_text(encoding="utf-8")
    assert "stage: existing" in gov and "planner: openspec" in gov
    assert "/openspec-propose" in (repo / "AGENTS.md").read_text(encoding="utf-8")


def test_init_planner_none_adds_native_docs(repo):
    init(repo, "--planner", "none")
    assert (repo / "SPECIFICATION.md").exists() and (repo / "TASKS.md").exists()


def test_init_creates_git_repository_when_missing(tmp_path):
    init(tmp_path)
    assert (tmp_path / ".git").exists() and git_hooks_installed(tmp_path)


def test_init_is_idempotent_and_keeps_user_notes(repo):
    init(repo)
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8") + "\nUse PostgreSQL 16.\n", encoding="utf-8")
    gitignore_before = (repo / ".gitignore").read_text(encoding="utf-8")
    init(repo)
    text = agents.read_text(encoding="utf-8")
    assert "Use PostgreSQL 16." in text and text.count(BLOCK_BEGIN) == 1
    assert (repo / ".gitignore").read_text(encoding="utf-8") == gitignore_before


def test_existing_user_agents_md_is_kept_below_block(repo):
    (repo / "AGENTS.md").write_text("# My rules\nAlways use tabs.\n", encoding="utf-8")
    init(repo)
    text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert text.index(BLOCK_END) < text.index("Always use tabs.")


def test_merge_block_replaces_only_managed_part():
    old = f"intro\n{BLOCK_BEGIN} v1 -->\nold rules\n{BLOCK_END}\nmy notes\n"
    new = f"{BLOCK_BEGIN} v2 -->\nnew rules\n{BLOCK_END}\n\n## Project notes\n"
    merged = merge_block(old, new)
    assert "new rules" in merged and "old rules" not in merged
    assert merged.startswith("intro\n") and merged.endswith("my notes\n")


def test_legacy_files_moved(repo):
    for name in ("CONSTITUTION.md", ".cursorrules", ".windsurfrules"):
        (repo / name).write_text("old", encoding="utf-8")
    (repo / "AGENTS.md").write_text("You are operating within an **Open Spec Project Harness**.", encoding="utf-8")
    init(repo)
    legacy = repo / ".harness" / "legacy"
    assert (legacy / "CONSTITUTION.md").exists() and (legacy / ".cursorrules").exists() and (legacy / "AGENTS.md").exists()
    assert not (repo / "CONSTITUTION.md").exists()
    assert "Open Spec Project Harness" not in (repo / "AGENTS.md").read_text(encoding="utf-8")


def test_foreign_git_hook_is_preserved_and_chained(repo):
    directory = hooks_dir(repo)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pre-commit").write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    init(repo)
    assert (directory / "pre-commit.local").read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"
    assert git_hooks_installed(repo)


def test_hooks_path_is_respected(repo):
    git(repo, "config", "core.hooksPath", ".husky/_")
    result = init(repo)
    assert "core.hooksPath" in result.output
    assert not (repo / ".husky").exists()


def test_update_regenerates_managed_workflow_but_keeps_customized(repo):
    init(repo)
    workflow = repo / ".github" / "workflows" / "mpharness.yml"
    dependabot = repo / ".github" / "dependabot.yml"
    workflow.write_text(workflow.read_text(encoding="utf-8") + "# tweak\n", encoding="utf-8")
    dependabot.write_text("version: 2\nupdates: []\n", encoding="utf-8")  # customized: no managed header
    result = CliRunner().invoke(main, ["update", "--dir", str(repo)])
    assert result.exit_code == 0, result.output
    assert "# tweak" not in workflow.read_text(encoding="utf-8")
    assert dependabot.read_text(encoding="utf-8") == "version: 2\nupdates: []\n"


def test_update_requires_governance(tmp_path):
    result = CliRunner().invoke(main, ["update", "--dir", str(tmp_path)])
    assert result.exit_code == 1


def test_templates_are_english_and_fully_rendered(repo):
    init(repo)
    for rel in ("AGENTS.md", "CLAUDE.md", "governance.yaml", ".github/workflows/mpharness.yml"):
        text = (repo / rel).read_text(encoding="utf-8")
        assert "__" not in text.replace("__init__", ""), rel
        assert not any(word in text for word in ("Bloqueado", "proyecto", "rama")), rel


def test_package_templates_exist():
    from harness_cli.util import TEMPLATES
    for rel in ("project/AGENTS.md", "project/CLAUDE.md", "project/.gitleaks.toml", "governance/governance.yaml",
                "github/mpharness.yml", "native/SPECIFICATION.md", "native/TASKS.md"):
        assert (Path(TEMPLATES) / rel).exists(), rel
