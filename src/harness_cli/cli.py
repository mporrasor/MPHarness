import click
import os
import shutil
from pathlib import Path
from rich.console import Console

console = Console()

TEMPLATE_DIR = Path(__file__).parent / "templates" / "spec-driven-project"

@click.group()
def main():
    """Universal Spec-Driven Project Harness for AI Agents."""
    pass

@main.command()
@click.option('--dir', default='.', help='Directory to initialize the harness.')
def init(dir):
    """Initialize a new spec-driven project."""
    target_dir = Path(dir).resolve()
    
    if not target_dir.exists():
        target_dir.mkdir(parents=True)
    
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
    git_dir = target_dir / ".git"
    if git_dir.exists():
        hooks_dir = git_dir / "hooks"
        if not hooks_dir.exists():
            hooks_dir.mkdir(parents=True)
        
        pre_commit_path = hooks_dir / "pre-commit"
        hook_script = """#!/bin/sh
# MPHarness Mechanical Pre-Commit Hook

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
exit 0
"""
        with open(pre_commit_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(hook_script)
        
        # Ensure it's executable on unix
        if os.name == 'posix':
            os.chmod(pre_commit_path, 0o755)
            
        console.print("[bold green]Installed mechanical git hook (pre-commit) with Gitleaks secret protection & branch shielding.[/bold green]")
    
    console.print("\n[bold green]Harness initialized successfully![/bold green]")
    console.print("[bold yellow]IMPORTANT:[/bold yellow] Place any initial requirements, analysis files, or UI prototypes inside the [bold]/docs[/bold] folder.")
    console.print("You can now start editing SPECIFICATION.md, or invite your AI to begin.")

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
        exit(1)
    else:
        console.print("[bold green]All harness specification files are present.[/bold green]")

@main.command()
@click.option('--dir', default='.', help='Directory to update.')
@click.option('--auto', is_flag=True, help='Run non-interactively, bypassing prompts and defaulting to Keep.')
def update(dir, auto):
    """Update harness templates without overwriting custom project rules."""
    target_dir = Path(dir).resolve()
    
    if not (target_dir / ".harness").exists():
        console.print("[yellow]Warning: No .harness directory found. Are you sure this project is initialized?[/yellow]")
        console.print("Run 'harness init' instead if this is a new project.")
    
    updates_dir = target_dir / ".harness" / "updates"
    updates_found = False
    
    import filecmp
    import urllib.request
    import tempfile
    
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/mporrasor/MPHarness/main/src/harness_cli/templates/spec-driven-project/"
    template_files = [f.name for f in TEMPLATE_DIR.iterdir() if f.is_file()]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        use_remote = True
        
        console.print("[cyan]Checking for updates from GitHub...[/cyan]")
        
        try:
            if template_files:
                urllib.request.urlopen(GITHUB_RAW_URL + template_files[0], timeout=5)
        except Exception as e:
            use_remote = False
            console.print(f"[yellow]Could not reach GitHub. Falling back to local templates.[/yellow]")
            
        for filename in template_files:
            local_template_path = TEMPLATE_DIR / filename
            
            if use_remote:
                remote_url = GITHUB_RAW_URL + filename
                temp_file_path = temp_dir_path / filename
                try:
                    urllib.request.urlretrieve(remote_url, temp_file_path)
                    source_file = temp_file_path
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to download {filename} from GitHub. Using local version.[/yellow]")
                    source_file = local_template_path
            else:
                source_file = local_template_path

            dest = target_dir / filename
            if not dest.exists():
                shutil.copy(source_file, dest)
                console.print(f"[green]Added missing template:[/green] {filename}")
            else:
                if not filecmp.cmp(source_file, dest, shallow=False):
                    if auto:
                        choice = 'K'
                    else:
                        console.print(f"\n[bold yellow]Attention:[/bold yellow] A new version of [bold]{filename}[/bold] is available, but your local file may have custom changes.")
                        choice = click.prompt("Do you want to (O)verwrite your local file or (K)eep it and prepare a merge?", type=click.Choice(['O', 'K'], case_sensitive=False), default='K')
                    
                    if choice.upper() == 'O':
                        shutil.copy(source_file, dest)
                        console.print(f"[red]Overwrote local file:[/red] {filename}")
                    else:
                        if not updates_dir.exists():
                            updates_dir.mkdir(parents=True)
                        
                        update_dest = updates_dir / filename
                        shutil.copy(source_file, update_dest)
                        updates_found = True
                        console.print(f"[blue]Update saved for manual/AI merge:[/blue] .harness/updates/{filename}")
                
    if updates_found:
        console.print("\n[bold yellow]Updates downloaded successfully![/bold yellow]")
        console.print("The updated templates have been safely stored in [bold].harness/updates/[/bold].")
        console.print("Your AI Agent is instructed to automatically detect these files, merge the new directives while respecting your custom rules, and clean up the folder the next time it reads the project. No manual prompting required.")
    else:
        console.print("\n[bold green]Your harness templates are up to date.[/bold green]")

@main.command()
@click.option('--dir', default='.', help='Directory to inspect.')
def tools(dir):
    """Inspect and report active tools and routing assignments (SpecKit, OpenSpec, Gitleaks, MPHarness)."""
    target_dir = Path(dir).resolve()
    
    console.print("\n[bold cyan]=== MPHarness Ecosystem & Action Dispatcher ===[/bold cyan]\n")
    
    # 1. MPHarness Core
    console.print("[bold green]✓ MPHarness (Supreme Governance):[/bold green] [bold]ACTIVE[/bold]")
    console.print("  • Scope: OWASP Security, Gitleaks Pre-commit Hook, Branch Shielding, Context Drift Protection")
    
    # 2. Gitleaks
    import shutil
    gitleaks_found = shutil.which("gitleaks") is not None
    if not gitleaks_found:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            winget_path = Path(local_app) / "Microsoft" / "WinGet" / "Packages" / "Gitleaks.Gitleaks_Microsoft.Winget.Source_8wekyb3d8bbwe" / "gitleaks.exe"
            gitleaks_found = winget_path.exists()
            
    if gitleaks_found:
        console.print("[bold green]✓ Gitleaks:[/bold green] [green]INSTALLED & INTEGRATED[/green]")
        console.print("  • Scope: Mechanical secret leak blocking in pre-commit hook")
    else:
        console.print("[bold yellow]! Gitleaks:[/bold yellow] [yellow]NOT FOUND[/yellow] (Fallback regex scanning active)")
        console.print("  • Install via: winget install Gitleaks.Gitleaks")

    # 3. Spec Kit
    speckit_found = shutil.which("specify") is not None or (target_dir / ".speckit").exists() or (target_dir / ".specify").exists()
    if speckit_found:
        console.print("[bold green]✓ GitHub Spec Kit (specify-cli):[/bold green] [green]DETECTED[/green]")
        console.print("  • Assigned For: [cyan]New Features & Greenfield Domains[/cyan] (/speckit.specify -> /speckit.plan -> /speckit.tasks)")
        console.print("  • Storage: Isolated in .speckit/ (Macro milestones synced to root TASKS.md)")
    else:
        console.print("[bold white]○ GitHub Spec Kit (specify-cli):[/bold white] [dim]Not detected in project[/dim]")
        console.print("  • Assigned For: New Features (Install via: uv tool install specify-cli)")

    # 4. OpenSpec
    openspec_found = shutil.which("openspec") is not None or (target_dir / ".openspec").exists()
    if openspec_found:
        console.print("[bold green]✓ OpenSpec (@fission-ai/openspec):[/bold green] [green]DETECTED[/green]")
        console.print("  • Assigned For: [cyan]Incremental Modifications & Refactors[/cyan] (openspec propose -> apply -> archive)")
        console.print("  • Storage: Quarantined in .openspec/proposals/ until accepted")
    else:
        console.print("[bold white]○ OpenSpec (@fission-ai/openspec):[/bold white] [dim]Not detected in project[/dim]")
        console.print("  • Assigned For: Incremental Spec Changes (Install via: npm i -g @fission-ai/openspec)")

    console.print("\n[bold blue]Dispatch Rule:[/bold blue] AI automatically routes New Features -> SpecKit, Modifications -> OpenSpec. Zero file collisions or duplicated checklists.\n")

if __name__ == "__main__":
    main()
