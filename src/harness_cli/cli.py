import click
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from rich.console import Console

from .adapters import ADAPTERS
from .governance import APPROVAL_FILE, GOVERNANCE_FILE, PLANNERS, load_policy
from .installers import AGENTS as AGENT_INSTALLERS, ConfigError
from .messages import msg
from .policy import DENY, Decision, current_branch, evaluate

console = Console()

TEMPLATE_DIR = Path(__file__).parent / "templates" / "spec-driven-project"
GOVERNANCE_TEMPLATE_DIR = Path(__file__).parent / "templates" / "governance"
RULE_ALIASES = [".windsurfrules", ".clinerules"]
HOOK_MARKER = "# MPHarness Mechanical Pre-Commit Hook"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/mporrasor/MPHarness"
TEMPLATE_REPO_PATH = "src/harness_cli/templates/spec-driven-project/"


def _default_template_ref():
    try:
        return f"v{package_version('ai-harness-cli')}"
    except PackageNotFoundError:
        return "v0.1.0"


def _run_tool(args, cwd):
    """Run an external CLI without a shell, resolving Windows .cmd/.bat shims."""
    exe = shutil.which(args[0])
    if exe is None:
        raise FileNotFoundError(f"{args[0]} not found on PATH")
    cmd = [exe, *args[1:]]
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        # Batch shims (npm.cmd, pnpm.cmd...) can only be executed through cmd.exe.
        return subprocess.run(subprocess.list2cmdline(cmd), cwd=cwd, capture_output=True, text=True, shell=True)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _git_output(args, cwd):
    if shutil.which("git") is None:
        return None
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else None

@click.group()
def main():
    """Universal Spec-Driven Project Harness for AI Agents."""
    pass

@main.command()
@click.option('--dir', default='.', help='Directory to initialize the harness.')
@click.option('--repo', default=None, help='GitHub repository (owner/name). Detected from the git remote when omitted.')
@click.option('--stage', type=click.Choice(['new', 'existing']), default=None, help='new project or existing code. Auto-detected when omitted.')
@click.option('--planner', type=click.Choice(list(PLANNERS)), default=None, help='Planning tool. Default: speckit for new projects, openspec for existing code.')
@click.option('--lang', type=click.Choice(['es', 'en']), default=None, help='Language for governance.yaml and guardrail messages.')
@click.option('--agents', default='claude,antigravity', show_default=True, help='Comma-separated AI agents to protect with guard hooks.')
@click.option('--yes', '-y', is_flag=True, help='Accept detected values without asking questions.')
def init(dir, repo, stage, planner, lang, agents, yes):
    """Set up governance, guardrails and templates in a project (new or existing)."""
    target_dir = Path(dir).resolve()

    if not target_dir.exists():
        target_dir.mkdir(parents=True)

    interactive = not yes and sys.stdin.isatty()
    _setup_governance(target_dir, repo, stage, planner, lang, interactive)
    _setup_agent_guards(target_dir, agents)

    harness_dir = target_dir / ".harness"
    if not harness_dir.exists():
        harness_dir.mkdir(parents=True)
        console.print(f"[green]Created harness directory at {harness_dir}[/green]")
    else:
        console.print(f"[yellow]Harness directory already exists at {harness_dir}[/yellow]")

    # Ensure docs directory exists
    docs_dir = target_dir / "docs"
    if not docs_dir.exists():
        docs_dir.mkdir(parents=True)
        console.print(f"[blue]Created directory:[/blue] {docs_dir.name}/")

    # Copy templates
    for file in TEMPLATE_DIR.iterdir():
        if file.is_file():
            dest = target_dir / file.name
            if not dest.exists():
                shutil.copy(file, dest)
                console.print(f"[blue]Created template:[/blue] {dest.name}")
            else:
                console.print(f"[yellow]Skipping {dest.name} (already exists)[/yellow]")
    
    # Create IDE rule aliases
    cursorrules_dest = target_dir / ".cursorrules"
    if cursorrules_dest.exists():
        for alias in [".windsurfrules", ".clinerules"]:
            alias_dest = target_dir / alias
            if not alias_dest.exists():
                shutil.copy(cursorrules_dest, alias_dest)
                console.print(f"[blue]Created IDE rule alias:[/blue] {alias}")

    # Auto-protect .gitignore against secrets and private documentation
    gitignore_path = target_dir / ".gitignore"
    mandatory_ignores = [
        ".env",
        ".env.*",
        "*.env",
        "*.pem",
        "*.key",
        "secrets.json",
        "credentials.json",
        "/docs/",
        ".harness/updates/",
        ".harness/approval.json",
        ".claude/settings.local.json",
    ]
    existing_gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    missing_ignores = [entry for entry in mandatory_ignores if entry not in existing_gitignore]
    if missing_ignores:
        with open(gitignore_path, "a", encoding="utf-8", newline="\n") as f:
            if existing_gitignore and not existing_gitignore.endswith("\n"):
                f.write("\n")
            f.write("\n# Security & Secrets Prevention (Enforced by MPHarness)\n")
            for entry in missing_ignores:
                f.write(f"{entry}\n")
        console.print("[bold green]Enhanced .gitignore with secret prevention and /docs/ privacy rules.[/bold green]")

    # Install Mechanical Git Hook (Prevent commits to main + Gitleaks Secret Scanning)
    _install_pre_commit_hook(target_dir)

    console.print("\n[bold green]Harness initialized successfully![/bold green]")
    console.print("[bold yellow]IMPORTANT:[/bold yellow] Place any initial requirements, analysis files, or UI prototypes inside the [bold]/docs[/bold] folder.")
    console.print("You can now start editing SPECIFICATION.md, or invite your AI to begin.")


def _detect_repository(target_dir):
    url = _git_output(["remote", "get-url", "origin"], target_dir) or ""
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else ""


_SCAFFOLD_NAMES = {".git", ".harness", "docs", ".gitignore", "README.md", "LICENSE", GOVERNANCE_FILE,
                   ".claude", ".agents", ".gitleaks.toml"} | {f.name for f in TEMPLATE_DIR.iterdir()}


def _detect_stage(target_dir):
    """'existing' if the folder already has project files or git history beyond scaffolding."""
    if _git_output(["rev-parse", "--verify", "HEAD"], target_dir):
        return "existing"
    return "existing" if any(p.name not in _SCAFFOLD_NAMES for p in target_dir.iterdir()) else "new"


def _setup_governance(target_dir, repo, stage, planner, lang, interactive):
    gov_path = target_dir / GOVERNANCE_FILE
    if gov_path.exists():
        console.print(f"[yellow]Skipping {GOVERNANCE_FILE} (already exists)[/yellow]")
        return

    lang = lang or (click.prompt("Idioma / Language", type=click.Choice(['es', 'en']), default='es') if interactive else 'es')
    es = lang == 'es'

    repo = repo or _detect_repository(target_dir)
    if not repo and interactive:
        repo = click.prompt("Repositorio de GitHub (usuario/nombre), vacío si aún no existe" if es
                            else "GitHub repository (owner/name), empty if it does not exist yet",
                            default="", show_default=False).strip()

    detected_stage = _detect_stage(target_dir)
    if stage is None:
        stage = detected_stage
        if interactive:
            question = ("Detecté un proyecto NUEVO. ¿Es correcto?" if stage == "new" else
                        "Detecté un proyecto con código EXISTENTE. ¿Es correcto?") if es else \
                       (f"Detected a {'NEW project' if stage == 'new' else 'project with EXISTING code'}. Is that right?")
            if not click.confirm(question, default=True):
                stage = "existing" if stage == "new" else "new"

    if planner is None:
        planner = "speckit" if stage == "new" else "openspec"
        if interactive:
            console.print(
                ("\nHerramienta para planificar el trabajo (recomendada: [bold]{p}[/bold])\n"
                 "  architect = The Architect: te entrevista y escribe un plano completo (solo Claude Code)\n"
                 "  speckit   = GitHub Spec Kit: ideal para empezar algo nuevo\n"
                 "  openspec  = OpenSpec: ideal para cambiar código que ya existe\n"
                 "  none      = sin herramienta externa") if es else
                ("\nPlanning tool (recommended: [bold]{p}[/bold])\n"
                 "  architect = The Architect: interviews you and writes a full blueprint (Claude Code only)\n"
                 "  speckit   = GitHub Spec Kit: best for starting something new\n"
                 "  openspec  = OpenSpec: best for changing existing code\n"
                 "  none      = no external tool")
                .format(p=planner))
            planner = click.prompt("Planner", type=click.Choice(list(PLANNERS)), default=planner)

    template = (GOVERNANCE_TEMPLATE_DIR / f"governance.{lang}.yaml").read_text(encoding="utf-8")
    content = (template.replace("__REPOSITORY__", repo)
                       .replace("__STAGE__", stage)
                       .replace("__PLANNER__", planner))
    gov_path.write_text(content, encoding="utf-8", newline="\n")
    console.print(f"[bold green]Created {GOVERNANCE_FILE}[/bold green] (repo: {repo or '-'}, stage: {stage}, planner: {planner})")


def _setup_agent_guards(target_dir, agents):
    for agent in [a.strip() for a in agents.split(",") if a.strip()]:
        installer = AGENT_INSTALLERS.get(agent)
        if installer is None:
            console.print(f"[yellow]Unknown agent '{agent}'. Supported: {', '.join(AGENT_INSTALLERS)}[/yellow]")
            continue
        try:
            path = installer(target_dir)
        except ConfigError as exc:
            console.print(f"[red]{exc}[/red]")
            continue
        console.print(f"[bold green]Installed {agent} guard hook:[/bold green] {path.relative_to(target_dir)}")
    if shutil.which("harness") is None:
        console.print("[bold yellow]Warning:[/bold yellow] 'harness' is not on PATH, so agent guard hooks will block every action. "
                      "Install it globally: uv tool install git+https://github.com/mporrasor/MPHarness")


def _install_pre_commit_hook(target_dir):
    # .git is a directory in normal clones but a file in worktrees and submodules.
    if not (target_dir / ".git").exists():
        return

    custom_hooks_path = _git_output(["config", "--get", "core.hooksPath"], target_dir)
    if custom_hooks_path:
        console.print(f"[yellow]core.hooksPath is set to '{custom_hooks_path}' (husky, lefthook, etc.). "
                      "Skipping MPHarness hook install to avoid clobbering it; add Gitleaks to that hook manager instead.[/yellow]")
        return

    hooks_rel = _git_output(["rev-parse", "--git-path", "hooks"], target_dir)
    if hooks_rel is None:
        console.print("[yellow]Could not resolve the git hooks directory (is git installed?). Pre-commit hook not installed.[/yellow]")
        return
    hooks_dir = Path(hooks_rel)
    if not hooks_dir.is_absolute():
        hooks_dir = target_dir / hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_path = hooks_dir / "pre-commit"
    chained_path = hooks_dir / "pre-commit.local"
    if pre_commit_path.exists() and HOOK_MARKER not in pre_commit_path.read_text(encoding="utf-8", errors="ignore"):
        if chained_path.exists():
            console.print(f"[red]Existing pre-commit hook found and {chained_path.name} already exists. "
                          "Pre-commit hook not installed; merge them manually.[/red]")
            return
        pre_commit_path.rename(chained_path)
        console.print(f"[yellow]Existing pre-commit hook preserved as {chained_path.name}; MPHarness will run it after its own checks.[/yellow]")

    hook_script = "#!/bin/sh\n" + HOOK_MARKER + "\n" + """
# 1. Block direct commits to main/master
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  echo "🚫 [MPHarness] Direct commits to the '$branch' branch are STRICTLY FORBIDDEN."
  echo "👉 Please create a semantic branch (e.g., 'feat/...', 'bugfix/...') and commit there."
  exit 1
fi

# 2. Secret Leak Prevention (Gitleaks + Fallback)
echo "🔒 [MPHarness] Inspecting staged changes for leaked secrets..."

GITLEAKS_CMD=""
if command -v gitleaks >/dev/null 2>&1; then
  GITLEAKS_CMD="gitleaks"
elif [ -n "$LOCALAPPDATA" ] && [ -f "$LOCALAPPDATA/Microsoft/WinGet/Packages/Gitleaks.Gitleaks_Microsoft.Winget.Source_8wekyb3d8bbwe/gitleaks.exe" ]; then
  GITLEAKS_CMD="$LOCALAPPDATA/Microsoft/WinGet/Packages/Gitleaks.Gitleaks_Microsoft.Winget.Source_8wekyb3d8bbwe/gitleaks.exe"
elif [ -n "$LOCALAPPDATA" ] && [ -f "$LOCALAPPDATA/Microsoft/WinGet/Links/gitleaks.exe" ]; then
  GITLEAKS_CMD="$LOCALAPPDATA/Microsoft/WinGet/Links/gitleaks.exe"
fi

if [ -n "$GITLEAKS_CMD" ]; then
  if ! "$GITLEAKS_CMD" protect --staged --verbose --redact; then
    echo ""
    echo "🚨 [MPHarness] COMMIT BLOCKED: Gitleaks detected one or more secrets in your staged changes!"
    echo "👉 Remove the secret(s), unstage the file with 'git restore --staged <file>', or configure .gitleaks.toml."
    exit 1
  fi
else
  STAGED_DIFF="$(git diff --cached -U0 --diff-filter=ACMR 2>/dev/null)"
  if echo "$STAGED_DIFF" | grep -Ei -q '(\bBEGIN [A-Z]+ PRIVATE KEY\b|sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z\\-_]{35}|xox[baprs]-[0-9a-zA-Z]{10,})'; then
    echo ""
    echo "🚨 [MPHarness] COMMIT BLOCKED: High-risk secret or private key pattern detected in staged changes!"
    echo "👉 Please remove the secret before committing."
    exit 1
  fi
  echo "⚠️ [MPHarness] Gitleaks not found in PATH. Run 'winget install Gitleaks.Gitleaks' or 'brew install gitleaks' for full 160+ detector coverage."
fi

echo "✅ [MPHarness] Pre-commit security verification passed."

# 3. Run the project's previous pre-commit hook, preserved by 'harness init'
LOCAL_HOOK="$(dirname "$0")/pre-commit.local"
if [ -f "$LOCAL_HOOK" ]; then
  "$LOCAL_HOOK" "$@" || exit $?
fi
exit 0
"""
    with open(pre_commit_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(hook_script)

    if os.name == 'posix':
        os.chmod(pre_commit_path, 0o755)

    console.print("[bold green]Installed mechanical git hook (pre-commit) with Gitleaks secret protection & branch shielding.[/bold green]")

@main.command()
@click.option('--dir', default='.', help='Directory to check.')
def check(dir):
    """Check if the project adheres to the harness structure."""
    target_dir = Path(dir).resolve()
    required_files = [
        "CONSTITUTION.md",
        "SPECIFICATION.md",
        "ARCHITECTURE.md",
        "TASKS.md",
        "AGENTS.md",
        "MANUAL.md",
        "TRACKING.md"
    ]
    
    missing = []
    for file in required_files:
        if not (target_dir / file).exists():
            missing.append(file)
            
    if missing:
        console.print("[bold red]Harness check failed![/bold red]")
        console.print(f"Missing required specification files: {', '.join(missing)}")
        console.print("Run 'harness init' to generate them.")
        sys.exit(1)
    else:
        console.print("[bold green]All harness specification files are present.[/bold green]")

@main.command()
@click.option('--dir', default='.', help='Directory to update.')
@click.option('--auto', is_flag=True, help='Run non-interactively, bypassing prompts and defaulting to Keep.')
@click.option('--ref', default=None,
              help='Git tag or commit SHA of MPHarness to fetch templates from. Defaults to the tag of the installed version (e.g. v0.1.0). Mutable branches like "main" are rejected unless --allow-branch is set.')
@click.option('--allow-branch', is_flag=True, help='Allow fetching templates from a mutable branch ref such as "main".')
def update(dir, auto, ref, allow_branch):
    """Update harness templates without overwriting custom project rules."""
    import tempfile
    import urllib.request

    target_dir = Path(dir).resolve()

    if not (target_dir / ".harness").exists():
        console.print("[yellow]Warning: No .harness directory found. Are you sure this project is initialized?[/yellow]")
        console.print("Run 'harness init' instead if this is a new project.")

    ref = ref or _default_template_ref()
    if ref in ("main", "master", "HEAD") and not allow_branch:
        console.print(f"[red]Refusing to fetch templates from mutable branch '{ref}'. Pin a tag or commit SHA, or pass --allow-branch.[/red]")
        sys.exit(1)

    updates_dir = target_dir / ".harness" / "updates"
    updates_found = False
    base_url = f"{GITHUB_RAW_BASE}/{ref}/{TEMPLATE_REPO_PATH}"
    template_files = [f.name for f in TEMPLATE_DIR.iterdir() if f.is_file()]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        use_remote = True

        console.print(f"[cyan]Checking for template updates from GitHub (ref: {ref})...[/cyan]")

        try:
            if template_files:
                urllib.request.urlopen(base_url + template_files[0], timeout=5)
        except Exception:
            use_remote = False
            console.print(f"[yellow]Could not fetch templates for ref '{ref}' (offline, or the tag does not exist). Falling back to the templates bundled with this CLI.[/yellow]")

        for filename in template_files:
            source_file = TEMPLATE_DIR / filename
            if use_remote:
                temp_file_path = temp_dir_path / filename
                try:
                    urllib.request.urlretrieve(base_url + filename, temp_file_path)
                    source_file = temp_file_path
                except Exception:
                    console.print(f"[yellow]Warning: Failed to download {filename} from GitHub. Using local version.[/yellow]")

            # IDE rule aliases are copies of .cursorrules and must stay in sync with it.
            dest_names = [filename] + (RULE_ALIASES if filename == ".cursorrules" else [])
            for dest_name in dest_names:
                if _apply_template_update(source_file, target_dir / dest_name, updates_dir, auto):
                    updates_found = True

    if updates_found:
        console.print("\n[bold yellow]Updates downloaded successfully![/bold yellow]")
        console.print("The updated templates have been safely stored in [bold].harness/updates/[/bold].")
        console.print("Your AI Agent is instructed to automatically detect these files, merge the new directives while respecting your custom rules, and clean up the folder the next time it reads the project. No manual prompting required.")
    else:
        console.print("\n[bold green]Your harness templates are up to date.[/bold green]")


def _apply_template_update(source_file, dest, updates_dir, auto):
    """Copy a template into the project, or stage it for merge if the local copy differs. Returns True if staged."""
    if not dest.exists():
        shutil.copy(source_file, dest)
        console.print(f"[green]Added missing template:[/green] {dest.name}")
        return False
    if filecmp.cmp(source_file, dest, shallow=False):
        return False

    if auto:
        choice = 'K'
    else:
        console.print(f"\n[bold yellow]Attention:[/bold yellow] A new version of [bold]{dest.name}[/bold] is available, but your local file may have custom changes.")
        choice = click.prompt("Do you want to (O)verwrite your local file or (K)eep it and prepare a merge?", type=click.Choice(['O', 'K'], case_sensitive=False), default='K')

    if choice.upper() == 'O':
        shutil.copy(source_file, dest)
        console.print(f"[red]Overwrote local file:[/red] {dest.name}")
        return False

    updates_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_file, updates_dir / dest.name)
    console.print(f"[blue]Update saved for manual/AI merge:[/blue] .harness/updates/{dest.name}")
    return True

@main.command()
@click.option('--dir', default='.', help='Directory to inspect.')
def tools(dir):
    """Inspect and report active tools and routing assignments (SpecKit, OpenSpec, Gitleaks, MPHarness)."""
    target_dir = Path(dir).resolve()
    
    console.print("\n[bold cyan]=== MPHarness Ecosystem & Action Dispatcher ===[/bold cyan]\n")
    
    # 1. MPHarness Core
    console.print("[bold green][+] MPHarness (Supreme Governance):[/bold green] [bold]ACTIVE[/bold]")
    console.print("  * Scope: OWASP Security, Gitleaks Pre-commit Hook, Branch Shielding, Context Drift Protection")
    
    # 2. Gitleaks
    gitleaks_found = shutil.which("gitleaks") is not None
    if not gitleaks_found:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            winget_dir = Path(local_app) / "Microsoft" / "WinGet"
            gitleaks_found = any(p.exists() for p in [
                winget_dir / "Packages" / "Gitleaks.Gitleaks_Microsoft.Winget.Source_8wekyb3d8bbwe" / "gitleaks.exe",
                winget_dir / "Links" / "gitleaks.exe",
            ])

    if gitleaks_found:
        console.print("[bold green][+] Gitleaks:[/bold green] [green]INSTALLED & INTEGRATED[/green]")
        console.print("  * Scope: Mechanical secret leak blocking in pre-commit hook")
    else:
        console.print("[bold yellow][!] Gitleaks:[/bold yellow] [yellow]NOT FOUND[/yellow] (Fallback regex scanning active)")
        console.print("  * Install via: winget install Gitleaks.Gitleaks")

    # 3. Spec Kit
    speckit_found = shutil.which("specify") is not None or (target_dir / ".speckit").exists() or (target_dir / ".specify").exists()
    if speckit_found:
        console.print("[bold green][+] GitHub Spec Kit (specify-cli):[/bold green] [green]DETECTED[/green]")
        console.print("  * Assigned For: [cyan]New Features & Greenfield Domains[/cyan] (/speckit.specify -> /speckit.plan -> /speckit.tasks)")
        console.print("  * Storage: Isolated in .speckit/ (Macro milestones synced to root TASKS.md)")
    else:
        console.print("[bold white][-] GitHub Spec Kit (specify-cli):[/bold white] [dim]Not detected in project[/dim]")
        console.print("  * Assigned For: New Features (Install via: uv tool install specify-cli)")

    # 4. OpenSpec
    openspec_found = shutil.which("openspec") is not None or (target_dir / ".openspec").exists()
    if openspec_found:
        console.print("[bold green][+] OpenSpec (@fission-ai/openspec):[/bold green] [green]DETECTED[/green]")
        console.print("  * Assigned For: [cyan]Incremental Modifications & Refactors[/cyan] (openspec propose -> apply -> archive)")
        console.print("  * Storage: Quarantined in .openspec/proposals/ until accepted")
    else:
        console.print("[bold white][-] OpenSpec (@fission-ai/openspec):[/bold white] [dim]Not detected in project[/dim]")
        console.print("  * Assigned For: Incremental Spec Changes (Install via: npm i -g @fission-ai/openspec)")

    console.print("\n[bold blue]Dispatch Rule:[/bold blue] AI automatically routes New Features -> SpecKit, Modifications -> OpenSpec. Zero file collisions or duplicated checklists.\n")

@main.command()
@click.option('--dir', default='.', help='Directory to audit.')
def audit(dir):
    """Audit project dependencies for vulnerabilities and outdated versions (NuGet, npm, pip/uv)."""
    target_dir = Path(dir).resolve()
    console.print("\n[bold cyan]=== MPHarness Dependency & Vulnerability Audit ===[/bold cyan]\n")

    found_stack = False

    # 1. .NET / NuGet Check
    dotnet_files = list(target_dir.glob("*.sln")) + list(target_dir.glob("*.csproj"))
    if dotnet_files:
        found_stack = True
        console.print("[bold green][+] .NET / NuGet Project Detected[/bold green]")
        if shutil.which("dotnet"):
            console.print("  * Checking for vulnerable packages (dotnet list package --vulnerable)...")
            try:
                res_v = _run_tool(["dotnet", "list", "package", "--vulnerable"], target_dir)
                out_v = res_v.stdout.strip()
                if out_v:
                    console.print(f"    {out_v}")
                else:
                    console.print("    [green]No known vulnerabilities reported by NuGet.[/green]")
            except Exception as e:
                console.print(f"    [red]Error running dotnet list --vulnerable: {e}[/red]")
                
            console.print("\n  * Checking for outdated packages (dotnet list package --outdated)...")
            try:
                res_o = _run_tool(["dotnet", "list", "package", "--outdated"], target_dir)
                out_o = res_o.stdout.strip()
                if out_o:
                    console.print(f"    {out_o}")
                else:
                    console.print("    [green]All NuGet packages are up to date.[/green]")
            except Exception as e:
                console.print(f"    [red]Error running dotnet list --outdated: {e}[/red]")
        else:
            console.print("  [yellow]dotnet CLI not found on PATH.[/yellow]")

    # 2. Node.js / npm / pnpm / yarn Check
    package_json = target_dir / "package.json"
    if package_json.exists():
        found_stack = True
        console.print("\n[bold green][+] Node.js Project Detected (package.json)[/bold green]")
        pm = "pnpm" if (target_dir / "pnpm-lock.yaml").exists() else ("yarn" if (target_dir / "yarn.lock").exists() else "npm")
        if shutil.which(pm):
            console.print(f"  * Checking for security vulnerabilities ({pm} audit)...")
            try:
                res_a = _run_tool([pm, "audit"], target_dir)
                out_a = res_a.stdout.strip() or res_a.stderr.strip()
                if out_a:
                    console.print(f"    {out_a[:2000]}")
                else:
                    console.print("    [green]No known vulnerabilities found.[/green]")
            except Exception as e:
                console.print(f"    [red]Error running {pm} audit: {e}[/red]")
                
            console.print(f"\n  * Checking for outdated dependencies ({pm} outdated)...")
            try:
                res_o = _run_tool([pm, "outdated"], target_dir)
                out_o = res_o.stdout.strip()
                if out_o:
                    console.print(f"    {out_o}")
                else:
                    console.print(f"    [green]All packages are up to date according to {pm}.[/green]")
            except Exception as e:
                console.print(f"    [red]Error running {pm} outdated: {e}[/red]")
        else:
            console.print(f"  [yellow]{pm} CLI not found on PATH.[/yellow]")

    # 3. Python Check
    pyproject = target_dir / "pyproject.toml"
    requirements = target_dir / "requirements.txt"
    if pyproject.exists() or requirements.exists():
        found_stack = True
        console.print("\n[bold green][+] Python Project Detected[/bold green]")
        if shutil.which("pip-audit"):
            # Audit the target project's declared dependencies, not the environment running this CLI.
            if requirements.exists():
                pip_audit_args = ["pip-audit", "-r", str(requirements)]
            else:
                pip_audit_args = ["pip-audit", str(target_dir)]
            console.print(f"  * Running {' '.join(pip_audit_args[:2])} for CVE vulnerabilities...")
            try:
                res_p = _run_tool(pip_audit_args, target_dir)
                console.print(f"    {res_p.stdout.strip() or res_p.stderr.strip() or 'No known vulnerabilities found.'}")
            except Exception as e:
                console.print(f"    [red]Error: {e}[/red]")
        elif shutil.which("uv"):
            console.print("  * Checking outdated packages with uv pip list --outdated...")
            try:
                res_u = _run_tool(["uv", "pip", "list", "--outdated"], target_dir)
                console.print(f"    {res_u.stdout.strip() or 'All packages up to date.'}")
            except Exception as e:
                console.print(f"    [red]Error: {e}[/red]")
        else:
            console.print("  [yellow]Install 'pip-audit' (uv tool install pip-audit) for CVE scanning.[/yellow]")

    if not found_stack:
        console.print("[yellow]No supported package manifests found in directory.[/yellow]")

    console.print("\n[bold blue]MPHarness Pre-Upgrade Protocol:[/bold blue]")
    console.print("  1. AI MUST present an Upgrade Proposal Report (Package, Current, Target, Reason, Affected Files).")
    console.print("  2. User can approve or reject specific packages (pinning).")
    console.print("  3. AI updates ONLY approved packages and MUST run tests on affected modules before committing.\n")

@main.command()
@click.option('--agent', type=click.Choice(list(ADAPTERS)), required=True, help='Which AI agent is sending the hook payload.')
def guard(agent):
    """Agent hook entry point: reads a PreToolUse payload on stdin and answers allow / ask / deny.

    Installed automatically by 'harness init'. Not meant to be run by hand.
    """
    to_actions, project_dir, render = ADAPTERS[agent]
    language = "es"
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(raw or "{}")
        policy = load_policy(project_dir(payload))
        language = policy.language
        decision = Decision()
        for action in to_actions(payload):
            result = evaluate(action, policy)
            for reason in result.reasons:
                decision.add(result.verdict, reason)
    except Exception as exc:  # Fail closed: a guard that crashes must never let the action through.
        decision = Decision()
        decision.add(DENY, msg("guard_error", language, detail=type(exc).__name__))

    out, code = render(decision)
    if out:
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.flush()
    sys.exit(code)


@main.command()
@click.option('--dir', default='.', help='Project directory.')
@click.option('--revoke', is_flag=True, help='Remove the current approval.')
def approve(dir, revoke):
    """Approve the current plan so the AI may edit code (only when require_plan_approval is on).

    The approval is tied to the current git branch and stays on this machine.
    """
    policy = load_policy(Path(dir).resolve())
    path = policy.root / APPROVAL_FILE
    es = policy.language == "es"
    if revoke:
        path.unlink(missing_ok=True)
        console.print("[yellow]Aprobación retirada.[/yellow]" if es else "[yellow]Approval revoked.[/yellow]")
        return
    if not policy.rule("require_plan_approval"):
        console.print("[yellow]require_plan_approval está desactivado en governance.yaml; la aprobación no es necesaria.[/yellow]" if es
                      else "[yellow]require_plan_approval is off in governance.yaml; approval is not required.[/yellow]")
    branch = current_branch(policy.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"branch": branch, "approved_at": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    console.print((f"[bold green]Plan aprobado para la rama '{branch}'.[/bold green] La IA ya puede editar código.") if es
                  else (f"[bold green]Plan approved for branch '{branch}'.[/bold green] The AI may now edit code."))


if __name__ == "__main__":
    main()
