"""`harness audit`: run each ecosystem's own vulnerability and outdated-package checks on the project."""
import shutil
from pathlib import Path

from .util import console, run_tool


def _report(title, args, root, empty_message, limit=4000):
    console.print(f"  * {title}...")
    try:
        res = run_tool(args, root)
    except (OSError, FileNotFoundError) as exc:
        console.print(f"    [red]Could not run {args[0]}: {exc}[/red]")
        return
    output = (res.stdout.strip() or res.stderr.strip())[:limit]
    console.print(f"    {output}" if output else f"    [green]{empty_message}[/green]", markup=not output, highlight=False)


def run(root):
    root = Path(root)
    found = False

    if list(root.glob("*.sln")) + list(root.glob("*.csproj")):
        found = True
        console.print("[bold green][+] .NET / NuGet project[/bold green]")
        if shutil.which("dotnet"):
            _report("Known vulnerabilities (dotnet list package --vulnerable)",
                    ["dotnet", "list", "package", "--vulnerable"], root, "No known vulnerabilities reported by NuGet.")
            _report("Outdated packages (dotnet list package --outdated)",
                    ["dotnet", "list", "package", "--outdated"], root, "All NuGet packages are up to date.")
        else:
            console.print("  [yellow]The dotnet CLI is not installed.[/yellow]")

    if (root / "package.json").exists():
        found = True
        console.print("\n[bold green][+] Node.js project[/bold green]")
        pm = "pnpm" if (root / "pnpm-lock.yaml").exists() else ("yarn" if (root / "yarn.lock").exists() else "npm")
        if shutil.which(pm):
            _report(f"Known vulnerabilities ({pm} audit)", [pm, "audit"], root, "No known vulnerabilities found.")
            _report(f"Outdated packages ({pm} outdated)", [pm, "outdated"], root, "All packages are up to date.")
        else:
            console.print(f"  [yellow]{pm} is not installed.[/yellow]")

    requirements = root / "requirements.txt"
    if (root / "pyproject.toml").exists() or requirements.exists():
        found = True
        console.print("\n[bold green][+] Python project[/bold green]")
        if shutil.which("pip-audit"):
            # Audit the project's declared dependencies, not the environment running MPHarness.
            args = ["pip-audit", "-r", str(requirements)] if requirements.exists() else ["pip-audit", str(root)]
            _report("Known vulnerabilities (pip-audit)", args, root, "No known vulnerabilities found.")
        else:
            console.print("  [yellow]Install pip-audit for vulnerability checks: uv tool install pip-audit[/yellow]")
        if shutil.which("uv"):
            _report("Outdated packages (uv pip list --outdated)", ["uv", "pip", "list", "--outdated"], root,
                    "All packages are up to date.")

    if not found:
        console.print("[yellow]No supported dependency files found (package.json, pyproject.toml, requirements.txt, *.csproj).[/yellow]")

    console.print("\n[bold]Before upgrading:[/bold] the AI must show you a table (package, current -> target, reason, risk),")
    console.print("update only what you approve, and run the tests afterwards. Dependabot also opens upgrade PRs on GitHub.")
