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

if __name__ == "__main__":
    main()
