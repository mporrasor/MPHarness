"""MPHarness command line: governance and guardrails for building secure apps with AI agents."""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from . import audit as audit_module
from . import doctor as doctor_module
from . import github as github_module
from . import verify as verify_module
from .adapters import ADAPTERS
from .githooks import install_git_hooks
from .governance import APPROVAL_FILE, PLANNERS, load_policy
from .installers import AGENTS as AGENT_INSTALLERS, ConfigError
from .messages import msg
from .planners import PLANNER_SETUP, is_installed, setup_commands
from .policy import DENY, Decision, current_branch, evaluate
from .scaffold import (
    detect_repository,
    detect_stage,
    legacy_files,
    move_legacy,
    write_governance,
    write_project_files,
)
from .util import console, harness_version, install_command, is_git_repo, run_tool

ICONS = {"created": "[green]+[/green]", "updated": "[cyan]~[/cyan]", "moved": "[yellow]>[/yellow]",
         "kept": "[dim]=[/dim]", "unchanged": "[dim]=[/dim]", "skipped": "[yellow]![/yellow]",
         "installed": "[green]+[/green]", "preserved": "[green]+[/green]", "error": "[red]x[/red]"}


def _root(dir):
    return Path(dir).resolve()


def _print_changes(changes):
    for change in changes:
        if change.action == "unchanged":
            continue
        detail = f" [dim]({change.detail})[/dim]" if change.detail else ""
        console.print(f"  {ICONS.get(change.action, '-')} {change.path} [dim]{change.action}[/dim]{detail}")


def _install_guards(root, agents):
    for agent in agents:
        installer = AGENT_INSTALLERS.get(agent)
        if installer is None:
            console.print(f"  [yellow]![/yellow] Unknown agent '{agent}' (supported: {', '.join(AGENT_INSTALLERS)})")
            continue
        try:
            path = installer(root)
            console.print(f"  [green]+[/green] {path.relative_to(root).as_posix()} [dim]{agent} guard active[/dim]")
        except ConfigError as exc:
            console.print(f"  [red]x[/red] {exc}")


def _install_hooks(root):
    for result in install_git_hooks(root):
        detail = f" [dim]({result.detail})[/dim]" if result.detail else ""
        console.print(f"  {ICONS.get(result.status, '-')} git {result.name} hook [dim]{result.status}[/dim]{detail}")


def _run_planner_setup(root, planner, agents, ask):
    spec = PLANNER_SETUP.get(planner)
    if spec is None:
        return
    commands = setup_commands(planner, agents)
    shown = "\n".join("    " + " ".join(c) for c in commands)
    if shutil.which(spec["needs"]) is None:
        console.print(f"\n[yellow]{spec['label']} needs '{spec['needs']}', which is not installed.[/yellow] "
                      f"Install it, then run:\n{shown}\n  Docs: {spec['docs']}")
        return
    if ask and not click.confirm(f"\nInstall and set up {spec['label']} now? It runs:\n{shown}\n", default=True):
        console.print(f"  Skipped. You can run it later with: harness planner setup")
        return
    for command in commands:
        console.print(f"[cyan]$ {' '.join(command)}[/cyan]")
        result = run_tool(command, root, capture=False)
        if result.returncode != 0:
            console.print(f"[red]That command failed. See the docs: {spec['docs']}[/red]")
            return
    console.print(f"[green]{spec['label']} is ready.[/green]")


def _next_steps(policy):
    usage = {
        "speckit": "Ask your AI for a feature, or run /speckit-specify to start the spec.",
        "openspec": "Ask your AI for a change, or run /openspec-propose <change>.",
        "architect": "In Claude Code run /architect (new app) or /architect-brownfield (existing app).",
        "none": "Describe what you want to your AI; it will write SPECIFICATION.md and TASKS.md first.",
    }[policy.planner if policy.planner in PLANNERS else "none"]
    github = (f"Push your code to GitHub, then run [bold]harness github apply[/bold] to protect {policy.repository}."
              if policy.repository else
              "Create the repository on GitHub, put it in governance.yaml (project.repository: owner/name), "
              "push your code, then run [bold]harness github apply[/bold].")
    console.print("\n[bold]Next steps[/bold]")
    console.print(f"  1. {usage}")
    console.print(f"  2. {github}")
    console.print("  3. Run [bold]harness doctor[/bold] any time to check that every protection is working.")
    if shutil.which("harness") is None:
        console.print(f"\n[bold yellow]Important:[/bold yellow] 'harness' is not on your PATH, so the AI guards will block "
                      f"every action. Install it:\n  {install_command()}")


# ------------------------------------------------------------------ commands

@click.group()
@click.version_option(harness_version(), prog_name="MPHarness")
def main():
    """MPHarness: guardrails for building secure apps with AI agents (Claude Code, Antigravity).

    Start with 'harness init' in your project folder, then 'harness doctor' to check everything.
    """
    # Legacy Windows consoles (cp1252) cannot print every character; never crash a git hook over output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


@main.command()
@click.option('--dir', default='.', help='Project folder.')
@click.option('--repo', default=None, help='GitHub repository (owner/name). Detected from the git remote when omitted.')
@click.option('--stage', type=click.Choice(['new', 'existing']), default=None, help='New project or existing code. Detected when omitted.')
@click.option('--planner', type=click.Choice(list(PLANNERS)), default=None,
              help='Planning tool. Default: speckit for new projects, openspec for existing code.')
@click.option('--agents', default='claude,antigravity', show_default=True, help='AI agents to protect (comma-separated).')
@click.option('--yes', '-y', is_flag=True, help='Use detected values and skip all questions.')
def init(dir, repo, stage, planner, agents, yes):
    """Set up MPHarness in a project (new or existing). Safe to run again."""
    root = _root(dir)
    root.mkdir(parents=True, exist_ok=True)
    ask = not yes and sys.stdin.isatty()
    agent_list = [a.strip() for a in agents.split(",") if a.strip()]
    console.print(f"[bold]MPHarness {harness_version()} setup[/bold] in {root}\n")

    if not is_git_repo(root):
        if shutil.which("git") is None:
            console.print("[yellow]Git is not installed, so commits cannot be protected. Install it from https://git-scm.com[/yellow]")
        elif not ask or click.confirm("This folder is not a git repository yet. Create one?", default=True):
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=False)
            console.print("  [green]+[/green] git repository created (branch main)")

    legacy = legacy_files(root)
    if legacy and (not ask or click.confirm(f"Found files from an older MPHarness ({', '.join(legacy)}). "
                                            f"Move them to .harness/legacy/?", default=True)):
        _print_changes(move_legacy(root))
        console.print("  [dim]Ask your AI to copy anything project-specific from .harness/legacy/ into AGENTS.md "
                      "(Project notes), then delete that folder.[/dim]")

    repo = repo or detect_repository(root)
    if not repo and ask:
        repo = click.prompt("GitHub repository (owner/name), leave empty if it does not exist yet",
                            default="", show_default=False).strip()

    if stage is None:
        stage = detect_stage(root)
        if ask:
            label = "a NEW project" if stage == "new" else "a project with EXISTING code"
            if not click.confirm(f"This looks like {label}. Is that right?", default=True):
                stage = "existing" if stage == "new" else "new"

    if planner is None:
        planner = "speckit" if stage == "new" else "openspec"
        if ask:
            console.print(f"\nHow should work be planned? Recommended: [bold]{planner}[/bold]\n"
                          "  speckit   GitHub Spec Kit - best for starting something new\n"
                          "  openspec  OpenSpec - best for changing code that already exists\n"
                          "  architect The Architect - interviews you and writes a full blueprint (Claude Code only)\n"
                          "  none      No extra tool: a simple SPECIFICATION.md and TASKS.md")
            planner = click.prompt("Planner", type=click.Choice(list(PLANNERS)), default=planner)

    console.print("\n[bold]Files[/bold]")
    _print_changes([write_governance(root, repo, stage, planner, agent_list)])
    policy = load_policy(root)
    _print_changes(write_project_files(root, policy))

    console.print("\n[bold]Guards[/bold]")
    _install_guards(root, policy.agents)
    _install_hooks(root)

    if planner in PLANNER_SETUP and not is_installed(planner) and ask:
        _run_planner_setup(root, planner, policy.agents, ask=True)
    elif planner in PLANNER_SETUP and not is_installed(planner):
        console.print(f"\n[dim]To install the planner later: harness planner setup[/dim]")

    _next_steps(policy)


@main.command()
@click.option('--dir', default='.', help='Project folder.')
def update(dir):
    """Refresh MPHarness files and guards from the installed version. Your own notes and rules are kept."""
    policy = load_policy(_root(dir))
    root = policy.root
    if not policy.found:
        console.print("[yellow]No governance.yaml here. Run 'harness init' first.[/yellow]")
        sys.exit(1)
    console.print(f"[bold]Updating project to MPHarness {harness_version()}[/bold]")
    _print_changes(write_project_files(root, policy))
    _install_guards(root, policy.agents)
    _install_hooks(root)
    console.print("\nTo get a newer MPHarness version first, run:\n"
                  f"  {install_command('<version, e.g. v0.3.0>')}\nthen run 'harness update' again.")


@main.command()
@click.option('--dir', default='.', help='Project folder.')
def doctor(dir):
    """Check every protection layer and explain how to fix what is missing."""
    checks = doctor_module.run(_root(dir))
    icons = {"ok": "[green]OK[/green]", "warn": "[yellow]![/yellow]", "fail": "[red]X [/red]"}
    for check in checks:
        console.print(f"{icons[check.status]} {check.title}")
        if check.fix and check.status != "ok":
            console.print(f"    [dim]-> {check.fix}[/dim]")
    failures = sum(c.status == "fail" for c in checks)
    warnings = sum(c.status == "warn" for c in checks)
    if failures:
        console.print(f"\n[red]{failures} problem(s) need attention.[/red]")
        sys.exit(1)
    console.print(f"\n[green]All protections are working.[/green]" + (f" {warnings} suggestion(s) above." if warnings else ""))


@main.command(hidden=True)
@click.option('--dir', default='.')
@click.pass_context
def check(ctx, dir):
    """Alias of 'doctor' (kept for older projects)."""
    ctx.invoke(doctor, dir=dir)


@main.command(hidden=True)
@click.option('--dir', default='.')
@click.pass_context
def tools(ctx, dir):
    """Alias of 'doctor' (kept for older projects)."""
    ctx.invoke(doctor, dir=dir)


@main.command()
@click.option('--stage', type=click.Choice(['pre-commit', 'pre-push', 'ci']), required=True, help='Which checkpoint is running.')
@click.option('--dir', default='.', help='Project folder.')
def verify(stage, dir):
    """Run the governance checks for a git hook or CI. Installed automatically; rarely run by hand."""
    refs = sys.stdin.read() if stage == "pre-push" and not sys.stdin.isatty() else ""
    findings = verify_module.run(stage, _root(dir), refs)
    errors = [f for f in findings if f.level == verify_module.ERROR]
    for finding in findings:
        prefix = "[red]X \\[MPHarness][/red]" if finding.level == verify_module.ERROR else "[yellow]! \\[MPHarness][/yellow]"
        console.print(f"{prefix} ", end="")
        console.print(finding.message, markup=False, highlight=False)
    if errors:
        console.print(f"[red]{stage}: {len(errors)} problem(s) found. Nothing was {'committed' if stage == 'pre-commit' else 'pushed' if stage == 'pre-push' else 'approved'}.[/red]")
        sys.exit(1)
    if stage == "ci":
        console.print("[green]MPHarness checks passed.[/green]")


@main.command()
@click.option('--agent', type=click.Choice(list(ADAPTERS)), required=True, help='Which AI agent sent the hook payload.')
def guard(agent):
    """Agent hook entry point: reads a tool call on stdin and answers allow / ask / deny.

    Installed automatically by 'harness init'. Not meant to be run by hand.
    """
    to_actions, project_dir, render = ADAPTERS[agent]
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        policy = load_policy(project_dir(payload))
        decision = Decision()
        for action in to_actions(payload):
            result = evaluate(action, policy)
            for reason in result.reasons:
                decision.add(result.verdict, reason)
    except Exception as exc:  # Fail closed: a guard that crashes must never let the action through.
        decision = Decision()
        decision.add(DENY, msg("guard_error", detail=type(exc).__name__))

    out, code = render(decision)
    if out:
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.flush()
    sys.exit(code)


@main.command()
@click.option('--dir', default='.', help='Project folder.')
@click.option('--revoke', is_flag=True, help='Remove the current approval.')
def approve(dir, revoke):
    """Approve the current plan so the AI may edit code (only needed when require_plan_approval is on).

    The approval is tied to the current git branch and stays on this computer.
    """
    policy = load_policy(_root(dir))
    path = policy.root / APPROVAL_FILE
    if revoke:
        path.unlink(missing_ok=True)
        console.print("[yellow]Approval removed.[/yellow]")
        return
    if not policy.rule("require_plan_approval"):
        console.print("[yellow]require_plan_approval is off in governance.yaml, so no approval is needed.[/yellow]")
    branch = current_branch(policy.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"branch": branch, "approved_at": datetime.now(timezone.utc).isoformat()}, indent=2),
                    encoding="utf-8")
    console.print(f"[bold green]Plan approved for branch '{branch or 'any'}'.[/bold green] The AI may now edit code.")


@main.command()
@click.option('--dir', default='.', help='Project folder.')
def audit(dir):
    """Check dependencies for known vulnerabilities and outdated versions (npm, Python, .NET)."""
    console.print("[bold]Dependency audit[/bold]\n")
    audit_module.run(_root(dir))


# ------------------------------------------------------------------ groups

@main.group()
def github():
    """Protect the project's GitHub repository."""


@github.command("apply")
@click.option('--dir', default='.', help='Project folder.')
@click.option('--yes', '-y', is_flag=True, help='Apply without asking for confirmation.')
def github_apply(dir, yes):
    """Turn on GitHub protection for the repository in governance.yaml (uses the 'gh' CLI)."""
    policy = load_policy(_root(dir))
    console.print(f"[bold]GitHub protection for {policy.repository or '(no repository set)'}[/bold]")
    for step in github_module.plan(policy):
        console.print(f"  - {step.name}")
    try:
        github_module.preflight(policy.root, policy.repository)
    except github_module.GitHubError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    if not yes and not click.confirm("\nThis changes settings on GitHub. Continue?", default=True):
        return
    failed = 0
    for step in github_module.apply(policy.root, policy):
        icon = "[green]OK[/green]" if step.status == "ok" else "[yellow]![/yellow]"
        failed += step.status == "failed"
        console.print(f"{icon} {step.name}" + (f" [dim]({step.detail})[/dim]" if step.detail else ""))
    if not (policy.root / github_module.WORKFLOW_PATH).exists():
        console.print("[yellow]The MPHarness workflow file is missing; run 'harness update' and push it, "
                      "or Pull Requests will wait for a check that never runs.[/yellow]")
    console.print("\n[green]Done.[/green]" if not failed else
                  "\n[yellow]Some features are not available for this repository; the rest is active.[/yellow]")


@main.group()
def planner():
    """Install the planning tool chosen in governance.yaml."""


@planner.command("setup")
@click.option('--dir', default='.', help='Project folder.')
@click.option('--yes', '-y', is_flag=True, help='Install without asking.')
def planner_setup(dir, yes):
    """Install and initialize Spec Kit, OpenSpec or The Architect for this project."""
    policy = load_policy(_root(dir))
    if policy.planner not in PLANNER_SETUP:
        console.print("This project does not use an external planner (planner: none). Nothing to install.")
        return
    _run_planner_setup(policy.root, policy.planner, policy.agents, ask=not yes)


if __name__ == "__main__":
    main()
