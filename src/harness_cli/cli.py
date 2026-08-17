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
    
    # Check templates
    for file in TEMPLATE_DIR.iterdir():
        if file.is_file():
            dest = target_dir / file.name
            if not dest.exists():
                # If it doesn't exist at all, just copy it directly
                shutil.copy(file, dest)
                console.print(f"[green]Added missing template:[/green] {dest.name}")
            else:
                # Compare to see if there is an actual update
                if not filecmp.cmp(file, dest, shallow=False):
                    if auto:
                        choice = 'K'
                    else:
                        console.print(f"\n[bold yellow]Attention:[/bold yellow] A new version of [bold]{dest.name}[/bold] is available, but your local file may have custom changes.")
                        choice = click.prompt("Do you want to (O)verwrite your local file or (K)eep it and prepare a merge?", type=click.Choice(['O', 'K'], case_sensitive=False), default='K')
                    
                    if choice.upper() == 'O':
                        shutil.copy(file, dest)
                        console.print(f"[red]Overwrote local file:[/red] {dest.name}")
                    else:
                        if not updates_dir.exists():
                            updates_dir.mkdir(parents=True)
                        
                        update_dest = updates_dir / file.name
                        shutil.copy(file, update_dest)
                        updates_found = True
                        console.print(f"[blue]Update saved for manual/AI merge:[/blue] .harness/updates/{file.name}")
                
    if updates_found:
        console.print("\n[bold yellow]Updates downloaded successfully![/bold yellow]")
        console.print("The updated templates have been safely stored in [bold].harness/updates/[/bold].")
        console.print("Your AI Agent is instructed to automatically detect these files, merge the new directives while respecting your custom rules, and clean up the folder the next time it reads the project. No manual prompting required.")
    else:
        console.print("\n[bold green]Your harness templates are up to date.[/bold green]")

if __name__ == "__main__":
    main()
